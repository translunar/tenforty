"""PDF field mapping for IRS Schedule B (Interest and Ordinary Dividends).

Parts I and II only. Part III (Foreign Accounts and Trusts) is not
implemented in tenforty v1; the scope-out is enforced at scenario load
via ``TaxReturnConfig.has_foreign_accounts`` (see #11 Task 6), so any
scenario reaching this mapping has already attested ``False``. Part III
/ FinCEN 114 (FBAR) support is tracked as a follow-up.

The 2025 Sch B PDF uses flat, sequential field names (``f1_01`` through
``f1_66``) rather than row-grouped names (e.g. ``Row1.f1_X``), so the
{i}-repeater shape introduced in Plan B Task 1 does not apply cleanly
here. The mapping declares every payer/amount slot as an explicit
scalar. Compute (Task 8) writes slots 1..N for N payers and leaves the
remaining slots unset; overflow is enforced in compute against the
14-interest / 16-dividend row caps.

Field-to-line assignment was established by filling every text field on
``pdfs/federal/2025/f1040sb.pdf`` with its own short name, flattening
via LibreOffice, rasterizing, and reading the rendered form (the
``filing/pdf.py`` probe methodology used for Form 4868).

Assignment (2025):
    f1_01 = taxpayer name, f1_02 = taxpayer SSN
    Line 1 interest rows:
        row 1 payer / amount = f1_03 / f1_04  (payer inside Line1_ReadOrder)
        rows 2..14           = f1_05 / f1_06 .. f1_29 / f1_30
    f1_31 = Line 2 (sum),  f1_32 = Line 3 (excludable), f1_33 = Line 4 (taxable)
    Line 5 dividend rows:
        row 1 payer / amount = f1_34 / f1_35  (payer inside ReadOrderControl)
        rows 2..16           = f1_36 / f1_37 .. f1_64 / f1_65
    f1_66 = Line 6 (sum)
"""

_PAGE1 = "topmostSubform[0].Page1[0]"

# Row 1's payer field is namespaced inside Line1_ReadOrder; all other
# line-1 payer/amount fields sit at Page1 scope.
_INTEREST_ROW_FIELDS: list[tuple[str, str]] = [
    (f"{_PAGE1}.Line1_ReadOrder[0].f1_03[0]", f"{_PAGE1}.f1_04[0]"),
    (f"{_PAGE1}.f1_05[0]", f"{_PAGE1}.f1_06[0]"),
    (f"{_PAGE1}.f1_07[0]", f"{_PAGE1}.f1_08[0]"),
    (f"{_PAGE1}.f1_09[0]", f"{_PAGE1}.f1_10[0]"),
    (f"{_PAGE1}.f1_11[0]", f"{_PAGE1}.f1_12[0]"),
    (f"{_PAGE1}.f1_13[0]", f"{_PAGE1}.f1_14[0]"),
    (f"{_PAGE1}.f1_15[0]", f"{_PAGE1}.f1_16[0]"),
    (f"{_PAGE1}.f1_17[0]", f"{_PAGE1}.f1_18[0]"),
    (f"{_PAGE1}.f1_19[0]", f"{_PAGE1}.f1_20[0]"),
    (f"{_PAGE1}.f1_21[0]", f"{_PAGE1}.f1_22[0]"),
    (f"{_PAGE1}.f1_23[0]", f"{_PAGE1}.f1_24[0]"),
    (f"{_PAGE1}.f1_25[0]", f"{_PAGE1}.f1_26[0]"),
    (f"{_PAGE1}.f1_27[0]", f"{_PAGE1}.f1_28[0]"),
    (f"{_PAGE1}.f1_29[0]", f"{_PAGE1}.f1_30[0]"),
]

# Row 1's payer field is namespaced inside ReadOrderControl.
_DIVIDEND_ROW_FIELDS: list[tuple[str, str]] = [
    (f"{_PAGE1}.ReadOrderControl[0].f1_34[0]", f"{_PAGE1}.f1_35[0]"),
    (f"{_PAGE1}.f1_36[0]", f"{_PAGE1}.f1_37[0]"),
    (f"{_PAGE1}.f1_38[0]", f"{_PAGE1}.f1_39[0]"),
    (f"{_PAGE1}.f1_40[0]", f"{_PAGE1}.f1_41[0]"),
    (f"{_PAGE1}.f1_42[0]", f"{_PAGE1}.f1_43[0]"),
    (f"{_PAGE1}.f1_44[0]", f"{_PAGE1}.f1_45[0]"),
    (f"{_PAGE1}.f1_46[0]", f"{_PAGE1}.f1_47[0]"),
    (f"{_PAGE1}.f1_48[0]", f"{_PAGE1}.f1_49[0]"),
    (f"{_PAGE1}.f1_50[0]", f"{_PAGE1}.f1_51[0]"),
    (f"{_PAGE1}.f1_52[0]", f"{_PAGE1}.f1_53[0]"),
    (f"{_PAGE1}.f1_54[0]", f"{_PAGE1}.f1_55[0]"),
    (f"{_PAGE1}.f1_56[0]", f"{_PAGE1}.f1_57[0]"),
    (f"{_PAGE1}.f1_58[0]", f"{_PAGE1}.f1_59[0]"),
    (f"{_PAGE1}.f1_60[0]", f"{_PAGE1}.f1_61[0]"),
    (f"{_PAGE1}.f1_62[0]", f"{_PAGE1}.f1_63[0]"),
    (f"{_PAGE1}.f1_64[0]", f"{_PAGE1}.f1_65[0]"),
]

INTEREST_MAX_ROWS = len(_INTEREST_ROW_FIELDS)   # 14
DIVIDEND_MAX_ROWS = len(_DIVIDEND_ROW_FIELDS)   # 16


def _build_2025_mapping() -> dict[str, str]:
    m: dict[str, str] = {
        "taxpayer_name": f"{_PAGE1}.f1_01[0]",
        "taxpayer_ssn": f"{_PAGE1}.f1_02[0]",
        "total_interest": f"{_PAGE1}.f1_31[0]",
        "excludable_savings_bond": f"{_PAGE1}.f1_32[0]",
        "taxable_interest": f"{_PAGE1}.f1_33[0]",
        "total_ordinary_dividends": f"{_PAGE1}.f1_66[0]",
    }
    for i, (payer, amount) in enumerate(_INTEREST_ROW_FIELDS, start=1):
        m[f"interest_payer_{i}"] = payer
        m[f"interest_amount_{i}"] = amount
    for i, (payer, amount) in enumerate(_DIVIDEND_ROW_FIELDS, start=1):
        m[f"dividend_payer_{i}"] = payer
        m[f"dividend_amount_{i}"] = amount
    return m


class PdfSchB:
    """PDF field mapping for IRS Schedule B (2025)."""

    _MAPPINGS: dict[int, dict[str, str]] = {
        2025: _build_2025_mapping(),
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict[str, str]:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule B PDF mapping for year {year}")
        return cls._MAPPINGS[year]
