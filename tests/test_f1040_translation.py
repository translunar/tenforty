import unittest

from tests.helpers import make_simple_scenario
from tenforty.result_translator import ResultTranslator
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC


class TestF1040PdfTranslation(unittest.TestCase):
    def test_interest_renamed(self):
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"interest_income": 250}, make_simple_scenario(),
        )
        self.assertEqual(result["taxable_interest"], 250)
        self.assertNotIn("interest_income", result)

    def test_dividend_renamed(self):
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"dividend_income": 2000}, make_simple_scenario(),
        )
        self.assertEqual(result["ordinary_dividends"], 2000)
        self.assertNotIn("dividend_income", result)

    def test_agi_expanded_to_both_pages(self):
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"agi": 100250}, make_simple_scenario(),
        )
        self.assertEqual(result["agi"], 100250)
        self.assertEqual(result["agi_page2"], 100250)

    def test_federal_withheld_expanded(self):
        """federal_withheld should appear as both total (25d) and W-2 (25a)."""
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"federal_withheld": 15000}, make_simple_scenario(),
        )
        self.assertEqual(result["federal_withheld"], 15000)
        self.assertEqual(result["federal_withheld_w2"], 15000)

    def test_direct_passthrough_preserved(self):
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"wages": 100000, "taxable_income": 84250, "overpaid": 1500},
            make_simple_scenario(),
        )
        self.assertEqual(result["wages"], 100000)
        self.assertEqual(result["taxable_income"], 84250)
        self.assertEqual(result["overpaid"], 1500)

    def test_schedule_subtotals_passed_through(self):
        """Schedule subtotals pass through but won't match any PDF field."""
        translator = ResultTranslator(F1040_PDF_SPEC)
        result = translator.translate(
            {"sche_line26": 5000, "schd_line16": 3000, "wages": 100000},
            make_simple_scenario(),
        )
        self.assertEqual(result["wages"], 100000)
