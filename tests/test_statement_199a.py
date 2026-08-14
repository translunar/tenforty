import unittest
import tempfile
from pathlib import Path
import pypdf
from tenforty.filing.statement_199a import _money, render_199a_statement_a
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

    def test_renders_negative_qbi_loss(self):
        # A loss year still gets box 17 code V + Statement A (it creates a
        # shareholder-level QBI carryforward), so a negative box_17v_qbi is
        # a supported, real-world input, not an edge case to reject.
        alloc = K1Allocation(
            entity=K1AllocationEntity(
                name="Widgets Inc", ein="00-0000000",
                address=Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701"),
            ),
            shareholder=K1AllocationShareholder(
                name="Pat Sample", ssn_or_ein="123-00-6789",
                address=Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701"),
            ),
            ownership_percentage=100.0,
            box_1_ordinary_business_income=-50_000.0,
            box_17v_qbi=-50_000.0, box_17v_w2_wages=40_000.0, box_17v_ubia=250_000.0,
        )
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(alloc, 2025, Path(d) / "stmtA_loss.pdf")
            reader = pypdf.PdfReader(str(out))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            self.assertIn("-50,000", text)


class MoneyRoundingTests(unittest.TestCase):
    def test_half_dollar_rounds_up_not_banker_style(self):
        # Python's f"{x:,.0f}" uses banker's rounding (round-half-to-even),
        # so 2.5 -> "2". _money must instead follow the repo's half-up
        # irs_round convention: 2.5 -> "3".
        self.assertEqual(_money(2.5), "3")
        self.assertEqual(_money(3.5), "4")

    def test_negative_half_dollar_rounds_away_from_zero(self):
        # irs_round's negative branch is symmetric half-up (half-away-from-
        # zero): -2.5 -> -3, matching irs_round(-2.5) == -3.
        self.assertEqual(_money(-2.5), "-3")
