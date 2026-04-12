"""Tests for the IRS Form 4868 PDF field mapping."""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_4868 import Pdf4868

F4868_PDF = Path("/Users/juno/Projects/tenforty/pdfs/federal/2025/f4868.pdf")

needs_4868_pdf = unittest.skipUnless(
    F4868_PDF.exists(),
    f"f4868 PDF not available at {F4868_PDF}",
)


@needs_4868_pdf
class TestPdf4868Mapping(unittest.TestCase):
    """Verify Pdf4868 mapping shape and that every value names a real PDF field."""

    def test_2025_mapping_exists(self):
        mapping = Pdf4868.get_mapping(2025)
        self.assertIsInstance(mapping, dict)
        self.assertGreater(len(mapping), 0)

    def test_all_mapped_fields_exist_in_pdf(self):
        """Every value in the mapping must be a real field name in f4868.pdf."""
        mapping = Pdf4868.get_mapping(2025)
        reader = PdfReader(F4868_PDF)
        pdf_fields = reader.get_fields()
        pdf_field_names = set(pdf_fields.keys())

        for result_key, pdf_field in mapping.items():
            self.assertIn(
                pdf_field,
                pdf_field_names,
                f"Mapping '{result_key}' -> '{pdf_field}' not found in PDF",
            )

    def test_part_i_keys_present(self):
        """All Part I identification keys must be in the mapping."""
        mapping = Pdf4868.get_mapping(2025)
        part_i_keys = ["full_name", "address", "address_city", "address_state",
                       "address_zip", "ssn", "spouse_ssn"]
        for key in part_i_keys:
            self.assertIn(key, mapping, f"Missing Part I key: '{key}'")

    def test_part_ii_keys_present(self):
        """All Part II income tax amount keys must be in the mapping."""
        mapping = Pdf4868.get_mapping(2025)
        part_ii_keys = [
            "estimated_total_tax",   # Line 4
            "total_payments",        # Line 5
            "balance_due",           # Line 6
            "amount_paying_with_extension",  # Line 7
            "out_of_country",        # Line 8 checkbox
            "nonresident_alien",     # Line 9 checkbox
        ]
        for key in part_ii_keys:
            self.assertIn(key, mapping, f"Missing Part II key: '{key}'")

    def test_voucher_key_present(self):
        mapping = Pdf4868.get_mapping(2025)
        self.assertIn("voucher_amount", mapping)

    def test_mapping_values_are_strings(self):
        mapping = Pdf4868.get_mapping(2025)
        for key, value in mapping.items():
            self.assertIsInstance(
                value, str,
                f"Mapping '{key}' value is {type(value)}, expected str",
            )

    def test_mapping_keys_are_valid_identifiers(self):
        mapping = Pdf4868.get_mapping(2025)
        for key in mapping:
            self.assertTrue(
                key.isidentifier(),
                f"Mapping key '{key}' is not a valid Python identifier",
            )

    def test_no_duplicate_field_values(self):
        """No two logical keys should map to the same PDF field name."""
        mapping = Pdf4868.get_mapping(2025)
        seen: dict[str, str] = {}
        for key, field in mapping.items():
            if field in seen:
                self.fail(
                    f"Duplicate PDF field '{field}' used for '{key}' and '{seen[field]}'"
                )
            seen[field] = key


class TestPdf4868Basic(unittest.TestCase):
    """Tests that don't require the PDF file."""

    def test_missing_year_raises_with_year_in_message(self):
        with self.assertRaisesRegex(ValueError, "1999"):
            Pdf4868.get_mapping(1999)
