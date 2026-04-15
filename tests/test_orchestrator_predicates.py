"""Tests for ReturnOrchestrator conditional-emission predicates."""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import Form1099DIV, Form1099INT, W2
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import make_simple_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]


class OrchestratorPredicateTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work_dir = Path(tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.work_dir,
        )

    def test_should_emit_sch_b_false_when_no_interest_or_dividends(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_true_when_interest_over_threshold(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_int.append(
            Form1099INT(payer="Bank A", interest=2000.0)
        )
        self.assertTrue(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_true_when_dividends_over_threshold(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_div.append(
            Form1099DIV(payer="Broker B", ordinary_dividends=2000.0)
        )
        self.assertTrue(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_false_when_totals_under_1500_each(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_int.append(
            Form1099INT(payer="Bank A", interest=800.0)
        )
        scenario.form1099_div.append(
            Form1099DIV(payer="Broker B", ordinary_dividends=600.0)
        )
        self.assertFalse(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_d_false_when_no_1099b(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_d(scenario))

    def test_should_emit_sch_e_false_when_no_rental_property(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_e(scenario))

    def test_should_emit_8959_false_when_wages_under_threshold(self) -> None:
        scenario = make_simple_scenario()
        # single filer, $100k medicare wages, threshold $200k
        self.assertFalse(self.orchestrator._should_emit_8959(scenario, {}))

    def test_should_emit_8959_prefers_oracle_required_flag(self) -> None:
        scenario = make_simple_scenario()
        # Oracle says required even though wages would be under threshold.
        self.assertTrue(self.orchestrator._should_emit_8959(
            scenario, {"f1040": {"f8959_required": True}},
        ))
        # Oracle says not required even though wages would exceed threshold.
        scenario.w2s = [W2(
            employer="X", wages=300_000, federal_tax_withheld=0,
            ss_wages=168_600, ss_tax_withheld=0,
            medicare_wages=300_000, medicare_tax_withheld=0,
        )]
        self.assertFalse(self.orchestrator._should_emit_8959(
            scenario, {"f1040": {"f8959_required": False}},
        ))


if __name__ == "__main__":
    unittest.main()
