"""Form 1040 line 12 must render the APPLIED deduction (std-or-itemized).

Regression guard for the line-12 emit bug: the line-12 PDF cell historically
read from the `standard_deduction` compute key, which the native spine zeroes
when itemized deductions win — so an itemizing filer's Form 1040 line 12
rendered 0 instead of the itemized total (inconsistent with line 14).

These tests EMIT the 1040 and read the filled fields back with pypdf, asserting
line 12 = the applied deduction for BOTH directions (itemizer + standard filer)
and that line 14 = line 12 + line 13 (QBI) stays consistent.

Native compute path only (single filers) — no LibreOffice required.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.models import ItemizedDeductions
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_itemizer_with_w2_state_tax
from tests.helpers import REPO_ROOT, make_simple_scenario

# Form 1040 page-2 field paths (identical across 2024/2025 templates).
_LINE_12 = "topmostSubform[0].Page2[0].f2_02[0]"  # std or itemized deduction
_LINE_13A = "topmostSubform[0].Page2[0].f2_03[0]"  # QBI deduction
_LINE_14 = "topmostSubform[0].Page2[0].f2_05[0]"  # add lines 12, 13a, 13b


def _emit_and_read_1040(scenario) -> dict[str, int]:
    """Compute + emit the federal 1040 for a (single) scenario and return the
    filled line-12 / line-13a / line-14 values as ints."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=tmp / "work",
        )
        results = orch.compute_federal(scenario)
        emitted = orch.emit_pdfs(scenario, results, tmp / "out")
        reader = PdfReader(str(emitted["1040"]))
        fields = reader.get_fields() or {}

        def val(path: str) -> int:
            f = fields.get(path)
            raw = None if f is None else f.get("/V")
            return int(raw) if raw not in (None, "") else 0

        return {
            "line_12": val(_LINE_12),
            "line_13a": val(_LINE_13A),
            "line_14": val(_LINE_14),
        }


class Form1040Line12EmitTests(unittest.TestCase):
    def test_itemizer_line_12_is_itemized_total(self):
        """Itemizing filer: line 12 must be the Sch A itemized total, not 0.

        build_itemizer_with_w2_state_tax itemizes to schedule_a_total = 35,000
        (20k mortgage + 15k SALT: 9k W-2 box 17 + 6k property, under the 2025
        $40k cap). No QBI, so line 14 == line 12.
        """
        lines = _emit_and_read_1040(build_itemizer_with_w2_state_tax())
        self.assertEqual(lines["line_12"], 35_000)
        # Line 14 = line 12 + line 13a (QBI = 0 here) stays consistent.
        self.assertEqual(lines["line_14"], lines["line_12"] + lines["line_13a"])

    def test_standard_filer_line_12_is_standard_amount(self):
        """Standard filer (guard the other direction): line 12 = the 2025
        single standard deduction ($15,750), unchanged by the fix."""
        scenario = make_simple_scenario()  # single, 2025, no itemized deductions
        lines = _emit_and_read_1040(scenario)
        self.assertEqual(lines["line_12"], 15_750)
        self.assertEqual(lines["line_14"], lines["line_12"] + lines["line_13a"])

    def test_itemizer_line_12_consistent_when_itemized_below_standard(self):
        """When itemized deductions fall below the standard deduction, the
        standard amount is applied — line 12 = the standard deduction."""
        scenario = make_simple_scenario()
        # Itemized total ($5,000) < 2025 standard ($15,750) → standard applies.
        scenario.itemized_deductions = ItemizedDeductions(
            charitable_contributions=5_000.0,
        )
        lines = _emit_and_read_1040(scenario)
        self.assertEqual(lines["line_12"], 15_750)
        self.assertEqual(lines["line_14"], lines["line_12"] + lines["line_13a"])


if __name__ == "__main__":
    unittest.main()
