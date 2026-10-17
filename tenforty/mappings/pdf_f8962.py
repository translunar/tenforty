# tenforty/mappings/pdf_f8962.py
"""PDF field mapping for IRS Form 8962 (Premium Tax Credit).

Probe-certified, year-keyed (2021-2025). Every field path here is copied
from that year's blind marker-probe correspondence table
(docs/plans/f8962-probe-tables.md) — equivalently that year's own
``get_fields()`` — never inferred from a neighboring year. The
fields-on-template gate re-verifies every path against each year's blank
template on every run.

Shape mirrors ``pdf_8959.py``: ``_FIELDS = {"scalars": {...}, "repeaters":
{}}`` because ``forms.f8962.compute`` emits FIXED per-month scalar keys
(``f8962_month_<n>_{a..f}`` for n=1..12), not a variable-length list, so the
72 monthly-grid cells are flat scalars. Absent keys (a month with no
premium/slcsp/aptc, so no row emitted) leave those cells blank.

Two checkboxes are handled outside the scalar value pass:

- **UI box A — 2021 ONLY.** The ARPA-2021 form carries an unemployment-
  compensation Box A at ``c1_1[0]`` with ON-state ``/2`` (its own
  ``/_States_`` is ``['/2', '/Off']`` — NOT ``/1``). ``f8962_ui_box_checked``
  (a bool compute key) maps to that path in the 2021 scalars, and
  ``get_checkbox_states(2021)`` carries its ``/2`` on-token so the filler
  writes the XFA appearance state for True / ``/Off`` for False. For
  2022-2025 ``c1_1[0]`` is instead the MFS-exception box (ON ``/1``), which
  tenforty (which never declares MFS) NEVER checks — so it is left entirely
  unmapped those years. ``get_checkbox_states`` also carries the line 9 / line 10
Yes-No boxes (all years; see ``_LINE_9_10_BOXES``).

- **Poverty-table box 4c — ALL years.** ``f8962_line_4c_other48`` (a bool
  compute key, True: line 4 prices the "Other 48 states and DC" table, the
  only one tenforty models; see forms.f8962.compute) maps to ``c1_2[2]``,
  and ``get_checkbox_states`` carries its ``/3`` on-token (uniform across
  all five years) — the same bool → on-token translation as the 2021 UI
  box. No derivation remains (ruling A3).
"""

from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping

_ROOT = "topmostSubform[0].Page1[0]"

# Part I — annual/monthly contribution amount. Line 2b (dependents' MAGI) is
# deliberately unmapped: the compute does not emit it (dependents' MAGI is
# not modeled).
_PART_I: dict[str, str] = {
    "f8962_line_1":  f"{_ROOT}.f1_3[0]",   # tax family size
    "f8962_line_2a": f"{_ROOT}.f1_4[0]",   # modified AGI
    "f8962_line_3":  f"{_ROOT}.f1_6[0]",   # household income
    "f8962_line_4":  f"{_ROOT}.f1_7[0]",   # federal poverty line amount
    "f8962_line_5":  f"{_ROOT}.f1_8[0]",   # household income as % of FPL
    "f8962_line_7":  f"{_ROOT}.f1_9[0]",   # applicable figure
    "f8962_line_8a": f"{_ROOT}.f1_10[0]",  # annual contribution amount
    "f8962_line_8b": f"{_ROOT}.f1_11[0]",  # monthly contribution amount
}

# Line 11 — annual totals row (Part2Table1), columns (a)-(f). Filled only when
# the annual calculation is mandatory (see forms/f8962.py, line-10 rule).
_LINE_11: dict[str, str] = {
    f"f8962_line_11_{letter}": f"{_ROOT}.Part2Table1[0].BodyRow1[0].f1_{13 + i}[0]"
    for i, letter in enumerate("abcdef")
}

# Lines 9 / 10 checkboxes (same paths and on-states in every year 2021-2025,
# probe-verified against each template's /_States_ and widget geometry):
# c1_4 = line 9 (Yes [0] ON /1, No [1] ON /2); c1_5 = line 10 (Yes [0] ON /1,
# No [1] ON /2). Bool compute keys routed through checkbox_states.
_LINE_9_10_BOXES: dict[str, str] = {
    "f8962_line_9_no":   f"{_ROOT}.c1_4[1]",
    "f8962_line_10_yes": f"{_ROOT}.c1_5[0]",
    "f8962_line_10_no":  f"{_ROOT}.c1_5[1]",
}
_LINE_9_10_STATES: dict[str, str] = {
    "f8962_line_9_no": "/2",
    "f8962_line_10_yes": "/1",
    "f8962_line_10_no": "/2",
}

# Monthly grid — lines 12-23 (Jan..Dec = row 1..12), columns a-f. For month
# n the six cells are f1_{19 + (n-1)*6 + i}[0] (i=0..5) under BodyRow{n}[0].
_MONTHLY: dict[str, str] = {
    f"f8962_month_{n}_{letter}":
        f"{_ROOT}.Part2Table2[0].BodyRow{n}[0].f1_{19 + (n - 1) * 6 + i}[0]"
    for n in range(1, 13)
    for i, letter in enumerate("abcdef")
}

# Lines 24-29 — Part II total / Part III repayment.
_LINES_24_29: dict[str, str] = {
    "f8962_line_24":            f"{_ROOT}.f1_91[0]",  # total premium tax credit
    "f8962_line_25":            f"{_ROOT}.f1_92[0]",  # advance payment of PTC
    # Line 26 binds the PRINTED key (blank when line 25 > line 24), not the
    # always-numeric f8962_line_26_net_ptc the spine sums.
    "f8962_line_26_printed":    f"{_ROOT}.f1_93[0]",  # net premium tax credit
    # Part III binds the PRINTED keys too (blank unless line 25 > line 24:
    # the form stops at line 26 otherwise), not the always-numeric
    # f8962_line_27 / f8962_line_28 / f8962_line_29_repayment.
    "f8962_line_27_printed":    f"{_ROOT}.f1_94[0]",  # excess advance payment
    "f8962_line_28_printed":    f"{_ROOT}.f1_95[0]",  # repayment limitation
    "f8962_line_29_printed":    f"{_ROOT}.f1_96[0]",  # excess APTC repayment
}

# Base scalars — IDENTICAL field paths across 2021-2025 for every mapped
# line (verified per-year in the probe tables). Only 2021 adds the UI box.
# Header — "Name shown on your return" (f1_1) and "Your social security
# number" (f1_2): same rects on every year's template, render-confirmed on 2025.
_HEADER: dict[str, str] = {
    "taxpayer_name": f"{_ROOT}.f1_1[0]",
    "taxpayer_ssn":  f"{_ROOT}.f1_2[0]",
}

# Line 4 poverty-table box 4c, "Other 48 states and DC" (c1_2[2], ON-state
# /3, uniform across all five years): a bool compute key.
_BOX_4C: dict[str, str] = {"f8962_line_4c_other48": f"{_ROOT}.c1_2[2]"}
_BOX_4C_STATES: dict[str, str] = {"f8962_line_4c_other48": "/3"}

_SCALARS_BASE: dict[str, str] = {
    **_HEADER, **_PART_I, **_BOX_4C, **_LINE_11, **_LINE_9_10_BOXES,
    **_MONTHLY, **_LINES_24_29}

# 2021 (ARPA year) also maps the unemployment Box A at c1_1[0].
_SCALARS_2021: dict[str, str] = {
    **_SCALARS_BASE,
    "f8962_ui_box_checked": f"{_ROOT}.c1_1[0]",
}

_FIELDS_2021: dict = {"scalars": _SCALARS_2021, "repeaters": {}}
_FIELDS_BASE: dict = {"scalars": _SCALARS_BASE, "repeaters": {}}

# Form 8962 has no derived cells: every printed value, including the box
# 4c poverty-table mark, is a compute key (ruling A1 / A3).
_DERIVATIONS: dict[str, Callable[[Mapping[str, object]], object]] = {}

# Per-field render-format overrides (compute key -> Python format spec). The
# fill-time renderer rounds every numeric to whole dollars; line 7 is the
# applicable figure, a 4-decimal RATE (e.g. 0.0850), which would print "0" and
# leave line 3 x line 7 = line 8a unfootable. Uniform across all five years.
_FIELD_FORMATS: dict[str, str] = {
    "f8962_line_7": ".4f",
}

# Checkbox on-states, year-keyed: the line 4 box 4c (/3) and the line 9 /
# line 10 boxes every year; 2021 (ARPA) also maps the unemployment Box A
# bool key, with its own /2 on-token.
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: {"f8962_ui_box_checked": "/2", **_BOX_4C_STATES, **_LINE_9_10_STATES},
    2022: {**_BOX_4C_STATES, **_LINE_9_10_STATES},
    2023: {**_BOX_4C_STATES, **_LINE_9_10_STATES},
    2024: {**_BOX_4C_STATES, **_LINE_9_10_STATES},
    2025: {**_BOX_4C_STATES, **_LINE_9_10_STATES},
}


class PdfF8962(PdfFormMapping[dict]):
    """PDF field mapping for IRS Form 8962 (Premium Tax Credit)."""

    _FORM_NAME = "Form 8962"
    _MAPPINGS: dict[int, dict] = {
        2021: _FIELDS_2021,
        2022: _FIELDS_BASE,
        2023: _FIELDS_BASE,
        2024: _FIELDS_BASE,
        2025: _FIELDS_BASE,
    }

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        """Compute key -> PDF "on" appearance state for bool checkbox fields.

        States are year-keyed data in ``_CHECKBOX_STATES_BY_YEAR`` (no
        year-literal dispatch): box 4c (ON ``/3``) and the line 9 / 10
        boxes every year, plus the 2021 ARPA unemployment Box A (ON
        ``/2``)."""
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} checkbox states for year {year}")
        return _CHECKBOX_STATES_BY_YEAR[year]

    @classmethod
    def get_derivations(
        cls, year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        """PDF cells whose value is derived (not a direct compute key).

        None, every year: every printed value is a compute key."""
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} derivations for year {year}")
        return _DERIVATIONS

    @classmethod
    def get_field_formats(cls, year: int) -> dict[str, str]:
        """Compute key -> Python format spec replacing the whole-dollar render.

        Sole entry, all years: ``f8962_line_7`` (applicable figure) as 4
        decimals. Every other field keeps the whole-dollar default."""
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} field formats for year {year}")
        return _FIELD_FORMATS
