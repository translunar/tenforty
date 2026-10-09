"""PDF field mapping for IRS Schedule C (Form 1040), Profit or Loss From
Business. One PDF is rendered per business from the same per-year template.

Flat scalars (page 1 plus Part V line 48 on page 2). Years 2021-2025
(tenforty.years.SCHEDULE_C_FAMILY_YEARS). Field names were derived by
marker-probe and are pinned in tests/fixtures/golden_field_lines.py.

LINE 13 (depreciation) prints the business's resolved depreciation; the
section 179 deduction that shares the line is unmodeled and has no input.

EXPENSE LINES. The twelve modeled Part II categories map to lines 8, 15, 17,
18, 20b, 22, 23, 24a, 24b, 25, 26 and "Other expenses (from line 48)" -- which
is line 27a through 2024 and line 27b in 2025 (the same field, relabelled when
the energy-efficient-buildings deduction took 27a; on the 2021 form 27b is
"Reserved for future use"). `rent_lease` is a single
modeled amount and prints on line 20b (other business property). Line 20a
(vehicles, machinery, equipment) is UNMODELED, consistent with the compute
layer refusing `vehicle_expenses`: tenforty models no vehicle or equipment
costs on Schedule C, so nothing can belong on 20a.

PRINTED CHAIN. Lines 1, 3, 5 and 7 all print (the compute emits each; they
are equal by construction), and Part V line 48 prints the other-expenses
total that the "Other expenses (from line 48)" line carries forward -- a
filled form prints every line its own arithmetic requires.

FIXED CHECKBOXES (get_derivations). Two boxes are always checked because they
are invariants of what tenforty models, not per-return facts:
  - Line F, accounting method = Cash. Accrual accounting is unmodeled.
  - Line G, material participation = Yes. Passive sole proprietorships are
    unmodeled.
The compute layer's refusals (cost of goods sold, home office,
vehicle, depletion, returns and allowances, statutory employee, and a net
loss without the at-risk attestation) fence everything else.

LINE 32 (at-risk). Box 32a (c1_7[0], on-state /1) is checked for a business
whose line 31 is a loss; a profit business leaves both boxes blank. Box 32b
(c1_7[1], on-state /2) is never written. Same field and states 2021-2025.

LEFT BLANK for hand-completion: business name (C), EIN (D), address (E), the
"started this year" box (H), the Form 1099 questions (I, J), the unmodeled
Part I lines 2, 4 and 6, Parts III and IV, and the Part V itemization rows
2-9 (row 1 itemizes the line 48 total).

The proprietor-name field sits inside a PgHeader subform in 2021, a Pg1Header
subform in 2022-2023, and directly on Page1 from 2024.
"""
from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping, inherit_pdf_fields

_P1 = "topmostSubform[0].Page1[0]"
_L8 = f"{_P1}.Lines8-17[0]"
_L18 = f"{_P1}.Lines18-27[0]"

_FIELDS_2022_2023: dict[str, str] = {
    "taxpayer_name": f"{_P1}.Pg1Header[0].f1_1[0]",
    "taxpayer_ssn": f"{_P1}.f1_2[0]",
    "sch_c_line_a_description": f"{_P1}.f1_3[0]",
    "sch_c_line_b_business_code": f"{_P1}.BComb[0].f1_4[0]",
    "sch_c_line_1_gross_receipts": f"{_P1}.f1_10[0]",
    "sch_c_line_3_net_receipts": f"{_P1}.f1_12[0]",
    "sch_c_line_5_gross_profit": f"{_P1}.f1_14[0]",
    "sch_c_line_7_gross_income": f"{_P1}.f1_16[0]",
    "sch_c_expense_advertising": f"{_L8}.f1_17[0]",          # line 8
    # Line 13 (depreciation). Probed on each year's own template, 2021-2025:
    # the widget beside the "13" label is Lines8-17.f1_22 in all five.
    "sch_c_line_13_depreciation": f"{_L8}.f1_22[0]",         # line 13
    "sch_c_expense_insurance": f"{_L8}.f1_24[0]",            # line 15
    "sch_c_expense_legal_professional": f"{_L8}.f1_27[0]",   # line 17
    "sch_c_expense_office_expense": f"{_L18}.f1_28[0]",      # line 18
    "sch_c_expense_rent_lease": f"{_L18}.f1_31[0]",          # line 20b
    "sch_c_expense_supplies": f"{_L18}.f1_33[0]",            # line 22
    "sch_c_expense_taxes_licenses": f"{_L18}.f1_34[0]",      # line 23
    "sch_c_expense_travel": f"{_L18}.f1_35[0]",              # line 24a
    "sch_c_expense_deductible_meals": f"{_L18}.f1_36[0]",    # line 24b
    "sch_c_expense_utilities": f"{_L18}.f1_37[0]",           # line 25
    "sch_c_expense_wages": f"{_L18}.f1_38[0]",               # line 26
    "sch_c_expense_other_expenses": f"{_L18}.f1_39[0]",      # line 27a / 27b
    "sch_c_line_28_total_expenses": f"{_P1}.f1_41[0]",
    "sch_c_line_29_tentative_profit": f"{_P1}.f1_42[0]",
    "sch_c_line_31_net_profit": f"{_P1}.f1_46[0]",
    # Part V (page 2): row 1 itemizes the line 48 total (single-aggregate v1;
    # rows 2-9 stay blank — multi-row itemization is out of scope). Same
    # paths in every year 2021-2025 (probe-verified: wide description box
    # left, narrow amount box right, top row of the table).
    "sch_c_part_v_row_1_description":
        "topmostSubform[0].Page2[0].PartVTable[0].Item1[0].f2_15[0]",
    "sch_c_part_v_row_1_amount":
        "topmostSubform[0].Page2[0].PartVTable[0].Item1[0].f2_16[0]",
    "sch_c_line_48_total_other_expenses":
        "topmostSubform[0].Page2[0].f2_33[0]",
}

# 2021: field inventory differs from 2022 in exactly one mapped path -- the
# proprietor-name wrapper is PgHeader[0], not Pg1Header[0]
# (scripts/diff_pdf_fields.py). Every other leaf was read on its printed line
# from the marker probe (pdfs/federal/2021/f1040sc.probe.pdf), not assumed
# from the shared names.
_FIELDS_2021: dict[str, str] = inherit_pdf_fields(
    _FIELDS_2022_2023,
    overrides={"taxpayer_name": f"{_P1}.PgHeader[0].f1_1[0]"},
)

_FIELDS_2024: dict[str, str] = inherit_pdf_fields(
    _FIELDS_2022_2023,
    overrides={"taxpayer_name": f"{_P1}.f1_1[0]"},
)

# 2025: "Other expenses (from line 48)" is line 27b (it was 27a through
# 2024). The probe shows it kept field f1_39 while the new line 27a took
# f1_40, so the path is restated here rather than inherited silently: the
# line is a per-year fact, and a future revision that moves the field is a
# one-entry edit.
_FIELDS_2025: dict[str, str] = inherit_pdf_fields(
    _FIELDS_2024,
    overrides={"sch_c_expense_other_expenses": f"{_L18}.f1_39[0]"},
)

# PDF path -> constant on-state. Same paths and states in all five years.
_DERIVATIONS: dict[str, Callable[[Mapping[str, object]], object]] = {
    f"{_P1}.c1_1[0]": lambda _values: "/1",    # line F: (1) Cash
    f"{_P1}.c1_2[0]": lambda _values: "/Yes",  # line G: Yes
    # Line 32a "All investment is at risk": marked only for a business with a
    # net loss (the compute emits the key for those alone). The companion
    # box 32b is c1_7[1] (on-state /2) and is never written -- Form 6198 is
    # unmodeled, and a loss without the 32a attestation refuses in compute.
    f"{_P1}.c1_7[0]": lambda values: (
        "/1" if values.get("sch_c_line_32a_all_investment_at_risk") else None),
}


class PdfSchC(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule C"

    _MAPPINGS: dict[int, dict] = {
        2021: _FIELDS_2021,
        2022: _FIELDS_2022_2023,
        2023: _FIELDS_2022_2023,
        2024: _FIELDS_2024,
        2025: _FIELDS_2025,
    }

    @classmethod
    def get_derivations(
        cls, year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in cls._MAPPINGS:
            raise ValueError(
                f"No {cls._FORM_NAME} derivations for year {year}")
        return _DERIVATIONS
