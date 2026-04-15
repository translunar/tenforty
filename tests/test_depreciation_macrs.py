"""forms.depreciation.macrs — per-asset per-year MACRS deduction."""

import unittest
from datetime import date

from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.models import DepreciableAsset


class MacrsDeductionTests(unittest.TestCase):
    def test_5_year_year_2_deduction_half_year_convention(self):
        a = DepreciableAsset(
            description="Office equipment",
            date_placed_in_service=date(2023, 3, 15),
            basis=10_000.0,
            recovery_class="5-year",
            convention="half-year",
        )
        # 32.00% × 10,000 = 3,200.
        self.assertEqual(macrs_deduction(a, tax_year=2024), 3_200)

    def test_27_5_year_first_year_january_mid_month(self):
        a = DepreciableAsset(
            description="Evans Ave building",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        )
        # 3.485% × 200,000 = 6,970.
        self.assertEqual(macrs_deduction(a, tax_year=2025), 6_970)

    def test_39_year_first_year_june_mid_month(self):
        a = DepreciableAsset(
            description="Commercial building",
            date_placed_in_service=date(2025, 6, 1),
            basis=500_000.0,
            recovery_class="39-year",
            convention="mid-month",
        )
        # 1.391% × 500,000 = 6,955.
        self.assertEqual(macrs_deduction(a, tax_year=2025), 6_955)

    def test_returns_zero_before_placed_in_service(self):
        a = DepreciableAsset(
            description="Not yet placed in service",
            date_placed_in_service=date(2026, 1, 1),
            basis=10_000.0,
            recovery_class="5-year",
            convention="half-year",
        )
        self.assertEqual(macrs_deduction(a, tax_year=2025), 0)

    def test_returns_zero_past_end_of_recovery_period(self):
        a = DepreciableAsset(
            description="Fully depreciated",
            date_placed_in_service=date(2015, 3, 15),
            basis=10_000.0,
            recovery_class="5-year",
            convention="half-year",
        )
        self.assertEqual(macrs_deduction(a, tax_year=2025), 0)

    def test_mid_quarter_convention_raises_not_implemented(self):
        a = DepreciableAsset(
            description="Equipment placed Q4",
            date_placed_in_service=date(2024, 11, 15),
            basis=50_000.0,
            recovery_class="5-year",
            convention="mid-quarter",
        )
        with self.assertRaisesRegex(NotImplementedError, "mid-quarter"):
            macrs_deduction(a, tax_year=2025)

    def test_disposition_raises_not_implemented(self):
        a = DepreciableAsset(
            description="Sold mid-year",
            date_placed_in_service=date(2023, 1, 10),
            basis=10_000.0,
            recovery_class="5-year",
            convention="half-year",
            disposed=date(2025, 8, 14),
        )
        with self.assertRaisesRegex(NotImplementedError, "disposition proration"):
            macrs_deduction(a, tax_year=2025)

    def test_unknown_convention_raises_value_error(self):
        a = DepreciableAsset(
            description="Bad convention",
            date_placed_in_service=date(2024, 1, 1),
            basis=10_000.0,
            recovery_class="5-year",
            convention="quarter-year",
        )
        with self.assertRaisesRegex(ValueError, "quarter-year"):
            macrs_deduction(a, tax_year=2025)

    def test_personal_property_with_mid_month_convention_raises(self):
        """5-year property cannot use mid-month (a real-property convention).

        Law 2: v1 refuses to silently zero the deduction for a class/
        convention combo it has no table for. The only legitimate 0-return
        paths are "not yet placed in service" and "past end of schedule
        for a KNOWN class."
        """
        a = DepreciableAsset(
            description="5-year asset marked mid-month (invalid)",
            date_placed_in_service=date(2024, 1, 15),
            basis=10_000.0,
            recovery_class="5-year",
            convention="mid-month",
        )
        with self.assertRaisesRegex(NotImplementedError, "MACRS table missing"):
            macrs_deduction(a, tax_year=2024)


if __name__ == "__main__":
    unittest.main()
