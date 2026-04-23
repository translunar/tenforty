import unittest

import openpyxl
from openpyxl.cell.cell import MergedCell

from tenforty.mappings.f1040 import F1040
from tests.helpers import SPREADSHEETS_DIR


class TestF1040Inputs2025(unittest.TestCase):
    def test_has_2025_inputs(self):
        inputs = F1040.get_inputs(2025)
        self.assertIsInstance(inputs, dict)
        self.assertGreater(len(inputs), 0)

    def test_w2_wage_fields(self):
        inputs = F1040.get_inputs(2025)
        self.assertEqual(inputs["w2_wages_1"], "C3")
        self.assertEqual(inputs["w2_fed_withheld_1"], "C4")
        self.assertEqual(inputs["w2_ss_wages_1"], "C5")
        self.assertEqual(inputs["w2_ss_withheld_1"], "C6")
        self.assertEqual(inputs["w2_medicare_wages_1"], "C7")
        self.assertEqual(inputs["w2_medicare_withheld_1"], "C8")

    def test_filing_status_fields(self):
        inputs = F1040.get_inputs(2025)
        self.assertEqual(inputs["filing_status_single"], "File_Single")
        self.assertEqual(inputs["filing_status_married_jointly"], "File_Marr_Joint")
        self.assertEqual(inputs["filing_status_married_separately"], "File_Marr_Sep")
        self.assertEqual(inputs["filing_status_head_of_household"], "File_Head")

    def test_birthdate_fields(self):
        inputs = F1040.get_inputs(2025)
        self.assertEqual(inputs["birthdate_month"], "YourBirthMonth")
        self.assertEqual(inputs["birthdate_day"], "YourBirthDay")
        self.assertEqual(inputs["birthdate_year"], "YourBirthYear")

    def test_1099_int_fields(self):
        inputs = F1040.get_inputs(2025)
        self.assertIn("interest_1", inputs)

    def test_1098_mortgage_interest(self):
        inputs = F1040.get_inputs(2025)
        self.assertIn("mortgage_interest", inputs)

    def test_schedule_e_rental_fields(self):
        inputs = F1040.get_inputs(2025)
        self.assertIn("sche_rents_a", inputs)
        self.assertIn("sche_property_type_a", inputs)


class TestF1040Outputs2025(unittest.TestCase):
    def test_has_2025_outputs(self):
        outputs = F1040.get_outputs(2025)
        self.assertIsInstance(outputs, dict)
        self.assertGreater(len(outputs), 0)

    def test_core_output_fields(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["agi"], "Adj_Gross_Inc")
        self.assertEqual(outputs["taxable_income"], "Taxable_Inc")
        self.assertEqual(outputs["total_tax"], "Tax")
        self.assertEqual(outputs["federal_withheld"], "W2_FedTaxWH")
        self.assertEqual(outputs["overpaid"], "Overpaid")

    def test_schedule_e_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["sche_line26"], "SchE1_Line26")

    def test_total_income_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_income"], "Total_Income")

    def test_total_payments_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_payments"], "Tot_Payments")

    def test_total_deductions_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_deductions"], "TotalDeductions")

    def test_schedule_a_total_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["schedule_a_total"], "Tot_Item_Deduct")

    def test_standard_deduction_uses_filing_status_aware_range(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(
            outputs["standard_deduction"], "Standard",
            "standard_deduction must map to Standard (1040!BI70, the filing-status-aware "
            "dollar amount), not SD_Single (single-only) or StdDeduct (boolean flag).",
        )


class TestF1040MappingValidity(unittest.TestCase):
    """Pre-flight checks: every direct cell ref in SHEET_MAP must point at a
    writable cell in the actual workbook. Catches merged-cell mapping bugs
    before they surface as cryptic 'MergedCell attribute is read-only' errors
    during e2e runs."""

    def test_no_input_maps_to_merged_cell(self):
        for year, sheet_map in F1040.SHEET_MAP.items():
            workbook_path = SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx"
            if not workbook_path.exists():
                continue
            wb = openpyxl.load_workbook(workbook_path, read_only=False)
            inputs = F1040.get_inputs(year)
            for key, sheet_name in sheet_map.items():
                cell_ref = inputs[key]
                cell = wb[sheet_name][cell_ref]
                self.assertNotIsInstance(
                    cell, MergedCell,
                    f"{year} input '{key}' maps to {sheet_name}!{cell_ref}, "
                    f"which is a merged cell. Map to the top-left of the merge range instead.",
                )


class TestF1040InputTypes(unittest.TestCase):
    def test_all_input_values_are_strings(self):
        for key, value in F1040.get_inputs(2025).items():
            self.assertIsInstance(value, str, f"Input '{key}' value is {type(value)}, expected str")

    def test_all_output_values_are_strings(self):
        for key, value in F1040.get_outputs(2025).items():
            self.assertIsInstance(value, str, f"Output '{key}' value is {type(value)}, expected str")


class TestF1040Form8949Mapping(unittest.TestCase):
    """Form 8949 per-lot row mapping: 4 boxes (A/B/D/E) × 11 lots × 7 fields.

    Box C/F (no 1099-B) is out of scope since Form1099B implies a received
    1099-B by definition.
    """

    def test_each_box_has_eleven_lot_rows(self):
        inputs = F1040.get_inputs(2025)
        for box in ("a", "b", "d", "e"):
            for idx in range(1, 12):
                self.assertIn(
                    f"f8949_box_{box}_lot_{idx}_description", inputs,
                    f"missing Box {box.upper()} lot {idx} description cell",
                )

    def test_box_a_lot_1_cells_are_part_i_row_41(self):
        inputs = F1040.get_inputs(2025)
        self.assertEqual(inputs["f8949_box_a_lot_1_description"],     "AJ41")
        self.assertEqual(inputs["f8949_box_a_lot_1_date_acquired"],   "AK41")
        self.assertEqual(inputs["f8949_box_a_lot_1_date_sold"],       "AL41")
        self.assertEqual(inputs["f8949_box_a_lot_1_proceeds"],        "AM41")
        self.assertEqual(inputs["f8949_box_a_lot_1_basis"],           "AN41")
        self.assertEqual(inputs["f8949_box_a_lot_1_adjustment_code"], "AO41")
        self.assertEqual(inputs["f8949_box_a_lot_1_adjustment_amount"], "AP41")

    def test_box_d_lot_1_cells_are_part_ii_row_91(self):
        inputs = F1040.get_inputs(2025)
        self.assertEqual(inputs["f8949_box_d_lot_1_description"], "AJ91")
        self.assertEqual(inputs["f8949_box_d_lot_1_proceeds"],    "AM91")

    def test_box_a_and_d_use_sheet_8949A(self):
        sheet_map = F1040.SHEET_MAP[2025]
        self.assertEqual(sheet_map["f8949_box_a_lot_1_description"], "8949A")
        self.assertEqual(sheet_map["f8949_box_d_lot_1_description"], "8949A")

    def test_box_b_and_e_use_sheet_8949B(self):
        sheet_map = F1040.SHEET_MAP[2025]
        self.assertEqual(sheet_map["f8949_box_b_lot_1_description"], "8949B")
        self.assertEqual(sheet_map["f8949_box_e_lot_1_description"], "8949B")

    def test_box_totals_map_to_named_ranges(self):
        """Per-box totals come from the workbook's 4-letter named ranges:
        {sheet}{S,L}T{D,E,G,H} where D/E/G/H columns are proceeds/basis/
        adjustment/gain respectively on the subsection total row."""
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["f8949_box_a_total_proceeds"],   "F8949ASTD")
        self.assertEqual(outputs["f8949_box_a_total_gain"],       "F8949ASTH")
        self.assertEqual(outputs["f8949_box_b_total_proceeds"],   "F8949BSTD")
        self.assertEqual(outputs["f8949_box_d_total_proceeds"],   "F8949ALTD")
        self.assertEqual(outputs["f8949_box_e_total_gain"],       "F8949BLTH")
