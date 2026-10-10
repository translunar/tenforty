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


RETURN_YEAR = 2025


def _asset(recovery_class: str, placed: date, basis: float = 10_000.0,
           **stated):
    return DepreciableAsset(
        description="Example asset", date_placed_in_service=placed,
        basis=basis, recovery_class=recovery_class, **stated)


def _deduction(asset, tax_year, *, mid_quarter, return_year=RETURN_YEAR):
    return macrs_deduction(
        asset, tax_year, return_year=return_year, mid_quarter=mid_quarter)


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


class ReturnYearConventionTests(unittest.TestCase):
    """Property placed in the return year: the convention is COMPUTED from
    the return's 40% answer, the quarter from the placement date."""

    def test_personal_property_follows_the_returns_answer(self):
        for cls in PERSONAL_PROPERTY_CLASSES:
            asset = _asset(cls, date(2025, 5, 1))
            with self.subTest(recovery_class=cls):
                self.assertEqual(
                    asset_convention(
                        asset, return_year=2025, mid_quarter=True),
                    (MID_QUARTER, 2))
                self.assertEqual(
                    asset_convention(
                        asset, return_year=2025, mid_quarter=False),
                    (HALF_YEAR, None))

    def test_quarter_is_the_placement_quarter(self):
        for month in range(1, 13):
            with self.subTest(month=month):
                self.assertEqual(
                    asset_convention(
                        _asset("5-year", date(2025, month, 15)),
                        return_year=2025, mid_quarter=True),
                    (MID_QUARTER, (month - 1) // 3 + 1))

    def test_real_property_is_mid_month_whatever_the_answer(self):
        for cls in ("27.5-year", "39-year"):
            for placed_year in (2023, 2025):
                for answer in (True, False):
                    with self.subTest(recovery_class=cls, year=placed_year,
                                      mid_quarter=answer):
                        self.assertEqual(
                            asset_convention(
                                _asset(cls, date(placed_year, 11, 1)),
                                return_year=2025, mid_quarter=answer),
                            (MID_MONTH, None))

    def test_the_answer_must_be_supplied(self):
        """No default: a caller that does not say cannot silently get
        half-year."""
        asset = _asset("5-year", date(2025, 5, 1))
        with self.assertRaises(TypeError):
            asset_convention(asset, return_year=2025)
        with self.assertRaises(TypeError):
            macrs_deduction(asset, 2025, return_year=2025)
        with self.assertRaises(TypeError):
            macrs_deduction(asset, 2025, mid_quarter=False)


class PriorYearConventionTests(unittest.TestCase):
    """Property placed before the return year: the convention and quarter
    are STATED on the asset and the return's own answer is not consulted."""

    def test_stated_convention_is_used_whatever_this_years_answer(self):
        cases = (
            ({"convention": "half-year"}, (HALF_YEAR, None)),
            ({"convention": "mid-quarter", "quarter": 4}, (MID_QUARTER, 4)),
        )
        for stated, expected in cases:
            for answer in (True, False):
                with self.subTest(stated=stated, mid_quarter=answer):
                    self.assertEqual(
                        asset_convention(
                            _asset("5-year", date(2023, 11, 1), **stated),
                            return_year=2025, mid_quarter=answer),
                        expected)

    def test_each_stated_quarter(self):
        for quarter, month in ((1, 2), (2, 5), (3, 8), (4, 11)):
            with self.subTest(quarter=quarter):
                self.assertEqual(
                    asset_convention(
                        _asset("7-year", date(2022, month, 1),
                               convention="mid-quarter", quarter=quarter),
                        return_year=2025, mid_quarter=False),
                    (MID_QUARTER, quarter))

    def test_missing_convention_refuses(self):
        """Fail closed: half-year is never assumed for an earlier year."""
        asset = _asset("5-year", date(2023, 11, 1))
        for answer in (True, False):
            with self.subTest(mid_quarter=answer):
                with self.assertRaisesRegex(
                        ValueError, r"states no `convention`"):
                    asset_convention(
                        asset, return_year=2025, mid_quarter=answer)
                with self.assertRaisesRegex(
                        ValueError, r"states no `convention`"):
                    _deduction(asset, 2025, mid_quarter=answer)

    def test_unusable_stated_values_refuse(self):
        cases = (
            ({"convention": "mid-quarter"}, r"without the `quarter`"),
            ({"convention": "mid-quarter", "quarter": 5}, r"`quarter: 5`"),
            ({"convention": "mid-quarter", "quarter": 0}, r"`quarter: 0`"),
            ({"convention": "half-year", "quarter": 4},
             r"`quarter` with `convention: half-year`"),
            ({"convention": "mid-month"}, r"`convention: mid-month`"),
            ({"convention": "mid-quarter", "quarter": 3},
             r"is in quarter 4"),
        )
        for stated, pattern in cases:
            with self.subTest(stated=stated):
                with self.assertRaisesRegex(ValueError, pattern):
                    asset_convention(
                        _asset("5-year", date(2023, 11, 1), **stated),
                        return_year=2025, mid_quarter=False)

    def test_the_boundary_is_the_return_year_itself(self):
        """Placed in the return year: computed, even if a value is stated
        (the ledger refuses that at load; the engine does not consult it).
        Placed the year before: stated."""
        stated = {"convention": "mid-quarter", "quarter": 4}
        this_year = _asset("5-year", date(2025, 11, 1), **stated)
        last_year = _asset("5-year", date(2024, 11, 1), **stated)
        self.assertEqual(
            asset_convention(this_year, return_year=2025, mid_quarter=False),
            (HALF_YEAR, None))
        self.assertEqual(
            asset_convention(last_year, return_year=2025, mid_quarter=False),
            (MID_QUARTER, 4))


class QuarterTableSelectionTests(unittest.TestCase):
    def test_return_year_asset_reads_its_own_quarter_class_and_year(self):
        with _patched():
            for month in range(1, 13):
                quarter = (month - 1) // 3 + 1
                for cls, class_years in CLASS_YEARS.items():
                    asset = _asset(cls, date(2025, month, 15), 100_000.0)
                    with self.subTest(month=month, recovery_class=cls):
                        self.assertEqual(
                            _deduction(asset, 2025, mid_quarter=True),
                            irs_round(100_000.0 * _sentinel(
                                quarter, class_years, 1)))

    def test_prior_year_asset_reads_its_stated_quarter_class_and_year(self):
        with _patched():
            for quarter, month in ((1, 2), (2, 5), (3, 8), (4, 11)):
                for cls, class_years in CLASS_YEARS.items():
                    for recovery_year in SENTINEL_YEARS:
                        placed = RETURN_YEAR - recovery_year + 1
                        if placed == RETURN_YEAR:
                            continue          # that is the computed path
                        asset = _asset(
                            cls, date(placed, month, 15), 100_000.0,
                            convention="mid-quarter", quarter=quarter)
                        with self.subTest(quarter=quarter, recovery_class=cls,
                                          recovery_year=recovery_year):
                            self.assertEqual(
                                _deduction(
                                    asset, RETURN_YEAR, mid_quarter=False),
                                irs_round(100_000.0 * _sentinel(
                                    quarter, class_years, recovery_year)))

    def test_quarter_boundary_months_read_different_tables(self):
        with _patched():
            for before, after in ((3, 4), (6, 7), (9, 10)):
                with self.subTest(boundary=(before, after)):
                    self.assertNotEqual(
                        _deduction(_asset("5-year", date(2025, before, 28)),
                                   2025, mid_quarter=True),
                        _deduction(_asset("5-year", date(2025, after, 2)),
                                   2025, mid_quarter=True))

    def test_months_inside_one_quarter_read_the_same_table(self):
        with _patched():
            for months in ((1, 2, 3), (4, 5, 6), (7, 8, 9), (10, 11, 12)):
                amounts = {
                    _deduction(_asset("7-year", date(2025, month, 10)),
                               2025, mid_quarter=True)
                    for month in months}
                with self.subTest(months=months):
                    self.assertEqual(len(amounts), 1)

    def test_half_year_asset_does_not_touch_the_quarter_tables(self):
        with mock.patch.object(
                macrs_mid_quarter, "TABLES_BY_QUARTER", None):
            self.assertEqual(
                _deduction(_asset("5-year", date(2025, 11, 15)), 2025,
                           mid_quarter=False), 2_000)
            self.assertEqual(
                _deduction(
                    _asset("5-year", date(2024, 11, 15),
                           convention="half-year"),
                    2025, mid_quarter=True), 3_200)

    def test_real_property_does_not_touch_the_quarter_tables(self):
        building = _asset("27.5-year", date(2025, 11, 15), 200_000.0)
        with mock.patch.object(
                macrs_mid_quarter, "TABLES_BY_QUARTER", None):
            self.assertEqual(
                _deduction(building, 2025, mid_quarter=True),
                _deduction(building, 2025, mid_quarter=False))

    def test_reconstructing_an_earlier_year_uses_the_same_convention(self):
        """The return year decides stated-versus-computed; the year being
        computed only picks the table row."""
        asset = _asset("5-year", date(2023, 8, 1), 3_333.0,
                       convention="mid-quarter", quarter=3)
        with _patched():
            for tax_year, recovery_year in ((2023, 1), (2024, 2), (2025, 3)):
                with self.subTest(tax_year=tax_year):
                    self.assertEqual(
                        _deduction(asset, tax_year, mid_quarter=False),
                        irs_round(3_333.0 * _sentinel(3, 5, recovery_year)))


class ForwardYearShapeTests(unittest.TestCase):
    def test_zero_before_placement_and_after_the_table_ends(self):
        asset = _asset("5-year", date(2021, 8, 1),
                       convention="mid-quarter", quarter=3)
        with _patched():
            self.assertEqual(_deduction(asset, 2020, mid_quarter=False), 0)
            self.assertGreater(_deduction(asset, 2024, mid_quarter=False), 0)
            # The sentinel table ends at recovery year 4.
            self.assertEqual(_deduction(asset, 2025, mid_quarter=False), 0)

    def test_module_exposes_the_convention_names(self):
        self.assertEqual(
            (macrs.HALF_YEAR, macrs.MID_QUARTER, macrs.MID_MONTH),
            ("half-year", "mid-quarter", "mid-month"))


class RealTablesAreWiredTests(unittest.TestCase):
    """Unpatched: the engine reads the landed tables, one per quarter. The
    expected value is READ from the table module, not restated here -- what
    the publication prints is pinned by the dual-transcription test."""

    def test_each_quarter_reads_its_own_landed_table(self):
        for quarter, month in ((1, 2), (2, 5), (3, 8), (4, 11)):
            table = macrs_mid_quarter.TABLES_BY_QUARTER[quarter]
            for cls, class_years in CLASS_YEARS.items():
                asset = _asset(cls, date(2025, month, 15), 100_000.0)
                with self.subTest(quarter=quarter, recovery_class=cls):
                    self.assertEqual(
                        _deduction(asset, 2025, mid_quarter=True),
                        irs_round(100_000.0 * table[class_years][1]))

    def test_last_printed_year_then_zero(self):
        last = {"3-year": 4, "5-year": 6, "7-year": 8, "10-year": 11,
                "15-year": 16, "20-year": 21}
        for cls, last_year in last.items():
            asset = _asset(cls, date(2000, 11, 15), 100_000.0,
                           convention="mid-quarter", quarter=4)
            with self.subTest(recovery_class=cls):
                self.assertGreater(
                    macrs_deduction(asset, 1999 + last_year,
                                    return_year=2040, mid_quarter=False), 0)
                self.assertEqual(
                    macrs_deduction(asset, 2000 + last_year,
                                    return_year=2040, mid_quarter=False), 0)


class MethodLabelTests(unittest.TestCase):
    """The method derives from the CLASS (Publication 946, Chart 1), never
    from the convention."""

    def test_method_by_class(self):
        expected = {"3-year": "200 DB", "5-year": "200 DB", "7-year": "200 DB",
                    "10-year": "200 DB", "15-year": "150 DB",
                    "20-year": "150 DB", "27.5-year": "S/L", "39-year": "S/L"}
        for cls, method in expected.items():
            with self.subTest(recovery_class=cls):
                self.assertEqual(macrs.method_for(cls), method)

    def test_unknown_class_refuses(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"has recovery_class '25-year'"):
            macrs.method_for("25-year")


if __name__ == "__main__":
    unittest.main()
