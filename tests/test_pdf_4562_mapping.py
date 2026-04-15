"""mappings.pdf_4562 — Form 4562 PDF field mapping."""

import unittest

from pypdf import PdfReader

from tenforty.mappings.pdf_4562 import Pdf4562


PDF_PATH = "pdfs/federal/2025/f4562.pdf"


class Pdf4562MappingTests(unittest.TestCase):
    def test_has_expected_header_and_total_scalars(self):
        m = Pdf4562.get_mapping(2025)
        s = m["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "f4562_line_22_total_depreciation",
        ):
            self.assertIn(k, s)

    def test_has_all_section_b_row_scalars(self):
        s = Pdf4562.get_mapping(2025)["scalars"]
        for label in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"):
            for col in (
                "date_placed_in_service", "basis", "recovery_period",
                "convention", "method", "deduction",
            ):
                self.assertIn(f"f4562_line_19{label}_{col}", s)

    def test_no_repeaters_in_v1(self):
        m = Pdf4562.get_mapping(2025)
        self.assertEqual(m["repeaters"], {})

    def test_every_mapped_field_exists_in_pdf(self):
        s = Pdf4562.get_mapping(2025)["scalars"]
        fields = PdfReader(PDF_PATH).get_fields()
        for key, pdf_path in s.items():
            self.assertIn(
                pdf_path, fields,
                f"mapping {key!r} → {pdf_path!r} not found in {PDF_PATH}",
            )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "No Form 4562 PDF mapping"):
            Pdf4562.get_mapping(2024)


if __name__ == "__main__":
    unittest.main()
