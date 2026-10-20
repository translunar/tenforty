"""Federal Schedule E (Form 1040) emit declarations, TY2021-2025.

Composed from two adjudicated author rounds:

* the first round (author "c"'s base, /private/tmp/pilot-packet-sch_e/
  ADJUDICATION.md): Part I property column A, Part II row A and the page's
  totals, with adoptions 1-6 (line 41 = total_income with total_pte
  not_printed "intermediate:"; the composed label "2A(Personal Use Days)"
  spelled as the column prints it; composed descriptions = the cell's own
  caption; grid anchors = SAME_ROW_RIGHT_OF chains);
* the supplementary round (author "e"'s base, /private/tmp/pilot-packet-
  sch_e-supp/ADJUDICATION.md): property columns B and C, Part I rows B/C of
  1a/1b/2, Part II rows B-D, the line A/B No boxes and the line 28 column
  (e) boxes, with adoptions 1-2 (one locator vocabulary; the line-19 family
  takes no MeF element) and its PROPOSED_REBINDS applied: the settled
  unserved lines a produced key serves (5-11, 13-15, 17, 19, 22, 25, and A/B
  from 2022) are bound.

Against the regenerated inventories (extractor-species-2): the property-type
legend no longer holds identities 1-8, so the real lines 2-8 are
inventory-backed and carry no exemption; every inventory-backed description
is the inventory's text verbatim (the description-refresh ruling), line 2
included (its full printed caption is kept in its comment).

Conventions (sch_e convention and supplement shape rulings):
  * Composed sub-lines label a grid cell the inventory does not list:
    property-column cells "<line><column>" (3B, 3C); single-column row cells
    "<line><row>" (1aB); multi-column row cells "<line><row>(<column
    caption>)" (2B(Fair Rental Days), 28B(a)). Each carries an inventory
    exemption.
  * Description locators: ", column B" (grid lines 3-22), "(line <n>,
    property <L>)" (line 2's cells), "(row <L>)" (1a/1b rows, Part II
    rows), "No (line A)" / "No (line B)".
  * Columns cannot be anchored: row anchors carry the gap-blind comment;
    SAME_ROW_RIGHT_OF and NEXT_ROW_BELOW chains constrain order only (audit
    item anchor-column-relation).
  * Lines 22 and 25 sit in preprinted parentheses; the producer stores them
    POSITIVE, so no presentation transform applies (emitted fields print the
    magnitude; line 21 prints signed).

Measured geometry: pdftotext -bbox and widget rects of the official PDFs;
"baseline" = text-row yMax, "box" = widget top-bottom, top-left origin, pt,
unless a comment says the evaluator's y-up coordinates.
"""
from tenforty.declarations.anchors import (
    FieldRelation,
    LabelRelation,
    NearField,
    NearLabel,
)
from tenforty.declarations.model import DeclaredLine, FormDeclaration

FORM = ("federal", "sch_e")
YEARS = (2021, 2022, 2023, 2024, 2025)

P1, P2, P3, P4, P5 = "Part I", "Part II", "Part III", "Part IV", "Part V"

_Q1 = ("sch_e convention ruling 2026-10-18 (Q1): composed sub-line of "
       "inventory line {line}; the printed grid cell has no label of its own")
_SHAPE = ("sch_e supplementary-round shape ruling 2026-10-19 (P1-P3): "
          "property-column grid cells '<line><col>' (3B, 3C); single-column "
          "row cells '<line><row>' (1aB, 1bB); multi-column row cells "
          "'<line><row>(<column caption>)' (2B(Fair Rental Days), 28B(a))")

_SRRO = FieldRelation.SAME_ROW_RIGHT_OF
_NRB = FieldRelation.NEXT_ROW_BELOW


def _q1(line):
    return _Q1.format(line=line)


def _supp(line):
    return _Q1.format(line=line) + "; " + _SHAPE


# Value-only (the sch_c / sch_2 / sch_1 / sch_d precedent, grounded in the
# producer): forms/sch_e_part_ii.merge_with_part_i sets line 41's total on
# every Schedule E, zero included, and the emit site always merges, so its
# nothing state is unreachable. Every other bound key is absent on some
# Schedule E (a column, row or line its return does not use) and is
# two-state.
_EMITTED = ("forms/sch_e_part_ii.merge_with_part_i sets this key on every "
            "Schedule E, zero included, so its nothing state is unreachable")
_VALUE_ONLY = frozenset({"sch_e_line_41_total_income"})


def _bound(section, line, description, key, kind="amount", *, mef=None,
           anchor=None, exemption=None, group=None, selects=None):
    value_only = key in _VALUE_ONLY
    return DeclaredLine(line=line, description=description, key=key,
                        kind=kind, section=section, anchor=anchor,
                        mef_element=mef, inventory_exemption=exemption,
                        group=group, selects=selects,
                        single_state="value" if value_only else None,
                        single_state_reason=_EMITTED if value_only else None)


def _unserved(section, line, description, meaning, kind="amount"):
    return DeclaredLine(line=line, description=description, key="",
                        kind=kind, section=section, single_state="nothing",
                        single_state_reason=f"unmodeled: {meaning}")


# --------------------------------------------------- inventory texts, per year
# Each inventory-backed line's description is its regenerated inventory text,
# verbatim (description-refresh ruling). 2021 first; later years list only
# what changed.
_TEXT = {2021: {
    (P1, "A"): "Did you make any payments",
    (P1, "B"): "If “Yes,” did you or will you",
    (P1, "1a"): "Physical address of each",
    (P1, "1b"): "Type of Property",
    (P1, "2"): "For each rental real estate property",
    (P1, "3"): "Rents received",
    (P1, "4"): "Royalties received",
    (P1, "5"): "Advertising",
    (P1, "6"): "Auto and travel (see instructions)",
    (P1, "7"): "Cleaning and maintenance",
    (P1, "8"): "Commissions.",
    (P1, "9"): "Insurance",
    (P1, "10"): "Legal and other professional",
    (P1, "11"): "Management fees",
    (P1, "12"): "Mortgage interest paid to",
    (P1, "13"): "Other interest.",
    (P1, "14"): "Repairs.",
    (P1, "15"): "Supplies",
    (P1, "16"): "Taxes",
    (P1, "17"): "Utilities",
    (P1, "18"): "Depreciation expense or",
    (P1, "19"): "Other (list) ▶",
    (P1, "20"): "Total expenses. Add lines",
    (P1, "21"): "Subtract line 20 from line",
    (P1, "22"): "Deductible rental real estate",
    (P1, "23a"): "Total of all amounts reported",
    (P1, "23b"): "Total of all amounts reported",
    (P1, "23c"): "Total of all amounts reported",
    (P1, "23d"): "Total of all amounts reported",
    (P1, "23e"): "Total of all amounts reported",
    (P1, "24"): "Income. Add positive amounts",
    (P1, "25"): "Losses. Add royalty losses",
    (P1, "26"): "Total rental real estate",
    (P2, "27"): ("Are you reporting any loss not allowed in a prior year due "
                 "to the at-risk"),
    (P2, "28"): "(a) Name",
    (P2, "29a"): "Totals",
    (P2, "29b"): "Totals",
    (P2, "30"): "Add columns (h) and (k) of line 29a.",
    (P2, "31"): "Add columns (g), (i), and (j) of line 29b.",
    (P2, "32"): ("Total partnership and S corporation income or (loss). "
                 "Combine lines"),
    (P3, "33"): "(a) Name",
    (P3, "34a"): "Totals",
    (P3, "34b"): "Totals",
    (P3, "35"): "Add columns (d) and (f) of line 34a",
    (P3, "36"): "Add columns (c) and (e) of line 34b",
    (P3, "37"): ("Total estate and trust income or (loss). Combine lines 35 "
                 "and 36"),
    (P4, "38"): "(a) Name (b) Employer identification Schedules Q, line",
    (P4, "39"): ("Combine columns (d) and (e) only. Enter the result here and "
                 "include in the"),
    (P5, "40"): ("Net farm rental income or (loss) from Form 4835. Also, "
                 "complete line 42"),
    (P5, "41"): ("Total income or (loss). Combine lines 26, 32, 37, 39, and "
                 "40. Enter the result here and on Schedule"),
    (P5, "42"): ("Reconciliation of farming and fishing income. Enter your "
                 "gross"),
    (P5, "43"): ("Reconciliation for real estate professionals. If you were a "
                 "real estate professional"),
}}
# 2022: the form's rewording and relayout (inventory and paper agree).
_TEXT[2022] = {**_TEXT[2021],
    (P1, "A"): "Did you make any payments in 2022 that would require you to",
    (P1, "B"): "If “Yes,” did you or will you file required Form(s) 1099?",
    (P1, "1a"): ("Physical address of each property (street, city, state, ZIP "
                 "code)"),
    (P1, "8"): "Commissions",
    (P1, "10"): "Legal and other professional fees",
    (P1, "12"): "Mortgage interest paid to banks, etc. (see instructions)",
    (P1, "13"): "Other interest",
    (P1, "14"): "Repairs",
    (P1, "18"): "Depreciation expense or depletion",
    (P1, "19"): "Other (list)",
    (P1, "20"): "Total expenses. Add lines 5 through 19",
    (P1, "21"): ("Subtract line 20 from line 3 (rents) and/or 4 (royalties). "
                 "If"),
    (P1, "22"): "Deductible rental real estate loss after limitation, if any,",
    (P1, "23a"): ("Total of all amounts reported on line 3 for all rental "
                  "properties"),
    (P1, "23b"): ("Total of all amounts reported on line 4 for all royalty "
                  "properties"),
    (P1, "23c"): "Total of all amounts reported on line 12 for all properties",
    (P1, "23d"): "Total of all amounts reported on line 18 for all properties",
    (P1, "23e"): "Total of all amounts reported on line 20 for all properties",
    (P1, "24"): "Income. Add positive amounts shown on line 21. Do not include",
    (P1, "25"): "Losses. Add royalty losses from line 21 and rental real estate",
    (P1, "26"): ("Total rental real estate and royalty income or (loss). "
                 "Combine"),
    (P2, "27"): ("Are you reporting any loss not allowed in a prior year due "
                 "to the at-risk or"),
    (P2, "28"): "(b) Enter P for (c) Check if",
    (P2, "30"): "Add columns (h) and (k) of line 29a",
    (P2, "32"): ("Total partnership and S corporation income or (loss). "
                 "Combine lines 30"),
    (P3, "33"): "",
    (P4, "38"): "(c) Excess inclusion",
    (P4, "39"): ("Combine columns (d) and (e) only. Enter the result here and "
                 "include in the total"),
    (P5, "40"): ("Net farm rental income or (loss) from Form 4835. Also, "
                 "complete line 42 below"),
    (P5, "41"): ("Total income or (loss). Combine lines 26, 32, 37, 39, and "
                 "40. Enter the result"),
    (P5, "43"): ("Reconciliation for real estate professionals. If you were a "
                 "real estate"),
}
_TEXT[2023] = {**_TEXT[2022],
    (P1, "A"): "Did you make any payments in 2023 that would require you to",
    (P1, "25"): ("Losses. Add royalty losses from line 21 and rental real "
                 "estate losses"),
    (P2, "31"): "Add columns (g), (i), and (j) of line 29b",
}
_TEXT[2024] = {**_TEXT[2023],
    (P1, "A"): "Did you make any payments in 2024 that would require you to",
}
_TEXT[2025] = {**_TEXT[2024],
    (P1, "A"): "Did you make any payments in 2025 that would require you to",
}


# ------------------------------------------------------ Part I property grid
# Lines 3-22: one row per line, property columns A | B | C left to right (x
# 316.8 | 403.2 | 489.6 every year; line 22 320.8 | 407.2 | 493.6, inside
# printed parentheses). (line, key suffix, MeF element.) Column A is the
# bare line; B and C are composed cells chained SAME_ROW_RIGHT_OF.
_GRID = (
    ("3", "rents", "RentsReceivedAmt"),
    ("5", "advertising", "AdvertisingAmt"),
    ("6", "auto_and_travel", "AutoAndTravelAmt"),
    ("7", "cleaning_and_maintenance", "CleaningAndMaintenanceAmt"),
    ("8", "commissions", "CommissionsAmt"),
    ("9", "insurance", "InsuranceAmt"),
    ("10", "legal_and_professional_fees", "LegalAndOtherProfFeesAmt"),
    ("11", "management_fees", "ManagementFeesAmt"),
    ("12", "mortgage_interest", "MortgageInterestPaidBanksAmt"),
    ("13", "other_interest", "MortgageInterestPaidOtherAmt"),
    ("14", "repairs", "RepairsAmt"),
    ("15", "supplies", "SuppliesAmt"),
    ("16", "taxes", "TaxesAmt"),
    ("17", "utilities", "UtilitiesAmt"),
    ("18", "depreciation", "DeprecExpenseOrDepletionAmt"),
    # The stylesheet carries line 19 as the repeating OtherExpenseDetail
    # group (Desc + Amt children); a two-child group container is not a line
    # element, so the line-19 family takes no MeF element (supplement
    # adjudication 2).
    ("19", "other_expenses", None),
    ("20", "total_expenses", "TotalExpensesAmt"),
    ("21", "income_loss", "NetRentalIncomeOrLossAmt"),
    ("22", "deductible_loss", "DedRentalRealEstateLossAmt"),
)

# Explicit anchors of column-A grid lines (every other grid line sits on its
# label row, the default anchor).
_GRID_ANCHOR = {
    # Line 3: the row token "3" recurs (line 21's text), so the line's own
    # text anchors (2021: baseline 323.3, column-A box 312-324).
    "3": NearLabel("Rents received", LabelRelation.ON_ROW),
    # Wrapped label (3 rows): the amount box is on the third row, beside the
    # right-hand "21" (2021: label baseline 553.3, box 564-576, phrase row
    # baseline 575.3); "21" also recurs on line 25's row.
    "21": NearLabel("file Form 6198", LabelRelation.ON_ROW),
    # Line 22's box sits on the label's SECOND row, beside "on Form 8582"
    # (2021: label baseline 588.3, box 588-600). "Form 8582" prints once on
    # page 1 every year. Measured against the evaluator (y-up): the phrase
    # overlaps the column-A box by 10.7 pt (2021: 192.6-203.3 vs 192.0-204.0)
    # and 10.4 pt (2022+: 163.6-174.3 vs 162.0-174.0), so ON_ROW is not
    # marginal; AFTER_WRAPPED off the first row would clear by only 0.4 pt.
    "22": NearLabel("Form 8582", LabelRelation.ON_ROW),
}


def _grid_lines(text):
    out = []
    for line, suffix, mef in _GRID:
        # column unconstrained: anchor vocabulary has no column relation.
        out.append(_bound(P1, line, text[(P1, line)],
                          f"sch_e_property_a_{suffix}", mef=mef,
                          anchor=_GRID_ANCHOR.get(line)))
        left = line
        for col in ("B", "C"):
            out.append(_bound(
                P1, f"{line}{col}", f"{text[(P1, line)]}, column {col}",
                f"sch_e_property_{col.lower()}_{suffix}", mef=mef,
                anchor=NearField(left, _SRRO), exemption=_supp(line)))
            left = f"{line}{col}"
    return out


# -------------------------------------------------- Part I header rows 1a-2
# Rows are 12pt apart and abut (2021 boxes A 168-180, B 180-192, C 192-204
# for 1a; 228/240/252/264 for 1b and 2. 2022+: 1a 180/192/204/216; 1b, 2
# 240/252/264/276). Each row's first cell is NEXT_ROW_BELOW the same column
# one row up (gap 0.0, column x0 identical); the row tokens "B"/"C" recur on
# page 1, so no label anchor.
def _header_rows(text):
    out = [
        # Off-row: the address box sits on the property-A row below the
        # label (2021: label baseline 167.4, box 168-180). AFTER_WRAPPED as
        # "field on the row below the phrase" (Q5a ruling).
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(P1, "1a", text[(P1, "1a")], "sch_e_property_a_address",
               "text", mef="PropertyUSAddress",
               anchor=NearLabel("Physical address of each property",
                                LabelRelation.AFTER_WRAPPED)),
        # Wrapped label "1b Type of Property / (from list below)"; the code
        # box is on the property-A row after the wrap (2021: wrap row
        # baseline 224.5, box 228-240). "Type of Property" itself is not
        # row-unique (the legend heading "Type of Property:").
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(P1, "1b", text[(P1, "1b")], "sch_e_property_a_type_code",
               "text",
               anchor=NearLabel("(from list below)",
                                LabelRelation.AFTER_WRAPPED)),
        # Line 2's printed caption, in full (provenance for its description,
        # which is the inventory's row text, "For each rental real estate
        # property"): "For each rental real estate property listed above,
        # report the number of fair rental and personal use days. Check the
        # QJV box only if you meet the requirements to file as a qualified
        # joint venture. See instructions."
        # Three cells per property row (Fair Rental Days, Personal Use Days,
        # QJV), none labeled; the fair-rental box is on the type-code box's
        # row, to its right (2021 both 228-240). kind="amount": numeric
        # rendering of an integer day count (Q4 ruling).
        _bound(P1, "2", text[(P1, "2")],
               "sch_e_property_a_fair_rental_days", mef="FairRentalDaysCnt",
               anchor=NearField("1b", _SRRO)),
        _bound(P1, "2A(Personal Use Days)",
               "Personal Use Days (line 2, property A)",
               "sch_e_property_a_personal_use_days", mef="PersonalUseDaysCnt",
               anchor=NearField("2", _SRRO), exemption=_q1("2")),
    ]
    prev_1a, prev_1b = "1a", "1b"
    for row in ("B", "C"):
        r = row.lower()
        # column unconstrained: anchor vocabulary has no column relation.
        out += [
            _bound(P1, f"1a{row}",
                   "Physical address of each property (street, city, state, "
                   f"ZIP code) (row {row})",
                   f"sch_e_property_{r}_address", "text",
                   mef="PropertyUSAddress", anchor=NearField(prev_1a, _NRB),
                   exemption=_supp("1a")),
            # 1b's code has no single stylesheet element (see WITNESS_NOTES).
            _bound(P1, f"1b{row}",
                   f"Type of Property (from list below) (row {row})",
                   f"sch_e_property_{r}_type_code", "text",
                   anchor=NearField(prev_1b, _NRB), exemption=_supp("1b")),
            # Fair-rental box right of the row's type-code box (2021 x 374.4
            # vs 151.2; 2022+ 381.6 vs 136.8), as "2" <- "1b".
            _bound(P1, f"2{row}(Fair Rental Days)",
                   f"Fair Rental Days (line 2, property {row})",
                   f"sch_e_property_{r}_fair_rental_days",
                   mef="FairRentalDaysCnt",
                   anchor=NearField(f"1b{row}", _SRRO), exemption=_supp("2")),
            _bound(P1, f"2{row}(Personal Use Days)",
                   f"Personal Use Days (line 2, property {row})",
                   f"sch_e_property_{r}_personal_use_days",
                   mef="PersonalUseDaysCnt",
                   anchor=NearField(f"2{row}(Fair Rental Days)", _SRRO),
                   exemption=_supp("2")),
        ]
        prev_1a, prev_1b = f"1a{row}", f"1b{row}"
    return out


# ------------------------------------------------------- Part I lines A, B
# 2022-2025: one key per line drives a Yes/No pair (option group). The bare
# line is the Yes box (first keyed cell in reading order, on the label row:
# the default anchor; 2022+ baselines 149.4 / 160.9 vs box bottoms 148 /
# 159.8); the No box is a composed sub-line of the same key. The fill writes
# only the CHOSEN box with its export state (Yes "/1", No "/2"); an unstated
# answer writes nothing, so both lines are two-state. "Yes", "No" and "Yes
# No" each print on both the A and B rows (token-exact), so no caption is
# row-unique: the No box is SAME_ROW_RIGHT_OF its Yes box (gap 28.0, dy 0.0)
# -- the accepted convention exception (supplement ruling Q-d).
# 2021: the template is outside the A/B fill table (OUT_OF_SCOPE), so 2021's
# A/B stay unserved.
_YESNO = (("A", "sch_e_payments_requiring_1099s",
           "PaymentRqrFilingForm1099Ind",
           "Yes/No: payments in the year requiring Form(s) 1099"),
          ("B", "sch_e_filed_required_1099s", "RequiredForms1099FiledInd",
           "Yes/No: did or will file required Form(s) 1099"))


def _answer_lines(year, text):
    out = []
    for line, key, mef, meaning in _YESNO:
        if year < 2022:
            out.append(_unserved(P1, line, text[(P1, line)], meaning,
                                 "checkbox"))
            continue
        out += [
            _bound(P1, line, text[(P1, line)], key, "checkbox", mef=mef,
                   group=line, selects="/1"),
            _bound(P1, f"{line}(No)", f"No (line {line})", key, "checkbox",
                   mef=mef, anchor=NearField(line, _SRRO),
                   exemption=_supp(line), group=line, selects="/2"),
        ]
    return out


# ------------------------------------------------------- Part I page totals
def _totals(text):
    return [
        _bound(P1, "23a", text[(P1, "23a")], "sch_e_line_23a_total_rents",
               mef="TotAllPaymentsAllRentalPropAmt"),
        _unserved(P1, "23b", text[(P1, "23b")],
                  "total of line 4 royalties for all royalty properties"),
        _bound(P1, "23c", text[(P1, "23c")],
               "sch_e_line_23c_total_mortgage_interest",
               mef="TotalMortgageInterestPaidAmt"),
        _bound(P1, "23d", text[(P1, "23d")],
               "sch_e_line_23d_total_depreciation",
               mef="TotalDepreciationAmt"),
        _bound(P1, "23e", text[(P1, "23e")], "sch_e_line_23e_total_expenses",
               mef="TotalAllPropTotalExpensesAmt"),
        _bound(P1, "24", text[(P1, "24")], "sch_e_line_24_income",
               mef="IncomeAmt"),
        # In preprinted parentheses; stored positive (no transform).
        _bound(P1, "25", text[(P1, "25")], "sch_e_line_25_losses",
               mef="LossesAmt"),
        # Wrapped label (3 rows); box on the third row (2021: label
        # baseline 697.3, box 708-720, phrase row baseline 719.3).
        _bound(P1, "26", text[(P1, "26")], "sch_e_line_26_total",
               mef="TotalIncomeOrLossAmt",
               anchor=NearLabel("Otherwise, include this amount",
                                LabelRelation.ON_ROW)),
    ]


# -------------------------------------------------------------- Part II
# Line 28 is a two-block grid (rows A-D x columns (a)-(f), then rows A-D x
# columns (g)-(k)). Row A's column (a) is the bare line; every other keyed
# cell is a composed sub-line. Rows B-D: each row's column (a) and (g) cell
# is NEXT_ROW_BELOW the same column one row up (gap 0.0, x0 identical); the
# rest chain SAME_ROW_RIGHT_OF as row A ((c), (f) and (j) are unmodeled
# cells the chain skips). Row tokens "A".."D" recur on page 2: no label
# anchor. (column letter, key suffix, kind, MeF element.)
_P2_CELLS = (
    ("a", "name", "text", "PartnershipOrSCorporationNm"),
    ("b", "entity_code", "text", "PartnershipSCorpCd"),
    ("d", "ein", "text", "PartnershipOrSCorpEIN"),
    ("g", "passive_loss", "amount", "PassiveLossAllowedAmt"),
    ("h", "passive_income", "amount", "BusinessPassiveIncomeAmt"),
    ("i", "nonpassive_loss", "amount", "NonpassiveLossAmt"),
    ("k", "nonpassive_income", "amount", "NonpassiveIncomeAmt"),
)
_P2_CAPTION = {
    "a": "(a) Name",
    "b": "(b) Enter P for partnership; S for S corporation",
    "d": "(d) Employer identification number",
    "g": "(g) Passive loss allowed (attach Form 8582 if required)",
    "h": "(h) Passive income from Schedule K-1",
    "i": "(i) Nonpassive loss allowed (see Schedule K-1)",
    "k": "(k) Nonpassive income from Schedule K-1",
}


def _row_a(text):
    return [
        # Row A sits below the wrapped column-header block, off the "28"
        # label row (2021: header last row baseline 190.7, row-A box 192-204;
        # edge-to-edge 1.3 2021 / 0.1 2022+).
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(P2, "28", text[(P2, "28")], "sch_e_part_ii_row_a_name",
               "text", mef="PartnershipOrSCorporationNm",
               anchor=NearLabel("for S corporation",
                                LabelRelation.AFTER_WRAPPED)),
        _bound(P2, "28A(b)", f"{_P2_CAPTION['b']} (row A)",
               "sch_e_part_ii_row_a_entity_code", "text",
               mef="PartnershipSCorpCd", anchor=NearField("28", _SRRO),
               exemption=_q1("28")),
        _bound(P2, "28A(d)", f"{_P2_CAPTION['d']} (row A)",
               "sch_e_part_ii_row_a_ein", "text",
               mef="PartnershipOrSCorpEIN",
               anchor=NearField("28A(b)", _SRRO), exemption=_q1("28")),
        # Second block, row A (2021: header last row baseline 271.3, row-A
        # box 276-288; edge-to-edge 4.7 2021 / 1.3 2022+). "(attach Form
        # 8582 if required)" is not row-unique; "deduction from Form 4562"
        # is.
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(P2, "28A(g)", f"{_P2_CAPTION['g']} (row A)",
               "sch_e_part_ii_row_a_passive_loss",
               mef="PassiveLossAllowedAmt",
               anchor=NearLabel("deduction from Form 4562",
                                LabelRelation.AFTER_WRAPPED),
               exemption=_q1("28")),
        _bound(P2, "28A(h)", f"{_P2_CAPTION['h']} (row A)",
               "sch_e_part_ii_row_a_passive_income",
               mef="BusinessPassiveIncomeAmt",
               anchor=NearField("28A(g)", _SRRO), exemption=_q1("28")),
        _bound(P2, "28A(i)", f"{_P2_CAPTION['i']} (row A)",
               "sch_e_part_ii_row_a_nonpassive_loss",
               mef="NonpassiveLossAmt",
               anchor=NearField("28A(h)", _SRRO), exemption=_q1("28")),
        # (k) is two boxes right of (i); (j) Section 179 (unmodeled) sits
        # between.
        _bound(P2, "28A(k)", f"{_P2_CAPTION['k']} (row A)",
               "sch_e_part_ii_row_a_nonpassive_income",
               mef="NonpassiveIncomeAmt",
               anchor=NearField("28A(i)", _SRRO), exemption=_q1("28")),
    ]


def _rows_b_to_d():
    # column unconstrained: anchor vocabulary has no column relation.
    above = {"a": "28", "b": "28A(b)", "d": "28A(d)", "g": "28A(g)",
             "h": "28A(h)", "i": "28A(i)", "k": "28A(k)"}
    out = []
    for row in ("B", "C", "D"):
        left = None
        for col, suffix, kind, mef in _P2_CELLS:
            label = f"28{row}({col})"
            anchor = (NearField(above[col], _NRB) if col in ("a", "g")
                      else NearField(left, _SRRO))
            out.append(_bound(
                P2, label, f"{_P2_CAPTION[col]} (row {row})",
                f"sch_e_part_ii_row_{row.lower()}_{suffix}", kind, mef=mef,
                anchor=anchor, exemption=_supp("28")))
            above[col] = left = label
    return out


# Line 28 column (e) "Check if basis computation is required", rows A-D,
# 2022-2025 (the fill table's years: a 2021 return needing the box REFUSES
# the Schedule E emit, see OUT_OF_SCOPE). The 8pt checkbox sits inside the
# 12pt row, its bottom exactly ROW_PT (2.0) above the row's text boxes, so a
# SAME_ROW_RIGHT_OF (d) chain sits on the tolerance boundary (ruling Q-e).
# Row A anchors under its own column caption's last row "is required"
# (token-exact, once on page 2 every year; measured against the evaluator,
# y-up: phrase 606.0-614.2 over box 596.0-604.0, gap 2.0); rows B-D are
# NEXT_ROW_BELOW the (e) box one row up (gap 4.0, x0 489.2). Drift record:
# the row-B (e) box is 14.1 pt from the phrase (2022+), 0.1 beyond WRAP_PT;
# the checker verifies the MAPPED field against the anchor, it does not
# select among candidate boxes. On-state "/1" (single box, no group).
def _basis_boxes(year):
    if year < 2022:
        return []
    out, prev = [], None
    for row in ("A", "B", "C", "D"):
        label = f"28{row}(e)"
        anchor = (NearLabel("is required", LabelRelation.AFTER_WRAPPED)
                  if prev is None else NearField(prev, _NRB))
        out.append(_bound(
            P2, label,
            f"(e) Check if basis computation is required (row {row})",
            f"sch_e_part_ii_row_{row.lower()}_basis_computation_box",
            "checkbox", mef="BasisComputationRequiredInd", anchor=anchor,
            exemption=_supp("28")))
        prev = label
    return out


def _part_ii_totals(text):
    return [
        # 29a/29b: five column boxes on the label row; the bare line is the
        # first produced column, the other produced column a composed cell.
        # column unconstrained: anchor vocabulary has no column relation.
        _bound(P2, "29a", text[(P2, "29a")],
               "sch_e_line_29a_total_passive_income",
               mef="TotalPassiveIncomeAmt"),
        _bound(P2, "29a(k)", "Totals, column (k) Nonpassive income",
               "sch_e_line_29a_total_nonpassive_income",
               mef="BusTotalNonpassiveIncomeAmt",
               anchor=NearField("29a", _SRRO), exemption=_q1("29a")),
        # 29b's row prints only a bare "b" and "Totals" (4x on page 2), and
        # "29a" prints twice 2022+, so the box anchors on line 30's
        # print-once caption one row below (ROW_ABOVE_LABEL, team-lead
        # ruling 2026-10-19): abut 0.9 pt every year (29a row 12.9), box x0
        # 100.8 (2021) / 93.6 under the phrase's [64.8, 159.7] (next column
        # 180.0 / 187.2). It selects 29b's column (g) box, unlike "Totals".
        _bound(P2, "29b", text[(P2, "29b")],
               "sch_e_line_29b_total_passive_loss",
               mef="TotalPassiveLossAllowedAmt",
               anchor=NearLabel("Add columns (h) and (k)",
                                LabelRelation.ROW_ABOVE_LABEL)),
        _bound(P2, "29b(i)", "Totals, column (i) Nonpassive loss allowed",
               "sch_e_line_29b_total_nonpassive_loss",
               mef="TotalNonpassiveLossAmt",
               anchor=NearField("29b", _SRRO), exemption=_q1("29b")),
        _bound(P2, "30", text[(P2, "30")], "sch_e_line_30_total_income",
               mef="TotalPrtshpSCorpIncomeAmt"),
        _bound(P2, "31", text[(P2, "31")], "sch_e_line_31_total_loss",
               mef="TotalPrtshpSCorpLossAmt"),
        _bound(P2, "32", text[(P2, "32")],
               "sch_e_line_32_total_partnership_scorp",
               mef="NetPrtshpSCorpIncomeOrLossAmt"),
    ]


def _parts_iii_to_v(year, text):
    return [
        _unserved(P3, "33", text[(P3, "33")],
                  "estate/trust rows A-B: name, EIN, columns (c)-(f)",
                  "text"),
        _unserved(P3, "34a", text[(P3, "34a")],
                  "estate/trust totals, columns (d) and (f)"),
        _unserved(P3, "34b", text[(P3, "34b")],
                  "estate/trust totals, columns (c) and (e)"),
        _unserved(P3, "35", text[(P3, "35")], "estate/trust income total"),
        _unserved(P3, "36", text[(P3, "36")], "estate/trust loss total"),
        _bound(P3, "37", text[(P3, "37")],
               "sch_e_line_37_total_estate_trust",
               mef="TotEstateAndTrustIncOrLossAmt"),
        _unserved(P4, "38", text[(P4, "38")],
                  "REMIC row: name, EIN, columns (c)-(e)", "text"),
        _unserved(P4, "39", text[(P4, "39")], "REMIC income total"),
        _unserved(P5, "40", text[(P5, "40")],
                  "net farm rental income or (loss) from Form 4835"),
        # Adjudicated (first round, item 1): line 41 is total_income;
        # total_pte is not printed. 2021: single-row label, box on the label
        # row. 2022+: the label wraps to two rows and its box (636-648) sits
        # on the second (baseline 646.9).
        _bound(P5, "41", text[(P5, "41")], "sch_e_line_41_total_income",
               mef="TotalSuppIncomeOrLossAmt",
               anchor=(None if year == 2021 else
                       NearLabel("(Form 1040), line 5",
                                 LabelRelation.ON_ROW))),
        _unserved(P5, "42", text[(P5, "42")],
                  "gross farming and fishing income reconciliation"),
        _unserved(P5, "43", text[(P5, "43")],
                  "real estate professional reconciliation"),
    ]


_NOT_PRINTED = {
    "taxpayer_name": ("presentation-only: page 1 header 'Name(s) shown on "
                      "return', outside the line inventory"),
    "taxpayer_ssn": ("presentation-only: page 1 header 'Your social "
                     "security number', outside the line inventory"),
    "taxpayer_name_page2": ("presentation-only: page 2 header 'Name(s) "
                            "shown on return', outside the line inventory"),
    "taxpayer_ssn_page2": ("presentation-only: page 2 header 'Your social "
                           "security number', outside the line inventory"),
    "sch_e_line_41_total_pte": (
        "intermediate: Part II's pass-through total feeding line 41's "
        "total_income; Schedule E prints no separate cell for it "
        "(first-round adjudication 1)"),
    # Consumed by the orchestrator's Schedule E fill to choose which line-28
    # column (e) box to check; the box itself is bound by 28A-D(e).
    **{f"sch_e_part_ii_row_{r}_basis_computation_required": (
        f"intermediate: selects the row {r.upper()} line-28 column (e) "
        f"basis-computation box (bound by 28{r.upper()}(e) 2022-2025; a "
        "2021 return that sets it refuses, see OUT_OF_SCOPE); the flag "
        "itself prints nowhere")
       for r in "abcd"},
}


def _declaration(year):
    text = _TEXT[year]
    lines = (
        *_answer_lines(year, text),
        *_header_rows(text),
        *[ln for ln in _grid_lines(text) if ln.line in ("3", "3B", "3C")],
        _unserved(P1, "4", text[(P1, "4")],
                  "royalties received (per property)"),
        *[ln for ln in _grid_lines(text) if ln.line not in ("3", "3B", "3C")],
        *_totals(text),
        _bound(P2, "27", text[(P2, "27")], "sch_e_line_27_no", "checkbox",
               mef="PriorYearsLossesInd",
               # Wrapped label (3 rows); the Yes/No boxes share the third row
               # (2021: label baseline 145.2, boxes 158-166). The No box sits
               # immediately left of the word "No" (gap 6.4 2021 / 3.8
               # 2022+), which is row-unique on page 2 as a whole token.
               anchor=NearLabel("No", LabelRelation.LEFT_OF)),
        *_row_a(text),
        *_rows_b_to_d(),
        *_basis_boxes(year),
        *_part_ii_totals(text),
        *_parts_iii_to_v(year, text),
    )
    return FormDeclaration(form=FORM, key=year, lines=tuple(lines),
                           not_printed=_NOT_PRINTED)


DECLARATIONS = {year: _declaration(year) for year in YEARS}


# -------------------------------------------------------- scope and notes
# Keys a year's fill table does not cover (supplement adjudication 3: the
# single 2021 carrier). The two shapes differ: an unstated A/B answer prints
# nothing, but a 2021 return that needs a basis box REFUSES the whole
# Schedule E emit (fail-closed).
OUT_OF_SCOPE = {
    2021: {
        **{key: ("2021 template outside the line A/B fill table (2022-2025 "
                 "only, the TY2022 feature floor): a stated 2021 answer is "
                 "refused at load, so 2021 lines A/B stay unserved")
           for _, key, _, _ in _YESNO},
        **{f"sch_e_part_ii_row_{r}_basis_computation_box": (
            "2021 template outside the line-28 column (e) fill table "
            "(2022-2025 only): a 2021 return that needs the box (an S "
            "corporation K-1 loss) REFUSES the whole Schedule E emit "
            "(fail-closed); no 2021 28(e) line declared")
           for r in "abcd"},
    },
}

# Inventory text the convention keeps verbatim although it is a fragment of
# the printed line (grid headers).
INVENTORY_NOTES = {
    (P2, "28"): (YEARS, "28 is a grid header: columns (a)-(f), rows A-D, "
                 "then columns (g)-(k), rows A-D; the inventory's row text "
                 "is a header fragment ('(a) Name' 2021, '(b) Enter P for (c) "
                 "Check if' 2022+)"),
    (P3, "33"): ((2022, 2023, 2024, 2025), "the inventory row text is empty; "
                 "33 prints '(a) Name / (b) Employer identification "
                 "number'"),
    (P4, "38"): (YEARS, "38 is a one-row grid, columns (a)-(e); the "
                 "inventory row text is column-header fragments"),
}

# Witness structure that suppresses no finding: documented so the
# declaration's choices are explained.
WITNESS_NOTES = {
    (P1, "1a-22 grid"): (YEARS, "the stylesheet has no per-line labels for "
                         "the property grid; all its elements "
                         "(RentsReceivedAmt ... DedRentalRealEstateLossAmt) "
                         "are lumped under label 'B'"),
    (P1, "1b"): (YEARS, "the property-type code has no single stylesheet "
                 "element (PropertyRealEstAndRoyaltyGroup/PropertyDesc "
                 "carries the type, OtherPropertyTypeDesc the 'Other "
                 "(describe)' text); mef None on 1b, 1bB, 1bC"),
    (P1, "19 description"): (YEARS, "line 19 prints a description box right "
                             "of 'Other (list)' besides the three amount "
                             "cells; no key serves it"),
    (P1, "22/25 parentheses"): (YEARS, "every line-22 cell and line 25's "
                                "cell print inside parentheses; the "
                                "producer stores these losses POSITIVE, so "
                                "no presentation transform (emitted fields "
                                "print the magnitude)"),
    (P2, "28/33/38 grids"): (YEARS, "grid rows have no stylesheet labels; "
                             "their elements are lumped under the preceding "
                             "label (27, 32, 37 respectively)"),
    (P2, "32"): (YEARS, "label 32 carries the Part III row elements "
                 "(EstateAndTrustGroup ... OtherIncomeAmt); the key choice "
                 "for 32 is its own total (NetPrtshpSCorpIncomeOrLossAmt)"),
    ("", "b..e labels"): (YEARS, "the stylesheet labels 23b-23e, 29b, 34b "
                          "bare 'b'..'e' (composed per convention 4)"),
    (P2, "29a/29b shaded cells"): (
        (2022, 2023, 2024, 2025),
        "pdf_sch_e maps four 29a/29b cross keys (29a passive/nonpassive "
        "loss, 29b passive/nonpassive income) that the producer never emits; "
        "each names a cell the official form SHADES (rendered evidence, "
        "supplement round). Mapping-cleanup audit, not a declaration "
        "concern"),
}


# ---------------------------------------------------- witness discrepancies
# Keys are exact (section, printed line) ids: each entry suppresses exactly
# its own stylesheet cross-check finding in the years listed, and an entry
# the stylesheet in fact agrees with is stale
# (tenforty.verification.crosscheck.discrepancies_in_force).
_GRID_LUMPED = ("the stylesheet has no per-line labels for the property "
                "grid (lines 1a-22): its elements are lumped under label "
                "'B', so this grid id is not a stylesheet line")
_CELL = ("composed grid cell (sch_e Q1 / supplement shape rulings): the "
         "stylesheet lists one line per printed row, whose cell elements sit "
         "under the row's label, so the cell id is not a stylesheet line")
_ROWS_LUMPED = ("grid rows have no stylesheet labels: line {line}'s elements "
                "are lumped under the preceding label ({prev})")
_FIRST_ROW = ("the declaration carries the inventory's text for this line, "
              "its first printed row; the stylesheet carries the full "
              "multi-row label, so the word overlap falls below the "
              "cross-check threshold")


def _discrepancies():
    record = {}
    for year in YEARS:
        for ln in DECLARATIONS[year].lines:
            section, line = ln.line_id
            if section == P1 and line not in (
                    "A", "B", "A(No)", "B(No)", "23a", "23b", "23c", "23d",
                    "23e", "24", "25", "26"):
                reason = _GRID_LUMPED
            elif "(" in line:
                reason = _CELL
            elif ln.line_id in ((P2, "28"), (P3, "33"), (P4, "38")):
                prev = {"28": "27", "33": "32", "38": "37"}[line]
                reason = _ROWS_LUMPED.format(line=line, prev=prev)
            else:
                continue
            years, _ = record.get(ln.line_id, ((), None))
            record[ln.line_id] = ((*years, year), reason)
    # First-row texts: 2021's short rows, and the rows that stay short.
    for line in ("A", "B", "23a", "23b", "23c", "23d", "23e", "24", "25"):
        record[(P1, line)] = ((2021,), _FIRST_ROW)
    for line_id in ((P1, "26"), (P2, "27"), (P5, "42"), (P5, "43")):
        record[line_id] = (YEARS, _FIRST_ROW)
    return record


WITNESS_DISCREPANCIES = _discrepancies()
