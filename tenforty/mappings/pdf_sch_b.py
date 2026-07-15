"""PDF field mapping for IRS Schedule B (Interest and Ordinary Dividends).

Parts I and II only. Part III (Foreign Accounts and Trusts) is not
implemented in tenforty v1; the scope-out is enforced at scenario load
via ``TaxReturnConfig.has_foreign_accounts``, so any
scenario reaching this mapping has already attested ``False``. Part III
/ FinCEN 114 (FBAR) support is tracked as a follow-up.

The 2025 Sch B PDF uses flat, sequential field names (``f1_01`` through
``f1_66``) rather than row-grouped names (e.g. ``Row1.f1_X``), so the
{i}-repeater shape used by other forms does not apply cleanly here.
The mapping declares every payer/amount slot as an explicit scalar.
Compute writes slots 1..N for N payers and leaves the
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

from tenforty.mappings.registry import PdfFormMapping

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


def _build_fields() -> dict[str, str]:
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


# 2024 and 2025 Schedule B PDFs share identical topmostSubform/Page1
# structure with the same Line1_ReadOrder and ReadOrderControl subform
# containers (pinned by tests/test_mapping_year_identity.py); one payload
# serves both years.
_FIELDS: dict[str, str] = _build_fields()


class PdfSchB(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for IRS Schedule B."""

    _FORM_NAME = "Schedule B"
    # 2023's field tree is byte-identical to 2024's (verified: identical
    # AcroForm field-path sets), so one payload serves all three years.
    _MAPPINGS: dict[int, dict[str, str]] = {
        2023: _FIELDS, 2024: _FIELDS, 2025: _FIELDS,
    }

# 2022's Schedule B keeps 2023's identical field-NAME inventory and mapped paths.
# Geometry has one isolated horizontal nudge (dividend row f1_65 -14.4pt x), which
# cannot change a line assignment. So 2022 reuses the 2023 payload.
PdfSchB._MAPPINGS[2022] = PdfSchB._MAPPINGS[2023]

# 2021 fresh probe (air-gapped) — field tree differs from 2022 (f1_N vs f1_0N
# padding; no ReadOrder container wrappers); controller-verified every path on
# the 2021 template.
PdfSchB._MAPPINGS[2021] = {
    "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
    "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",

    "interest_payer_1": "topmostSubform[0].Page1[0].f1_3[0]",
    "interest_amount_1": "topmostSubform[0].Page1[0].f1_4[0]",
    "interest_payer_2": "topmostSubform[0].Page1[0].f1_5[0]",
    "interest_amount_2": "topmostSubform[0].Page1[0].f1_6[0]",
    "interest_payer_3": "topmostSubform[0].Page1[0].f1_7[0]",
    "interest_amount_3": "topmostSubform[0].Page1[0].f1_8[0]",
    "interest_payer_4": "topmostSubform[0].Page1[0].f1_9[0]",
    "interest_amount_4": "topmostSubform[0].Page1[0].f1_10[0]",
    "interest_payer_5": "topmostSubform[0].Page1[0].f1_11[0]",
    "interest_amount_5": "topmostSubform[0].Page1[0].f1_12[0]",
    "interest_payer_6": "topmostSubform[0].Page1[0].f1_13[0]",
    "interest_amount_6": "topmostSubform[0].Page1[0].f1_14[0]",
    "interest_payer_7": "topmostSubform[0].Page1[0].f1_15[0]",
    "interest_amount_7": "topmostSubform[0].Page1[0].f1_16[0]",
    "interest_payer_8": "topmostSubform[0].Page1[0].f1_17[0]",
    "interest_amount_8": "topmostSubform[0].Page1[0].f1_18[0]",
    "interest_payer_9": "topmostSubform[0].Page1[0].f1_19[0]",
    "interest_amount_9": "topmostSubform[0].Page1[0].f1_20[0]",
    "interest_payer_10": "topmostSubform[0].Page1[0].f1_21[0]",
    "interest_amount_10": "topmostSubform[0].Page1[0].f1_22[0]",
    "interest_payer_11": "topmostSubform[0].Page1[0].f1_23[0]",
    "interest_amount_11": "topmostSubform[0].Page1[0].f1_24[0]",
    "interest_payer_12": "topmostSubform[0].Page1[0].f1_25[0]",
    "interest_amount_12": "topmostSubform[0].Page1[0].f1_26[0]",
    "interest_payer_13": "topmostSubform[0].Page1[0].f1_27[0]",
    "interest_amount_13": "topmostSubform[0].Page1[0].f1_28[0]",
    "interest_payer_14": "topmostSubform[0].Page1[0].f1_29[0]",
    "interest_amount_14": "topmostSubform[0].Page1[0].f1_30[0]",

    "total_interest": "topmostSubform[0].Page1[0].f1_31[0]",          # line 2
    "excludable_savings_bond": "topmostSubform[0].Page1[0].f1_32[0]", # line 3
    "taxable_interest": "topmostSubform[0].Page1[0].f1_33[0]",        # line 4

    "dividend_payer_1": "topmostSubform[0].Page1[0].f1_34[0]",
    "dividend_amount_1": "topmostSubform[0].Page1[0].f1_35[0]",
    "dividend_payer_2": "topmostSubform[0].Page1[0].f1_36[0]",
    "dividend_amount_2": "topmostSubform[0].Page1[0].f1_37[0]",
    "dividend_payer_3": "topmostSubform[0].Page1[0].f1_38[0]",
    "dividend_amount_3": "topmostSubform[0].Page1[0].f1_39[0]",
    "dividend_payer_4": "topmostSubform[0].Page1[0].f1_40[0]",
    "dividend_amount_4": "topmostSubform[0].Page1[0].f1_41[0]",
    "dividend_payer_5": "topmostSubform[0].Page1[0].f1_42[0]",
    "dividend_amount_5": "topmostSubform[0].Page1[0].f1_43[0]",
    "dividend_payer_6": "topmostSubform[0].Page1[0].f1_44[0]",
    "dividend_amount_6": "topmostSubform[0].Page1[0].f1_45[0]",
    "dividend_payer_7": "topmostSubform[0].Page1[0].f1_46[0]",
    "dividend_amount_7": "topmostSubform[0].Page1[0].f1_47[0]",
    "dividend_payer_8": "topmostSubform[0].Page1[0].f1_48[0]",
    "dividend_amount_8": "topmostSubform[0].Page1[0].f1_49[0]",
    "dividend_payer_9": "topmostSubform[0].Page1[0].f1_50[0]",
    "dividend_amount_9": "topmostSubform[0].Page1[0].f1_51[0]",
    "dividend_payer_10": "topmostSubform[0].Page1[0].f1_52[0]",
    "dividend_amount_10": "topmostSubform[0].Page1[0].f1_53[0]",
    "dividend_payer_11": "topmostSubform[0].Page1[0].f1_54[0]",
    "dividend_amount_11": "topmostSubform[0].Page1[0].f1_55[0]",
    "dividend_payer_12": "topmostSubform[0].Page1[0].f1_56[0]",
    "dividend_amount_12": "topmostSubform[0].Page1[0].f1_57[0]",
    "dividend_payer_13": "topmostSubform[0].Page1[0].f1_58[0]",
    "dividend_amount_13": "topmostSubform[0].Page1[0].f1_59[0]",
    "dividend_payer_14": "topmostSubform[0].Page1[0].f1_60[0]",
    "dividend_amount_14": "topmostSubform[0].Page1[0].f1_61[0]",
    "dividend_payer_15": "topmostSubform[0].Page1[0].f1_62[0]",
    "dividend_amount_15": "topmostSubform[0].Page1[0].f1_63[0]",
    "dividend_payer_16": "topmostSubform[0].Page1[0].f1_64[0]",
    "dividend_amount_16": "topmostSubform[0].Page1[0].f1_65[0]",

    "total_ordinary_dividends": "topmostSubform[0].Page1[0].f1_66[0]", # line 6
}
