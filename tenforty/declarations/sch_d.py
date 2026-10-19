"""Federal Schedule D (Form 1040) emit declarations, TY2021-2025.

Author "c"'s declaration (the adjudicated base,
/private/tmp/pilot-packet-sch_d/ADJUDICATION.md), with the one adoption from
author "d": lines 1a and 8a anchor AFTER_WRAPPED on the same phrase (ON_ROW
measured marginal at 2.15 pt against ROW_PT 2), all years. Bindings and
descriptions converged 100% between the two authors.

Conventions (sch_se / sch_c / sch_e rulings, incl. 2026-10-18):
  * Grid lines 1a/1b/2/3/8a/8b/9/10 print four cells (d), (e), (g), (h).
    The bare inventory line binds the FIRST keyed cell in reading order,
    (d) proceeds; the other keyed cells are composed sub-lines labeled with
    the printed column caption ("1a(e)", "1a(h)"), described by their own
    cell's caption, and carry an inventory exemption (the inventory lists
    one entry per line, not per cell). Column (g) has no key (unmodeled).
  * Columns cannot be anchored: row anchors carry the verbatim gap-blind
    comment; SAME_ROW_RIGHT_OF chains constrain order only.
  * Lines 6/14 (prior-year carryover IN) are unserved; the carryforward keys
    are the amount carried OUT and are not printed (adjudicated option B).
  * The unlabeled QOF question is not declared (no printed identity).

Measured geometry (pdftotext -bbox, widget rects of the official PDFs):
"baseline" = text-row yMax, "box" = widget top-bottom, top-left origin, pt.
"""
import dataclasses

from tenforty.declarations.anchors import (
    FieldRelation,
    LabelRelation,
    NearField,
    NearLabel,
)
from tenforty.declarations.model import DeclaredLine, FormDeclaration, derive

FORM = ("federal", "sch_d")

P1, P2, P3 = "Part I", "Part II", "Part III"

_Q1 = ("sch_e convention ruling 2026-10-18 (Q1), carried to sch_d: composed "
       "sub-line of inventory line {line}; the printed grid cell has no "
       "label of its own")
_COL = "column unconstrained: anchor vocabulary has no column relation."

# Official printed column captions (identical in Parts I and II for the
# keyed columns), used verbatim as composed-sub-line descriptions.
_CAP_E = "(e) Cost (or other basis)"
_CAP_H = ("(h) Gain or (loss) Subtract column (e) from column (d) and combine "
          "the result with column (g)")


def _bound(section, line, description, key, kind="amount", *, mef=None,
           anchor=None, exemption=None):
    return DeclaredLine(line=line, description=description, key=key,
                        kind=kind, section=section, anchor=anchor,
                        mef_element=mef, inventory_exemption=exemption)


def _unserved(section, line, description, meaning, kind="amount"):
    return DeclaredLine(line=line, description=description, key="",
                        kind=kind, section=section, single_state="nothing",
                        single_state_reason=f"unmodeled: {meaning}")


def _grid(section, line, description, stem, group, anchor):
    """A four-column totals row: bare line = (d) proceeds; composed (e)
    basis and (h) gain, each right of the previous keyed cell (order only;
    (g) sits between (e) and (h), unmodeled)."""
    return (
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(section, line, description, f"sch_d_line_{stem}_proceeds",
               mef=f"{group}/TotalProceedsSalesPriceAmt", anchor=anchor),
        _bound(section, f"{line}(e)", _CAP_E, f"sch_d_line_{stem}_basis",
               mef=f"{group}/TotalCostOrOtherBasisAmt",
               anchor=NearField(line, FieldRelation.SAME_ROW_RIGHT_OF),
               exemption=_Q1.format(line=line)),
        _bound(section, f"{line}(h)", _CAP_H, f"sch_d_line_{stem}_gain",
               mef=f"{group}/TotalGainOrLossAmt",
               anchor=NearField(f"{line}(e)", FieldRelation.SAME_ROW_RIGHT_OF),
               exemption=_Q1.format(line=line)),
    )


# Anchor phrases end on a printed token boundary (the evaluator matches
# whole pdftotext tokens): "partnerships,", "below.", "(loss)." carry their
# punctuation (adjudication fixed the row and rationale; measurement
# finalized the string).
# Grid rows: every label wraps; the four boxes sit on the LAST row of the
# label, so each is anchored ON_ROW on a row-unique phrase of that row,
# except 1a and 8a: AFTER_WRAPPED on the same phrase (adjudication 1; ON_ROW
# is marginal there, dy 2.15 pt against ROW_PT 2).
# 2021 measurements: 1a box 264-276 on row 273.9; 1b 288-300 on "Box A
# checked" 298.4; 2 312-324 / 322.4; 3 336-348 / 346.4; 8a 552-564 / 561.9;
# 8b 576-588 / 586.4; 9 600-612 / 610.4; 10 624-636 / 634.4. Columns:
# (d) x 288-359.2, (e) 360-431.2, (g) 432-503.2, (h) 504-576.
_LINES_2021 = (
    # --- Part I -------------------------------------------------------------
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P1, "1a", "Totals for all short-term transactions reported on Form",
           "1a", "TotalSTCGL1099BBssRptNoAdjGrp",
           NearLabel("leave this line blank and go to line 1b",
                     LabelRelation.AFTER_WRAPPED)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P1, "1b",
           "Totals for all transactions reported on Form(s) 8949 with",
           "1b", "TotalSTCGL1099BShowsBasisGrp",
           NearLabel("Box A", LabelRelation.ON_ROW)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P1, "2",
           "Totals for all transactions reported on Form(s) 8949 with",
           "2", "TotalSTCGL1099BNotShowBasisGrp",
           NearLabel("Box B", LabelRelation.ON_ROW)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P1, "3",
           "Totals for all transactions reported on Form(s) 8949 with",
           "3", "TotalSTCGL1099BNotReceivedGrp",
           NearLabel("Box C", LabelRelation.ON_ROW)),
    _unserved(P1, "4",
              "Short-term gain from Form 6252 and short-term gain or (loss) "
              "from Forms 4684, 6781, and 8824",
              "short-term gain or (loss) from Forms 6252, 4684, 6781, 8824"),
    # Wrapped label; box 372-384 spans the label row (372.6) and the wrap
    # row (383.4): field overlaps the phrase row (edge gap 0). The wrap-row
    # phrase "Schedule(s) K-1" is not row-unique (line 12 repeats it).
    _bound(P1, "5",
           "Net short-term gain or (loss) from partnerships, S corporations, "
           "estates, and trusts from",
           "sch_d_line_5_net_short_k1", mef="NetSTGainOrLossFromSchK1Amt",
           anchor=NearLabel("Net short-term gain or (loss) from partnerships,",
                            LabelRelation.AFTER_WRAPPED)),
    # Adjudicated 2026-10-18 (option B): the st carryforward key is the
    # amount carried OUT to next year (not_printed); line 6 is unserved.
    _unserved(P1, "6",
              "Short-term capital loss carryover. Enter the amount, if any, "
              "from line 8 of your Capital Loss Carryover",
              "prior-year capital loss carryover"),
    # Wrapped label; box 420-432 on the wrap row (baseline 430.4).
    _bound(P1, "7",
           "Net short-term capital gain or (loss). Combine lines 1a through 6 "
           "in column (h). If you have any long-",
           "sch_d_line_7_net_short", mef="NetSTCapitalGainOrLossAmt",
           anchor=NearLabel("go to Part II below.", LabelRelation.ON_ROW)),
    # --- Part II ------------------------------------------------------------
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P2, "8a", "Totals for all long-term transactions reported on Form",
           "8a", "TotalLTCGL1099BBssRptNoAdjGrp",
           NearLabel("leave this line blank and go to line 8b",
                     LabelRelation.AFTER_WRAPPED)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P2, "8b",
           "Totals for all transactions reported on Form(s) 8949 with",
           "8b", "TotalLTCGL1099BShowsBasisGrp",
           NearLabel("Box D", LabelRelation.ON_ROW)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P2, "9",
           "Totals for all transactions reported on Form(s) 8949 with",
           "9", "TotalLTCGL1099BNotShowBasisGrp",
           NearLabel("Box E", LabelRelation.ON_ROW)),
    # column unconstrained: anchor vocabulary has no column relation.
    *_grid(P2, "10",
           "Totals for all transactions reported on Form(s) 8949 with",
           "10", "TotalLTCGL1099BNotReceivedGrp",
           NearLabel("Box F", LabelRelation.ON_ROW)),
    _unserved(P2, "11",
              "Gain from Form 4797, Part I; long-term gain from Forms 2439 and "
              "6252; and long-term gain or (loss)",
              "long-term gain or (loss) from Forms 4797, 2439, 6252, 4684, "
              "6781, 8824"),
    _bound(P2, "12",
           "Net long-term gain or (loss) from partnerships, S corporations, "
           "estates, and trusts from Schedule(s) K-1",
           "sch_d_line_12_net_long_k1", mef="NetLTGainOrLossFromSchK1Amt"),
    _bound(P2, "13", "Capital gain distributions. See the instructions",
           "sch_d_line_13_cap_gain_dist", mef="CapitalGainDistributionsAmt"),
    # Adjudicated 2026-10-18 (option B): the lt carryforward key is the
    # amount carried OUT to next year (not_printed); line 14 is unserved.
    _unserved(P2, "14",
              "Long-term capital loss carryover. Enter the amount, if any, "
              "from line 13 of your Capital Loss Carryover",
              "prior-year capital loss carryover"),
    # Wrapped label; box 720-732 overlaps the label row 720.6 (edge gap 0).
    # The wrap-row phrase "on the back" is not row-unique (line 7 repeats it).
    _bound(P2, "15",
           "Net long-term capital gain or (loss). Combine lines 8a through 14 "
           "in column (h). Then, go to Part III",
           "sch_d_line_15_net_long", mef="NetLTCapitalGainOrLossAmt",
           anchor=NearLabel("Net long-term capital gain or (loss).",
                            LabelRelation.AFTER_WRAPPED)),
    # --- Part III (page 2) --------------------------------------------------
    _bound(P3, "16", "Combine lines 7 and 15 and enter the result",
           "sch_d_line_16_total", mef="NetSTAndLTCapitalGainOrLossAmt"),
    _unserved(P3, "17", "Are lines 15 and 16 both gains?",
              "Yes/No: lines 15 and 16 both gains", "checkbox"),
    # Wrapped label; box 252-264 on the wrap row (baseline 261.5 in 2021,
    # 263.4 in 2022+).
    _bound(P3, "18",
           "If you are required to complete the 28% Rate Gain Worksheet (see "
           "instructions), enter the",
           "sch_d_28_rate_gain", mef="RateGainWrkshtAmt",
           anchor=NearLabel("from line 7 of that worksheet",
                            LabelRelation.ON_ROW)),
    # Wrapped label; box 288-300 on the wrap row (297.5 / 299.4).
    _bound(P3, "19",
           "If you are required to complete the Unrecaptured Section 1250 "
           "Gain Worksheet (see",
           "sch_d_unrecap_1250", mef="UnrcptrSect1250GainWrkshtAmt",
           anchor=NearLabel("from line 18 of that worksheet",
                            LabelRelation.ON_ROW)),
    _unserved(P3, "20",
              "Are lines 18 and 19 both zero or blank and are you not filing "
              "Form 4952?",
              "Yes/No: lines 18 and 19 both zero or blank and no Form 4952",
              "checkbox"),
    # Box 420-432 sits below the label row (407.3), beside the bullet list;
    # its own row holds only "21 ( )" (token "21" recurs). Label-above use
    # of AFTER_WRAPPED (Q5a): edge gap 12.7 (phrase 407.3 -> box top 420).
    _bound(P3, "21",
           "If line 16 is a loss, enter here and on Form 1040, 1040-SR, or "
           "1040-NR, line 7, the smaller of:",
           "sch_d_line_21_allowed_loss", mef="AllowableLossAmt",
           anchor=NearLabel("If line 16 is a loss, enter here",
                            LabelRelation.AFTER_WRAPPED)),
    _unserved(P3, "22",
              "Do you have qualified dividends on Form 1040, 1040-SR, or "
              "1040-NR, line 3a?",
              "Yes/No: qualified dividends on Form 1040 line 3a", "checkbox"),
)

_NOT_PRINTED = {
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "return', outside the line inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
    "sch_d_st_capital_loss_carryforward":
        "intermediate: next-year carryforward, not printed on Schedule D",
    "sch_d_lt_capital_loss_carryforward":
        "intermediate: next-year carryforward, not printed on Schedule D",
}

_D2021 = FormDeclaration(form=FORM, key=2021, lines=_LINES_2021,
                         not_printed=_NOT_PRINTED)


def _redescribe(base, key, descriptions, *, anchors=None):
    """Year diff: lines whose inventory text changed are dropped and re-added
    with the new verbatim text; ``anchors`` replaces a line's anchor the same
    way (None = back to the default label-row anchor)."""
    anchors = anchors or {}
    by_id = {ln.line_id: ln for ln in base.lines}
    ids = list(dict.fromkeys([*descriptions, *anchors]))
    new = []
    for lid in ids:
        changes = {}
        if lid in descriptions:
            changes["description"] = descriptions[lid]
        if lid in anchors:
            changes["anchor"] = anchors[lid]
        new.append(dataclasses.replace(by_id[lid], **changes))
    return derive(base, key, drop=ids, add=new)


# 2022: line 20 wording "and are you not" -> "and you are not" (official PDF
# and inventory agree). Layout: line 18/19 wrap rows move down ~2pt; widget
# rects identical to 2021. No anchor consequence.
_D2022 = _redescribe(_D2021, 2022, {
    (P3, "20"): ("Are lines 18 and 19 both zero or blank and you are not "
                 "filing Form 4952?"),
})

# 2023, 2024: no inventory or widget change vs 2022.
_D2023 = derive(_D2022, 2023)
_D2024 = derive(_D2023, 2024)

# 2025: re-layout of page 1.
#  * 1a/8a add "or Form 1099-DA" (6-row labels); grid rows 1a-3 and 8a-10
#    move down 12pt (1a box 276-288 on row 285.3; 8a 564-576 / 573.3). The
#    1a/8a anchor phrases are unchanged and still on the box row.
#  * 1b-3, 8b-10 read "with Box A or Box G checked" etc.; the "Box A".."Box
#    F" phrases stay row-unique and on the box row (310.9 / box 300-312 ...).
#  * Line 5 no longer wraps (label baseline 383.4, box 372-384): the default
#    label row now works, so its explicit anchor is DROPPED.
#  * 14 and 15 move down 12pt; still wrapped, same anchors.
#  * Line 21 refers to Form 1040 "line 7a".
#  * The top QOF Yes/No boxes move right (see WITNESS_DISCREPANCIES).
_D2025 = _redescribe(_D2024, 2025, {
    (P1, "1a"): "Totals for all short-term transactions reported on",
    (P1, "1b"): "Totals for all transactions reported on Form(s) 8949",
    (P1, "2"): "Totals for all transactions reported on Form(s) 8949",
    (P1, "3"): "Totals for all transactions reported on Form(s) 8949",
    (P1, "5"): ("Net short-term gain or (loss) from partnerships, S "
                "corporations, estates, and trusts from Schedule(s) K-1"),
    (P1, "6"): ("Short-term capital loss carryover. Enter the amount, if any, "
                "from line 8 of your Capital Loss"),
    (P1, "7"): ("Net short-term capital gain or (loss). Combine lines 1a "
                "through 6 in column (h). If you have any"),
    (P2, "8b"): "Totals for all transactions reported on Form(s) 8949",
    (P2, "9"): "Totals for all transactions reported on Form(s) 8949",
    (P2, "10"): "Totals for all transactions reported on Form(s) 8949",
    (P2, "14"): ("Long-term capital loss carryover. Enter the amount, if any, "
                 "from line 13 of your Capital Loss"),
    (P3, "21"): ("If line 16 is a loss, enter here and on Form 1040, 1040-SR, "
                 "or 1040-NR, line 7a, the smaller of:"),
}, anchors={
    (P1, "5"): None,
})

DECLARATIONS = {decl.key: decl for decl in
                (_D2021, _D2022, _D2023, _D2024, _D2025)}


# ---------------------------------------------------- witness records
_ALL = (2021, 2022, 2023, 2024, 2025)
_GRID = ((P1, "1a"), (P1, "1b"), (P1, "2"), (P1, "3"),
         (P2, "8a"), (P2, "8b"), (P2, "9"), (P2, "10"))
_FIRST_ROW = ("the declaration carries the inventory's text for this line, "
              "its first printed row; the stylesheet carries the full "
              "multi-row label, so the word overlap falls below the "
              "cross-check threshold")
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force).
WITNESS_DISCREPANCIES = {
    **{(section, f"{line}({col})"): (
        _ALL, "composed grid cell (sch_e Q1 convention): the stylesheet "
        "lists one line per grid row, whose cell elements sit under the "
        "row's group, so the cell id is not a stylesheet line")
       for section, line in _GRID for col in ("e", "h")},
    (P1, "1a"): (_ALL, _FIRST_ROW),
    (P2, "8a"): (_ALL, _FIRST_ROW),
    (P3, "19"): (_ALL, _FIRST_ROW),
    (P1, "7"): ((2025,), _FIRST_ROW + " (the 2025 first row rewraps)"),
}
# Witness structure that suppresses no finding: documented so the
# declaration's choices are explained.
WITNESS_NOTES = {
    ("", "QOF"): (_ALL, "unlabeled printed question absent from both "
                  "witnesses: the top Yes/No 'Did you dispose of any "
                  "investment(s) in a qualified opportunity fund during the "
                  "tax year?' has no printed line label and no output key; "
                  "not declared (QOF ruling 2026-10-18)"),
    (P3, "20"): (_ALL, "the stylesheet keeps 'and are you not' in every "
                 "year; the official PDF and inventory read 'and you are "
                 "not' from 2022. Within the cross-check threshold"),
    ("", "column (g)"): (_ALL, "the stylesheet witnesses "
                         "TotAdjustmentsToGainOrLossAmt on 1b/2/3/8b/9/10 "
                         "(none on 1a/8a); no output key serves column (g); "
                         "the official PDF has a (g) box on all eight rows"),
    ("", "13/22 extras"): (_ALL, "13 and 22 also carry Form8814LiteralCd / "
                           "Form8814Amt (an attached literal, not a printed "
                           "box); 22 carries $FormData"),
    ("", "grid cells"): (_ALL, "the inventory lists one entry per grid line; "
                         "the paper prints four cells (d), (e), (g), (h). "
                         "The keyed (e) and (h) cells are composed sub-lines "
                         "with an inventory exemption"),
}
