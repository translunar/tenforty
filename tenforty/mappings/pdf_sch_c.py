"""PDF field mapping for IRS Schedule C (Form 1040), Profit or Loss From
Business. One PDF is rendered per business from the same per-year template.

Flat scalars (page 1 plus Part V line 48 on page 2). Years 2022-2025
(tenforty.years.SCHEDULE_C_FAMILY_YEARS). Field names were derived by
marker-probe and are pinned in tests/fixtures/golden_field_lines.py.

EXPENSE LINES. The twelve modeled Part II categories map to lines 8, 15, 17,
18, 20b, 22, 23, 24a, 24b, 25, 26 and "Other expenses (from line 48)" -- which
is line 27a through 2024 and line 27b in 2025 (the same field, relabelled when
the energy-efficient-buildings deduction took 27a). `rent_lease` is a single
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
The compute layer's refusals (cost of goods sold, depreciation, home office,
vehicle, depletion, returns and allowances, net loss, statutory employee)
fence everything else.

LEFT BLANK for hand-completion: business name (C), EIN (D), address (E), the
"started this year" box (H), the Form 1099 questions (I, J), the unmodeled
Part I lines 2, 4 and 6, Parts III and IV, and the Part V itemization rows
(only its line 48 total is filled).

The proprietor-name field sits inside a Pg1Header subform in 2022-2023 and
directly on Page1 from 2024.
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
    # Part V line 48 (page 2): the other-expenses total. The itemization
    # rows above it are left blank for hand-completion.
    "sch_c_line_48_total_other_expenses":
        "topmostSubform[0].Page2[0].f2_33[0]",
}

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

# PDF path -> constant on-state. Same paths and states in all four years.
_DERIVATIONS: dict[str, Callable[[Mapping[str, object]], object]] = {
    f"{_P1}.c1_1[0]": lambda _values: "/1",    # line F: (1) Cash
    f"{_P1}.c1_2[0]": lambda _values: "/Yes",  # line G: Yes
}


class PdfSchC(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule C"

    _MAPPINGS: dict[int, dict] = {
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
