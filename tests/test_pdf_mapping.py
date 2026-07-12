import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tests.helpers import F1040_PDF, needs_pdf


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

    def test_2023_supported_with_probed_relocated_paths(self):
        # 2023 is a supported year. Its layout differs structurally from
        # 2024 (not a field-name renumbering you can inherit) — these pins
        # guard the invisible-shift traps the marker-probe caught:
        #   * Line 10 (adjustments) is f1_54 — the SAME f-number 2024 uses
        #     for line 7b child_capital_gain. Inheriting 2024 would have put
        #     adjustments on the wrong line.
        #   * Lines 12–15 sit on PAGE 1 in 2023 (2024 moved them to page 2),
        #     so taxable_income is Page1 f1_59, not Page2.
        #   * Page 2 starts at line 16: tax is Page2 f2_02 (2024: f2_07).
        #   * 2023 has no line-11b AGI repeat, so agi_page2 is absent.
        m = Pdf1040.get_mapping(2023)
        self.assertEqual(
            m["adjustments"],
            "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_54[0]",
        )
        self.assertEqual(
            m["taxable_income"], "topmostSubform[0].Page1[0].f1_59[0]"
        )
        self.assertEqual(m["total_tax"], "topmostSubform[0].Page2[0].f2_02[0]")
        self.assertEqual(
            m["total_tax_liability"], "topmostSubform[0].Page2[0].f2_10[0]"
        )
        self.assertNotIn("agi_page2", m)
