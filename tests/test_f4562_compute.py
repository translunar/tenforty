"""forms.f4562.compute — Form 4562 Part III MACRS."""

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
        self.assertEqual(r["f4562_part_iii_macrs_assets"], [])

    def test_one_rental_building_first_year_january(self):
        asset = DepreciableAsset(
            description="Evans Ave",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        )
        r = form_f4562.compute(_scenario_with_assets(asset), upstream={})
        self.assertEqual(len(r["f4562_part_iii_macrs_assets"]), 1)
        row = r["f4562_part_iii_macrs_assets"][0]
        self.assertEqual(row["description"], "Evans Ave")
        self.assertEqual(row["basis"], 200_000.0)
        self.assertEqual(row["deduction"], 6_970)
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970)

    def test_multiple_assets_sum_to_line_22(self):
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
        # Building 6,970; laptop 20.00% × 2,500 = 500.
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970 + 500)

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

    def test_overflow_beyond_7_slots_is_caught_at_pdf_fill_not_compute(self):
        """Compute accepts >7 assets and returns the full list. OverflowError
        is raised by the PDF filler (tested separately in Task 17)."""
        assets = [
            DepreciableAsset(
                description=f"Asset {i}",
                date_placed_in_service=date(2024, 1, 1),
                basis=1_000.0,
                recovery_class="5-year",
                convention="half-year",
            )
            for i in range(8)
        ]
        r = form_f4562.compute(_scenario_with_assets(*assets), upstream={})
        self.assertEqual(len(r["f4562_part_iii_macrs_assets"]), 8)


if __name__ == "__main__":
    unittest.main()
