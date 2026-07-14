"""Form 8962 — Premium Tax Credit (PTC), monthly reconciliation.

Pure compute over a ``Form1095A`` block, a MAGI figure, the tax year, and
that year's ``F8962Params`` — no spine/orchestrator wiring here (that is
a separate seam). Callers use only ``f8962_line_26_net_ptc``,
``f8962_line_29_repayment``, and ``f8962_ui_box_checked``; every other
key exists for the mapping/oracle layer.

Line disposition (per the printed form; the oracle battery is the
authority if instructions ever disagree with this module):

    line 1      household size — fixed at 1 (v1 scope: single filer only)
    line 2a     MAGI (see MAGI seam note below); line 2b out of scope
    line 3      = line 2a (household income, since line 2b is out of
                scope)
    line 4      FPL for household size 1, 48 contiguous states + DC
                (``params.fpl_single_48``)
    line 5      household income as a percentage of the FPL:
                floor(line3 / line4 * 100), clamped to
                [applicable_figure_floor_pct, applicable_figure_ceiling_pct].
                When ``block.received_unemployment_2021`` and
                ``params.unemployment_rule`` (the ARPA 2021 rule), line 5
                is further replaced with min(line5, 133).
    line 7      applicable figure — a floor-key step lookup into
                ``params.applicable_figures`` at line 5 (NOT a bare dict
                lookup: the published table is only defined at discrete
                percentage points, and household income between points
                uses the next-lower table entry).
    line 8a     irs_round(line3 * line7) — annual contribution amount
    line 8b     irs_round(line8a / 12) — monthly contribution amount
    monthly     for each of the 12 months (only months with any nonzero
    (a-f)       premium/slcsp/aptc emit a row):
                  (c) = line 8b
                  (d) = max(0, slcsp - (c))
                  (e) = min(premium, (d))
                  (f) = aptc
                each cell irs_round'd individually.
    line 24     sum of monthly (e) — total premium tax credit
    line 25     sum of monthly (f) — total APTC
    line 26     net PTC = max(0, line24 - line25)
    line 27     excess APTC repayment (pre-cap) = max(0, line25 - line24)
    line 28     repayment limitation: the cap dollars for line 5's FPL
                band, from ``params.repayment_caps_single`` (ascending
                ``(exclusive_upper_bound_pct, cap)`` pairs — the first
                entry whose bound exceeds line 5). Uncapped (None) when
                no band's bound exceeds line 5 (this naturally covers
                line 5 >= 400% for the standard table without hardcoding
                that threshold here).
    line 29     repayment = min(line27, line28) when capped, else line27.

MAGI seam: MAGI (line 2a) is computed by the CALLER as AGI + tax-exempt
interest (``block.tax_exempt_interest`` — carried on the block but not
yet folded in here; this module receives the final MAGI figure as an
argument). Other statutory MAGI additions (excluded foreign income,
non-taxable Social Security) are out of spine scope for v1 and are the
caller's responsibility to fold into the ``magi`` argument if ever
needed — this is the marked seam.
"""

import math
from dataclasses import astuple

from tenforty.models import Form1095A
from tenforty.params.f8962 import F8962Params
from tenforty.rounding import irs_round

_MONTH_CELLS = ("a", "b", "c", "d", "e", "f")


def compute(block: Form1095A, magi: float, year: int, params: F8962Params) -> dict:
    if block.received_unemployment_2021 and not params.unemployment_rule:
        raise ValueError(
            "Form1095A.received_unemployment_2021 is set but this year's "
            "F8962Params.unemployment_rule is False — statute/params "
            "mismatch (the 2021 ARPA unemployment rule only applies in "
            "tax year 2021)."
        )

    line_1 = 1
    line_2a = magi
    line_3 = line_2a
    line_4 = params.fpl_single_48

    line_5 = _clamp(
        _floor_pct(line_3, line_4),
        params.applicable_figure_floor_pct,
        params.applicable_figure_ceiling_pct,
    )
    if block.received_unemployment_2021 and params.unemployment_rule:
        line_5 = min(line_5, 133)

    line_7 = _applicable_figure(params.applicable_figures, line_5)

    line_8a = irs_round(line_3 * line_7)
    line_8b = irs_round(line_8a / 12)

    result: dict = {
        "f8962_line_1": line_1,
        "f8962_line_2a": irs_round(line_2a),
        "f8962_line_3": irs_round(line_3),
        "f8962_line_4": irs_round(line_4),
        "f8962_line_5": line_5,
        "f8962_line_7": line_7,
        "f8962_line_8a": line_8a,
        "f8962_line_8b": line_8b,
    }

    line_24 = 0
    line_25 = 0
    for n, month in enumerate(block.months, start=1):
        premium, slcsp, aptc = astuple(month)
        if premium == 0 and slcsp == 0 and aptc == 0:
            continue
        cell_a = irs_round(premium)
        cell_b = irs_round(slcsp)
        cell_c = irs_round(line_8b)
        cell_d = irs_round(max(0, slcsp - line_8b))
        cell_e = irs_round(min(premium, max(0, slcsp - line_8b)))
        cell_f = irs_round(aptc)
        for letter, value in zip(_MONTH_CELLS, (cell_a, cell_b, cell_c, cell_d, cell_e, cell_f)):
            result[f"f8962_month_{n}_{letter}"] = value
        line_24 += cell_e
        line_25 += cell_f

    result["f8962_line_24"] = line_24
    result["f8962_line_25"] = line_25

    line_26 = max(0, line_24 - line_25)
    line_27 = max(0, line_25 - line_24)
    line_28 = _repayment_cap(params.repayment_caps_single, line_5)
    line_29 = min(line_27, line_28) if line_28 is not None else line_27

    result["f8962_line_26_net_ptc"] = line_26
    result["f8962_line_27"] = line_27
    result["f8962_line_28"] = line_28
    result["f8962_line_29_repayment"] = line_29
    result["f8962_ui_box_checked"] = block.received_unemployment_2021

    return result


def _floor_pct(numerator: float, denominator: float) -> int:
    return math.floor(numerator / denominator * 100)


def _clamp(value: int, floor: int, ceiling: int) -> int:
    return max(floor, min(ceiling, value))


def _applicable_figure(table: dict[int, float], line_5: int) -> float:
    keys_at_or_below = [k for k in table if k <= line_5]
    if not keys_at_or_below:
        return table[min(table)]
    return table[max(keys_at_or_below)]


def _repayment_cap(caps: tuple[tuple[int, int], ...], line_5: int) -> int | None:
    for bound, cap in caps:
        if bound > line_5:
            return cap
    return None
