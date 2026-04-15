"""Structural test for pdf_sch_1 mapping."""

import unittest

from tenforty.mappings.pdf_sch_1 import PdfSch1


class PdfSch1MappingTests(unittest.TestCase):
    def test_has_expected_scalars_for_2025(self):
        m = PdfSch1.get_mapping(2025)
        s = m["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "sch_1_line_5_rental_re_royalty",
            "sch_1_line_10_total_additional_income",
            "sch_1_line_26_total_adjustments",
        ):
            self.assertIn(k, s, f"missing scalar key: {k}")

    def test_has_empty_repeaters_in_v1(self):
        m = PdfSch1.get_mapping(2025)
        self.assertEqual(m["repeaters"], {})

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "No Schedule 1 PDF mapping"):
            PdfSch1.get_mapping(2024)


if __name__ == "__main__":
    unittest.main()
