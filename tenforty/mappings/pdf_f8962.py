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
  tenforty (single-filer only) NEVER checks — so it is left entirely
  unmapped those years and ``get_checkbox_states`` is empty.

- **Poverty-table box 4c — hardwired ON, ALL years.** The CA filer always
  uses the "Other 48 states and DC" poverty table, so box 4c
  (``c1_2[2]``, ON-state ``/3``, uniform across all five years) must always
  be checked. There is no compute key for it (Task-3 compute is out of
  scope to touch), so it is hardwired via a DERIVATION that emits the
  ``/3`` appearance-state string directly — the established house pattern
  for a constant/always-on checkbox (see pdf_f540.py's line-31 tax-source
  checkbox derivations, which likewise emit the on/off state string
  directly rather than routing a bool through checkbox_states).
"""

from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping

_ROOT = "topmostSubform[0].Page1[0]"

# Part I — annual/monthly contribution amount. Line 2b (dependents' MAGI)
# and line 11 (annual-calc row) are deliberately unmapped: the compute
# emits neither (single-filer, monthly-grid-only scope).
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
    "f8962_line_26_net_ptc":    f"{_ROOT}.f1_93[0]",  # net premium tax credit
    "f8962_line_27":            f"{_ROOT}.f1_94[0]",  # excess advance payment
    "f8962_line_28":            f"{_ROOT}.f1_95[0]",  # repayment limitation
    "f8962_line_29_repayment":  f"{_ROOT}.f1_96[0]",  # excess APTC repayment
}

# Base scalars — IDENTICAL field paths across 2021-2025 for every mapped
# line (verified per-year in the probe tables). Only 2021 adds the UI box.
_SCALARS_BASE: dict[str, str] = {**_PART_I, **_MONTHLY, **_LINES_24_29}

# 2021 (ARPA year) also maps the unemployment Box A at c1_1[0].
_SCALARS_2021: dict[str, str] = {
    **_SCALARS_BASE,
    "f8962_ui_box_checked": f"{_ROOT}.c1_1[0]",
}

_FIELDS_2021: dict = {"scalars": _SCALARS_2021, "repeaters": {}}
_FIELDS_BASE: dict = {"scalars": _SCALARS_BASE, "repeaters": {}}

# Poverty-table box 4c — "Other 48 states and DC", ON-state /3, uniform
# across all five years. Always-on: a derivation keyed by the PDF path that
# emits the /3 appearance-state string directly (the fill layer str-passes
# it through). No compute key, no scalar entry, no bool routing.
_POVERTY_TABLE_4C_PATH = f"{_ROOT}.c1_2[2]"
_DERIVATIONS: dict[str, Callable[[Mapping[str, object]], object]] = {
    _POVERTY_TABLE_4C_PATH: lambda _values: "/3",
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

        Only the 2021 ARPA unemployment Box A is routed this way (ON ``/2``);
        every other year has no bool-mapped checkbox (the 4c poverty-table
        box is a constant handled by ``get_derivations``, not a bool)."""
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} checkbox states for year {year}")
        if year == 2021:
            return {"f8962_ui_box_checked": "/2"}
        return {}

    @classmethod
    def get_derivations(
        cls, year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        """PDF cells whose value is derived (not a direct compute key).

        Sole entry, all years: the always-on 4c poverty-table checkbox,
        emitting the ``/3`` on-state string directly."""
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} derivations for year {year}")
        return _DERIVATIONS
