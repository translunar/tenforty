"""The mid-quarter convention in the per-asset engine: which convention an
asset takes, which quarter's table it reads, and the forward-year shape.

WIRING ONLY. Every percentage in this module is a SENTINEL patched over the
real tables -- a made-up number that encodes (quarter, class, recovery year)
so a wrong lookup is visible. Nothing here says what Publication 946 prints;
the published values are pinned by tests/test_macrs_mid_quarter_table_
attestation.py and the worked-example battery is authored separately.
"""

import unittest
from datetime import date
from unittest import mock

from tenforty.forms.depreciation import macrs
from tenforty.forms.depreciation.macrs import (
    HALF_YEAR, MID_MONTH, MID_QUARTER, asset_convention, macrs_deduction,
    placement_quarter,
)
from tenforty.models import PERSONAL_PROPERTY_CLASSES, DepreciableAsset
from tenforty.params import macrs_mid_quarter
from tenforty.rounding import irs_round

CLASS_YEARS = {"3-year": 3, "5-year": 5, "7-year": 7, "10-year": 10,
               "15-year": 15, "20-year": 20}
SENTINEL_YEARS = range(1, 5)


def _sentinel(quarter: int, class_years: int, recovery_year: int) -> float:
    """A made-up percentage unique to its (quarter, class, year) cell."""
    return quarter / 10 + class_years / 1_000 + recovery_year / 100_000


SENTINEL_TABLES = {
    quarter: {
        class_years: {
            year: _sentinel(quarter, class_years, year)
            for year in SENTINEL_YEARS}
        for class_years in CLASS_YEARS.values()}
    for quarter in (1, 2, 3, 4)}


def _patched():
    return mock.patch.object(
        macrs_mid_quarter, "TABLES_BY_QUARTER", SENTINEL_TABLES)


def _asset(recovery_class: str, placed: date, basis: float = 10_000.0):
    return DepreciableAsset(
        description="Example asset", date_placed_in_service=placed,
        basis=basis, recovery_class=recovery_class)


class PlacementQuarterTests(unittest.TestCase):
    def test_every_month(self):
        expected = {1: 1, 2: 1, 3: 1, 4: 2, 5: 2, 6: 2,
                    7: 3, 8: 3, 9: 3, 10: 4, 11: 4, 12: 4}
        for month, quarter in expected.items():
            with self.subTest(month=month):
                self.assertEqual(
                    placement_quarter(date(2025, month, 15)), quarter)

    def test_first_and_last_day_of_each_quarter(self):
        edges = {1: (date(2025, 1, 1), date(2025, 3, 31)),
                 2: (date(2025, 4, 1), date(2025, 6, 30)),
                 3: (date(2025, 7, 1), date(2025, 9, 30)),
                 4: (date(2025, 10, 1), date(2025, 12, 31))}
        for quarter, days in edges.items():
            for day in days:
                with self.subTest(day=day):
                    self.assertEqual(placement_quarter(day), quarter)


class ConventionSelectionTests(unittest.TestCase):
    def test_personal_property_in_a_mid_quarter_year(self):
        for cls in PERSONAL_PROPERTY_CLASSES:
            with self.subTest(recovery_class=cls):
                self.assertEqual(
                    asset_convention(
                        _asset(cls, date(2025, 5, 1)),
                        mid_quarter_years=frozenset({2025})),
                    MID_QUARTER)

    def test_personal_property_in_any_other_year_is_half_year(self):
        for years in (frozenset(), frozenset({2024}), frozenset({2026})):
            with self.subTest(mid_quarter_years=sorted(years)):
                self.assertEqual(
                    asset_convention(
                        _asset("5-year", date(2025, 5, 1)),
                        mid_quarter_years=years),
                    HALF_YEAR)

    def test_the_year_that_matters_is_the_placement_year(self):
        """An asset placed in 2023 is mid-quarter only if 2023 is."""
        old = _asset("5-year", date(2023, 11, 1))
        self.assertEqual(
            asset_convention(old, mid_quarter_years=frozenset({2025})),
            HALF_YEAR)
        self.assertEqual(
            asset_convention(old, mid_quarter_years=frozenset({2023})),
            MID_QUARTER)

    def test_real_property_is_mid_month_whatever_the_year(self):
        for cls in ("27.5-year", "39-year"):
            for years in (frozenset(), frozenset({2025})):
                with self.subTest(recovery_class=cls, years=sorted(years)):
                    self.assertEqual(
                        asset_convention(
                            _asset(cls, date(2025, 11, 1)),
                            mid_quarter_years=years),
                        MID_MONTH)

    def test_the_answer_must_be_supplied(self):
        """No default: a caller that does not say which years are
        mid-quarter cannot silently get half-year."""
        asset = _asset("5-year", date(2025, 5, 1))
        with self.assertRaises(TypeError):
            asset_convention(asset)
        with self.assertRaises(TypeError):
            macrs_deduction(asset, 2025)


class QuarterTableSelectionTests(unittest.TestCase):
    def test_each_asset_reads_its_own_quarter_class_and_year(self):
        with _patched():
            for month in range(1, 13):
                quarter = (month - 1) // 3 + 1
                for cls, class_years in CLASS_YEARS.items():
                    asset = _asset(cls, date(2025, month, 15), 100_000.0)
                    for recovery_year in SENTINEL_YEARS:
                        with self.subTest(month=month, recovery_class=cls,
                                          recovery_year=recovery_year):
                            self.assertEqual(
                                macrs_deduction(
                                    asset, 2025 + recovery_year - 1,
                                    mid_quarter_years=frozenset({2025})),
                                irs_round(100_000.0 * _sentinel(
                                    quarter, class_years, recovery_year)))

    def test_quarter_boundary_months_read_different_tables(self):
        with _patched():
            for before, after in ((3, 4), (6, 7), (9, 10)):
                with self.subTest(boundary=(before, after)):
                    self.assertNotEqual(
                        macrs_deduction(
                            _asset("5-year", date(2025, before, 28)), 2025,
                            mid_quarter_years=frozenset({2025})),
                        macrs_deduction(
                            _asset("5-year", date(2025, after, 2)), 2025,
                            mid_quarter_years=frozenset({2025})))

    def test_months_inside_one_quarter_read_the_same_table(self):
        with _patched():
            for months in ((1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)):
                amounts = {
                    macrs_deduction(
                        _asset("7-year", date(2025, month, 10)), 2025,
                        mid_quarter_years=frozenset({2025}))
                    for month in months}
                with self.subTest(months=months):
                    self.assertEqual(len(amounts), 1)

    def test_half_year_asset_does_not_touch_the_quarter_tables(self):
        """Same asset, placement year not mid-quarter: the half-year table
        answers and the quarter tables are never read."""
        asset = _asset("5-year", date(2025, 11, 15))
        with mock.patch.object(
                macrs_mid_quarter, "TABLES_BY_QUARTER", None):
            half_year = macrs_deduction(
                asset, 2025, mid_quarter_years=frozenset())
        self.assertEqual(half_year, 2_000)
        with _patched():
            self.assertNotEqual(
                macrs_deduction(
                    asset, 2025, mid_quarter_years=frozenset({2025})),
                half_year)

    def test_real_property_does_not_touch_the_quarter_tables(self):
        building = _asset("27.5-year", date(2025, 11, 15), 200_000.0)
        with mock.patch.object(
                macrs_mid_quarter, "TABLES_BY_QUARTER", None):
            self.assertEqual(
                macrs_deduction(
                    building, 2025, mid_quarter_years=frozenset({2025})),
                macrs_deduction(
                    building, 2025, mid_quarter_years=frozenset()))


class ForwardYearShapeTests(unittest.TestCase):
    def test_each_year_is_rounded_on_its_own(self):
        # 3,333 x the sentinel is fractional in every year.
        asset = _asset("5-year", date(2025, 8, 1), 3_333.0)
        with _patched():
            for recovery_year in SENTINEL_YEARS:
                with self.subTest(recovery_year=recovery_year):
                    self.assertEqual(
                        macrs_deduction(
                            asset, 2024 + recovery_year,
                            mid_quarter_years=frozenset({2025})),
                        irs_round(3_333.0 * _sentinel(3, 5, recovery_year)))

    def test_zero_before_placement_and_after_the_table_ends(self):
        asset = _asset("5-year", date(2025, 8, 1))
        with _patched():
            self.assertEqual(
                macrs_deduction(
                    asset, 2024, mid_quarter_years=frozenset({2025})), 0)
            self.assertGreater(
                macrs_deduction(
                    asset, 2028, mid_quarter_years=frozenset({2025})), 0)
            # The sentinel table ends at recovery year 4.
            self.assertEqual(
                macrs_deduction(
                    asset, 2029, mid_quarter_years=frozenset({2025})), 0)

    def test_module_exposes_the_convention_names(self):
        self.assertEqual(
            (macrs.HALF_YEAR, macrs.MID_QUARTER, macrs.MID_MONTH),
            ("half-year", "mid-quarter", "mid-month"))


if __name__ == "__main__":
    unittest.main()
