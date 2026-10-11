"""MACRS table products are rounded from the EXACT decimal product.

A table amount is basis x percentage, rounded half-up to whole dollars. The
percentages are exact 4- and 5-place decimals and a basis is dollars and
cents, so the true product is an exact decimal -- and when it ends in
exactly .50 the amount rounds UP. A binary float cannot hold most of those
products: 25,000 x 0.0197 is 492.50, but as floats it is
492.49999999999994, which rounds down to 492. The engine therefore
multiplies in decimal and never rounds a float product.

EXPECTED VALUES here come from integer arithmetic alone (the percentage as
an integer count of 1/100,000ths, the basis as integer cents), a different
instrument from the decimal arithmetic under test.
"""

import functools
import unittest
from datetime import date
from decimal import Decimal

from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.tables import TABLE_A_1, TABLE_A_6, TABLE_A_7a
from tenforty.models import DepreciableAsset
from tenforty.params.macrs_mid_quarter import TABLES_BY_QUARTER
from tenforty.rounding import irs_round, irs_round_product

RETURN_YEAR = 2025
SCALE = 100_000                 # table percentages have at most 5 places
CLASS_YEARS = {"3-year": 3, "5-year": 5, "7-year": 7, "10-year": 10,
               "15-year": 15, "20-year": 20}
QUARTER_MONTH = {1: 2, 2: 5, 3: 8, 4: 11}


def _rate_units(rate: float) -> int:
    """The percentage as an integer number of 1/100,000ths."""
    units = round(rate * SCALE)
    assert Decimal(units) / SCALE == Decimal(str(rate)), rate
    return units


def _expected(basis_cents: int, rate: float) -> int:
    """Half-up whole dollars of basis x rate, in integers only:
    floor(x + 1/2) with x = basis_cents * units / (100 * SCALE)."""
    denominator = 100 * SCALE
    return (2 * basis_cents * _rate_units(rate) + denominator) // (
        2 * denominator)


@functools.lru_cache(maxsize=None)
def _half_dollar_bases(rate: float, *, limit_cents: int, step_cents: int,
                       want: int) -> tuple[int, ...]:
    """Up to ``want`` bases (in cents, multiples of ``step_cents``) whose
    exact product with ``rate`` ends in exactly .50, found by direct
    search of the congruence basis_cents * units = 1/2 (mod 1 dollar)."""
    units = _rate_units(rate)
    denominator = 100 * SCALE
    found = []
    for basis_cents in range(step_cents, limit_cents + 1, step_cents):
        if (basis_cents * units) % denominator == denominator // 2:
            found.append(basis_cents)
            if len(found) == want:
                break
    return tuple(found)


# Bases every cell is probed with, in cents: small, round, large, and odd
# cents. The .50-boundary bases are derived per percentage on top of these.
GENERAL_BASES_CENTS = (
    1, 99, 100, 35_000, 1_000_000, 2_500_000, 12_345_678, 99_999_999,
    1_234_567_89, 3_117_009, 2_078_006, 50, 150, 33_333)


def _cells():
    """Every table cell the engine can read:
    ``(table, recovery_class, recovery year, month or quarter, rate)``."""
    for cls, years in TABLE_A_1.items():
        for year, rate in years.items():
            yield ("A-1", cls, year, None, rate)
    for quarter, table in TABLES_BY_QUARTER.items():
        for cls, class_years in CLASS_YEARS.items():
            for year, rate in table[class_years].items():
                yield (f"mid-quarter Q{quarter}", cls, year, quarter, rate)
    for name, cls, table in (("A-6", "27.5-year", TABLE_A_6["27.5-year"]),
                             ("A-7a", "39-year", TABLE_A_7a["39-year"])):
        for year, months in table.items():
            for month, rate in months.items():
                yield (name, cls, year, month, rate)


def _engine(table: str, cls: str, recovery_year: int, slot, basis: float):
    """The engine's amount for one table cell, through `macrs_deduction`
    with an asset placed so that RETURN_YEAR is its ``recovery_year``."""
    placed_year = RETURN_YEAR - recovery_year + 1
    stated = {}
    if table == "A-1":
        month, mid_quarter = 6, False
        if recovery_year > 1:
            stated = {"convention": "half-year"}
    elif table.startswith("mid-quarter"):
        month, mid_quarter = QUARTER_MONTH[slot], True
        if recovery_year > 1:
            stated = {"convention": "mid-quarter", "quarter": slot}
    else:
        month, mid_quarter = slot, False
    asset = DepreciableAsset(
        description="Example asset",
        date_placed_in_service=date(placed_year, month, 15),
        basis=basis, recovery_class=cls, **stated)
    return macrs_deduction(
        asset, RETURN_YEAR, return_year=RETURN_YEAR, mid_quarter=mid_quarter)


class NamedReproTests(unittest.TestCase):
    """The three confirmed cases: the exact product ends in .50 and the
    float product falls just under it."""

    def test_residential_june_year_one_basis_25000(self):
        """1.970% x 25,000 = 492.50 exactly -> 493."""
        self.assertLess(25_000.0 * TABLE_A_6["27.5-year"][1][6], 492.5)
        self.assertEqual(_expected(2_500_000, TABLE_A_6["27.5-year"][1][6]), 493)
        self.assertEqual(_engine("A-6", "27.5-year", 1, 6, 25_000.0), 493)

    def test_nonresidential_may_year_one_basis_10000(self):
        """1.605% x 10,000 = 160.50 exactly -> 161."""
        self.assertLess(10_000.0 * TABLE_A_7a["39-year"][1][5], 160.5)
        self.assertEqual(_expected(1_000_000, TABLE_A_7a["39-year"][1][5]), 161)
        self.assertEqual(_engine("A-7a", "39-year", 1, 5, 10_000.0), 161)

    def test_five_year_mid_quarter_first_quarter_basis_350(self):
        """35.00% x 350 = 122.50 exactly -> 123."""
        self.assertLess(350.0 * TABLES_BY_QUARTER[1][5][1], 122.5)
        self.assertEqual(_expected(35_000, TABLES_BY_QUARTER[1][5][1]), 123)
        self.assertEqual(
            _engine("mid-quarter Q1", "5-year", 1, 1, 350.0), 123)


class ProductRoundingTests(unittest.TestCase):
    def test_exact_half_rounds_up(self):
        self.assertEqual(irs_round_product(25_000.0, 0.0197), 493)
        self.assertEqual(irs_round_product(10_000.0, 0.01605), 161)
        self.assertEqual(irs_round_product(350.0, 0.35), 123)

    def test_one_cent_either_side_of_the_half(self):
        # 0.35 x 350.00 = 122.50; a cent of basis moves the product 0.0035.
        self.assertEqual(irs_round_product(349.99, 0.35), 122)   # 122.4965
        self.assertEqual(irs_round_product(350.01, 0.35), 123)   # 122.5035

    def test_ordinary_products(self):
        self.assertEqual(irs_round_product(10_000.0, 0.2), 2_000)
        self.assertEqual(irs_round_product(200_000.0, 0.03485), 6_970)
        self.assertEqual(irs_round_product(3_333.0, 0.1152), 384)  # 383.96
        self.assertEqual(irs_round_product(0.0, 0.2), 0)
        self.assertEqual(irs_round_product(10_000.0, 0.0), 0)

    def test_result_is_a_plain_int(self):
        self.assertIs(type(irs_round_product(350.0, 0.35)), int)

    def test_large_and_cent_valued_bases_stay_exact(self):
        # 12,345,678,901.23 x 0.03636 = 448,888,884.8487228 -> ...885
        self.assertEqual(
            irs_round_product(12_345_678_901.23, 0.03636), 448_888_885)
        self.assertEqual(
            _expected(1_234_567_890_123, 0.03636), 448_888_885)

    def test_amount_is_read_as_the_decimal_it_was_written_as(self):
        """2.40 x 0.625 = 1.50 exactly -> 2. The float nearest 2.40 is a
        hair under it, so taking the amount's binary value instead of its
        written decimal would put the product under the half. (No table
        percentage reaches this. With these tables a product lands on a
        half dollar at whole-dollar bases and at a few quarter-dollar ones
        -- 8% of 6.25, 14.4% of 31.25, 10.56% of 156.25 -- and a float
        holds every one of those bases exactly, so reading the binary value
        changes nothing there. The helper is general, so the hazard is
        pinned at a general rate.)"""
        self.assertLess(Decimal(2.4), Decimal("2.4"))
        self.assertEqual(irs_round_product(2.4, 0.625), 2)
        self.assertEqual(irs_round_product(2.39, 0.625), 1)

    def test_quarter_dollar_half_products_are_binary_exact(self):
        """The claim above, checked: these land on a half dollar and their
        bases are exact in binary."""
        for basis, rate, expected in ((6.25, 0.08, 1), (31.25, 0.144, 5),
                                      (31.25, 0.112, 4),
                                      (156.25, 0.1056, 17),
                                      (156.25, 0.1184, 19),
                                      (156.25, 0.1248, 20)):
            with self.subTest(basis=basis, rate=rate):
                self.assertEqual(Decimal(basis), Decimal(str(basis)))
                self.assertEqual(
                    (round(basis * 100) * _rate_units(rate)) % (100 * SCALE),
                    50 * SCALE)
                self.assertEqual(irs_round_product(basis, rate), expected)
                self.assertEqual(
                    _expected(round(basis * 100), rate), expected)

    def test_too_little_precision_would_round_the_product_itself(self):
        """138,538,308.63 x 0.07219 = 10,001,080.4999997 exactly -> ...080.
        Fifteen significant digits sit ahead of the deciding 7; a
        multiplication that keeps 14 or fewer rounds the product up to
        ...080.5 first and then prints ...081."""
        self.assertEqual(13_853_830_863 * 7_219, 100_010_804_999_997)
        self.assertEqual(_expected(13_853_830_863, 0.07219), 10_001_080)
        self.assertEqual(
            irs_round_product(138_538_308.63, 0.07219), 10_001_080)

    def test_long_products_are_not_shortened_before_rounding(self):
        """100,000,000,025,000 x 0.0197 = 1,970,000,000,492.50 -> ...493:
        fourteen significant digits ahead of the half."""
        self.assertEqual(
            irs_round_product(100_000_000_025_000.0, 0.0197),
            1_970_000_000_493)
        self.assertEqual(
            _expected(100_000_000_025_000 * 100, 0.0197), 1_970_000_000_493)

    def test_agrees_with_plain_rounding_away_from_the_half(self):
        """Where the product is not on a half dollar the old float path was
        already right; the two agree there."""
        for basis in (1.0, 99.0, 1_234.56, 77_777.77, 200_000.0):
            for rate in (0.2, 0.0197, 0.03636, 0.04462, 0.5833):
                if (round(basis * 100) * _rate_units(rate)) % (
                        100 * SCALE) == 50 * SCALE:
                    continue
                with self.subTest(basis=basis, rate=rate):
                    self.assertEqual(
                        irs_round_product(basis, rate),
                        irs_round(basis * rate))


class TableWideSweepTests(unittest.TestCase):
    """Every class x recovery year x month/quarter cell, through the
    engine, at the general probe bases and at bases built to land the
    exact product on a half dollar."""

    def _bases_for(self, rate: float) -> list[int]:
        whole_dollar = _half_dollar_bases(
            rate, limit_cents=20_000_000, step_cents=100, want=4)
        any_cent = _half_dollar_bases(
            rate, limit_cents=2_000_000, step_cents=1, want=4)
        return sorted(set(GENERAL_BASES_CENTS) | set(whole_dollar)
                      | set(any_cent))

    def test_every_cell_matches_integer_arithmetic(self):
        checked = 0
        for table, cls, year, slot, rate in _cells():
            for basis_cents in self._bases_for(rate):
                checked += 1
                with self.subTest(table=table, recovery_class=cls, year=year,
                                  slot=slot, basis_cents=basis_cents):
                    self.assertEqual(
                        _engine(table, cls, year, slot, basis_cents / 100),
                        _expected(basis_cents, rate))
        self.assertGreater(checked, 10_000)

    def test_the_sweep_reaches_the_hazard_in_every_table_family(self):
        """Reachability: the sweep above is only a test of this fix if it
        includes products that are exactly on a half dollar AND that a
        float product would round the wrong way -- in each table family."""
        on_the_half: dict[str, int] = {}
        float_wrong: dict[str, int] = {}
        for table, _cls, _year, _slot, rate in _cells():
            family = "mid-quarter" if table.startswith("mid-quarter") else table
            for basis_cents in self._bases_for(rate):
                if (basis_cents * _rate_units(rate)) % (
                        100 * SCALE) != 50 * SCALE:
                    continue
                on_the_half[family] = on_the_half.get(family, 0) + 1
                if irs_round(basis_cents / 100 * rate) != _expected(
                        basis_cents, rate):
                    float_wrong[family] = float_wrong.get(family, 0) + 1
        for family in ("A-1", "mid-quarter", "A-6", "A-7a"):
            with self.subTest(family=family):
                self.assertGreater(on_the_half.get(family, 0), 50)
                self.assertGreater(float_wrong.get(family, 0), 0)


if __name__ == "__main__":
    unittest.main()
