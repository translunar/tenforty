"""Form 1040 line 27 (earned income credit) harvest wiring.

The vendor workbook computes the credit into the workbook-scoped `EIC` name
(the 1040 sheet's line-27 cell) in every year, and its total-payments cell
(`Tot_Payments`, line 33) sums it through the line-32 cell. Without an `eic`
OUTPUT the credit reached line 33 while line 27 printed blank, so the payments
section did not foot. Static checks only (openpyxl, no recalc): the computed
amounts are exercised on the oracle tier.
"""
import unittest

import openpyxl

from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tests.helpers import SPREADSHEETS_DIR

YEARS = (2021, 2022, 2023, 2024, 2025)

# The line-32 cell ("total other payments and refundable credits") on the
# '1040' sheet: unnamed in every year, so pinned by address. Recon 2026-10-20.
LINE_32_CELL = {2021: "AC82", 2022: "AC86", 2023: "AD92", 2024: "AD95",
                2025: "AL123"}


def _resolve(wb, name: str) -> tuple[str, str]:
    sheet, cell = wb.defined_names[name].value.split("!")
    return sheet.strip("'"), cell.replace("$", "")


class EicHarvestWiringTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workbooks = {
            year: openpyxl.load_workbook(
                SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx")
            for year in YEARS}

    @classmethod
    def tearDownClass(cls):
        for wb in cls.workbooks.values():
            wb.close()

    def test_eic_output_harvests_the_named_range(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(F1040.get_outputs(year).get("eic"), "EIC")

    def test_eic_name_is_the_line_27_cell(self):
        for year, wb in self.workbooks.items():
            with self.subTest(year=year):
                sheet, cell = _resolve(wb, "EIC")
                self.assertEqual(sheet, "1040")
                self.assertIn("EarnedIncomeCredit", wb[sheet][cell].value)

    def test_eic_reaches_total_payments_through_line_32(self):
        for year, wb in self.workbooks.items():
            with self.subTest(year=year):
                line_32 = LINE_32_CELL[year]
                self.assertTrue(
                    wb["1040"][line_32].value.startswith("=SUM(EIC,"))
                sheet, cell = _resolve(wb, "Tot_Payments")
                self.assertEqual(sheet, "1040")
                self.assertIn(line_32, wb[sheet][cell].value)

    def test_line_27_is_mapped_on_every_year_pdf(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertIn("eic", Pdf1040.get_mapping(year))
