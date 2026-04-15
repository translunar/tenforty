"""Static structure tests for the Schedule B PDF field mapping.

Sch B 2025 uses flat sequential field names (f1_01..f1_66) rather than
row-grouped names, so the mapping is a plain scalar dict (every
per-row slot is its own key) rather than the {scalars, repeaters}
shape used for forms with indexable row names.
"""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_sch_b import (
    DIVIDEND_MAX_ROWS,
    INTEREST_MAX_ROWS,
    PdfSchB,
)

SCH_B_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040sb.pdf"
)


class PdfSchBStructureTests(unittest.TestCase):
    def test_row_counts(self):
        self.assertEqual(INTEREST_MAX_ROWS, 14)
        self.assertEqual(DIVIDEND_MAX_ROWS, 16)

    def test_2025_scalars_cover_totals_and_header(self):
        m = PdfSchB.get_mapping(2025)
        for required in (
            "taxpayer_name",
            "taxpayer_ssn",
            "total_interest",
            "excludable_savings_bond",
            "taxable_interest",
            "total_ordinary_dividends",
        ):
            self.assertIn(required, m, f"missing scalar: {required}")

    def test_2025_interest_row_slots(self):
        m = PdfSchB.get_mapping(2025)
        for i in range(1, INTEREST_MAX_ROWS + 1):
            self.assertIn(f"interest_payer_{i}", m)
            self.assertIn(f"interest_amount_{i}", m)

    def test_2025_dividend_row_slots(self):
        m = PdfSchB.get_mapping(2025)
        for i in range(1, DIVIDEND_MAX_ROWS + 1):
            self.assertIn(f"dividend_payer_{i}", m)
            self.assertIn(f"dividend_amount_{i}", m)

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_B_TEMPLATE.exists():
            self.skipTest(f"Sch B template not available at {SCH_B_TEMPLATE}")
        reader = PdfReader(str(SCH_B_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        m = PdfSchB.get_mapping(2025)
        for key, pdf_field in m.items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040sb.pdf",
            )

    def test_2025_mapping_values_are_unique(self):
        m = PdfSchB.get_mapping(2025)
        values = list(m.values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchB mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule B"):
            PdfSchB.get_mapping(1999)


if __name__ == "__main__":
    unittest.main()
