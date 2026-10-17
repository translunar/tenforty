"""The EIC gate counts the head-of-household qualifying child, and an
EIC-possible head-of-household return refuses instead of rerouting.

A head-of-household filer's qualifying person under the v0.2.0 scope is a
qualifying child (schema rule 13), and that child may be the filer's EIC
qualifying child even when no dependent is claimed: under a Form 8332
release the custodial parent keeps the EIC (IRS Pub. 596, Rule 9). The gate
used to read `len(dependents)` (0) and so tested the childless ceiling;
it now counts one child for every head-of-household return (ruling
R-eic-count-by-status). Neither path computes the EIC with a qualifying
child -- the workbook receives no child count and would figure it childless
-- so a declared-year head-of-household return the gate rules EIC-possible
refuses before routing (ruling Q2).

Ceilings are read from params; no tax values are written here. Synthetic
values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years as year_manifest
from tenforty.models import (
    FilingStatus,
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    Scenario,
)
from tenforty.orchestrator import (
    ReturnOrchestrator,
    eic_gate_child_count,
    refuse_hoh_possible_eic,
)
from tenforty.params.federal import load as load_params
from tests.fixtures.spine_battery import (
    _battery_config,
    _w2,
    build_ptc_reconciliation,
)
from tests.helpers import REPO_ROOT

_HOH = FilingStatus.HEAD_OF_HOUSEHOLD
_YEARS = tuple(year for year in sorted(year_manifest.NATIVE_SPINE_STATUSES)
               if year_manifest.native_spine_supports(year, _HOH.value))


def _block(year: int) -> HeadOfHouseholdFacts:
    return HeadOfHouseholdFacts(
        marital_status=HohMaritalStatus.UNMARRIED,
        qualifying_person=HohQualifyingPerson(
            first_name="Example", last_name="Child", ssn="000000005",
            birthdate=f"{year - 10}-03-07",
            relationship=HohRelationship.CHILD_OR_STEPCHILD,
            full_time_student=None, permanently_disabled=None,
            gross_income=0.0, days_lived_with_you=365))


def _between_ceilings(year: int) -> float:
    """W-2 wages strictly between the zero-child and one-child ceilings."""
    ceilings = load_params(year).eic_income_ceiling
    return float(round((ceilings[0] + ceilings[1]) / 2))


def _above_one_child_ceiling(year: int) -> float:
    """Wages between the one-child and two-child ceilings."""
    ceilings = load_params(year).eic_income_ceiling
    return float(round((ceilings[1] + ceilings[2]) / 2))


def _scenario(year: int, status: FilingStatus, wages: float,
              **config) -> Scenario:
    # Built without a head_of_household block on purpose: the count is
    # keyed on the status (R-eic-count-by-status), not on the block.
    config.setdefault("head_of_household", None)
    return Scenario(config=_battery_config(year, status, **config),
                    w2s=[_w2(year, "Synthetic Employer E", wages,
                             federal_tax_withheld=float(round(wages / 10)))])


def _orchestrator(test: unittest.TestCase) -> ReturnOrchestrator:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                              work_dir=Path(tmp.name) / "work")


def _never_the_workbook(*args, **kwargs):
    raise AssertionError("routed to the workbook path")


class EicGateChildCountTests(unittest.TestCase):
    def test_head_of_household_without_dependents_counts_one(self):
        cfg = _battery_config(2025, _HOH, head_of_household=None)
        self.assertIsNone(cfg.head_of_household)
        self.assertEqual(eic_gate_child_count(cfg), 1)

    def test_single_counts_zero(self):
        self.assertEqual(eic_gate_child_count(
            _battery_config(2025, FilingStatus.SINGLE)), 0)

    def test_block_is_not_counted_twice(self):
        self.assertEqual(eic_gate_child_count(_battery_config(
            2025, _HOH, head_of_household=_block(2025))), 1)

    def test_dependents_still_count(self):
        self.assertEqual(eic_gate_child_count(_battery_config(
            2025, FilingStatus.SINGLE, dependents=["Child A", "Child B"])), 2)


class HohEicGateTests(unittest.TestCase):
    """Review Focus 5: income between the zero-child and one-child ceilings."""

    def test_head_of_household_between_ceilings_refuses_naming_the_eic(self):
        orch = _orchestrator(self)
        for year in _YEARS:
            with self.subTest(year=year):
                scn = _scenario(year, _HOH, _between_ceilings(year))
                with mock.patch.object(
                        ReturnOrchestrator, "_compute_1040_via_workbook",
                        side_effect=_never_the_workbook):
                    with self.assertRaises(NotImplementedError) as ctx:
                        orch.compute_federal(scn)
                message = str(ctx.exception)
                self.assertIn("Earned Income Credit", message)
                self.assertIn("qualifying child", message)
                self.assertIn("Form 8332", message)
                self.assertIn("by hand", message)

    def test_single_between_ceilings_still_routes_native(self):
        orch = _orchestrator(self)
        for year in _YEARS:
            with self.subTest(year=year):
                scn = _scenario(year, FilingStatus.SINGLE,
                                _between_ceilings(year))
                eff, _ = orch._build_effective_scenario(scn)
                self.assertTrue(orch._scenario_in_spine_scope(eff))
                with mock.patch.object(
                        ReturnOrchestrator, "_compute_1040_via_workbook",
                        side_effect=_never_the_workbook):
                    orch.compute_federal(scn)

    def test_head_of_household_above_the_one_child_ceiling_routes_native(self):
        orch = _orchestrator(self)
        for year in _YEARS:
            with self.subTest(year=year):
                # Computes the federal header, so it carries the block.
                scn = _scenario(year, _HOH, _above_one_child_ceiling(year),
                                head_of_household=_block(year))
                eff, _ = orch._build_effective_scenario(scn)
                self.assertTrue(orch._scenario_in_spine_scope(eff))
                with mock.patch.object(
                        ReturnOrchestrator, "_compute_1040_via_workbook",
                        side_effect=_never_the_workbook):
                    orch.compute_federal(scn)

    def test_between_ceilings_head_of_household_is_out_of_spine_scope(self):
        # The precondition refuse_hoh_possible_eic relies on: on a declared
        # (year, head_of_household), out of scope means EIC-possible.
        orch = _orchestrator(self)
        for year in _YEARS:
            with self.subTest(year=year):
                eff, _ = orch._build_effective_scenario(
                    _scenario(year, _HOH, _between_ceilings(year)))
                self.assertFalse(orch._scenario_in_spine_scope(eff))


class RefuseHohPossibleEicUnitTests(unittest.TestCase):
    def test_refuses_head_of_household(self):
        with self.assertRaises(NotImplementedError) as ctx:
            refuse_hoh_possible_eic(_battery_config(2025, _HOH))
        self.assertIn("Pub. 596", str(ctx.exception))

    def test_other_statuses_pass(self):
        for status in (FilingStatus.SINGLE,
                       FilingStatus.MARRIED_FILING_JOINTLY):
            with self.subTest(status=status.value):
                refuse_hoh_possible_eic(_battery_config(2025, status))


class HohEicRefusalOrderTests(unittest.TestCase):
    def test_1095a_family_size_refusal_fires_first(self):
        # A head-of-household 1095-A return with between-ceilings wages gets
        # the R-hoh-ptc refusal (it runs ahead of routing), not the EIC one.
        orch = _orchestrator(self)
        for year in _YEARS:
            with self.subTest(year=year):
                scn = build_ptc_reconciliation(year, _HOH)
                scn = dataclasses.replace(scn, w2s=[_w2(
                    year, "Synthetic Employer P", _between_ceilings(year),
                    federal_tax_withheld=0.0)])
                eff, _ = orch._build_effective_scenario(scn)
                self.assertFalse(orch._scenario_in_spine_scope(eff))
                with self.assertRaisesRegex(
                        NotImplementedError,
                        r"(?s)head_of_household.*dependents spec") as ctx:
                    orch.compute_federal(scn)
                self.assertNotIn("Earned Income Credit", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
