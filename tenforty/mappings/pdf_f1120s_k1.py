"""PDF field mapping for IRS Schedule K-1 (Form 1120-S), 2023–2025."""

from tenforty.mappings.registry import PdfFormMapping, trim_decimal


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
    # Field D: Corporation's total number of shares (beginning / end), Part I
    "k1_total_shares_beginning": "topmostSubform[0].Page1[0].LeftCol[0].f1_09[0]",
    "k1_total_shares_end":       "topmostSubform[0].Page1[0].LeftCol[0].f1_10[0]",
    # Field C: IRS Center where corporation filed return (Part I)
    "k1_irs_center":            "topmostSubform[0].Page1[0].LeftCol[0].f1_08[0]",
    # Field G: Current year allocation percentage
    "ownership_percentage":     "topmostSubform[0].Page1[0].LeftCol[0].f1_16[0]",
    # Field H: Shareholder's number of shares (beginning / end of tax year) and
    # Field I: Loans from shareholder (beginning / end). Certified by printed
    # caption beside each widget Rect on the 2024 and 2025 templates.
    "k1_shares_beginning":      "topmostSubform[0].Page1[0].LeftCol[0].f1_17[0]",
    "k1_shares_end":            "topmostSubform[0].Page1[0].LeftCol[0].f1_18[0]",
    "k1_loans_beginning":       "topmostSubform[0].Page1[0].LeftCol[0].f1_19[0]",
    "k1_loans_end":             "topmostSubform[0].Page1[0].LeftCol[0].f1_20[0]",
    # Part III — Shareholder's Share of Current Year Income, Deductions,
    #             Credits, and Other Items
    # Line 1: Ordinary business income (loss)
    "box_1_ordinary_business_income": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines1-12[0].f1_21[0]"
    ),
    # Part III — Line 17 (Other information), code V (§199A): the code cell
    # holds the literal "V"; the amount cell holds "STMT" because §199A info
    # is furnished on the attached Statement A, not inline (IRS Sch K-1
    # (1120-S) instructions, box 17). Confirmed by marker-probe render of the
    # 2025 template: the "17 Other information" block's first row is
    # f1_90 (code) / f1_91 (amount).
    "box_17_code_v": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_90[0]"
    ),
    "box_17_code_v_amount": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_91[0]"
    ),
    # Part III box 16 "Items affecting shareholder basis", first row: code cell
    # (the letter D = distributions) and its amount. Certified by the printed
    # "16 Items affecting shareholder basis" header (y 446) with the first row
    # directly below it; the row above the header belongs to box 15 (AMT).
    "box_16_code_d": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_80[0]"
    ),
    "box_16_code_d_amount": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_81[0]"
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
    # Part I — Field D: Corporation's total shares (beginning / end); f1_09 /
    # f1_10 beside the printed caption on 2021-2023 as on 2024-2025.
    "k1_total_shares_beginning": "topmostSubform[0].Page1[0].LeftCol[0].f1_09[0]",
    "k1_total_shares_end":       "topmostSubform[0].Page1[0].LeftCol[0].f1_10[0]",
    # Part I — Field C: IRS Center where corporation filed return
    "k1_irs_center":            "topmostSubform[0].Page1[0].LeftCol[0].f1_08[0]",
    # Part II — Field G: Current year allocation percentage (2023: f1_13)
    "ownership_percentage":     "topmostSubform[0].Page1[0].LeftCol[0].f1_13[0]",
    # Part II — Field H shares / Field I loans (beginning, end). On 2021-2023
    # these sit at f1_14..f1_17; the 2024-era f1_17..f1_20 paths also EXIST on
    # these templates but land at different printed items (position, not
    # existence, distinguishes them).
    "k1_shares_beginning":      "topmostSubform[0].Page1[0].LeftCol[0].f1_14[0]",
    "k1_shares_end":            "topmostSubform[0].Page1[0].LeftCol[0].f1_15[0]",
    "k1_loans_beginning":       "topmostSubform[0].Page1[0].LeftCol[0].f1_16[0]",
    "k1_loans_end":             "topmostSubform[0].Page1[0].LeftCol[0].f1_17[0]",
    # Part III — Line 1: Ordinary business income (loss) (2023: f1_18)
    "box_1_ordinary_business_income": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines1-12[0].f1_18[0]"
    ),
    # Part III — Line 17 code V. Confirmed by marker-probe renders of BOTH the
    # 2023 and 2021 templates: box 17's first row is f1_87 (code) / f1_88
    # (amount) in each (2022 is byte-identical to 2023 per the existing note
    # below). The 2024-era f1_90/f1_91 paths also EXIST on these templates but
    # land at different printed lines — position, not existence, distinguishes
    # them, exactly as for ownership_percentage and box 1 above.
    "box_17_code_v": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_87[0]"
    ),
    "box_17_code_v_amount": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_88[0]"
    ),
    # Box 16 first row (2021-2023 vintage: f1_77 code / f1_78 amount); same
    # caption-row certification as the 2024-2025 payload above.
    "box_16_code_d": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_77[0]"
    ),
    "box_16_code_d_amount": (
        "topmostSubform[0].Page1[0].RightCol[0].Lines13-17[0].f1_78[0]"
    ),
}


# Item G is a 0-100 percentage that may be fractional (33.333); the default
# whole-dollar renderer would print "33". Trimmed decimals keep 100 -> "100".
# Shares may be fractional too (item H), so they share the trimmed-decimal
# renderer; loans stay whole-dollar (the form prints the "$").
_FIELD_FORMATS = {
    "ownership_percentage": trim_decimal,
    "k1_shares_beginning": trim_decimal,
    "k1_shares_end": trim_decimal,
    "k1_total_shares_beginning": trim_decimal,
    "k1_total_shares_end": trim_decimal,
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

    @classmethod
    def get_field_formats(cls, year: int) -> dict:
        """Compute key -> render override (see ``PdfFiller.resolve_fields``)."""
        if year not in cls._MAPPINGS:
            raise ValueError(f"No {cls._FORM_NAME} field formats for year {year}")
        return _FIELD_FORMATS

    @classmethod
    def get_amended_mark(cls, year: int) -> tuple[str, str]:
        """(field_path, ON-state) for the "Amended K-1" checkbox (§4a).

        ADDITIVE: independent of the ``_MAPPINGS`` value registry above; the
        orchestrator merges this single entry into the fill only when the
        S-corp return is flagged amended. Certified from each template's own
        get_fields()/_States_ (probe-tables §(b)): path
        topmostSubform[0].Page1[0].c1_02[0], /_States_ ['/1','/Off'], ON '/1',
        IDENTICAL across all supported years 2021-2025.
        """
        if year not in _AMENDED_MARK_BY_YEAR:
            raise ValueError(
                f"No Schedule K-1 (1120-S) amended mark for year {year}")
        return _AMENDED_MARK_BY_YEAR[year]

    @classmethod
    def get_final_mark(cls, year: int) -> tuple[str, str]:
        """(field_path, ON-state) for the "Final K-1" checkbox (top of the
        form, beside "Amended K-1"). Same additive pattern as
        ``get_amended_mark``: independent of the ``_MAPPINGS`` registry; the
        orchestrator merges it per shareholder only when that shareholder is
        flagged final. Certified by the printed "Final" caption beside the
        c1_01 widget on every year's template; ON '/1', identical 2021-2025.
        """
        if year not in _FINAL_MARK_BY_YEAR:
            raise ValueError(
                f"No Schedule K-1 (1120-S) final mark for year {year}")
        return _FINAL_MARK_BY_YEAR[year]


_AMENDED_MARK_K1: tuple[str, str] = (
    "topmostSubform[0].Page1[0].c1_02[0]", "/1")
_AMENDED_MARK_BY_YEAR: dict[int, tuple[str, str]] = {
    y: _AMENDED_MARK_K1 for y in (2021, 2022, 2023, 2024, 2025)
}
_FINAL_MARK_K1: tuple[str, str] = (
    "topmostSubform[0].Page1[0].c1_01[0]", "/1")
_FINAL_MARK_BY_YEAR: dict[int, tuple[str, str]] = {
    y: _FINAL_MARK_K1 for y in (2021, 2022, 2023, 2024, 2025)
}

# 2022's Schedule K-1 field tree is byte-identical to 2023's (verified widget-level:
# same names, pages, and /Rects), so 2022 reuses the 2023 payload.
PdfF1120SK1._MAPPINGS[2022] = PdfF1120SK1._MAPPINGS[2023]
# 2021 verified identical to 2022 by marker-probe (K-1 ownership%=f1_13,
# box 1=f1_18 confirmed at their 2021 lines); inherit the 2022 mapping.
PdfF1120SK1._MAPPINGS[2021] = PdfF1120SK1._MAPPINGS[2022]
