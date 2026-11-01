"""Ruling R-S8-21: tax year 2021 is feature-frozen, and its native EIC will
never be built, so a 2021 return that may qualify for the EIC refuses
(eic_2021_not_modeled) before any workbook route. Every refusal here is
proven with the workbook path patched to fail, and each is paired with a
neighbor that must NOT refuse: another year, or the far side of the 2021
ceiling. All identities synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.models import FilingStatus, Form1095A, ScheduleCBusiness, Scenario
from tenforty.orchestrator import (
    DEPENDENTS_REFUSAL,
    ReturnOrchestrator,
    eic_possible,
)
from tests.fixtures.eic_battery import favorable_eligibility
from tests.fixtures.spine_battery import _battery_config, _w2
from tests.helpers import SPREADSHEETS_DIR
from tests.test_eic_routing import HOH_EIC_REFUSAL_0267E03
from tests.test_f8962_spine_wiring import _months

PREFIX = "eic_2021_not_modeled: "
SINGLE, MFJ, MFS, HOH = (
    FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY,
    FilingStatus.MARRIED_FILING_SEPARATELY, FilingStatus.HEAD_OF_HOUSEHOLD)
LOW_WAGES = 10_000.0
# The 2021 no-child ceiling written out from Pub. 596 (2021), $27,380, so the
# param is load-bearing: a moved param fails the pair instead of moving it.
UNDER_THE_2021_CEILING = 27_350.0
OVER_THE_2021_CEILING = 27_400.0


class _WorkbookRouted(Exception):
    """Raised by the patched workbook path: the return left the spine."""


def _scenario(year=2021, status=SINGLE, wages=LOW_WAGES, **fields) -> Scenario:
    joint = status is MFJ
    return Scenario(
        config=_battery_config(year, status),
        w2s=[_w2(year, "Synthetic Employer F", wages, 0.0,
                 owner="taxpayer" if joint else None)] if wages else [],
        **fields)


class _RoutedTestCase(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                       work_dir=self.tmp / "work")
        patcher = mock.patch.object(
            ReturnOrchestrator, "_compute_1040_via_workbook",
            side_effect=_WorkbookRouted)
        self.workbook = patcher.start()
        self.addCleanup(patcher.stop)

    def _refusal(self, scenario) -> str:
        self.assertTrue(eic_possible(scenario))
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scenario)
        self.workbook.assert_not_called()
        return str(ctx.exception)


class Eic2021RefusesTests(_RoutedTestCase):

    def test_single_childless_refuses(self):
        self.assertTrue(
            self._refusal(_scenario()).startswith(PREFIX))

    def test_the_message_gives_cause_doubt_and_consequence(self):
        message = self._refusal(_scenario())
        for words in ("does not model the 2021 Earned Income Credit",
                      "American Rescue Plan Act",
                      "permanently out of scope",
                      "may qualify",
                      "conservative",
                      "understate the refund",
                      "refused"):
            with self.subTest(words=words):
                self.assertIn(words, message)

    def test_every_status_with_no_child_candidate_refuses_here(self):
        # Married filing separately is outside the native grid, so without
        # this gate it would reach the workbook.
        for status in (SINGLE, MFJ, MFS):
            with self.subTest(status=status.value):
                self.assertTrue(self._refusal(
                    _scenario(status=status)).startswith(PREFIX))

    def test_schedule_c_only_filer_refuses_here(self):
        # Self-employment is earned income. No W-2 at all.
        business = ScheduleCBusiness(description="Example Route",
                                     gross_receipts=10_000.0)
        self.assertTrue(self._refusal(_scenario(
            wages=0.0, schedule_c_businesses=[business])).startswith(PREFIX))

    def test_a_1095a_filer_refuses_here(self):
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=0))
        self.assertTrue(self._refusal(
            _scenario(form_1095a=block)).startswith(PREFIX))

    def test_the_emit_chokepoint_refuses_too(self):
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.emit_pdfs(_scenario(), {}, self.tmp / "out")
        self.assertTrue(str(ctx.exception).startswith(PREFIX))


class EarlierRefusalsKeepTheirCauseTests(_RoutedTestCase):
    """A 2021 return with dependents or a head-of-household child candidate
    refuses too, naming the cause that applies on every year."""

    def test_dependents_refuse_with_their_own_message(self):
        for status in (SINGLE, MFJ, MFS, HOH):
            with self.subTest(status=status.value):
                scenario = _scenario(status=status)
                scenario = dataclasses.replace(
                    scenario, config=dataclasses.replace(
                        scenario.config, dependents=["Example Child"]))
                self.assertTrue(self._refusal(scenario).startswith(
                    DEPENDENTS_REFUSAL.split("{", 1)[0]))

    def test_head_of_household_refuses_with_its_own_message(self):
        self.assertEqual(self._refusal(_scenario(status=HOH)),
                         HOH_EIC_REFUSAL_0267E03)


class Eic2021GateBoundaryTests(_RoutedTestCase):

    def test_one_step_under_the_ceiling_refuses(self):
        self.assertTrue(self._refusal(
            _scenario(wages=UNDER_THE_2021_CEILING)).startswith(PREFIX))

    def test_one_step_over_the_ceiling_computes_natively(self):
        scenario = _scenario(wages=OVER_THE_2021_CEILING)
        self.assertFalse(eic_possible(scenario))
        result = self.orch.compute_federal(scenario)
        self.workbook.assert_not_called()
        self.assertEqual(result["wages"], OVER_THE_2021_CEILING)
        self.assertNotIn("eic", result)

    def test_no_earned_income_computes_natively(self):
        scenario = _scenario(wages=0.0)
        self.assertFalse(eic_possible(scenario))
        self.orch.compute_federal(scenario)
        self.workbook.assert_not_called()


class OtherYearsAreUnchangedTests(_RoutedTestCase):
    """The refusal keys on the year: the same returns, one year on, route
    as they did before it."""

    def test_later_years_single_computes_natively_with_the_credit(self):
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                result = self.orch.compute_federal(_scenario(
                    year=year, eic_eligibility=favorable_eligibility()))
                self.workbook.assert_not_called()
                self.assertGreater(result["eic"], 0)

    def test_2022_married_filing_separately_keeps_the_workbook_route(self):
        with self.assertRaises(_WorkbookRouted):
            self.orch.compute_federal(_scenario(year=2022, status=MFS))
