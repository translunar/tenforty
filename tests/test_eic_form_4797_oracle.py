"""Rulings R-S7-6a / R-S7-10, oracle tier: production's workbook path, no
adapter.

In every workbook year the EIC sheet's Step 2 stop (investment income over
the limit) is DISPLAY-ONLY: R-S7-6a's Form 4797 answer makes the sheet's
NoEICredit verdict truthful, but line 27 never reads it, so the table
credit is still printed (the oracle on ec4ea3d: 155 on both rows below —
that log is this file's red, by ruling). R-S7-10 refuses that
contradiction:

* investment income over the limit is REFUSED with the exact key;
* a credited row keeps native's credit and is NOT refused — plateau, and
  investment_at_limit (Q2 = No, exactly at the boundary).

What this file does NOT pin: an unconditional "X" in the Q3 "No" cell
would leave line 27 untouched too (it only feeds NoEICredit), so these
credited rows would still pass under it. The catcher for that failure mode
is the parity file's credited-row NoEICredit == FALSE pin
(tests/test_eic_parity_oracle.py, R-S7-9a).

2021-2024 credited rows are covered by tests/test_eic_routing_oracle.py
(every undeclared cell routes to the workbook WITH a credit). All
identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice

YEAR = 2025
STATUSES = ("single", "married_filing_jointly")
CREDITED = ("plateau", "investment_at_limit")
REFUSAL = "workbook_eic_inconsistent: "


def _n(value) -> int:
    return int(round(value or 0))


@needs_libreoffice
class Form4797AnswerOnTheWorkbookPathTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workbook, cls.refusals, cls.native = {}, {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for status in STATUSES:
                rows = eic_battery.battery_for(YEAR, status)
                for kind in ("investment_over_limit", *CREDITED):
                    scenario = rows[kind](YEAR)
                    eff, _ = orch._build_effective_scenario(scenario)
                    try:
                        cls.workbook[(status, kind)] = (
                            orch._compute_1040_via_workbook(eff))
                    except NotImplementedError as refusal:
                        cls.refusals[(status, kind)] = str(refusal)
                    cls.native[(status, kind)] = orch.compute_federal(
                        scenario)

    def test_investment_income_over_the_limit_is_refused(self):
        for status in STATUSES:
            with self.subTest(status=status):
                self.assertTrue(
                    self.refusals.get((status, "investment_over_limit"), "")
                    .startswith(REFUSAL),
                    self.refusals.get((status, "investment_over_limit")))

    def test_a_credited_row_keeps_its_credit_and_is_not_refused(self):
        for status in STATUSES:
            for kind in CREDITED:
                with self.subTest(status=status, kind=kind):
                    self.assertNotIn((status, kind), self.refusals)
                    expected = _n(self.native[(status, kind)].get("eic"))
                    self.assertGreater(expected, 0)
                    self.assertEqual(
                        _n(self.workbook[(status, kind)].get("eic")),
                        expected)
