"""Schedule 2 compute: component presence, subtotals, per-year Part I layout.

Synthetic values only. The amounts are arbitrary round numbers chosen to make
each line distinguishable; they are not tax computations."""
import dataclasses
import unittest

from tenforty.forms import sch_2
from tests.helpers import make_simple_scenario


def _scn(year: int):
    base = make_simple_scenario()
    return dataclasses.replace(
        base, config=dataclasses.replace(base.config, year=year))


class Sch2ComputeTests(unittest.TestCase):
    def test_part_ii_components_and_total(self):
        out = sch_2.compute(_scn(2023), {"f1040": {
            "f8962_repayment": 0, "sch_se_line_12_se_tax": 700,
            "f8959_tax_total": 30}})
        self.assertEqual(out["sch_2_line_4_se_tax"], 700)
        self.assertEqual(out["sch_2_line_11_additional_medicare_tax"], 30)
        self.assertEqual(out["sch_2_line_21_total_other_taxes"], 730)
        self.assertEqual(out["sch_2_line_3_part_i_total"], 0)

    def test_zero_components_are_omitted_but_totals_always_present(self):
        out = sch_2.compute(_scn(2023), {"f1040": {
            "f8962_repayment": 0, "sch_se_line_12_se_tax": 0,
            "f8959_tax_total": 0}})
        for absent in ("sch_2_line_2_excess_aptc_repayment",
                       "sch_2_line_4_se_tax",
                       "sch_2_line_11_additional_medicare_tax"):
            self.assertNotIn(absent, out)
        self.assertEqual(out["sch_2_line_3_part_i_total"], 0)
        self.assertEqual(out["sch_2_line_21_total_other_taxes"], 0)

    def test_repayment_prints_on_line_2_in_2022_and_2023(self):
        for year in (2022, 2023):
            with self.subTest(year=year):
                out = sch_2.compute(_scn(year), {"f1040": {
                    "f8962_repayment": 450}})
                self.assertEqual(out["sch_2_line_2_excess_aptc_repayment"], 450)
                self.assertEqual(out["sch_2_line_3_part_i_total"], 450)
                self.assertNotIn("sch_2_line_1a_excess_aptc_repayment", out)
                self.assertNotIn("sch_2_line_1z_total_additions", out)

    def test_repayment_prints_on_lines_1a_and_1z_in_2024_and_2025(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                out = sch_2.compute(_scn(year), {"f1040": {
                    "f8962_repayment": 450}})
                self.assertEqual(out["sch_2_line_1a_excess_aptc_repayment"], 450)
                self.assertEqual(out["sch_2_line_1z_total_additions"], 450)
                self.assertEqual(out["sch_2_line_3_part_i_total"], 450)
                self.assertNotIn("sch_2_line_2_excess_aptc_repayment", out)

    def test_line_11_fills_whenever_the_form_8959_total_is_present(self):
        # No end-to-end battery scenario can reach line 11: a single-filer
        # Schedule C return large enough to owe Additional Medicare Tax also
        # exceeds the Form 8995 threshold and refuses. This is the wiring's
        # coverage: upstream key present -> line 11 fills and joins line 21.
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                out = sch_2.compute(_scn(year), {"f1040": {
                    "sch_se_line_12_se_tax": 500, "f8959_tax_total": 120}})
                self.assertEqual(
                    out["sch_2_line_11_additional_medicare_tax"], 120)
                self.assertEqual(out["sch_2_line_4_se_tax"], 500)
                self.assertEqual(out["sch_2_line_21_total_other_taxes"], 620)

    def test_workbook_shaped_results_without_se_key(self):
        # The XLSX workbook path produces no sch_se_line_12_se_tax key at all.
        out = sch_2.compute(_scn(2025), {"f1040": {
            "f8962_repayment": 0, "f8959_tax_total": 90}})
        self.assertNotIn("sch_2_line_4_se_tax", out)
        self.assertEqual(out["sch_2_line_21_total_other_taxes"], 90)

    def test_none_components_are_treated_as_zero(self):
        out = sch_2.compute(_scn(2025), {"f1040": {
            "f8962_repayment": None, "f8959_tax_total": None}})
        self.assertEqual(out["sch_2_line_3_part_i_total"], 0)
        self.assertEqual(out["sch_2_line_21_total_other_taxes"], 0)

    def test_header_keys_present(self):
        out = sch_2.compute(_scn(2025), {"f1040": {}})
        self.assertIn("taxpayer_name", out)
        self.assertIn("taxpayer_ssn", out)

    def test_unsupported_year_raises(self):
        with self.assertRaises(ValueError) as ctx:
            sch_2.compute(_scn(2021), {"f1040": {}})
        self.assertIn("2021", str(ctx.exception))

    def test_layout_table_covers_exactly_2022_through_2025(self):
        self.assertEqual(sorted(sch_2.PART_I_LAYOUT), [2022, 2023, 2024, 2025])


if __name__ == "__main__":
    unittest.main()
