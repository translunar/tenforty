"""Federal Form 8959 (Additional Medicare Tax) emit declarations, TY2021-2025.

Author "c"'s declaration (the adjudicated base,
/private/tmp/pilot-packet-8959/ADJUDICATION.md): FORM tuple ("federal",
"8959") per the catalog; bindings, kinds, mef elements and descriptions
converged 100% between the two authors. Keys are wordless
(f8959_line_<n>); every key number was checked against the printed line of
the same number on each year's official form (all 24 agree).

Single page, one amount column per line (inner column x 410.4-481.6, outer
x 504-576); every line has exactly one box.

Anchors: explicit only where the box is not on the label's printed row.
  * Wrapped labels whose box overlaps the label row: AFTER_WRAPPED on a
    row-unique phrase of the label row.
  * Filing-status threshold lines 5, 9, 15: the box sits three rows below
    the label, on the "Single, Head of household, ..." row, whose text
    recurs on all three lines. ON_ROW on a row-unique phrase that includes
    the printed line number. DEPENDENCY: lines 5 and 15 anchor on the
    printed statutory threshold "$200,000" followed by the line number;
    a change to the printed amount breaks them.
  * Line 24: three-row label, box beside the third row; AFTER_WRAPPED on
    the second row's phrase (edge gap 0.4).
Every explicit phrase ends on a pdftotext token boundary (the anchor
matcher compares whole tokens) and prints exactly once on its page.

Measured geometry (pdftotext -bbox, widget rects of the official PDFs):
"baseline" = text-row yMax, "box" = widget top-bottom, top-left origin, pt.
Body rows and boxes are identical in all five years (only header rows
move).
"""
from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "8959")

P1, P2, P3, P4, P5 = "Part I", "Part II", "Part III", "Part IV", "Part V"

# Value-only (the sch_c / sch_2 / sch_1 / sch_d precedent, grounded in the
# producer): forms/f8959.compute's return dict sets every one of the 24
# line keys on every Form 8959, zero included, so no scenario can leave one
# absent.
_EMITTED = ("forms/f8959.compute sets this key on every Form 8959, zero "
            "included, so its nothing state is unreachable")


def _line(section, line, description, anchor=None, mef=None):
    return DeclaredLine(line=line, description=description,
                        key=f"f8959_line_{line}", kind="amount",
                        section=section, anchor=anchor, mef_element=mef,
                        single_state="value", single_state_reason=_EMITTED)


def _wrapped(phrase):
    return NearLabel(phrase, LabelRelation.AFTER_WRAPPED)


_G = "AdditionalTaxGrp/"
_AM = _G + "AdditionalMedicareTaxGrp/"
_SE = _G + "AddnlSelfEmploymentTaxGrp/"
_RR = _G + "AddnlRailroadRetirementTaxGrp/"

_LINES = (
    # --- Part I -------------------------------------------------------------
    # Wrapped: label 132.6, box 132-144 (beside wrap row 143.4).
    _line(P1, "1", "Medicare wages and tips from Form W-2, box 5. If you have "
          "more than one",
          _wrapped("Medicare wages and tips from Form W-2, box 5."),
          _AM + "TotalW2MedicareWagesAndTipsAmt"),
    _line(P1, "2", "Unreported tips from Form 4137, line 6",
          mef=_AM + "TotalUnreportedMedicareTipsAmt"),
    _line(P1, "3", "Wages from Form 8919, line 6",
          mef=_AM + "TotalWagesWithNoWithholdingAmt"),
    _line(P1, "4", "Add lines 1 through 3",
          mef=_AM + "TotalMedicareWagesAndTipsAmt"),
    # Threshold: label 191.4; box 216-228 on row 227.4 ("Single, Head of
    # household, ... $200,000 5"); that row's text recurs on lines 9 and 15.
    # Depends on the printed threshold "$200,000".
    _line(P1, "5", "Enter the following amount for your filing status:",
          NearLabel("$200,000 5", LabelRelation.ON_ROW),
          _G + "FilingStatusThresholdCd"),
    _line(P1, "6", "Subtract line 5 from line 4. If zero or less, enter -0-",
          mef=_AM + "WagesTipsSubjToAddlMedcrTaxAmt"),
    # Wrapped: label 252.1, box 252-264 (wrap row 262.9 "Part II 7").
    _line(P1, "7", "Additional Medicare Tax on Medicare wages. Multiply line 6 "
          "by 0.9% (0.009). Enter",
          _wrapped("Additional Medicare Tax on Medicare wages."),
          _AM + "AdditionalMedicareTaxAmt"),
    # --- Part II ------------------------------------------------------------
    # Wrapped: label 288.4, box 288-300 (wrap row 299.4).
    _line(P2, "8", "Self-employment income from Schedule SE (Form 1040), Part "
          "I, line 6. If you",
          _wrapped("Self-employment income from Schedule SE"),
          _SE + "TotalSelfEmploymentIncomeAmt"),
    # Threshold: label 311.4; box 336-348 on row 347.4. On this row
    # pdftotext reads the line number "9" BEFORE the row text (on lines 5
    # and 15 it follows "$200,000"), so the phrase is "9 Single, Head of
    # household," (row-unique: lines 5 and 15 have no "9" before it).
    _line(P2, "9", "Enter the following amount for your filing status:",
          NearLabel("9 Single, Head of household,", LabelRelation.ON_ROW),
          _G + "FilingStatusThresholdCd"),
    _line(P2, "10", "Enter the amount from line 4",
          mef=_AM + "TotalMedicareWagesAndTipsAmt"),
    _line(P2, "11", "Subtract line 10 from line 9. If zero or less, enter -0-",
          mef=_SE + "MedcrWagesTipsBelowThrshldAmt"),
    _line(P2, "12", "Subtract line 11 from line 8. If zero or less, enter -0-",
          mef=_SE + "SEIncomeSubjToAddSETaxAmt"),
    # Wrapped: label 396.1, box 396-408 (wrap row 406.9).
    _line(P2, "13", "Additional Medicare Tax on self-employment income. "
          "Multiply line 12 by 0.9% (0.009).",
          _wrapped("Additional Medicare Tax on self-employment income."),
          _SE + "AddlSelfEmploymentTaxAmt"),
    # --- Part III -----------------------------------------------------------
    # Wrapped: label 432.6, box 432-444 (wrap row 443.4).
    _line(P3, "14", "Railroad retirement (RRTA) compensation and tips from "
          "Form(s) W-2, box 14",
          _wrapped("Railroad retirement (RRTA) compensation and tips"),
          _RR + "TotalRailroadRetirementCompAmt"),
    # Threshold: label 455.4; box 480-492 on row 491.4. Depends on the
    # printed threshold "$200,000".
    _line(P3, "15", "Enter the following amount for your filing status:",
          NearLabel("$200,000 15", LabelRelation.ON_ROW),
          _G + "FilingStatusThresholdCd"),
    _line(P3, "16", "Subtract line 15 from line 14. If zero or less, enter -0-",
          mef=_RR + "RRTCompSubjToAddRRTTaxAmt"),
    # Wrapped: label 516.1, box 516-528 (wrap row 526.9). Case matters: the
    # Part III heading reads "... on Railroad Retirement ...".
    _line(P3, "17", "Additional Medicare Tax on railroad retirement (RRTA) "
          "compensation. Multiply line",
          _wrapped("Additional Medicare Tax on railroad retirement (RRTA) "
                   "compensation."),
          _RR + "AddlRailroadRetirementTaxAmt"),
    # --- Part IV ------------------------------------------------------------
    # Wrapped: label 552.1, box 552-564 (wrap row 562.9).
    _line(P4, "18", "Add lines 7, 13, and 17. Also include this amount on "
          "Schedule 2 (Form 1040), line",
          _wrapped("Add lines 7, 13, and 17."), _G + "TotalAMRRTTaxAmt"),
    # --- Part V -------------------------------------------------------------
    # Wrapped: label 588.6, box 588-600 (wrap row 599.4).
    _line(P5, "19", "Medicare tax withheld from Form W-2, box 6. If you have "
          "more than one Form",
          _wrapped("Medicare tax withheld from Form W-2, box 6."),
          "TotalW2MedicareTaxWithheldAmt"),
    _line(P5, "20", "Enter the amount from line 1",
          mef=_AM + "TotalW2MedicareWagesAndTipsAmt"),
    # Wrapped: label 624.6, box 624-636 (wrap row 635.4).
    _line(P5, "21", "Multiply line 20 by 1.45% (0.0145). This is your regular "
          "Medicare tax",
          _wrapped("Multiply line 20 by 1.45%"), "TotalMedicareTaxAmt"),
    # Wrapped: label 648.6, box 648-660 (wrap row 659.4).
    _line(P5, "22", "Subtract line 21 from line 19. If zero or less, enter "
          "-0-. This is your Additional",
          _wrapped("Subtract line 21 from line 19."),
          "AddnlMedicareTaxWithholdingAmt"),
    # Wrapped: label 672.6, box 672-684 (wrap row 683.4).
    _line(P5, "23", "Additional Medicare Tax withholding on railroad "
          "retirement (RRTA) compensation from",
          _wrapped("Additional Medicare Tax withholding on railroad "
                   "retirement"),
          "TotalW2AddlRRTTaxAmt"),
    # Three-row label (696.8 / 707.6 / 718.4); box 708-720 beside row 3,
    # whose text ("... see instructions) 24") is not row-unique (line 18).
    # Phrase on row 2: edge gap 0.4 (707.6 -> box top 708).
    _line(P5, "24", "Total Additional Medicare Tax withholding. Add lines 22 "
          "and 23. Also include",
          _wrapped("federal income tax withholding on Form 1040,"),
          "AddlMedcrRRTTaxWithholdingAmt"),
)

_NOT_PRINTED = {
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "return', outside the line inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
}

_D2021 = FormDeclaration(form=FORM, key=2021, lines=_LINES,
                         not_printed=_NOT_PRINTED)

# 2022-2025: inventory text identical to 2021 (the truncated inventory texts
# end before every printed wording change). Official changes, none touching
# an anchor phrase or a box:
#  2022: "Qualifying widow(er)" -> "Qualifying surviving spouse" on the
#        threshold rows of 5, 9, 15 (the anchor phrases stop before it).
#  2023: Form 1040-PR references dropped: line 8 wrap row loses its
#        parenthetical; 18's and 24's wrap rows rewrap (24 still three rows,
#        row-2 phrase unchanged).
#  2024, 2025: no body change. Header rows move only.
_D2022 = derive(_D2021, 2022)
_D2023 = derive(_D2022, 2023)
_D2024 = derive(_D2023, 2024)
_D2025 = derive(_D2024, 2025)

DECLARATIONS = {decl.key: decl for decl in
                (_D2021, _D2022, _D2023, _D2024, _D2025)}


# ---------------------------------------------------- witness records
_ALL = (2021, 2022, 2023, 2024, 2025)
_FIRST_ROW = ("the declaration carries the inventory's text for this line, "
              "its first printed row; the stylesheet carries the full "
              "multi-row label, so the word overlap falls below the "
              "cross-check threshold")
_THRESHOLD = ("the stylesheet folds the filing-status threshold table "
              "(\"Married filing jointly $250,000 ...\") into this line's "
              "text; the paper prints it as separate rows below the label, "
              "and the declaration carries the inventory's label row")
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force).
WITNESS_DISCREPANCIES = {
    (P1, "5"): (_ALL, _THRESHOLD),
    (P2, "9"): (_ALL, _THRESHOLD),
    (P3, "15"): (_ALL, _THRESHOLD),
    (P3, "17"): (_ALL, _FIRST_ROW),
    (P5, "23"): (_ALL, _FIRST_ROW),
    (P5, "24"): (_ALL, _FIRST_ROW),
    (P2, "8"): ((2021, 2022), _FIRST_ROW + "; the stylesheet's trailing "
                "\"(Form 1040-PR or Form 1040-SS filers, see "
                "instructions.)\" (dropped in 2023) widens the gap"),
    (P4, "18"): ((2021, 2022), _FIRST_ROW + "; the stylesheet's \"Form "
                 "1040-PR or\" clause (dropped in 2023) widens the gap"),
}
# Witness structure that suppresses no finding: documented so the
# declaration's choices are explained.
WITNESS_NOTES = {
    ("", "5, 9, 15 element"): (_ALL, "the stylesheet witnesses one shared "
                               "FilingStatusThresholdCd (a code) for all "
                               "three threshold lines; the paper prints an "
                               "amount box on each. mef_element set to that "
                               "shared element; kind 'amount' per the "
                               "paper"),
    ("", "10, 20 elements"): (_ALL, "copy lines: 10 reuses line 4's "
                              "element, 20 reuses line 1's"),
    (P2, "8"): ((2023, 2024, 2025), "the stylesheet reads 'Part 1, line 6'; "
                "the paper and inventory read 'Part I, line 6'. Within the "
                "cross-check threshold"),
    (P1, "7"): (_ALL, "the stylesheet reads 'Additional Medicare tax' "
                "(lower-case t); the paper and inventory read 'Additional "
                "Medicare Tax'. Within the cross-check threshold"),
    ("", "24 extra element"): (_ALL, "24 also carries $FormData beside "
                               "AddlMedcrRRTTaxWithholdingAmt"),
}
