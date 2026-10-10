"""forms.depreciation.macrs — per-asset per-year MACRS deduction.

The dollar figures pinned here are LEGACY regression pins carried over from
the pre-wire-through version of this file (same asset inputs, minus the
deleted `convention` field). They are not hand oracles: the Pub 946
worked-example battery is authored separately, air-gapped from this module.
"""

import unittest
from datetime import date

from tenforty.forms.depreciation.macrs import convention_for, macrs_deduction
from tenforty.models import DepreciableAsset


def _asset(recovery_class: str, placed: date, basis: float, **extra):
    return DepreciableAsset(
        description="Example asset", date_placed_in_service=placed,
        basis=basis, recovery_class=recovery_class, **extra)


class ConventionIsComputedTests(unittest.TestCase):
    def test_real_property_is_mid_month(self):
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                self.assertEqual(convention_for(cls, mid_quarter=False), "mid-month")

    def test_personal_property_is_half_year(self):
        for cls in ("3-year", "5-year", "7-year", "10-year", "15-year",
                    "20-year"):
            with self.subTest(recovery_class=cls):
                self.assertEqual(convention_for(cls, mid_quarter=False), "half-year")

    def test_unknown_class_refuses(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"has recovery_class '25-year'"):
            convention_for("25-year", mid_quarter=False)


class MacrsDeductionTests(unittest.TestCase):
    def test_5_year_year_2_deduction(self):
        a = _asset("5-year", date(2023, 3, 15), 10_000.0)
        self.assertEqual(macrs_deduction(a, tax_year=2024, mid_quarter_years=frozenset()), 3_200)

    def test_27_5_year_first_year_january(self):
        a = _asset("27.5-year", date(2025, 1, 15), 200_000.0)
        self.assertEqual(macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset()), 6_970)

    def test_39_year_first_year_june(self):
        a = _asset("39-year", date(2025, 6, 1), 500_000.0)
        self.assertEqual(macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset()), 6_955)

    def test_placement_month_changes_a_real_property_first_year(self):
        """Mid-month is live: the same building placed in a different month
        of the same year takes a different first-year amount."""
        january = _asset("27.5-year", date(2025, 1, 15), 200_000.0)
        october = _asset("27.5-year", date(2025, 10, 15), 200_000.0)
        self.assertGreater(
            macrs_deduction(january, 2025, mid_quarter_years=frozenset()), macrs_deduction(october, 2025, mid_quarter_years=frozenset()))

    def test_placement_month_does_not_change_personal_property(self):
        """Half-year is live: placement month within the year is ignored."""
        february = _asset("5-year", date(2023, 2, 1), 10_000.0)
        september = _asset("5-year", date(2023, 9, 1), 10_000.0)
        for year in (2023, 2024):
            with self.subTest(year=year):
                self.assertEqual(
                    macrs_deduction(february, year, mid_quarter_years=frozenset()),
                    macrs_deduction(september, year, mid_quarter_years=frozenset()))
        self.assertGreater(macrs_deduction(february, 2023, mid_quarter_years=frozenset()), 0)

    def test_returns_zero_before_placed_in_service(self):
        a = _asset("5-year", date(2026, 1, 1), 10_000.0)
        self.assertEqual(macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset()), 0)

    def test_returns_zero_past_end_of_recovery_period(self):
        a = _asset("5-year", date(2015, 3, 15), 10_000.0)
        # Twin: the same asset inside its recovery period is nonzero.
        self.assertGreater(macrs_deduction(a, tax_year=2016, mid_quarter_years=frozenset()), 0)
        self.assertEqual(macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset()), 0)

    def test_disposed_asset_refuses_with_the_ledger_message(self):
        a = _asset("5-year", date(2023, 1, 10), 10_000.0,
                   disposed=date(2025, 8, 14))
        with self.assertRaisesRegex(
                NotImplementedError,
                r"asset 'Example asset' is marked `disposed`.*"
                r"partial dispositions"):
            macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset())

    def test_unknown_class_refuses_with_the_ledger_message(self):
        a = _asset("25-year", date(2023, 1, 10), 10_000.0)
        with self.assertRaisesRegex(
                NotImplementedError,
                r"asset 'Example asset' has recovery_class '25-year'.*"
                r"never approximated"):
            macrs_deduction(a, tax_year=2025, mid_quarter_years=frozenset())


if __name__ == "__main__":
    unittest.main()
