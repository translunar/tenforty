"""Schedule C (Form 1040) emit declarations, TY2021-2025.

Written from two independent author files and team-lead's adjudication of
their differences (emit-verification protocol steps 2-4; /private/tmp/pilot-
packet-sch_c/ADJUDICATION.md). The authors worked only from the official
forms, the line inventories, the MeF stylesheets and the computation's
output-key names. This module is the adjudicated union, and was not written
by either author:

* the line universe is the paper form, 71 lines a year (Parts I-V and the
  header items A-J), identical in both author files;
* descriptions are the paper form's text (author A's), including the two
  2023 lines whose stylesheet text is stale (27b, 28; WITNESS_DISCREPANCIES);
* ``mef_element`` is author B's throughout;
* line 20b binds the rent key (ruling 1; 20a, vehicles/machinery/equipment,
  stays unmodeled: the computation refuses vehicle expenses);
* explicit anchors where the printed label row cannot locate the entry
  field (ruling 3, author A's): the two-field rows of Part II, header item F
  (LEFT_OF "Cash", ruling 4), and the wrapped labels of A, 1 and 31.

The header items carry section "", the regenerated inventory's printed-page
section; both authors wrote "Header" against the pre-fix inventory, which did
not list them (a forced deviation, approved). Anchor phrases end on token
boundaries as printed: the evaluator matches whole ``pdftotext`` words, so
line 1 uses author A's "Gross receipts or sales." (the shorter variant,
"... sales", cut inside the printed token "sales." and printed nowhere).

The delta round (ADDENDUM 3 / 3a: nine keys the first output-key list
missed) binds lines B, 13, 15, 25, the "Other expenses (from line 48)" line
(27a through 2024, 27b in 2025), 32a and 48, and Part V's first row. Part V's
nine grid rows print no label; they take synthetic ids in the keys' own
vocabulary, "row{i}(description)" / "row{i}(amount)": row 1 is bound, rows
2-9 are unserved Repeat templates. Row 1 has no anchor yet (no
below-a-heading relation exists; routed) and is excluded from placement.
Anchors for the new lines (3a): 13 on its wrapped label (author B), 15 on
its box label (author A), 25 beside line 15's field from 2023, and the
other-expenses line below line 26's field (2021-2024) or beside line 17's
(2025).

2021 is the base year; 2022-2025 are ``derive`` diffs. A line whose text,
reason or anchor changes is dropped and re-added with the same binding.
"""
import dataclasses

from tenforty.declarations.anchors import (
    FieldRelation, LabelRelation, NearField, NearLabel)
from tenforty.declarations.model import (
    DeclaredLine, FormDeclaration, Repeat, derive)

FORM = ("federal", "sch_c")
# Header items A-J: section "" as the regenerated inventory prints them (the
# authors' "Header" is translated here).
H, P1, P2, P3, P4, P5 = "", "Part I", "Part II", "Part III", "Part IV", "Part V"

# Author B's MeF elements (ruling 2), by line; year changes in the diffs.
_MEF = {
    (H, "A"): "PrincipalBusinessActivityDesc",
    (H, "B"): "PrincipalBusinessActivityCd", (H, "C"): "BusinessNameLine1Txt",
    (H, "D"): "EIN", (H, "F"): "MethodOfAccountingCashInd",
    (H, "G"): "MaterialParticipationInCYInd",
    (H, "H"): "NewBusinessInCurrentYearInd",
    (H, "I"): "PaymentRqrFilingForm1099Ind",
    (H, "J"): "RequiredForm1099FiledInd",
    (P1, "1"): "TotalGrossReceiptsAmt", (P1, "2"): "ReturnsAndAllowancesAmt",
    (P1, "3"): "NetGrossReceiptsAmt", (P1, "4"): "CostOfGoodsSoldAmt",
    (P1, "5"): "GrossProfitAmt", (P1, "6"): "OtherIncomeAmt",
    (P1, "7"): "GrossIncomeAmt",
    (P2, "8"): "AdvertisingAmt", (P2, "9"): "CarAndTruckExpensesAmt",
    (P2, "10"): "CommissionsAndFeesAmt", (P2, "11"): "ContractLaborAmt",
    (P2, "12"): "DepletionAmt", (P2, "13"): "DeprecAndSect179ExpnsDedAmt",
    (P2, "14"): "EmployeeBenefitProgramAmt", (P2, "15"): "InsuranceAmt",
    (P2, "16a"): "MortgageInterestPaidBanksAmt",
    (P2, "16b"): "MortgageInterestPaidOtherAmt",
    (P2, "17"): "LegalAndProfessionalServiceAmt",
    (P2, "18"): "OfficeExpensesAmt", (P2, "19"): "PensionProfitSharingPlansAmt",
    (P2, "20a"): "MachineryAndEquipmentRentAmt",
    (P2, "20b"): "OtherBusinessPropertyRentAmt",
    (P2, "21"): "RepairsAndMaintenanceAmt", (P2, "22"): "SuppliesAmt",
    (P2, "23"): "TaxesAndLicensesAmt", (P2, "24a"): "TravelAmt",
    (P2, "24b"): "MealsAndEntertainmentAmt", (P2, "25"): "UtilitiesAmt",
    (P2, "26"): "WagesLessEmploymentCreditsAmt",
    (P2, "27a"): "TotalOtherExpensesAmt", (P2, "28"): "TotalExpensesAmt",
    (P2, "29"): "TentativeProfitOrLossAmt", (P2, "30"): "HomeBusinessExpenseAmt",
    (P2, "31"): "NetProfitOrLossAmt", (P2, "32a"): "AllInvestmentIsAtRiskInd",
    (P2, "32b"): "SomeInvestmentIsNotAtRiskInd",
    (P3, "34"): "ChangeInValuationsInd", (P3, "35"): "BeginningOfYearInventoryAmt",
    (P3, "36"): "PurchasesLessPersonalItemsAmt", (P3, "37"): "CostOfLaborAmt",
    (P3, "38"): "MaterialsAndSuppliesAmt", (P3, "39"): "OtherCostsAmt",
    (P3, "40"): "TotalCostsAmt", (P3, "41"): "EndOfYearInventoryAmt",
    (P3, "42"): "CostOfGoodsSoldAmt",
    (P4, "43"): "VehiclePlacedInServiceDt", (P4, "44a"): "BusinessMilesCnt",
    (P4, "44b"): "CommutingMilesCnt", (P4, "44c"): "OtherMilesCnt",
    (P4, "45"): "VehicleAvailableOffDutyHrsInd",
    (P4, "46"): "AnotherVehicleForPrsnlUseInd",
    (P4, "47a"): "EvidenceToSupportDeductionInd",
    (P4, "47b"): "EvidenceWrittenInd",
    (P5, "48"): "TotalOtherExpensesAmt",
    (P5, "row1(description)"): "OtherExpenseDetail/Desc",
    (P5, "row1(amount)"): "OtherExpenseDetail/Amt",
}


def _bound(section, line, d, key, kind="amount", anchor=None):
    return DeclaredLine(line=line, description=d[(section, line)], key=key,
                        kind=kind, section=section, anchor=anchor,
                        mef_element=_MEF.get((section, line)))


def _unserved(section, line, d, meaning, kind="amount"):
    return DeclaredLine(line=line, description=d[(section, line)], key="",
                        kind=kind, section=section,
                        mef_element=_MEF.get((section, line)),
                        single_state="nothing",
                        single_state_reason="unmodeled: " + meaning)


def _wrapped(phrase):
    """The entry field sits on the row after the label row printing
    ``phrase``."""
    return NearLabel(phrase=phrase, relation=LabelRelation.AFTER_WRAPPED)


def _right_of(phrase):
    return NearLabel(phrase=phrase, relation=LabelRelation.RIGHT_OF)


def _beside(line):
    """On the row of ``line``'s field, to its right."""
    return NearField(other_line=line, relation=FieldRelation.SAME_ROW_RIGHT_OF)


def _below(line):
    """On the row below ``line``'s field, in its column."""
    return NearField(other_line=line, relation=FieldRelation.NEXT_ROW_BELOW)


def _left_of(phrase):
    return NearLabel(phrase=phrase, relation=LabelRelation.LEFT_OF)


# ------------------------------------------- descriptions (the paper form)
_D21 = {
    (H, "A"): "Principal business or profession, including product or service (see instructions)",
    (H, "B"): "Enter code from instructions",
    (H, "C"): "Business name. If no separate business name, leave blank.",
    (H, "D"): "Employer ID number (EIN)/ (see instr.)",
    (H, "E"): "Business address (including suite or room no.) City, town or post office, state, and ZIP code",
    (H, "F"): "Accounting method: (1) Cash (2) Accrual (3) Other (specify)",
    (H, "G"): 'Did you "materially participate" in the operation of this business during 2021? If "No," see instructions for limit on losses .',
    (H, "H"): "If you started or acquired this business during 2021, check here",
    (H, "I"): "Did you make any payments in 2021 that would require you to file Form(s) 1099? (see instructions)",
    (H, "J"): 'If "Yes," did you or will you file required Forms 1099?',
    (P1, "1"): 'Gross receipts or sales. See instructions for line 1 and check the box if this income was reported to you on Form W-2 and the "Statutory employee" box on that form was checked',
    (P1, "2"): "Returns and allowances",
    (P1, "3"): "Subtract line 2 from line 1",
    (P1, "4"): "Cost of goods sold (from line 42)",
    (P1, "5"): "Gross profit. Subtract line 4 from line 3",
    (P1, "6"): "Other income, including federal and state gasoline or fuel tax credit or refund (see instructions)",
    (P1, "7"): "Gross income. Add lines 5 and 6",
    (P2, "8"): "Advertising",
    (P2, "9"): "Car and truck expenses (see instructions)",
    (P2, "10"): "Commissions and fees",
    (P2, "11"): "Contract labor (see instructions)",
    (P2, "12"): "Depletion",
    (P2, "13"): "Depreciation and section 179 expense deduction (not included in Part III) (see instructions)",
    (P2, "14"): "Employee benefit programs (other than on line 19)",
    (P2, "15"): "Insurance (other than health)",
    (P2, "16"): "Interest (see instructions):",
    (P2, "16a"): "Mortgage (paid to banks, etc.)",
    (P2, "16b"): "Other",
    (P2, "17"): "Legal and professional services",
    (P2, "18"): "Office expense (see instructions)",
    (P2, "19"): "Pension and profit-sharing plans",
    (P2, "20"): "Rent or lease (see instructions):",
    (P2, "20a"): "Vehicles, machinery, and equipment",
    (P2, "20b"): "Other business property",
    (P2, "21"): "Repairs and maintenance",
    (P2, "22"): "Supplies (not included in Part III)",
    (P2, "23"): "Taxes and licenses",
    (P2, "24"): "Travel and meals:",
    (P2, "24a"): "Travel",
    (P2, "24b"): "Deductible meals (see instructions) .",
    (P2, "25"): "Utilities",
    (P2, "26"): "Wages (less employment credits)",
    (P2, "27a"): "Other expenses (from line 48)",
    (P2, "27b"): "Reserved for future use",
    (P2, "28"): "Total expenses before expenses for business use of home. Add lines 8 through 27a",
    (P2, "29"): "Tentative profit or (loss). Subtract line 28 from line 7",
    (P2, "30"): "Expenses for business use of your home. Do not report these expenses elsewhere. Attach Form 8829 unless using the simplified method (see instructions). Simplified method filers only: enter the total square footage of: (a) your home: and (b) the part of your home used for business: . Use the Simplified Method Worksheet in the instructions to figure the amount to enter on line 30.",
    (P2, "31"): "Net profit or (loss). Subtract line 30 from line 29. If a profit, enter on both Schedule 1 (Form 1040), line 3 and on Schedule SE, line 2. (If you checked the box on line 1, see instructions). Estates and trusts, enter on Form 1041, line 3. If a loss, you must go to line 32.",
    (P2, "32"): "If you have a loss, check the box that describes your investment in this activity (see instructions). If you checked 32a, enter the loss on both Schedule 1 (Form 1040), line 3 and on Schedule SE, line 2 . (If you checked the box on line 1, see the line 31 instructions). Estates and trusts, enter on Form 1041, line 3. If you checked 32b, you must attach Form 6198. Your loss may be limited.",
    (P2, "32a"): "All investment is at risk.",
    (P2, "32b"): "Some investment is not at risk.",
    (P3, "33"): "Method(s) used to value closing inventory:",
    (P3, "34"): 'Was there any change in determining quantities, costs, or valuations between opening and closing inventory? If "Yes," attach explanation Yes No',
    (P3, "35"): "Inventory at beginning of year. If different from last year's closing inventory, attach explanation",
    (P3, "36"): "Purchases less cost of items withdrawn for personal use",
    (P3, "37"): "Cost of labor. Do not include any amounts paid to yourself",
    (P3, "38"): "Materials and supplies",
    (P3, "39"): "Other costs",
    (P3, "40"): "Add lines 35 through 39",
    (P3, "41"): "Inventory at end of year",
    (P3, "42"): "Cost of goods sold. Subtract line 41 from line 40. Enter the result here and on line 4",
    (P4, "43"): "When did you place your vehicle in service for business purposes? (month, day, year)",
    (P4, "44"): "Of the total number of miles you drove your vehicle during 2021, enter the number of miles you used your vehicle for:",
    (P4, "44a"): "Business",
    (P4, "44b"): "Commuting (see instructions)",
    (P4, "44c"): "Other",
    (P4, "45"): "Was your vehicle available for personal use during off-duty hours?",
    (P4, "46"): "Do you (or your spouse) have another vehicle available for personal use?",
    (P4, "47a"): "Do you have evidence to support your deduction?",
    (P4, "47b"): 'If "Yes," is the evidence written? Yes No',
    (P5, "48"): "Total other expenses. Enter here and on line 27a",
    **{(P5, row): "Other Expenses. List below business expenses not included on lines 8–26 or line 30."
       for row in ("row1(description)", "row1(amount)", "row{i}(description)",
                   "row{i}(amount)")},
}
_PART_V_ROWS = ("row1(description)", "row1(amount)", "row{i}(description)",
                "row{i}(amount)")
_TEXT_2022 = {  # changes vs 2021
    (H, "D"): "Employer ID number (EIN) (see instr.)",
    (H, "G"): 'Did you "materially participate" in the operation of this business during 2022? If "No," see instructions for limit on losses .',
    (H, "H"): "If you started or acquired this business during 2022, check here",
    (H, "I"): "Did you make any payments in 2022 that would require you to file Form(s) 1099? (see instructions)",
    (P4, "44"): "Of the total number of miles you drove your vehicle during 2022, enter the number of miles you used your vehicle for:",
}
_TEXT_2023 = {  # changes vs 2022; 27b / 28 follow the paper (stylesheet stale)
    (H, "G"): 'Did you "materially participate" in the operation of this business during 2023? If "No," see instructions for limit on losses .',
    (H, "H"): "If you started or acquired this business during 2023, check here",
    (H, "I"): "Did you make any payments in 2023 that would require you to file Form(s) 1099? (see instructions)",
    (P2, "27b"): "Energy efficient commercial bldgs deduction (attach Form 7205)",
    (P2, "28"): "Total expenses before expenses for business use of home. Add lines 8 through 27b",
    (P4, "44"): "Of the total number of miles you drove your vehicle during 2023, enter the number of miles you used your vehicle for:",
    **{(P5, row): "Other Expenses. List below business expenses not included on lines 8–26, line 27b, or line 30."
       for row in _PART_V_ROWS},
}
_TEXT_2024 = {  # changes vs 2023
    (H, "G"): 'Did you "materially participate" in the operation of this business during 2024? If "No," see instructions for limit on losses .',
    (H, "H"): "If you started or acquired this business during 2024, check here",
    (H, "I"): "Did you make any payments in 2024 that would require you to file Form(s) 1099? See instructions",
    (P2, "30"): "Expenses for business use of your home. Do not report these expenses elsewhere. Attach Form 8829 unless using the simplified method. See instructions. Simplified method filers only: Enter the total square footage of: (a) your home: and (b) the part of your home used for business: . Use the Simplified Method Worksheet in the instructions to figure the amount to enter on line 30.",
    (P2, "32"): "If you have a loss, check the box that describes your investment in this activity. See instructions. If you checked 32a, enter the loss on both Schedule 1 (Form 1040), line 3 and on Schedule SE, line 2 . (If you checked the box on line 1, see the line 31 instructions.) Estates and trusts, enter on Form 1041, line 3. If you checked 32b, you must attach Form 6198. Your loss may be limited.",
    (P4, "43"): "When did you place your vehicle in service for business purposes? (month/day/year)",
    (P4, "44"): "Of the total number of miles you drove your vehicle during 2024, enter the number of miles you used your vehicle for:",
}
_TEXT_2025 = {  # changes vs 2024; 27a and 27b swap
    (H, "G"): 'Did you "materially participate" in the operation of this business during 2025? If "No," see instructions for limit on losses .',
    (H, "H"): "If you started or acquired this business during 2025, check here",
    (H, "I"): "Did you make any payments in 2025 that would require you to file Form(s) 1099? See instructions",
    (H, "J"): 'If "Yes," did you or will you file required Form(s) 1099?',
    (P2, "27a"): "Energy efficient commercial bldgs deduction (attach Form 7205)",
    (P2, "27b"): "Other expenses (from line 48)",
    (P2, "30"): "Expenses for business use of your home. Do not report these expenses elsewhere. Attach Form 8829 unless using the simplified method. See instructions. Simplified method filers only: Enter the total square footage of (a) your home: and (b) the part of your home used for business: . Use the Simplified Method Worksheet in the instructions to figure the amount to enter on line 30.",
    (P2, "31"): "Net profit or (loss). Subtract line 30 from line 29. If a profit, enter on both Schedule 1 (Form 1040), line 3 and on Schedule SE, line 2. (If you checked the box on line 1, see instructions.) Estates and trusts, enter on Form 1041, line 3. If a loss, you must go to line 32.",
    (P4, "44"): "Of the total number of miles you drove your vehicle during 2025, enter the number of miles you used your vehicle for:",
    (P5, "48"): "Total other expenses. Enter here and on line 27b",
    **{(P5, row): "Other Expenses. List below business expenses not included on lines 8-27a, or line 30."
       for row in _PART_V_ROWS},
}

# Meanings of lines 27a / 27b / 48 change by year (see the year diffs).
_27A_21 = "other expenses from line 48 (Part V total)"
_27B_21 = "reserved for future use; no entry"
_27B_23 = "energy efficient commercial buildings deduction (attach Form 7205)"

def _lines(d):
    return (
        # ---------------------------------------------- header items A-J
        # A: the entry band is on the row below the caption (+14 pt, at
        # WRAP_PT; both authors flagged the boundary). The phrase prints
        # once a page.
        _bound(H, "A", d, "sch_c_line_a_description", kind="text",
               anchor=_wrapped("Principal business or profession, including "
                               "product or service")),
        # B: the principal business code; its box is on the row below the
        # caption, as line A's is.
        _bound(H, "B", d, "sch_c_line_b_business_code", kind="text",
               anchor=_wrapped("Enter code from instructions")),
        _unserved(H, "C", d, "business name", kind="text"),
        _unserved(H, "D", d, "employer ID number (EIN)", kind="text"),
        _unserved(H, "E", d, "business address; city, town or post office, "
                  "state, and ZIP code", kind="text"),
        # F: the key names only the Cash option; (2) Accrual and (3) Other
        # have no key. The row holds three option boxes, so the Cash box is
        # located immediately left of the printed "Cash" (once a page).
        _bound(H, "F", d, "sch_c_line_f_cash_method", kind="checkbox",
               anchor=_left_of("Cash")),
        # G: a Yes/No pair on one row; the key's value marks Yes.
        _bound(H, "G", d, "sch_c_line_g_material_participation",
               kind="checkbox"),
        _unserved(H, "H", d, "started or acquired this business during the "
                  "year (checkbox)", kind="checkbox"),
        _unserved(H, "I", d, "made payments that would require Form(s) 1099 "
                  "(Yes/No)", kind="checkbox"),
        _unserved(H, "J", d, "did or will file required Form(s) 1099 "
                  "(Yes/No)", kind="checkbox"),

        # ---------------------------------------------------- Part I
        # 1: the label wraps; the amount box is on the next row (+10 pt).
        # The line-1 statutory-employee checkbox has no key.
        _bound(P1, "1", d, "sch_c_line_1_gross_receipts",
               anchor=_wrapped("Gross receipts or sales.")),
        _unserved(P1, "2", d, "returns and allowances"),
        _bound(P1, "3", d, "sch_c_line_3_net_receipts"),
        _unserved(P1, "4", d, "cost of goods sold (from line 42)"),
        _bound(P1, "5", d, "sch_c_line_5_gross_profit"),
        _unserved(P1, "6", d, "other income, including federal and state "
                  "gasoline or fuel tax credit or refund"),
        _bound(P1, "7", d, "sch_c_line_7_gross_income"),

        # ---------------------------------------------------- Part II
        # Two columns of entry boxes; where a bound line shares its row with
        # another line's box, the anchor is the printed box label just left
        # of its own box (author A, ruling 3).
        _bound(P2, "8", d, "sch_c_expense_advertising",
               anchor=_right_of("8")),
        _unserved(P2, "9", d, "car and truck expenses"),
        _unserved(P2, "10", d, "commissions and fees"),
        _unserved(P2, "11", d, "contract labor"),
        _unserved(P2, "12", d, "depletion"),
        # 13: four-row label; the field is on the row after the label's
        # last-but-one row (author B). It carries section 179 expense too.
        _bound(P2, "13", d, "sch_c_line_13_depreciation",
               anchor=_wrapped("included in Part III) (see")),
        _unserved(P2, "14", d, "employee benefit programs (other than on "
                  "line 19)"),
        # 15: other than health insurance; its row also holds a right-column
        # field (24b through 2022, 25 from 2023).
        _bound(P2, "15", d, "sch_c_expense_insurance",
               anchor=_right_of("15")),
        _unserved(P2, "16", d, "caption only ('Interest (see "
                  "instructions):'); no entry space -- amounts go on 16a/16b"),
        _unserved(P2, "16a", d, "mortgage interest paid to banks, etc."),
        _unserved(P2, "16b", d, "other interest"),
        _bound(P2, "17", d, "sch_c_expense_legal_professional",
               anchor=_right_of("17")),
        _bound(P2, "18", d, "sch_c_expense_office_expense",
               anchor=_right_of("18")),
        _unserved(P2, "19", d, "pension and profit-sharing plans"),
        _unserved(P2, "20", d, "caption only ('Rent or lease (see "
                  "instructions):'); no entry space -- amounts go on 20a/20b"),
        _unserved(P2, "20a", d, "rent or lease of vehicles, machinery, and "
                  "equipment (vehicle expenses are refused by the "
                  "computation)"),
        # 20b: the rent key (ruling 1).
        _bound(P2, "20b", d, "sch_c_expense_rent_lease"),
        _unserved(P2, "21", d, "repairs and maintenance"),
        _bound(P2, "22", d, "sch_c_expense_supplies"),
        _bound(P2, "23", d, "sch_c_expense_taxes_licenses"),
        _unserved(P2, "24", d, "caption only ('Travel and meals:'); no "
                  "entry space -- amounts go on 24a/24b"),
        _bound(P2, "24a", d, "sch_c_expense_travel"),
        _bound(P2, "24b", d, "sch_c_expense_deductible_meals",
               anchor=_right_of("24b")),
        # 25: alone on its row through 2022 (line 16 is a caption); beside
        # line 15's field from 2023 (see the year diffs).
        _bound(P2, "25", d, "sch_c_expense_utilities"),
        # 26: the printed value is net of the employment credits. Anchored
        # in 2021-2022, where its row is shared with line 16a's box.
        _bound(P2, "26", d, "sch_c_expense_wages", anchor=_right_of("26")),
        # 27a: "Other expenses (from line 48)" through 2024; its row is
        # shared with a left-column field, so it is located below line 26's.
        _bound(P2, "27a", d, "sch_c_expense_other_expenses",
               anchor=_below("26")),
        _unserved(P2, "27b", d, _27B_21),
        # 28: PARTIAL-TOTAL RISK (both authors): only 13 expense categories
        # carry keys, but line 28 is the total of every line 8 through 27.
        _bound(P2, "28", d, "sch_c_line_28_total_expenses"),
        # 29: "tentative profit or (loss)".
        _bound(P2, "29", d, "sch_c_line_29_tentative_profit"),
        _unserved(P2, "30", d, "expenses for business use of home (Form 8829 "
                  "or simplified method), incl. the two square-footage "
                  "entries"),
        # 31: three-row label; the field is on the third row. CAVEATS (both
        # authors): line 30 has no key, so line 31 equals line 29 unless
        # home office is modeled; a loss must first pass the at-risk and
        # passive-activity rules ("it may be smaller than the amount you
        # figured by subtracting line 30 from line 29").
        _bound(P2, "31", d, "sch_c_line_31_net_profit",
               anchor=_wrapped("If a profit, enter on both Schedule 1")),
        _unserved(P2, "32", d, "loss-only at-risk question; answered in "
                  "boxes 32a/32b", kind="checkbox"),
        # 32a: both states -- line 32 is reached only on a loss ("If a loss,
        # you must go to line 32"); a profit leaves 32a blank.
        _bound(P2, "32a", d, "sch_c_line_32a_all_investment_at_risk",
               kind="checkbox"),
        _unserved(P2, "32b", d, "some investment is not at risk (attach "
                  "Form 6198)", kind="checkbox"),

        # ---------------------------------------------------- Part III
        _unserved(P3, "33", d, "method(s) used to value closing inventory: "
                  "cost / lower of cost or market / other", kind="checkbox"),
        _unserved(P3, "34", d, "change in determining quantities, costs, or "
                  "valuations between opening and closing inventory (Yes/No)",
                  kind="checkbox"),
        _unserved(P3, "35", d, "inventory at beginning of year"),
        _unserved(P3, "36", d, "purchases less cost of items withdrawn for "
                  "personal use"),
        _unserved(P3, "37", d, "cost of labor"),
        _unserved(P3, "38", d, "materials and supplies (cost of goods sold)"),
        _unserved(P3, "39", d, "other costs (cost of goods sold)"),
        _unserved(P3, "40", d, "add lines 35 through 39"),
        _unserved(P3, "41", d, "inventory at end of year"),
        _unserved(P3, "42", d, "cost of goods sold: line 40 minus line 41"),

        # ---------------------------------------------------- Part IV
        _unserved(P4, "43", d, "date vehicle placed in service", kind="date"),
        _unserved(P4, "44", d, "caption only for vehicle miles; entries on "
                  "44a/44b/44c"),
        _unserved(P4, "44a", d, "business miles"),
        _unserved(P4, "44b", d, "commuting miles"),
        _unserved(P4, "44c", d, "other miles"),
        _unserved(P4, "45", d, "vehicle available for personal use during "
                  "off-duty hours (Yes/No)", kind="checkbox"),
        _unserved(P4, "46", d, "another vehicle available for personal use "
                  "(Yes/No)", kind="checkbox"),
        _unserved(P4, "47a", d, "evidence to support the deduction (Yes/No)",
                  kind="checkbox"),
        _unserved(P4, "47b", d, "evidence is written (Yes/No)",
                  kind="checkbox"),

        # ---------------------------------------------------- Part V
        # 48: PARTIAL-TOTAL RISK: the sum of every Part V row; only row 1
        # has keys.
        _bound(P5, "48", d, "sch_c_line_48_total_other_expenses"),
        # Part V's grid: nine unlabeled rows. Row 1 is bound (no anchor yet:
        # no below-a-heading relation exists); rows 2-9 are unserved.
        _bound(P5, "row1(description)", d, "sch_c_part_v_row_1_description",
               kind="text"),
        _bound(P5, "row1(amount)", d, "sch_c_part_v_row_1_amount"),
        _part_v_rows(d, "description", "text"),
        _part_v_rows(d, "amount", "amount"),
    )


def _part_v_rows(d, cell, kind):
    line = f"row{{i}}({cell})"
    return DeclaredLine(
        line=line, description=d[(P5, line)], key="", kind=kind, section=P5,
        single_state="nothing",
        single_state_reason=(f"unmodeled: Part V rows 2-9, {cell} -- the "
                             "keys name row 1 only"),
        repeat=Repeat(index_name="i", values=tuple(str(i) for i in range(2, 10))))


# Header prints outside the line universe (ruling: as for Schedule SE).
_NOT_PRINTED = {
    "taxpayer_name": (
        "presentation-only: page 1 header 'Name of proprietor', outside the "
        "line inventory"),
    "taxpayer_ssn": (
        "presentation-only: page 1 header 'Social security number (SSN)', "
        "outside the line inventory"),
}

SCH_C_2021 = FormDeclaration(form=FORM, key=2021, lines=_lines(_D21),
                             not_printed=_NOT_PRINTED)


def _section(line):
    if line in "ABCDEFGHIJ":
        return H
    if line.startswith("row"):
        return P5
    n = int("".join(c for c in line if c.isdigit()))
    return (P1 if n <= 7 else P2 if n <= 32 else P3 if n <= 42 else
            P4 if n <= 47 else P5)


def _revise(base, key, text=None, reason=None, anchor=None, mef=None,
            replace=()):
    """``base`` for year ``key`` with the given lines changed: text,
    unserved reason, anchor or MeF element (drop and re-add); ``replace``
    swaps whole lines."""
    text, reason = text or {}, reason or {}
    anchor, mef = anchor or {}, mef or {}
    replaced = {ln.line_id: ln for ln in replace}
    ids = list(dict.fromkeys(
        [*text, *[(_section(l), l) for l in [*reason, *anchor, *mef]]]))
    by_id = {**{ln.line_id: ln for ln in base.lines}, **replaced}
    ids += [i for i in replaced if i not in ids]
    new = []
    for i in ids:
        change = {}
        if i in text:
            change["description"] = text[i]
        if i[1] in reason:
            change["single_state_reason"] = "unmodeled: " + reason[i[1]]
        if i[1] in anchor:
            change["anchor"] = anchor[i[1]]
        if i[1] in mef:
            change["mef_element"] = mef[i[1]]
        new.append(dataclasses.replace(by_id[i], **change))
    return derive(base, key, drop=ids, add=new)


SCH_C_2022 = _revise(SCH_C_2021, 2022, text=_TEXT_2022)

# 2023: the paper form fills line 27b with the Form 7205 deduction and line
# 28 adds "through 27b" (the stylesheet still says Reserved / 27a). Line 26's
# row is no longer shared, so its anchor is removed; line 25 now shares line
# 15's row.
SCH_C_2023 = _revise(SCH_C_2022, 2023, text=_TEXT_2023,
                     reason={"27b": _27B_23},
                     anchor={"26": None, "25": _beside("15")})

# 2024: the stylesheet names line 27b's element.
SCH_C_2024 = _revise(SCH_C_2023, 2024, text=_TEXT_2024,
                     mef={"27b": "EnergyEffcntCmrclBldgDedAmt"})

# 2025: 27a and 27b swap -- 27a is the Form 7205 deduction (unserved), 27b
# is other expenses from line 48 (bound, beside line 17's field), and line 48
# now carries to 27b.
SCH_C_2025 = _revise(SCH_C_2024, 2025, text=_TEXT_2025, replace=(
    DeclaredLine(line="27a", description=_TEXT_2025[(P2, "27a")], key="",
                 kind="amount", section=P2,
                 mef_element="EnergyEffcntCmrclBldgDedAmt",
                 single_state="nothing",
                 single_state_reason="unmodeled: " + _27B_23),
    DeclaredLine(line="27b", description=_TEXT_2025[(P2, "27b")],
                 key="sch_c_expense_other_expenses", kind="amount",
                 section=P2, mef_element="TotalOtherExpensesAmt",
                 anchor=_beside("17")),
))

DECLARATIONS = {decl.key: decl for decl in (
    SCH_C_2021, SCH_C_2022, SCH_C_2023, SCH_C_2024, SCH_C_2025)}


# Where the two witnesses (MeF stylesheet, PDF inventory) diverge from the
# paper form: recorded, not reconciled. The pre-fix inventory's own defects
# (two-column composition, missing A-J / 27b / 44b / 44c) are resolved by the
# inventory-fixes lane and no longer appear in the regenerated inventory.
_ALL = (2021, 2022, 2023, 2024, 2025)
WITNESS_DISCREPANCIES = {
    (P2, "32a"): (_ALL, "the stylesheet has a single line 32 (two indicator "
                  "elements); the paper prints separate boxes 32a 'All "
                  "investment is at risk.' and 32b; description from the "
                  "paper"),
    (P2, "32b"): (_ALL, "as 32a; the paper prints 32b 'Some investment is "
                  "not at risk.'"),
    (P2, "27b@2023"): ((2023,), "the 2023 stylesheet still says 'Reserved "
                       "for future use' for line 27b and 'Add lines 8 "
                       "through 27a' for line 28; the 2023 paper form prints "
                       "the Form 7205 deduction on 27b and '8 through 27b' "
                       "on 28. The descriptions follow the paper"),
    (P4, "dup"): (_ALL, "the stylesheet repeats Part IV (43-47b) three times "
                  "(additional-vehicle blocks); the paper prints Part IV "
                  "once"),
    (P5, "row1..row9"): (_ALL, "Part V's nine printed rows are absent from "
                         "both witnesses: the inventory lists only line 48 "
                         "in Part V, and the stylesheet files the row "
                         "elements (OtherExpenseDetail Desc / Amt) under the "
                         "repeated Part IV block's 47b"),
}
