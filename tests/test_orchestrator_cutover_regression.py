import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario


class CutoverRegressionTests(unittest.TestCase):
    def test_federal_runs_without_libreoffice(self):
        # Native spine must compute with no soffice dependency at runtime.
        scenario = make_simple_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            result = orch.compute_federal(scenario)
        for key in ("agi", "taxable_income", "total_tax"):
            self.assertIn(key, result)
            self.assertIsInstance(result[key], int)
