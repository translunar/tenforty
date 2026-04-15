"""Cell-by-cell oracle test: regenerate each MACRS table from first
principles and diff every cell against the hand-keyed literals in
forms.depreciation.tables.

Marked @pytest.mark.oracle — the MACRS tables are year-stable (statutory),
so this need only run on checkin / pre-release, not every commit. Any
single-cell diff fails with a table/class/year/month-specific error."""

import unittest

import pytest

from tenforty.forms.depreciation import tables as T
from tenforty.forms.depreciation.table_generator import (
    generate_table_a_1,
    generate_table_a_6,
    generate_table_a_7a,
)


# Pub 946 hand-balances columns by alternating last-digit rounding
# (3.636/3.637 in A-6 middle rows, 5.90/5.91 in A-1 15-year, etc.) so
# each column sums to exactly 100.000%. The algorithmic generator
# can't replicate that balancing — each cell is rounded independently —
# so we tolerate up to 1.5e-4 per cell. This still catches gross keying
# bugs (digit transpositions, wrong order of magnitude, missing rows).
TOLERANCE = 1.5e-4


@pytest.mark.oracle
class TableA1OracleTests(unittest.TestCase):
    def test_regenerates_cell_for_cell(self):
        generated = generate_table_a_1()
        self.assertEqual(
            set(generated.keys()), set(T.TABLE_A_1.keys()),
            f"TABLE_A_1 class-set mismatch: missing={set(T.TABLE_A_1) - set(generated)}; "
            f"extra={set(generated) - set(T.TABLE_A_1)}",
        )
        for cls, expected_rows in T.TABLE_A_1.items():
            gen_rows = generated[cls]
            self.assertEqual(
                set(gen_rows.keys()), set(expected_rows.keys()),
                f"TABLE_A_1[{cls!r}] year-set mismatch",
            )
            for year, expected in expected_rows.items():
                with self.subTest(cls=cls, year=year):
                    self.assertAlmostEqual(
                        gen_rows[year], expected, delta=TOLERANCE,
                        msg=(f"TABLE_A_1[{cls!r}][{year}]: "
                             f"hand-keyed={expected!r} generated={gen_rows[year]!r}"),
                    )


@pytest.mark.oracle
class TableA6OracleTests(unittest.TestCase):
    def test_regenerates_cell_for_cell(self):
        generated = generate_table_a_6()
        self.assertEqual(set(generated.keys()), set(T.TABLE_A_6.keys()))
        for cls, expected_years in T.TABLE_A_6.items():
            for year, expected_months in expected_years.items():
                for month, expected in expected_months.items():
                    with self.subTest(cls=cls, year=year, month=month):
                        actual = generated[cls][year][month]
                        self.assertAlmostEqual(
                            actual, expected, delta=TOLERANCE,
                            msg=(f"TABLE_A_6[{cls!r}][{year}][{month}]: "
                                 f"hand-keyed={expected!r} generated={actual!r}"),
                        )


@pytest.mark.oracle
class TableA7aOracleTests(unittest.TestCase):
    def test_regenerates_cell_for_cell(self):
        generated = generate_table_a_7a()
        self.assertEqual(set(generated.keys()), set(T.TABLE_A_7a.keys()))
        for cls, expected_years in T.TABLE_A_7a.items():
            for year, expected_months in expected_years.items():
                for month, expected in expected_months.items():
                    with self.subTest(cls=cls, year=year, month=month):
                        actual = generated[cls][year][month]
                        self.assertAlmostEqual(
                            actual, expected, delta=TOLERANCE,
                            msg=(f"TABLE_A_7a[{cls!r}][{year}][{month}]: "
                                 f"hand-keyed={expected!r} generated={actual!r}"),
                        )


if __name__ == "__main__":
    unittest.main()
