"""Form 1040-X (Rev. December 2025) PDF field mapping.

Flat 1:1 compute-key -> IRS AcroForm field. Consumes the ``forms/f1040x``
assembler's output keys and maps each to its field PATH on the Dec-2025
1040-X template. Every path is the template's OWN ``get_fields()`` key,
marker-probe certified against ``pdfs/federal/amendments/f1040x.pdf`` (each
entry's trailing comment records page + printed label). No path is inferred.

REVISION-KEYED, not year-keyed
------------------------------
The year-keyed mapping classes (e.g. PdfF100S) key ``_MAPPINGS`` by tax-year
int. Form 1040-X is different: one CURRENT revision of the form serves every
amendable federal year (the amended year is a page-1 write-in, not a distinct
template). So ``_MAPPINGS`` is keyed by the REVISION STRING and ``get_mapping``
takes a ``revision: str`` (e.g. ``"rev-2025-12"``). The module-level
``get_mapping`` helper delegates to the class; the completeness gate calls it.

Three-column grid (lines 1-15) vs single-column tail (16-23)
------------------------------------------------------------
Lines 1-15 are the A/B/C grid: each assembler key ``f1040x_line<N>_a/_b/_c``
maps to that line's A (Original amount) / B (Net change) / C (Correct amount)
field. tenforty sources lines 1, 2, 3, 4a, 5, 6, 7, 8, 10, 11, 12, 13, 15
(line 7 is sourced as 0/0 in practice per the ``forms/f1040x`` assembler
docstring — a nonzero FILED value already refuses via the out-of-scope guard
before this line is reached; the guarded out-of-scope lines 4b/14 are never
emitted, so never mapped; line 9 is Reserved-for-future-use and never
mapped). Lines 16-23 are single-column final-amount fields.

INTENTIONALLY UNMAPPED diagnostic aliases
-----------------------------------------
The assembler emits three DUPLICATE aliases that carry the exact same value as
their bare line key:
  - ``f1040x_line18_overpayment_on_original`` duplicates ``f1040x_line18``
  - ``f1040x_line20_amount_owed``            duplicates ``f1040x_line20``
  - ``f1040x_line22_refund``                 duplicates ``f1040x_line22``
Only the BARE keys are mapped to their fields. Mapping the aliases too would
double-fill a single field (identical value written twice to the same widget),
so they are DELIBERATELY absent from ``_MAPPING``. The payload-coverage test
asserts their absence.

PAGE-1 HEADER — a separate mapping
----------------------------------
Name, SSN, spouse, address and the "Amended return filing status" row are
scenario-derived (``forms.f1040x.presentation_keys``), not assembler output, so
they live in ``_PRESENTATION_MAPPING`` (``get_presentation_mapping``) and the
orchestrator merges the two at emit. That keeps ``_MAPPING`` exactly the
assembler's key set. The filing-status boxes are five separate /Btn fields
whose on-states are ``/1``..``/5`` left to right (``get_checkbox_states``).
"""
from tenforty.mappings.registry import PdfFormMapping

# Path prefixes (all fields nest under topmostSubform[0]).
_P1 = "topmostSubform[0].Page1[0]."
_ID = _P1 + "Table_IncomeDeductions[0]."   # lines 1-5 grid
_TL = _P1 + "Table_TaxLiability[0]."       # lines 6-11 grid
_PM = _P1 + "Table_Payments[0]."           # lines 12-15 grid

# compute-key -> 1040-X field path. Marker-probe certified against
# pdfs/federal/amendments/f1040x.pdf get_fields() (221 fields). Trailing
# comment: page + printed label, from docs/plans/amended-returns-probe-tables.md.
_MAPPING: dict[str, str] = {
    # ----- Three-column grid, lines 1-15 (A=Original / B=Net change / C=Correct)
    "f1040x_line1_a":  _ID + "Line1[0].f1_18[0]",   # p1 L1 Adjusted gross income — Col A
    "f1040x_line1_b":  _ID + "Line1[0].f1_19[0]",   # p1 L1 Adjusted gross income — Col B
    "f1040x_line1_c":  _ID + "Line1[0].f1_20[0]",   # p1 L1 Adjusted gross income — Col C
    "f1040x_line2_a":  _ID + "Line2[0].f1_21[0]",   # p1 L2 Itemized/standard deduction — Col A
    "f1040x_line2_b":  _ID + "Line2[0].f1_22[0]",   # p1 L2 Itemized/standard deduction — Col B
    "f1040x_line2_c":  _ID + "Line2[0].f1_23[0]",   # p1 L2 Itemized/standard deduction — Col C
    "f1040x_line3_a":  _ID + "Line3[0].f1_24[0]",   # p1 L3 Subtract line 2 from line 1 — Col A
    "f1040x_line3_b":  _ID + "Line3[0].f1_25[0]",   # p1 L3 Subtract line 2 from line 1 — Col B
    "f1040x_line3_c":  _ID + "Line3[0].f1_26[0]",   # p1 L3 Subtract line 2 from line 1 — Col C
    "f1040x_line4a_a": _ID + "Line4a[0].f1_27[0]",  # p1 L4a Qualified business income deduction — Col A
    "f1040x_line4a_b": _ID + "Line4a[0].f1_28[0]",  # p1 L4a Qualified business income deduction — Col B
    "f1040x_line4a_c": _ID + "Line4a[0].f1_29[0]",  # p1 L4a Qualified business income deduction — Col C
    "f1040x_line5_a":  _ID + "Line5[0].f1_33[0]",   # p1 L5 Taxable income — Col A
    "f1040x_line5_b":  _ID + "Line5[0].f1_34[0]",   # p1 L5 Taxable income — Col B
    "f1040x_line5_c":  _ID + "Line5[0].f1_35[0]",   # p1 L5 Taxable income — Col C
    # Lines 6/7/8/10: the amended-returns probe table
    # (docs/plans/amended-returns-probe-tables.md) lists these as BARE
    # ``Table_TaxLiability[0]…`` suffixes; the mapping below uses the full
    # ``_TL``-prefixed forms, independently re-verified against the
    # template's own get_fields() (bare-vs-prefixed namespace — same table
    # prefix constant that f1040x_line11_* already uses).
    "f1040x_line6_a":  _TL + "Line6[0].f1_37[0]",   # p1 L6 Tax — Col A
    "f1040x_line6_b":  _TL + "Line6[0].f1_38[0]",   # p1 L6 Tax — Col B
    "f1040x_line6_c":  _TL + "Line6[0].f1_39[0]",   # p1 L6 Tax — Col C
    "f1040x_line7_a":  _TL + "Line7[0].f1_40[0]",   # p1 L7 Nonrefundable credits — Col A
    "f1040x_line7_b":  _TL + "Line7[0].f1_41[0]",   # p1 L7 Nonrefundable credits — Col B
    "f1040x_line7_c":  _TL + "Line7[0].f1_42[0]",   # p1 L7 Nonrefundable credits — Col C
    "f1040x_line8_a":  _TL + "Line8[0].f1_43[0]",   # p1 L8 Subtract line 7 from line 6 — Col A
    "f1040x_line8_b":  _TL + "Line8[0].f1_44[0]",   # p1 L8 Subtract line 7 from line 6 — Col B
    "f1040x_line8_c":  _TL + "Line8[0].f1_45[0]",   # p1 L8 Subtract line 7 from line 6 — Col C
    "f1040x_line10_a": _TL + "Line10[0].f1_49[0]",  # p1 L10 Other taxes — Col A
    "f1040x_line10_b": _TL + "Line10[0].f1_50[0]",  # p1 L10 Other taxes — Col B
    "f1040x_line10_c": _TL + "Line10[0].f1_51[0]",  # p1 L10 Other taxes — Col C
    "f1040x_line11_a": _TL + "Line11[0].f1_52[0]",  # p1 L11 Total tax (add lines 8 and 10) — Col A
    "f1040x_line11_b": _TL + "Line11[0].f1_53[0]",  # p1 L11 Total tax (add lines 8 and 10) — Col B
    "f1040x_line11_c": _TL + "Line11[0].f1_54[0]",  # p1 L11 Total tax (add lines 8 and 10) — Col C
    "f1040x_line12_a": _PM + "Line12[0].f1_55[0]",  # p1 L12 Federal income tax withheld — Col A
    "f1040x_line12_b": _PM + "Line12[0].f1_56[0]",  # p1 L12 Federal income tax withheld — Col B
    "f1040x_line12_c": _PM + "Line12[0].f1_57[0]",  # p1 L12 Federal income tax withheld — Col C
    "f1040x_line13_a": _PM + "Line13[0].f1_58[0]",  # p1 L13 Estimated tax payments — Col A
    "f1040x_line13_b": _PM + "Line13[0].f1_59[0]",  # p1 L13 Estimated tax payments — Col B
    "f1040x_line13_c": _PM + "Line13[0].f1_60[0]",  # p1 L13 Estimated tax payments — Col C
    "f1040x_line15_a": _PM + "Line15[0].f1_65[0]",  # p1 L15 Total refundable credits — Col A
    "f1040x_line15_b": _PM + "Line15[0].f1_66[0]",  # p1 L15 Total refundable credits — Col B
    "f1040x_line15_c": _PM + "Line15[0].f1_67[0]",  # p1 L15 Total refundable credits — Col C
    # ----- Single-column tail, lines 16-23 (final-amount column, right edge)
    "f1040x_line16": _P1 + "f1_68[0]",  # p1 L16 Total amount paid with extension/original/after filing
    "f1040x_line17": _P1 + "f1_69[0]",  # p1 L17 Total payments (add lines 12-15 col C, and line 16)
    "f1040x_line18": _P1 + "f1_70[0]",  # p1 L18 Overpayment on original return / as adjusted by IRS
    "f1040x_line19": _P1 + "f1_71[0]",  # p1 L19 Subtract line 18 from line 17
    "f1040x_line20": _P1 + "f1_72[0]",  # p1 L20 Amount you owe
    "f1040x_line21": _P1 + "f1_73[0]",  # p1 L21 Overpaid on this return
    "f1040x_line22": _P1 + "f1_74[0]",  # p1 L22 Amount of line 21 refunded to you
    "f1040x_line23": _P1 + "f1_76[0]",  # p1 L23 Amount of line 21 applied to est. tax (amount field)
    # ----- Year write-in + Part II explanation (special fields)
    "f1040x_amended_year": _P1 + "f1_01[0]",             # p1 "This return is for calendar year (enter year)"
    "f1040x_explanation":  "topmostSubform[0].Page2[0].f2_35[0]",  # p2 Part II — Explanation of Changes
}

# Page-1 header. Each path was confirmed by rendering a fill of the template
# with every header cell stamped with its own field name and each filing-status
# box checked in turn. NOT mapped: f1_02 (fiscal year ended), f1_10 (apt. no.),
# f1_14-f1_16 (foreign address), c1_1/c1_2 (Presidential Election Campaign),
# f1_17 (name line under the filing-status row).
_AD = _P1 + "Address_ReadOrder[0]."
_PRESENTATION_MAPPING: dict[str, str] = {
    "f1040x_first_name":        _P1 + "f1_03[0]",  # Your first name and middle initial
    "f1040x_last_name":         _P1 + "f1_04[0]",  # Last name
    "f1040x_ssn":               _P1 + "f1_05[0]",  # Your social security number (9-cell comb)
    "f1040x_spouse_first_name": _P1 + "f1_06[0]",  # Spouse's first name and middle initial
    "f1040x_spouse_last_name":  _P1 + "f1_07[0]",  # Spouse's last name
    "f1040x_spouse_ssn":        _P1 + "f1_08[0]",  # Spouse's social security number (9-cell comb)
    "f1040x_address":           _AD + "f1_09[0]",  # Home address (number and street)
    "f1040x_city":              _AD + "f1_11[0]",  # City, town, or post office
    "f1040x_state":             _AD + "f1_12[0]",  # State
    "f1040x_zip_code":          _AD + "f1_13[0]",  # ZIP code
    "f1040x_filing_status_single": _P1 + "c1_3[0]",  # Single
    "f1040x_filing_status_mfj":    _P1 + "c1_3[1]",  # Married filing jointly
    "f1040x_filing_status_mfs":    _P1 + "c1_3[2]",  # Married filing separately (MFS)
    "f1040x_filing_status_hoh":    _P1 + "c1_3[3]",  # Head of household (HOH)
    "f1040x_filing_status_qss":    _P1 + "c1_3[4]",  # Qualifying surviving spouse (QSS)
}

# On-state of each filing-status box, from its own /_States_.
_CHECKBOX_STATES: dict[str, str] = {
    "f1040x_filing_status_single": "/1",
    "f1040x_filing_status_mfj": "/2",
    "f1040x_filing_status_mfs": "/3",
    "f1040x_filing_status_hoh": "/4",
    "f1040x_filing_status_qss": "/5",
}


class PdfF1040X(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for Form 1040-X (Rev. December 2025). Flat 1:1,
    REVISION-keyed (one current-revision pack serves every amendable federal
    year; the amended year is a page-1 write-in). Marker-probe certified."""

    _FORM_NAME = "Form 1040-X"
    _MAPPINGS: dict[str, dict[str, str]] = {"rev-2025-12": _MAPPING}
    _PRESENTATION_MAPPINGS: dict[str, dict[str, str]] = {
        "rev-2025-12": _PRESENTATION_MAPPING}
    _CHECKBOX_STATES_BY_REVISION: dict[str, dict[str, str]] = {
        "rev-2025-12": _CHECKBOX_STATES}

    @classmethod
    def get_mapping(cls, revision: str) -> dict[str, str]:
        if revision not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} PDF mapping for revision {revision!r}"
            )
        return cls._MAPPINGS[revision]

    @classmethod
    def get_presentation_mapping(cls, revision: str) -> dict[str, str]:
        """The page-1 header cells (``forms.f1040x.presentation_keys``)."""
        cls.get_mapping(revision)  # same unknown-revision refusal
        return cls._PRESENTATION_MAPPINGS[revision]

    @classmethod
    def get_checkbox_states(cls, revision: str) -> dict[str, str]:
        cls.get_mapping(revision)
        return cls._CHECKBOX_STATES_BY_REVISION[revision]


def get_mapping(revision: str) -> dict[str, str]:
    """Module-level accessor the completeness gate calls."""
    return PdfF1040X.get_mapping(revision)
