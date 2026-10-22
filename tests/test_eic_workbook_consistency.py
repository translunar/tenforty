"""Ruling R-S7-10: the workbook path refuses a sheet that contradicts itself.

In every workbook year the EIC sheet's Step 2 stop (investment income over
the limit) is display-only: NoEICredit (A1) turns TRUE and the sheet says
"You can't take the Earned Income Credit", but line 27 never reads A1, so
the table credit is still printed (the oracle on ec4ea3d: 155 on
investment_over_limit). FAIL-CLOSED (R-S7-10a) on the verdict's value, TYPE
and PRESENCE: when line 27 is positive, the only harvest that lets the
credit through is exactly bool False. TRUE, 1, None, a missing key, or
anything else refuses — a contradicted verdict, or one that cannot be read.
When line 27 is zero the verdict is irrelevant and never refuses.

All engine output here is a harvested FIXTURE (the engine is stubbed), so
nothing reaches LibreOffice. All identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.mappings.f1040 import F1040
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR

DECLARED = "eic_no_credit_declared"
PREFIX = "workbook_eic_inconsistent: "


class _Stop(Exception):
    """form_1040.compute was reached: the check let the return through."""


class WorkbookEicConsistencyTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                       work_dir=Path(tmp.name))
        scenario = eic_battery.battery_for(
            2025, "married_filing_jointly")["investment_over_limit"](2025)
        self.eff, _ = self.orch._build_effective_scenario(scenario)

    def _run(self, harvested, after=None):
        """The workbook path on a harvested fixture; `after` stands in for
        form_1040.compute (the step right after the check)."""
        with mock.patch.object(self.orch.engine, "compute",
                               return_value=dict(harvested)), \
                mock.patch("tenforty.orchestrator.form_1040.compute",
                           side_effect=after or (lambda **kw: {})):
            return self.orch._compute_1040_via_workbook(self.eff)

    def test_a_declared_no_credit_with_a_credit_refuses(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self._run({"eic": 155.0, DECLARED: True})
        message = str(ctx.exception)
        self.assertTrue(message.startswith(PREFIX), message)
        self.assertIn("155", message)

    def test_a_credit_refuses_unless_the_verdict_is_exactly_false(self):
        # R-S7-10a: fail-closed on type and presence — 1 and None are not
        # "False", and a missing key is not a verdict.
        missing = object()
        for declared in (True, 1, 0, None, "", "FALSE", missing):
            harvested = {"eic": 155.0}
            if declared is not missing:
                harvested[DECLARED] = declared
            label = "missing" if declared is missing else repr(declared)
            with self.subTest(declared=label):
                with self.assertRaises(NotImplementedError) as ctx:
                    self._run(harvested)
                self.assertTrue(str(ctx.exception).startswith(PREFIX))

    def test_it_passes_a_credit_with_an_exact_false_verdict(self):
        with self.assertRaises(_Stop):
            self._run({"eic": 155.0, DECLARED: False},
                      after=mock.Mock(side_effect=_Stop))

    def test_no_credit_never_refuses_whatever_the_verdict(self):
        missing = object()
        for eic in (0.0, None):
            for declared in (True, False, 1, None, missing):
                harvested = {"eic": eic}
                if declared is not missing:
                    harvested[DECLARED] = declared
                label = "missing" if declared is missing else repr(declared)
                with self.subTest(eic=eic, declared=label):
                    with self.assertRaises(_Stop):
                        self._run(harvested,
                                  after=mock.Mock(side_effect=_Stop))

    def test_the_refusal_carries_the_harvest(self):
        from tenforty.orchestrator import WorkbookEicInconsistent
        with self.assertRaises(WorkbookEicInconsistent) as ctx:
            self._run({"eic": 155.0, DECLARED: True, "other": 7})
        self.assertEqual(ctx.exception.harvested,
                         {"eic": 155.0, DECLARED: True, "other": 7})

    def test_the_declaration_does_not_reach_the_results(self):
        seen = {}

        def record(raw_1040, upstream):
            seen.update(raw_1040)
            return {}
        self._run({"eic": 0.0, DECLARED: False}, after=record)
        self.assertIn("eic", seen)
        self.assertNotIn(DECLARED, seen)

    def test_every_workbook_year_harvests_no_eic_credit(self):
        for year in sorted(F1040.INPUTS):
            with self.subTest(year=year):
                self.assertEqual(F1040.get_outputs(year).get(DECLARED),
                                 "NoEICredit")
