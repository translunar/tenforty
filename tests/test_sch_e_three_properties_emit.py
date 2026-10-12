"""Schedule E with three rental properties, end to end.

Three invented rentals fill columns A, B and C of page 1 on every template
2021-2025, and the totals block sums the columns:

            address              line 3   line 12  line 16  line 18  line 20  line 21
  A   100 Example Street         24,000    8,000    3,000    5,000   16,000    8,000
  B   200 Example Street         12,000        -    2,000   14,000   16,000   (4,000)
  C   300 Example Street          9,000    4,000    1,000        -    5,000    4,000

  23a 45,000   23c 12,000   23d 19,000   23e 37,000
  24  12,000   25   4,000   26   8,000

Every PDF assertion names its widget by literal path, typed here from the
templates rather than looked up through the mapping.
"""

import dataclasses
import unittest

from tenforty.audit import depreciation_workbook
from tenforty.models import RentalProperty
from tests import _audit_workbook_fixtures as fx
from tests.test_sch_e_totals_and_line_27 import _EmitCase, _rental, _scenario

_YEARS = (2021, 2022, 2023, 2024, 2025)
_P1 = "topmostSubform[0].Page1[0]."

# Line 1a address rows, A / B / C. 2021 nests the table under Line1; 2022
# zero-pads the single-digit leaves.
_ADDRESS_ROWS = {
    2021: (_P1 + "Line1[0].Table1a[0].RowA[0].f1_3[0]",
           _P1 + "Line1[0].Table1a[0].RowB[0].f1_4[0]",
           _P1 + "Line1[0].Table1a[0].RowC[0].f1_5[0]"),
    2022: (_P1 + "Table_Line1a[0].RowA[0].f1_03[0]",
           _P1 + "Table_Line1a[0].RowB[0].f1_04[0]",
           _P1 + "Table_Line1a[0].RowC[0].f1_05[0]"),
}
_ADDRESS_ROWS_2023_ON = (
    _P1 + "Table_Line1a[0].RowA[0].f1_3[0]",
    _P1 + "Table_Line1a[0].RowB[0].f1_4[0]",
    _P1 + "Table_Line1a[0].RowC[0].f1_5[0]")

# Line 3 cells, A / B / C. 2021 has one more container level.
_LINE_3_2021 = (
    _P1 + "Table_Income[0].Income[0].Line3[0].f1_16[0]",
    _P1 + "Table_Income[0].Income[0].Line3[0].f1_17[0]",
    _P1 + "Table_Income[0].Income[0].Line3[0].f1_18[0]")
_LINE_3_2022_ON = (
    _P1 + "Table_Income[0].Line3[0].f1_16[0]",
    _P1 + "Table_Income[0].Line3[0].f1_17[0]",
    _P1 + "Table_Income[0].Line3[0].f1_18[0]")

# Lines 20, 21 and 22, A / B / C: the same paths on all five templates.
_LINE_20 = (_P1 + "Table_Expenses[0].Line20[0].f1_68[0]",
            _P1 + "Table_Expenses[0].Line20[0].f1_69[0]",
            _P1 + "Table_Expenses[0].Line20[0].f1_70[0]")
_LINE_21 = (_P1 + "Table_Expenses[0].Line21[0].f1_71[0]",
            _P1 + "Table_Expenses[0].Line21[0].f1_72[0]",
            _P1 + "Table_Expenses[0].Line21[0].f1_73[0]")
_LINE_22 = (_P1 + "Table_Expenses[0].Line22[0].f1_74[0]",
            _P1 + "Table_Expenses[0].Line22[0].f1_75[0]",
            _P1 + "Table_Expenses[0].Line22[0].f1_76[0]")

_LINE_23A = _P1 + "f1_77[0]"
_LINE_23C = _P1 + "f1_79[0]"
_LINE_23D = _P1 + "f1_80[0]"
_LINE_23E = _P1 + "f1_81[0]"
_LINE_24 = _P1 + "f1_82[0]"
_LINE_25 = _P1 + "f1_83[0]"
_LINE_26 = _P1 + "f1_84[0]"

# Every column C cell on the 2023-2025 templates, by line.
_COLUMN_C_2023_ON = {
    "1a": _P1 + "Table_Line1a[0].RowC[0].f1_5[0]",
    "1b": _P1 + "Table_Line1b[0].RowC[0].f1_8[0]",
    "2 fair rental days": _P1 + "Table_Line2[0].RowC[0].f1_13[0]",
    "2 personal use days": _P1 + "Table_Line2[0].RowC[0].f1_14[0]",
    "3": _P1 + "Table_Income[0].Line3[0].f1_18[0]",
    "5": _P1 + "Table_Expenses[0].Line5[0].f1_24[0]",
    "6": _P1 + "Table_Expenses[0].Line6[0].f1_27[0]",
    "7": _P1 + "Table_Expenses[0].Line7[0].f1_30[0]",
    "8": _P1 + "Table_Expenses[0].Line8[0].f1_33[0]",
    "9": _P1 + "Table_Expenses[0].Line9[0].f1_36[0]",
    "10": _P1 + "Table_Expenses[0].Line10[0].f1_39[0]",
    "11": _P1 + "Table_Expenses[0].Line11[0].f1_42[0]",
    "12": _P1 + "Table_Expenses[0].Line12[0].f1_45[0]",
    "13": _P1 + "Table_Expenses[0].Line13[0].f1_48[0]",
    "14": _P1 + "Table_Expenses[0].Line14[0].f1_51[0]",
    "15": _P1 + "Table_Expenses[0].Line15[0].f1_54[0]",
    "16": _P1 + "Table_Expenses[0].Line16[0].f1_57[0]",
    "17": _P1 + "Table_Expenses[0].Line17[0].f1_60[0]",
    "18": _P1 + "Table_Expenses[0].Line18[0].f1_63[0]",
    "19": _P1 + "Table_Expenses[0].Line19[0].f1_67[0]",
    "20": _P1 + "Table_Expenses[0].Line20[0].f1_70[0]",
    "21": _P1 + "Table_Expenses[0].Line21[0].f1_73[0]",
    "22": _P1 + "Table_Expenses[0].Line22[0].f1_76[0]",
}
# The same cells on the two templates whose tree differs.
_COLUMN_C_BY_YEAR = {
    2021: {**_COLUMN_C_2023_ON,
           "1a": _P1 + "Line1[0].Table1a[0].RowC[0].f1_5[0]",
           "1b": _P1 + "Line1[0].Table1b[0].RowC[0].f1_8[0]",
           "3": _P1 + "Table_Income[0].Income[0].Line3[0].f1_18[0]"},
    2022: {**_COLUMN_C_2023_ON,
           "1a": _P1 + "Table_Line1a[0].RowC[0].f1_05[0]",
           "1b": _P1 + "Table_Line1b[0].RowC[0].f1_08[0]"},
}
# The lines property C prints (line 18 is zero, so it and line 22 are blank).
_COLUMN_C_PRINTED_LINES = {
    "1a", "1b", "2 fair rental days", "2 personal use days", "3", "12",
    "16", "20", "21"}


def _three_rentals(*, c_rents: float = 9_000.0) -> list[RentalProperty]:
    return [
        _rental(address="100 Example Street", rents_received=24_000.0,
                mortgage_interest=8_000.0, taxes=3_000.0,
                depreciation=5_000.0),
        _rental(address="200 Example Street", rents_received=12_000.0,
                mortgage_interest=0.0, taxes=2_000.0, depreciation=14_000.0),
        _rental(address="300 Example Street", rents_received=c_rents,
                mortgage_interest=4_000.0, taxes=1_000.0, depreciation=0.0,
                acknowledges_depreciation_stated_outside_macrs=False),
    ]


class ThreePropertyEmitTests(_EmitCase):
    def test_each_column_and_the_totals_print_on_their_widgets(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, rentals=_three_rentals()), f"three{year}")
                addresses = _ADDRESS_ROWS.get(year, _ADDRESS_ROWS_2023_ON)
                line_3 = _LINE_3_2021 if year == 2021 else _LINE_3_2022_ON
                self.assertEqual(
                    [values[p] for p in addresses],
                    ["100 Example Street", "200 Example Street",
                     "300 Example Street"])
                self.assertEqual(
                    [values[p] for p in line_3], ["24000", "12000", "9000"])
                self.assertEqual(
                    [values[p] for p in _LINE_20], ["16000", "16000", "5000"])
                self.assertEqual(
                    [values[p] for p in _LINE_21], ["8000", "-4000", "4000"])
                self.assertEqual(
                    [values[p] for p in _LINE_22], ["", "4000", ""])
                self.assertEqual(values[_LINE_23A], "45000")
                self.assertEqual(values[_LINE_23C], "12000")
                self.assertEqual(values[_LINE_23D], "19000")
                self.assertEqual(values[_LINE_23E], "37000")
                self.assertEqual(values[_LINE_24], "12000")
                self.assertEqual(values[_LINE_25], "4000")
                self.assertEqual(values[_LINE_26], "8000")

    def test_the_return_takes_the_summed_line_26(self):
        # Property C at rents 10,000 nets +5,000, so the page total is
        # 8,000 - 4,000 + 5,000 = 9,000: a figure neither column A alone
        # (8,000) nor A and B together (4,000) produces.
        results = self.orch.compute_federal(
            _scenario(rentals=_three_rentals(c_rents=10_000.0)))
        self.assertEqual(results["sche_line26"], 9_000)

    def test_two_properties_leave_column_c_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                cells = _COLUMN_C_BY_YEAR.get(year, _COLUMN_C_2023_ON)
                two, _ = self._emit_sch_e(
                    _scenario(year, rentals=_three_rentals()[:2]),
                    f"two{year}")
                self.assertEqual(
                    {line for line, path in cells.items() if two[path]},
                    set())
                # Twin: with the third property the same cells fill.
                three, _ = self._emit_sch_e(
                    _scenario(year, rentals=_three_rentals()), f"all{year}")
                self.assertEqual(
                    {line for line, path in cells.items() if three[path]},
                    _COLUMN_C_PRINTED_LINES)


class FourthRentalEmitTests(_EmitCase):
    def test_three_emit_and_four_refuse(self):
        three = _three_rentals()
        values, _ = self._emit_sch_e(_scenario(rentals=three), "three")
        self.assertEqual(values[_LINE_26], "8000")
        four = three + [_rental(address="400 Example Street")]
        with self.assertRaisesRegex(NotImplementedError, r"rental_3"):
            self.orch.compute_federal(_scenario(rentals=four))


class MultiActivityPacketTests(_EmitCase):
    def test_two_rentals_and_a_business_emit_a_complete_packet(self):
        # Two asset-mode rentals, each with a prior-year building (so no
        # Form 4562 is required), and one Schedule C business.
        base = fx.scenario(business_assets=())
        scenario = dataclasses.replace(base, rental_properties=[
            RentalProperty(
                address=address, property_type=1, fair_rental_days=365,
                personal_use_days=0, rents_received=24_000.0,
                depreciable_assets=[building])
            for address, building in (
                ("100 Example Street", fx.BUILDING),
                ("200 Example Street", fx.OLD_BUILDING))])
        plan = self.orch._federal_individual_emit_plan(
            scenario, self.orch.compute_federal(scenario))
        specs = plan.specs
        names = {spec.name for spec in specs}
        self.assertIn("sch_e", names)
        self.assertIn("sch_c_1", names)
        self.assertNotIn("f4562", names)
        (sch_e,) = [spec.values for spec in specs if spec.name == "sch_e"]
        self.assertEqual(sch_e["sch_e_property_a_depreciation"], 7_272)
        self.assertEqual(
            sch_e["sch_e_property_b_depreciation"], fx.OLD_BUILDING_2025)
        out_dir = self.tmp / "packet"
        out_dir.mkdir()
        emitted = self.orch._emit_depreciation_audit(scenario, plan, out_dir)
        self.assertTrue(emitted[depreciation_workbook.EMITTED_KEY].is_file())


if __name__ == "__main__":
    unittest.main()
