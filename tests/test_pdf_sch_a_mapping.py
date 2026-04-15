"""Structural test for pdf_sch_a mapping."""

import unittest

from tenforty.mappings.pdf_sch_a import PdfSchA


class PdfSchAMappingTests(unittest.TestCase):
    def test_has_expected_scalars_for_2025(self):
        s = PdfSchA.get_mapping(2025)["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "sch_a_line_1_medical_gross",
            "sch_a_line_4_medical_deductible",
            "sch_a_line_5a_state_income_tax",
            "sch_a_line_5b_property_tax",
            "sch_a_line_5e_salt_capped",
            "sch_a_line_7_taxes_total",
            "sch_a_line_8a_mortgage_interest",
            "sch_a_line_10_interest_total",
            "sch_a_line_11_charity_cash",
            "sch_a_line_14_charity_total",
            "sch_a_line_17_total",
        ):
            self.assertIn(k, s, f"missing scalar key: {k}")

    def test_has_empty_repeaters_in_v1(self):
        self.assertEqual(PdfSchA.get_mapping(2025)["repeaters"], {})

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "No Schedule A PDF mapping"):
            PdfSchA.get_mapping(2024)


if __name__ == "__main__":
    unittest.main()
