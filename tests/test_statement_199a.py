import unittest
import tempfile
from pathlib import Path
import pypdf
from tenforty.filing.statement_199a import render_199a_statement_a
from tenforty.models import (
    K1Allocation, K1AllocationEntity, K1AllocationShareholder, Address,
)

def _alloc():
    addr = Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701")
    return K1Allocation(
        entity=K1AllocationEntity(name="Widgets Inc", ein="00-0000000", address=addr),
        shareholder=K1AllocationShareholder(name="Pat Sample", ssn_or_ein="123-00-6789", address=addr),
        ownership_percentage=100.0,
        box_1_ordinary_business_income=100_000.0,
        box_17v_qbi=100_000.0, box_17v_w2_wages=40_000.0, box_17v_ubia=250_000.0,
    )

class Statement199ATests(unittest.TestCase):
    def test_renders_one_page_with_all_199a_items(self):
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(_alloc(), 2025, Path(d) / "stmtA.pdf")
            reader = pypdf.PdfReader(str(out))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            self.assertIn("Statement A", text)
            self.assertIn("Widgets Inc", text)
            self.assertIn("Pat Sample", text)
            self.assertIn("100,000", text)   # QBI
            self.assertIn("40,000", text)     # W-2 wages
            self.assertIn("250,000", text)    # UBIA
            self.assertIn("2025", text)

    def test_output_is_deterministic_across_renders(self):
        """DD2 condition 2: identical inputs must not produce differing bytes,
        or tests downstream will flake on embedded timestamps."""
        with tempfile.TemporaryDirectory() as d:
            a = render_199a_statement_a(_alloc(), 2025, Path(d) / "a.pdf")
            b = render_199a_statement_a(_alloc(), 2025, Path(d) / "b.pdf")
            self.assertEqual(a.read_bytes(), b.read_bytes())
