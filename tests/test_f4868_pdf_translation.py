"""Tests for the F4868 PDF TranslationSpec."""

import unittest

from tenforty.models import FilingStatus, Scenario, TaxReturnConfig, W2
from tenforty.result_translator import ResultTranslator
from tenforty.translations.f4868_pdf import F4868_PDF_SPEC


def make_single_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1990-06-15",
            state="CA",
            first_name="Alex",
            last_name="Rivera",
            ssn="000-12-3456",
            address="123 Main St",
            address_city="Austin",
            address_state="TX",
            address_zip="78701",
        ),
    )


def make_mfj_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.MARRIED_JOINTLY,
            birthdate="1988-03-10",
            state="CA",
            first_name="Jordan",
            last_name="Kim",
            ssn="000-23-4567",
            spouse_first_name="Casey",
            spouse_last_name="Kim",
            spouse_ssn="000-34-5678",
            address="456 Oak Ave",
            address_city="Portland",
            address_state="OR",
            address_zip="97201",
        ),
    )


SAMPLE_ENGINE_OUTPUT = {
    "total_tax": 12000,
    "total_payments": 9000,
    "wages": 75000,
}


class TestF4868PdfTranslationSpec(unittest.TestCase):
    def test_spec_loads_without_overlap_error(self):
        # TranslationSpec.__post_init__ raises if renames and expansions overlap
        from tenforty.translations.f4868_pdf import F4868_PDF_SPEC as spec
        self.assertIsNotNone(spec)

    def test_full_name_combined_for_single(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        self.assertEqual(result["full_name"], "Alex Rivera")

    def test_full_name_combined_for_mfj(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_mfj_scenario())
        self.assertEqual(result["full_name"], "Jordan Kim")

    def test_ssn_from_config(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        self.assertEqual(result["ssn"], "000-12-3456")

    def test_address_fields_from_config(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        self.assertEqual(result["address"], "123 Main St")
        self.assertEqual(result["address_city"], "Austin")
        self.assertEqual(result["address_state"], "TX")
        self.assertEqual(result["address_zip"], "78701")

    def test_spouse_ssn_empty_for_single(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        # Empty string is not None so it passes through scenario_fields
        self.assertEqual(result["spouse_ssn"], "")

    def test_spouse_ssn_populated_for_mfj(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_mfj_scenario())
        self.assertEqual(result["spouse_ssn"], "000-34-5678")

    def test_total_tax_renamed_to_estimated_total_tax(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        self.assertIn("estimated_total_tax", result)
        self.assertEqual(result["estimated_total_tax"], 12000)
        self.assertNotIn("total_tax", result)

    def test_total_payments_passes_through_unrenamed(self):
        translator = ResultTranslator(F4868_PDF_SPEC)
        result = translator.translate(SAMPLE_ENGINE_OUTPUT, make_single_scenario())
        self.assertEqual(result["total_payments"], 9000)
        self.assertIn("total_payments", result)


if __name__ == "__main__":
    unittest.main()
