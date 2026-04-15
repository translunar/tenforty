"""Oracle cross-check for forms.f4562.

The 2025 1040.xlsx workbook contains a ``4562`` sheet but exposes no
defined name for its total depreciation cell — verified via openpyxl
enumeration of ``wb.defined_names``. Sch E consumes a depreciation
scalar from the scenario's ``RentalProperty.depreciation`` directly;
the 4562 sheet is for viewer reference only and is not wired into any
named range.

Per the plan: if no XLSX name exposes the 4562 total, the oracle is
skipped rather than invented. The cell-by-cell oracle for the MACRS
tables themselves lives in test_depreciation_table_generator.py
(@pytest.mark.oracle); that's the statutory cross-check we rely on.
"""

import unittest

import pytest


@pytest.mark.oracle
class F4562OracleTests(unittest.TestCase):
    def test_f4562_line_22_matches_xlsx_total_depreciation(self):
        self.skipTest(
            "1040.xlsx exposes no defined name for the 4562 sheet's "
            "total depreciation (confirmed via openpyxl enumeration). "
            "MACRS correctness is covered by the Pub 946 cell-by-cell "
            "oracle in test_depreciation_table_generator.py."
        )
