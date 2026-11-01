"""Ruling R-S7-2: the workbook-path EIC fact guard.

Production never writes the workbook's EIC answers, and with every answer
input blank the sheet's derived answers are exactly the ALL-FAVORABLE facts
(pinned per year by tests/test_eic_workbook_health.py). So the workbook is
right for an all-favorable eligibility block and silently wrong for any
unfavorable fact. `_compute_1040_via_workbook` therefore refuses — before
any engine call — a stated block that the defaults would contradict: an
unfavorable fact, Form 8862 applying, or a block on a status that is not
SINGLE/MFJ. The oracle-only adapter (the sole answer-writer) is exempt.

Production single/MFJ no longer reaches this path (ruling R-S8-21), so those
cases call it directly. The guard stays live for MFS/QSS production and for
the oracle instrument. All identities synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.models import FilingStatus, ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_params
from tests.eic_oracle_adapter import eic_answers_adapter
from tests.fixtures.eic_battery import favorable_eligibility, favorable_person
from tests.fixtures.spine_battery import _battery_config, _w2
from tests.helpers import SPREADSHEETS_DIR

YEAR = 2024


class _Engine(Exception):
    """The patched engine was reached: the guard let the return through."""


def _scenario(eligibility, status=FilingStatus.SINGLE, year=YEAR):
    wages = float(load_params(year).eic_income_ceiling[0] // 3)
    joint = status is FilingStatus.MARRIED_FILING_JOINTLY
    return Scenario(
        config=_battery_config(year, status),
        w2s=[_w2(year, "Synthetic Employer G", wages, 0.0,
                 owner="taxpayer" if joint else None)],
        eic_eligibility=eligibility)


class WorkbookEicFactGuardTests(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                       work_dir=Path(tmp.name))
        patcher = mock.patch.object(self.orch.engine, "compute",
                                    side_effect=_Engine)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _workbook(self, scenario):
        eff, _ = self.orch._build_effective_scenario(scenario)
        return self.orch._compute_1040_via_workbook(eff)

    def _refusal(self, scenario):
        with self.assertRaises(NotImplementedError) as ctx:
            self._workbook(scenario)
        return str(ctx.exception)

    def test_each_unfavorable_fact_refuses_naming_it(self):
        for fact, value in (
                ("ssn_valid_for_employment", False),
                ("nonresident_alien_any_part_of_year", True),
                ("main_home_in_us_more_than_half_year", False),
                ("could_be_qualifying_child_of_another", True),
                ("can_be_claimed_as_dependent", True)):
            with self.subTest(fact=fact):
                message = self._refusal(_scenario(favorable_eligibility(
                    taxpayer=favorable_person(**{fact: value}))))
                self.assertTrue(message.startswith(
                    "workbook_eic_fact_not_modeled"), message)
                self.assertIn(fact, message)

    def test_a_joint_spouse_fact_refuses(self):
        message = self._refusal(_scenario(
            favorable_eligibility("married_filing_jointly",
                                  spouse=favorable_person(
                                      main_home_in_us_more_than_half_year=False)),
            status=FilingStatus.MARRIED_FILING_JOINTLY))
        self.assertIn("main_home_in_us_more_than_half_year", message)

    def test_form_8862_refuses(self):
        message = self._refusal(_scenario(favorable_eligibility(
            prior_eic_disallowance_requires_8862=True)))
        self.assertIn("prior_eic_disallowance_requires_8862", message)

    def test_a_block_on_an_undeclared_status_refuses(self):
        mfs = FilingStatus.MARRIED_FILING_SEPARATELY
        scenario = _scenario(favorable_eligibility(), status=mfs, year=2025)
        # The production route: MFS is outside the native grid.
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scenario)
        message = str(ctx.exception)
        self.assertTrue(message.startswith("workbook_eic_fact_not_modeled"))
        self.assertIn("married_filing_separately", message)

    def test_the_joint_skip_of_questions_5_and_6_holds_here_too(self):
        # 2025 joint wording (R-S5-2): a joint return is never asked
        # questions 5 and 6, so stating them unfavorable is not refused.
        mfj = FilingStatus.MARRIED_FILING_JOINTLY
        with self.assertRaises(_Engine):
            self._workbook(_scenario(favorable_eligibility(
                mfj.value, taxpayer=favorable_person(
                    could_be_qualifying_child_of_another=True,
                    can_be_claimed_as_dependent=True)), status=mfj))

    def test_an_on_grid_schedule_c_filer_is_told_the_eic_is_the_cause(self):
        # Direct call: compute_federal refuses this return earlier (R-S8-21).
        scenario = dataclasses.replace(
            _scenario(None, year=2021), w2s=[],
            schedule_c_businesses=[ScheduleCBusiness(
                description="Example Route", gross_receipts=10_000.0)])
        message = self._refusal(scenario)
        self.assertIn("possibly eligible for the Earned Income Credit",
                      message)
        self.assertNotIn("filer class declared on the native grid", message)

    def test_the_oracle_adapter_is_exempt(self):
        # TY2025: the year whose answer cells the adapter has located.
        scenario = _scenario(favorable_eligibility(
            taxpayer=favorable_person(ssn_valid_for_employment=False)),
            year=2025)
        eff, _ = self.orch._build_effective_scenario(scenario)
        with eic_answers_adapter(self.orch):
            with self.assertRaises(_Engine):
                self.orch._compute_1040_via_workbook(eff)
