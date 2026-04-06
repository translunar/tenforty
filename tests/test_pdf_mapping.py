import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040

F1040_PDF = Path("/tmp/f1040_2025.pdf")


def pdf_available() -> bool:
    return F1040_PDF.exists()


needs_pdf = unittest.skipUnless(pdf_available(), "f1040 PDF not available at /tmp/f1040_2025.pdf")


@needs_pdf
class TestPdf1040Mapping(unittest.TestCase):
    """Verify PDF field mapping by filling known values and reading them back."""

    def test_has_2025_mapping(self):
        mapping = Pdf1040.get_mapping(2025)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_core_output_keys_are_mapped(self):
        mapping = Pdf1040.get_mapping(2025)
        core_keys = [
            "wages", "agi", "taxable_income", "total_tax",
            "federal_withheld", "overpaid",
        ]
        for key in core_keys:
            self.assertIn(key, mapping, f"Missing mapping for '{key}'")

    def test_all_pdf_field_names_exist_in_pdf(self):
        """Every PDF field name in our mapping must exist in the actual PDF."""
        mapping = Pdf1040.get_mapping(2025)
        reader = PdfReader(F1040_PDF)
        pdf_fields = reader.get_fields()
        pdf_field_names = set(pdf_fields.keys())

        for result_key, pdf_field in mapping.items():
            self.assertIn(
                pdf_field, pdf_field_names,
                f"Mapping '{result_key}' -> '{pdf_field}' not found in PDF",
            )

    def test_fill_and_read_back_wages(self):
        """Fill wages field and verify we can read it back."""
        mapping = Pdf1040.get_mapping(2025)
        filler = PdfFiller()
        output = Path("/tmp/test_pdf_wages.pdf")

        values = {"wages": 100000}
        filler.fill(F1040_PDF, output, mapping, values)

        reader = PdfReader(output)
        fields = reader.get_fields()
        wages_field = mapping["wages"]
        self.assertEqual(fields[wages_field].get("/V"), "100000")

    def test_fill_and_read_back_multiple_fields(self):
        """Fill several core fields and verify all read back correctly."""
        mapping = Pdf1040.get_mapping(2025)
        filler = PdfFiller()
        output = Path("/tmp/test_pdf_multi.pdf")

        values = {
            "wages": 100000,
            "agi": 100250,
            "taxable_income": 84500,
            "total_tax": 13500,
            "federal_withheld": 15000,
            "overpaid": 1500,
        }

        filler.fill(F1040_PDF, output, mapping, values)

        reader = PdfReader(output)
        fields = reader.get_fields()

        for key, expected in values.items():
            pdf_field = mapping[key]
            actual = fields[pdf_field].get("/V")
            self.assertEqual(
                actual, str(expected),
                f"Field '{key}' ({pdf_field}): expected '{expected}', got '{actual}'",
            )

    def test_interest_and_dividends_mapped(self):
        mapping = Pdf1040.get_mapping(2025)
        self.assertIn("taxable_interest", mapping)
        self.assertIn("qualified_dividends", mapping)
        self.assertIn("ordinary_dividends", mapping)

    def test_mapping_values_are_strings(self):
        mapping = Pdf1040.get_mapping(2025)
        for key, value in mapping.items():
            self.assertIsInstance(
                value, str,
                f"Mapping '{key}' value is {type(value)}, expected str",
            )

    def test_mapping_keys_are_valid_identifiers(self):
        mapping = Pdf1040.get_mapping(2025)
        for key in mapping:
            self.assertTrue(
                key.isidentifier(),
                f"Mapping key '{key}' is not a valid Python identifier",
            )


class TestPdf1040Basic(unittest.TestCase):
    """Tests that don't require the PDF file."""

    def test_unsupported_year_raises(self):
        with self.assertRaises(ValueError):
            Pdf1040.get_mapping(1999)
