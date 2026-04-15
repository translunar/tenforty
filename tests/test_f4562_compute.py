"""forms.f4562.compute — Form 4562 Part III Section B (MACRS by class)."""

import unittest
from datetime import date

from tenforty.forms import f4562 as form_f4562
from tenforty.models import DepreciableAsset
from tests.helpers import make_simple_scenario


def _scenario_with_assets(*assets):
    s = make_simple_scenario()
    s.config.first_name = "Test"
    s.config.last_name = "Filer"
    s.config.ssn = "000-00-0000"
    s.config.year = 2025
    s.depreciable_assets = list(assets)
    return s


class F4562ComputeTests(unittest.TestCase):
    def test_empty_assets_total_zero(self):
        r = form_f4562.compute(_scenario_with_assets(), upstream={})
        self.assertEqual(r["f4562_line_22_total_depreciation"], 0)
        self.assertEqual(r["f4562_part_iii_section_b_rows"], [])

    def test_one_rental_building_emits_19i_row(self):
        asset = DepreciableAsset(
            description="Evans Ave",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        )
        r = form_f4562.compute(_scenario_with_assets(asset), upstream={})
        self.assertEqual(len(r["f4562_part_iii_section_b_rows"]), 1)
        row = r["f4562_part_iii_section_b_rows"][0]
        self.assertEqual(row["row_label"], "i")
        self.assertEqual(row["recovery_class"], "27.5-year")
        self.assertEqual(row["basis"], 200_000.0)
        self.assertEqual(row["deduction"], 6_970)
        self.assertEqual(row["method"], "S/L")
        self.assertEqual(r["f4562_line_19i_basis"], 200_000)
        self.assertEqual(r["f4562_line_19i_deduction"], 6_970)
        self.assertEqual(r["f4562_line_19i_date_placed_in_service"], "01/2025")
        self.assertEqual(r["f4562_line_19i_recovery_period"], "27.5 yrs.")
        self.assertEqual(r["f4562_line_19i_convention"], "MM")
        self.assertEqual(r["f4562_line_19i_method"], "S/L")
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970)

    def test_building_and_laptop_emit_two_rows_summed(self):
        building = DepreciableAsset(
            description="Building",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        )
        laptop = DepreciableAsset(
            description="Laptop",
            date_placed_in_service=date(2025, 3, 1),
            basis=2_500.0,
            recovery_class="5-year",
            convention="half-year",
        )
        r = form_f4562.compute(
            _scenario_with_assets(building, laptop), upstream={},
        )
        # 5-year → 19b, 27.5-year → 19i.
        self.assertEqual(r["f4562_line_19b_basis"], 2_500)
        self.assertEqual(r["f4562_line_19b_deduction"], 500)
        self.assertEqual(r["f4562_line_19b_method"], "200DB")
        self.assertEqual(r["f4562_line_19b_convention"], "HY")
        self.assertEqual(r["f4562_line_19i_basis"], 200_000)
        self.assertEqual(r["f4562_line_19i_deduction"], 6_970)
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970 + 500)

    def test_multiple_5_year_assets_aggregate_into_one_19b_row(self):
        a = DepreciableAsset(
            description="Laptop A", date_placed_in_service=date(2025, 3, 1),
            basis=2_500.0, recovery_class="5-year", convention="half-year",
        )
        b = DepreciableAsset(
            description="Laptop B", date_placed_in_service=date(2025, 7, 1),
            basis=1_500.0, recovery_class="5-year", convention="half-year",
        )
        r = form_f4562.compute(_scenario_with_assets(a, b), upstream={})
        self.assertEqual(len(r["f4562_part_iii_section_b_rows"]), 1)
        # Earliest placement drives the row date.
        self.assertEqual(r["f4562_line_19b_date_placed_in_service"], "03/2025")
        self.assertEqual(r["f4562_line_19b_basis"], 4_000)
        # 20.00% × 4,000 = 800.
        self.assertEqual(r["f4562_line_19b_deduction"], 800)

    def test_identity_fields_from_config(self):
        r = form_f4562.compute(_scenario_with_assets(), upstream={})
        self.assertEqual(r["taxpayer_name"], "Test Filer")
        self.assertEqual(r["taxpayer_ssn"], "000-00-0000")

    def test_propagates_disposition_not_implemented(self):
        a = DepreciableAsset(
            description="Sold asset",
            date_placed_in_service=date(2022, 1, 1),
            basis=10_000.0,
            recovery_class="5-year",
            convention="half-year",
            disposed=date(2025, 6, 1),
        )
        with self.assertRaisesRegex(NotImplementedError, "disposition"):
            form_f4562.compute(_scenario_with_assets(a), upstream={})

    def test_mixed_conventions_in_one_class_raise(self):
        a = DepreciableAsset(
            description="Q1 laptop", date_placed_in_service=date(2025, 2, 1),
            basis=1_000.0, recovery_class="5-year", convention="half-year",
        )
        b = DepreciableAsset(
            description="Q4 laptop", date_placed_in_service=date(2025, 11, 1),
            basis=1_000.0, recovery_class="5-year", convention="mid-quarter",
        )
        with self.assertRaisesRegex(NotImplementedError, "Mixed conventions"):
            form_f4562.compute(_scenario_with_assets(a, b), upstream={})


if __name__ == "__main__":
    unittest.main()
