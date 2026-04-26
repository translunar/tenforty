"""PDF field mapping for IRS 2025 Schedule K-1 (Form 1120-S)."""


class PdfF1120SK1:
    """PDF field mapping for IRS Schedule K-1 (Form 1120-S).

    Single flat registry — Schedule K-1 is a single-page form with a 1:1
    correspondence between K1Allocation fields and PDF cells (no combined
    cells, no derivations, no structural suppressions). Matches the
    `Pdf1040` flat-mapping precedent."""

    @classmethod
    def get_mapping(cls, year: int) -> dict[str, str]:
        if year == 2025:
            return _MAPPING_2025
        raise ValueError(f"No Sch K-1 mapping for year {year}")


_MAPPING_2025: dict[str, str] = {
    # Part I — Information About the Corporation
    # Field A: Corporation's employer identification number
    "entity_ein":             "topmostSubform[0].Page1[0].LeftCol[0].f1_06[0]",
    # Field B: Corporation's name, address, city, state, and ZIP code.
    # The IRS K-1 PDF uses a single combined multi-line text area for the
    # entire name+address block (h=60, no sub-fields). All five address
    # component keys map to the same PDF path; the orchestrator concatenates
    # the components into one string before writing to the PDF.
    "entity_name":            "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    "entity_address_street":  "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    "entity_address_city":    "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    "entity_address_state":   "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    "entity_address_zip":     "topmostSubform[0].Page1[0].LeftCol[0].f1_07[0]",
    # Part II — Information About the Shareholder
    # Field E: Shareholder's identifying number (SSN or EIN)
    "shareholder_ssn_or_ein":     "topmostSubform[0].Page1[0].LeftCol[0].f1_11[0]",
    # Field F1: Shareholder's name, address, city, state, and ZIP code.
    # Same combined-block constraint as field B above.
    "shareholder_name":           "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    "shareholder_address_street": "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    "shareholder_address_city":   "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    "shareholder_address_state":  "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    "shareholder_address_zip":    "topmostSubform[0].Page1[0].LeftCol[0].f1_12[0]",
    # Field G: Current year allocation percentage
    "ownership_percentage":       "topmostSubform[0].Page1[0].LeftCol[0].f1_16[0]",
    # Part III — Shareholder's Share of Current Year Income, Deductions,
    #             Credits, and Other Items
    # Line 1: Ordinary business income (loss)
    "box_1_ordinary_business_income": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines1-12[0].f1_21[0]"
    ),
}
