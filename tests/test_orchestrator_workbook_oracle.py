"""Verify that _compute_1040_via_workbook exists and returns core 1040 keys.

This is an oracle test — it requires LibreOffice. Without it the test skips.
After the cutover task repoints _compute_1040_pipeline at the native spine,
_compute_1040_via_workbook remains the stable workbook-oracle entry point for
cross-checking native results against the spreadsheet.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, needs_libreoffice, make_simple_scenario


@needs_libreoffice
class WorkbookOracleEntryPointTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_via_workbook_returns_core_keys(self):
        scenario = make_simple_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            eff, _ = orch._build_effective_scenario(scenario)
            result = orch._compute_1040_via_workbook(eff)
        for key in ("agi", "taxable_income", "total_tax", "standard_deduction"):
            self.assertIn(key, result)


if __name__ == "__main__":
    unittest.main()
