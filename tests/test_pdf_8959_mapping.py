"""Static structure tests for the Form 8959 PDF field mapping."""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_8959 import Pdf8959

F8959_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f8959.pdf"
)


class Pdf8959StructureTests(unittest.TestCase):
    def test_2025_has_all_24_lines_and_header(self):
        scalars = set(Pdf8959.get_mapping(2025)["scalars"].keys())
        self.assertIn("taxpayer_name", scalars)
        self.assertIn("taxpayer_ssn", scalars)
        for n in range(1, 25):
            self.assertIn(f"f8959_line_{n}", scalars, f"missing line {n}")

    def test_2025_has_empty_repeaters(self):
        self.assertEqual(Pdf8959.get_mapping(2025).get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not F8959_TEMPLATE.exists():
            self.skipTest(f"Form 8959 template not available at {F8959_TEMPLATE}")
        reader = PdfReader(str(F8959_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in Pdf8959.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f8959.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(Pdf8959.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "Pdf8959 mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "8959"):
            Pdf8959.get_mapping(1999)


if __name__ == "__main__":
    unittest.main()
