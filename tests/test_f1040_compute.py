import unittest

from tenforty.forms.f1040 import compute


class F1040ComputeTests(unittest.TestCase):
    def test_renames_engine_keys_to_pdf_keys(self):
        raw = {
            "interest_income": 100,
            "dividend_income": 200,
            "schd_line16": 300,
            "sche_line26": 400,
            "federal_withheld": 1000,
            "additional_medicare_withheld": 50,
            "agi": 75000,
        }
        result = compute(raw_1040=raw, upstream={})
        self.assertEqual(result["taxable_interest"], 100)
        self.assertEqual(result["ordinary_dividends"], 200)
        self.assertEqual(result["capital_gain_loss"], 300)
        self.assertEqual(result["other_income"], 400)
        self.assertEqual(result["federal_withheld_w2"], 1000)
        self.assertEqual(result["federal_withheld_other"], 50)
        self.assertEqual(result["agi"], 75000)
        self.assertEqual(result["agi_page2"], 75000)

    def test_sums_line_25d(self):
        raw = {
            "federal_withheld": 1000,
            "additional_medicare_withheld": 50,
            "federal_withheld_1099": 25,
        }
        result = compute(raw_1040=raw, upstream={})
        self.assertEqual(result["federal_withheld"], 1000 + 25 + 50)

    def test_missing_agi_omits_page2(self):
        result = compute(raw_1040={"federal_withheld": 0}, upstream={})
        self.assertNotIn("agi_page2", result)

    def test_qbi_deduction_1040_reemitted_normalized(self):
        # Value arm: the raw workbook value is re-emitted under the
        # oracle-facing key AND matches the normalized qbi_deduction.
        result = compute(
            raw_1040={"_qbi_deduction_1040": 450.0}, upstream={})
        self.assertEqual(result["_qbi_deduction_1040"], 450.0)
        self.assertEqual(result["qbi_deduction"], 450.0)

        # None arm: a blank workbook cell normalizes to 0 on BOTH keys,
        # matching the native spine (which always emits a number).
        result = compute(
            raw_1040={"_qbi_deduction_1040": None}, upstream={})
        self.assertEqual(result["_qbi_deduction_1040"], 0)
        self.assertEqual(result["qbi_deduction"], 0)

    def test_f8959_tax_total_none_normalized_to_zero(self):
        # None arm: a blank F8959_Tax cell normalizes to 0, not None.
        result = compute(raw_1040={"f8959_tax_total": None}, upstream={})
        self.assertEqual(result["f8959_tax_total"], 0)

        # Value arm: a real Additional Medicare Tax amount passes through
        # unchanged.
        result = compute(raw_1040={"f8959_tax_total": 123.0}, upstream={})
        self.assertEqual(result["f8959_tax_total"], 123.0)
