"""Ruling R-S7-6a, oracle tier: production's workbook path, no adapter.

* RED-FIRST: investment income over the limit is DENIED (at d9dec1f the
  unanswered Form 4797 question let the table credit through: 155);
* the MANDATORY anti-regression: a credited row keeps its credit. The Q3
  "No" cell is in NoEICredit (A1) unconditionally, so this pins the exact
  failure of an unconditional write — investment_at_limit (Q2 = No, at the
  boundary) and plateau must still carry native's credit.

2021-2024 credited rows are covered by tests/test_eic_routing_oracle.py
(every undeclared cell routes to the workbook WITH a credit). All
identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice

YEAR = 2025
STATUSES = ("single", "married_filing_jointly")
CREDITED = ("plateau", "investment_at_limit")


def _n(value) -> int:
    return int(round(value or 0))


@needs_libreoffice
class Form4797AnswerOnTheWorkbookPathTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workbook, cls.native = {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for status in STATUSES:
                rows = eic_battery.battery_for(YEAR, status)
                for kind in ("investment_over_limit", *CREDITED):
                    scenario = rows[kind](YEAR)
                    eff, _ = orch._build_effective_scenario(scenario)
                    cls.workbook[(status, kind)] = (
                        orch._compute_1040_via_workbook(eff))
                    with mock.patch.dict(years.NATIVE_EIC_STATUSES,
                                         {YEAR: STATUSES}):
                        cls.native[(status, kind)] = orch.compute_federal(
                            scenario)

    def test_investment_income_over_the_limit_is_denied(self):
        for status in STATUSES:
            with self.subTest(status=status):
                result = self.workbook[(status, "investment_over_limit")]
                self.assertEqual(_n(result.get("eic")), 0)

    def test_a_credited_row_keeps_its_credit(self):
        for status in STATUSES:
            for kind in CREDITED:
                with self.subTest(status=status, kind=kind):
                    expected = _n(self.native[(status, kind)].get("eic"))
                    self.assertGreater(expected, 0)
                    self.assertEqual(
                        _n(self.workbook[(status, kind)].get("eic")),
                        expected)
