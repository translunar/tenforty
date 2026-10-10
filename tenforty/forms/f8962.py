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
    line 5      household income as a percentage of the FPL, per this
                exact four-part rule:
                  (1) if ``block.received_unemployment_2021`` and
                      ``params.unemployment_rule`` (the 2021 ARPA
                      unemployment rule): line 5 = 133 FLAT
                      (i8962--2021 line-5 instruction: a filer who
                      received/was-approved-for unemployment compensation
                      is told to "enter 133 on line 5" — UI filers skip
                      Worksheet 2's percentage computation entirely).
                      This bypasses (2) and (3) below completely.
                  (2) otherwise: line 5 = exact integer truncation
                      (irs_round(line3) * 100) // line4 (Worksheet 2:
                      "multiply by 100 and drop any decimals" — integer
                      arithmetic, never float; float division underflows
                      at exact-integer FPL percentages, e.g. 230%
                      dropping to 229).
                  (3) then the per-year 400%-FPL boundary is applied to
                      that result, replacing it with 401 when over:
                      2021 is INCLUSIVE (``line5_raw >= 400``;
                      i8962--2021: "Is the result 400 or more? ... Enter
                      401"); 2022-2025 is STRICT (``line3 > 4 * fpl``;
                      i8962--YYYY: "multiply line 2 by 4.0 ... more than
                      400% ... Enter 401"). Which comparison applies is
                      carried by ``params.line5_400_boundary_inclusive``.
                  (4) the reported line 5 is NOT clamped to
                      [applicable_figure_floor_pct,
                      applicable_figure_ceiling_pct] — those edges govern
                      ONLY the line-7 table lookup below (via
                      ``_applicable_figure``'s floor-keying), never the
                      reported line-5 value itself.
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
                (printed cell: blank when line25 > line24 -- see
                ``f8962_line_26_printed``)
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

from dataclasses import astuple

from tenforty.models import Form1095A
from tenforty.params.f8962 import F8962Params
from tenforty.rounding import irs_round

_MONTH_CELLS = ("a", "b", "c", "d", "e", "f")


def compute(block: Form1095A, magi: float, year: int, params: F8962Params) -> dict:
    assert params.year == year, f"params.year {params.year} != requested year {year}"
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

    if block.received_unemployment_2021 and params.unemployment_rule:
        # 2021 ARPA rule (i8962--2021 line-5 instruction): a filer who
        # received/was-approved-for unemployment compensation is told to
        # "enter 133 on line 5" — flat, full stop. Worksheet 2's
        # percentage computation (and the 400% boundary step within it)
        # is skipped entirely for these filers, not applied and then
        # clamped down to 133.
        line_5 = 133
    else:
        # Worksheet 2's line-5 400%-FPL-boundary step is NOT worded the
        # same every year (see F8962Params.line5_400_boundary_inclusive):
        #   2021: "Is the result 400 or more? Yes -> enter 401" (INCLUSIVE
        #     — the floored FPL% itself, not the raw magi, is compared to
        #     400).
        #   2022-2025: "...more than 400%... enter 401" (STRICT — a direct
        #     magi-vs-4x-fpl comparison; raw 400.x floors to 400 yet is
        #     still "more than 400%", so this must NOT be a check on the
        #     floored percentage).
        # Exact integer arithmetic for "divide, multiply by 100, drop the
        # decimal" — float division underflows at exact-integer FPL
        # percentages (e.g. 31257/13590*100 == 229.99999999999997, which
        # floors to 229 instead of the true 230). irs_round(line_3) matches
        # the whole-dollar line_3 already reported above.
        line5_raw = (irs_round(line_3) * 100) // params.fpl_single_48
        if params.line5_400_boundary_inclusive:
            over_400 = line5_raw >= 400
        else:
            over_400 = line_3 > 4 * params.fpl_single_48
        # Line 5 reports the TRUE household-income percentage — it is NOT
        # clamped to the applicable-figure table's domain edges (those
        # edges only govern the line-7 lookup below, via
        # _applicable_figure's floor-keying).
        line_5 = 401 if over_400 else line5_raw

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

    # Per-month cells (a)-(f), computed from each month's own 1095-A data —
    # never by dividing annual totals by 12. A month with no coverage (all
    # three figures zero) has no row: its cells stay BLANK, not 0.
    month_rows: dict[int, tuple[int, ...]] = {}
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
        month_rows[n] = (cell_a, cell_b, cell_c, cell_d, cell_e, cell_f)

    # Line 10 rule (i8962 (2024), Line 10 — imperative: "Check 'Yes' and
    # continue to line 11 if all of the following apply ... Otherwise, check
    # 'No' and continue to lines 12 through 23"), so the ANNUAL calculation is
    # MANDATORY when eligible. Eligibility, per the instructions' own heading
    # ("no changes on Form 1095-A, Part III, column A or B"):
    #   1. enrolled in the plan all 12 months — an ENROLLED month is one with
    #      an enrollment premium (column A) > 0;
    #   2. column A identical every month;
    #   3. column B (SLCSP) identical every month.
    # APTC (column C) sameness is deliberately NOT a condition.
    month_triples = [astuple(m) for m in block.months]
    annual_allowed = (
        len(month_triples) == 12
        and all(t[0] > 0 for t in month_triples)
        and len({t[0] for t in month_triples}) == 1
        and len({t[1] for t in month_triples}) == 1
    )

    # Line 9 ("allocating policy amounts with another taxpayer, or using the
    # alternative calculation for year of marriage?") is always "No": tenforty
    # has no input that could express either situation, so No is correct for
    # every scenario it can compute. (Yes would route to Part IV / Part V.)
    result["f8962_line_9_no"] = True

    if annual_allowed:
        # Line 11 (annual totals) from the annual sums; (c) is line 8a.
        # Sums of the whole-dollar-rounded 1095-A figures (the instructions
        # round each 1095-A amount before entering it).
        a_tot = sum(irs_round(t[0]) for t in month_triples)
        b_tot = sum(irs_round(t[1]) for t in month_triples)
        f_tot = sum(irs_round(t[2]) for t in month_triples)
        d_tot = irs_round(max(0, b_tot - line_8a))
        e_tot = irs_round(min(a_tot, d_tot))
        for letter, value in zip(
            _MONTH_CELLS, (a_tot, b_tot, line_8a, d_tot, e_tot, f_tot)
        ):
            result[f"f8962_line_11_{letter}"] = value
        result["f8962_line_10_yes"] = True
        line_24 = e_tot  # line 24 = 11(e)
        line_25 = f_tot  # line 25 = 11(f)
    else:
        result["f8962_line_10_no"] = True
        for n, cells in month_rows.items():
            for letter, value in zip(_MONTH_CELLS, cells):
                result[f"f8962_month_{n}_{letter}"] = value
        line_24 = sum(c[4] for c in month_rows.values())  # sum of 12(e)-23(e)
        line_25 = sum(c[5] for c in month_rows.values())  # sum of 12(f)-23(f)

    result["f8962_line_24"] = line_24
    result["f8962_line_25"] = line_25

    line_26 = max(0, line_24 - line_25)
    line_27 = max(0, line_25 - line_24)
    line_28 = _repayment_cap(params.repayment_caps_single, line_5)
    line_29 = min(line_27, line_28) if line_28 is not None else line_27

    result["f8962_line_26_net_ptc"] = line_26
    # Line 26 as PRINTED (i8962, lines 26 and 27): the difference when line 24
    # is greater; "enter -0-" when the two are equal; "leave line 26 blank"
    # when line 25 is greater. `f8962_line_26_net_ptc` above stays a number in
    # every case because the spine adds it into total payments.
    result["f8962_line_26_printed"] = None if line_25 > line_24 else line_26
    result["f8962_line_27"] = line_27
    result["f8962_line_28"] = line_28
    result["f8962_line_29_repayment"] = line_29
    result["f8962_ui_box_checked"] = block.received_unemployment_2021

    return result


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
