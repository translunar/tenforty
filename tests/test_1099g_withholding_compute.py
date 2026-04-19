"""1099-G box-4 federal withholding flows through to line 25b.
Regression guard that the native supplementation is wired correctly."""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import Form1099G
from tenforty.orchestrator import ReturnOrchestrator

from tests.helpers import REPO_ROOT, make_simple_scenario, needs_libreoffice


@needs_libreoffice
class F1040Line25bTests(unittest.TestCase):
    def test_1099g_withholding_included_in_total(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(
            payer="State", unemployment_compensation=8_000.0,
            federal_tax_withheld=800.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results = orch.compute_federal(s)
        # Baseline W-2 withholding is 15_000; 1099-G adds 800.
        self.assertGreaterEqual(
            round(results["federal_withheld"]), 15_800,
        )


if __name__ == "__main__":
    unittest.main()
