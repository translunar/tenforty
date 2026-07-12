"""PDF field mapping for IRS Schedule K-1 (Form 1120-S), 2023–2025."""

from tenforty.mappings.registry import PdfFormMapping


# 2024 and 2025 Schedule K-1 (1120-S) PDFs share an identical field tree
# (pinned by tests/test_mapping_year_identity.py); one payload serves both.
_FIELDS: dict[str, str] = {
    # Part I — Information About the Corporation
    # Field A: Corporation's employer identification number
    "entity_ein":               "topmostSubform[0].Page1[0].LeftCol[0].f1_06[0]",
    # Field B: Corporation's name, address, city, state, and ZIP code —
    # a single multi-line text area; the orchestrator builds the
    # concatenated name+address string before writing.
    "entity_name_and_address":  "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    # Part II — Information About the Shareholder
    # Field E: Shareholder's identifying number (SSN or EIN)
    "shareholder_ssn_or_ein":   "topmostSubform[0].Page1[0].LeftCol[0].f1_11[0]",
    # Field F1: Shareholder's name, address, city, state, and ZIP code —
    # same combined multi-line text area as field B above.
    "shareholder_name_and_address": "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    # Field G: Current year allocation percentage
    "ownership_percentage":     "topmostSubform[0].Page1[0].LeftCol[0].f1_16[0]",
    # Part III — Shareholder's Share of Current Year Income, Deductions,
    #             Credits, and Other Items
    # Line 1: Ordinary business income (loss)
    "box_1_ordinary_business_income": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines1-12[0].f1_21[0]"
    ),
}


# The 2023 Schedule K-1 field tree differs from 2024/2025 (the differ reports
# +11/-15 fields). Four of our six mapped cells keep 2024's short names, but
# two moved and were confirmed by a marker-probe render of the 2023 template
# (committed as pdfs/federal/2023/f1120s_k1.probe.pdf):
#   * ownership_percentage — Item G "Current year allocation percentage" is
#     f1_13 in 2023 (2024: f1_16). On the 2023 form f1_16 is Item I "Loans
#     from shareholder, beginning of year" — inheriting 2024 would mis-map it.
#   * box_1_ordinary_business_income — Part III Line 1 is f1_18 in 2023
#     (2024: f1_21). On the 2023 form f1_21 is Line 4 "Interest income".
# Both 2024 paths exist on the 2023 template, so only the rendered position
# (not path existence) distinguishes them.
_FIELDS_2023: dict[str, str] = {
    # Part I — Field A: Corporation's EIN
    "entity_ein":               "topmostSubform[0].Page1[0].LeftCol[0].f1_06[0]",
    # Part I — Field B: Corporation's name/address (combined multi-line text)
    "entity_name_and_address":  "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    # Part II — Field E: Shareholder's identifying number
    "shareholder_ssn_or_ein":   "topmostSubform[0].Page1[0].LeftCol[0].f1_11[0]",
    # Part II — Field F: Shareholder's name/address (combined multi-line text)
    "shareholder_name_and_address": "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    # Part II — Field G: Current year allocation percentage (2023: f1_13)
    "ownership_percentage":     "topmostSubform[0].Page1[0].LeftCol[0].f1_13[0]",
    # Part III — Line 1: Ordinary business income (loss) (2023: f1_18)
    "box_1_ordinary_business_income": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines1-12[0].f1_18[0]"
    ),
}


class PdfF1120SK1(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for IRS Schedule K-1 (Form 1120-S).

    Single flat registry — Schedule K-1 is a single-page form with a 1:1
    correspondence between K1Allocation fields and PDF cells (no combined
    cells, no derivations, no structural suppressions). Matches the
    `Pdf1040` flat-mapping precedent."""

    _FORM_NAME = "Schedule K-1 (Form 1120-S)"
    _MAPPINGS: dict[int, dict[str, str]] = {
        2023: _FIELDS_2023, 2024: _FIELDS, 2025: _FIELDS,
    }

# 2022's Schedule K-1 field tree is byte-identical to 2023's (verified widget-level:
# same names, pages, and /Rects), so 2022 reuses the 2023 payload.
PdfF1120SK1._MAPPINGS[2022] = PdfF1120SK1._MAPPINGS[2023]
