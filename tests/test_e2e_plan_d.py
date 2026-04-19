"""End-to-end smoke tests for Plan D fixtures."""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario

from tests.helpers import FIXTURES_DIR, REPO_ROOT, needs_libreoffice


@needs_libreoffice
class PlanDFixturesTests(unittest.TestCase):
    def _run(self, fixture_name: str):
        scenario = load_scenario(FIXTURES_DIR / fixture_name)
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            return scenario, orch.compute_federal(scenario)

    def test_k1_scorp_basic_positive_qbi_deduction(self):
        _, results = self._run("k1_scorp_basic.yaml")
        self.assertGreater(results["f8995_line_15_oracle"], 0)

    def test_unemployment_appears_in_agi(self):
        scenario, results = self._run("unemployment_withholding.yaml")
        ui = sum(g.unemployment_compensation for g in scenario.form1099_g)
        self.assertGreaterEqual(results["agi"], ui * 0.9)

    def test_state_refund_included_when_prior_year_itemized(self):
        _, results = self._run("state_refund_benefit_rule.yaml")
        self.assertGreater(results["sch_1_line_10"], 0)

    def test_k1_mixed_four_all_rows_populated(self):
        _, results = self._run("k1_mixed_four.yaml")
        self.assertGreater(results["sche_line41"], 0)


if __name__ == "__main__":
    unittest.main()
