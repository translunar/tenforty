"""Spot-check hand-keyed MACRS tables. Exhaustive verification lives in
test_depreciation_table_generator.py (Task 12)."""

import unittest

from tenforty.forms.depreciation.tables import (
    TABLE_A_1, TABLE_A_6, TABLE_A_7a,
)


class TableA1SpotCheckTests(unittest.TestCase):
    def test_5_year_year_1_is_20_percent(self):
        self.assertEqual(TABLE_A_1["5-year"][1], 0.2000)

    def test_5_year_sums_to_one(self):
        total = sum(TABLE_A_1["5-year"].values())
        self.assertEqual(round(total, 4), 1.0000)

    def test_7_year_sums_to_one(self):
        total = sum(TABLE_A_1["7-year"].values())
        self.assertEqual(round(total, 4), 1.0000)

    def test_3_year_year_1_is_33_33_percent(self):
        self.assertEqual(TABLE_A_1["3-year"][1], 0.3333)


class TableA6SpotCheckTests(unittest.TestCase):
    def test_residential_rental_january_year_1(self):
        # Pub 946 Table A-6: 27.5-year, year 1, month 1 = 3.485%
        self.assertEqual(TABLE_A_6["27.5-year"][1][1], 0.03485)

    def test_residential_rental_june_year_1(self):
        self.assertEqual(TABLE_A_6["27.5-year"][1][6], 0.01970)


class TableA7aSpotCheckTests(unittest.TestCase):
    def test_nonresidential_real_property_january_year_1(self):
        # Pub 946 Table A-7a: 39-year, year 1, month 1 = 2.461%
        self.assertEqual(TABLE_A_7a["39-year"][1][1], 0.02461)


if __name__ == "__main__":
    unittest.main()
