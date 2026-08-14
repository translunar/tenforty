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

def _parse_money(s: str) -> int:
    """Convert a rendered money string like '-70,000' or '80,000' (as
    extracted from the PDF text) into an int, for arithmetic assertions
    against the figures as actually printed."""
    return int(s.replace(",", ""))

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

    def test_qbi_override_renders_reconciliation_rows(self):
        # Ruling I-1: when box_17v_qbi differs from box_1_ordinary_business_
        # income (i.e. a qbi_override was in effect), row 1 must ALWAYS tie
        # to box 1 (never the override), and two additional rows must show
        # the adjustment and the QBI total, so the three figures add up.
        addr = Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701")
        alloc = K1Allocation(
            entity=K1AllocationEntity(name="Widgets Inc", ein="00-0000000", address=addr),
            shareholder=K1AllocationShareholder(name="Pat Sample", ssn_or_ein="123-00-6789", address=addr),
            ownership_percentage=100.0,
            box_1_ordinary_business_income=70_000.0,
            box_17v_qbi=80_000.0, box_17v_w2_wages=40_000.0, box_17v_ubia=250_000.0,
        )
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(alloc, 2025, Path(d) / "stmtA_override.pdf")
            reader = pypdf.PdfReader(str(out))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            self.assertIn("70,000", text)   # box 1 tie-out (row 1)
            self.assertIn("10,000", text)   # adjustment = 80,000 - 70,000
            self.assertIn("80,000", text)   # QBI total
            self.assertIn("Other QBI adjustments (preparer-determined)", text)
            self.assertIn("Qualified business income", text)
            # Row 1 must equal box 1, never the override: the tie-out. The
            # renderer draws the label and its right-aligned figure as
            # separate text objects at the same y, which pypdf extracts as
            # adjacent lines — so the figure immediately following the
            # "Ordinary business income (loss)" label is row 1's value.
            lines = text.splitlines()
            label_idx = lines.index("Ordinary business income (loss)")
            self.assertEqual(lines[label_idx + 1], "70,000")
            # The three printed figures must add up exactly, as printed —
            # parsed from the extracted PDF text (not literals), so this
            # actually exercises the renderer's arithmetic rather than
            # Python's.
            row1 = _parse_money(lines[label_idx + 1])
            adj_idx = lines.index("Other QBI adjustments (preparer-determined)")
            adjustment = _parse_money(lines[adj_idx + 1])
            total_idx = lines.index("Qualified business income")
            total = _parse_money(lines[total_idx + 1])
            self.assertEqual(row1 + adjustment, total)

    def test_default_path_no_override_single_row_layout_preserved(self):
        # Ruling I-1: when box_17v_qbi equals box_1_ordinary_business_income
        # (the default, no-override path), the layout must be exactly as
        # before — no separate adjustment/total rows.
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(_alloc(), 2025, Path(d) / "stmtA_default.pdf")
            reader = pypdf.PdfReader(str(out))
            text = reader.pages[0].extract_text()
            self.assertNotIn("Other QBI adjustments", text)
            self.assertNotIn("Qualified business income", text)

    def test_sub_dollar_difference_rounds_to_single_row(self):
        # Ruling I-1 corollary: box_1 and QBI can differ by a sub-dollar
        # float amount yet round (via irs_round) to the SAME whole dollar.
        # Because the renderer rounds BEFORE comparing the two figures, this
        # must NOT trigger the override layout with a nonsensical
        # zero-value adjustment row — the single-row default layout must be
        # used, exactly as when the two figures are equal outright.
        addr = Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701")
        alloc = K1Allocation(
            entity=K1AllocationEntity(name="Widgets Inc", ein="00-0000000", address=addr),
            shareholder=K1AllocationShareholder(name="Pat Sample", ssn_or_ein="123-00-6789", address=addr),
            ownership_percentage=100.0,
            box_1_ordinary_business_income=70_000.3,
            box_17v_qbi=70_000.4, box_17v_w2_wages=40_000.0, box_17v_ubia=250_000.0,
        )
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(alloc, 2025, Path(d) / "stmtA_subdollar.pdf")
            reader = pypdf.PdfReader(str(out))
            text = reader.pages[0].extract_text()
            self.assertNotIn("Other QBI adjustments", text)
            self.assertNotIn("Qualified business income", text)

    def test_qbi_override_negative_figures_add_up(self):
        # Both box 1 and QBI negative (loss year with an override still in
        # effect) must behave sanely: row 1 ties to box 1, and the three
        # printed figures still add up exactly.
        addr = Address(street="1 Test Way", city="Austin", state="TX", zip_code="78701")
        alloc = K1Allocation(
            entity=K1AllocationEntity(name="Widgets Inc", ein="00-0000000", address=addr),
            shareholder=K1AllocationShareholder(name="Pat Sample", ssn_or_ein="123-00-6789", address=addr),
            ownership_percentage=100.0,
            box_1_ordinary_business_income=-70_000.0,
            box_17v_qbi=-80_000.0, box_17v_w2_wages=40_000.0, box_17v_ubia=250_000.0,
        )
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(alloc, 2025, Path(d) / "stmtA_override_neg.pdf")
            reader = pypdf.PdfReader(str(out))
            text = reader.pages[0].extract_text()
            self.assertIn("-70,000", text)   # box 1 tie-out (row 1)
            self.assertIn("-10,000", text)   # adjustment = -80,000 - (-70,000)
            self.assertIn("-80,000", text)   # QBI total
            # The three printed figures must add up exactly, as printed —
            # parsed from the extracted PDF text (not literals).
            lines = text.splitlines()
            label_idx = lines.index("Ordinary business income (loss)")
            row1 = _parse_money(lines[label_idx + 1])
            adj_idx = lines.index("Other QBI adjustments (preparer-determined)")
            adjustment = _parse_money(lines[adj_idx + 1])
            total_idx = lines.index("Qualified business income")
            total = _parse_money(lines[total_idx + 1])
            self.assertEqual(row1 + adjustment, total)

    def test_sstb_ptp_aggregation_disclaimer_present(self):
        # Ruling I-2: an explicit footnote disclaiming SSTB/PTP/aggregation
        # determination must be rendered on the statement itself. Assert on
        # distinctive substrings since the sentence may wrap across lines.
        with tempfile.TemporaryDirectory() as d:
            out = render_199a_statement_a(_alloc(), 2025, Path(d) / "stmtA_disclaimer.pdf")
            reader = pypdf.PdfReader(str(out))
            text = reader.pages[0].extract_text()
            self.assertIn("SSTB status not determined", text)
            self.assertIn("1.199A-5", text)
            self.assertIn("PTP/aggregation likewise not determined", text)


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
