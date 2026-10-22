"""Routing after the childless-EITC routing change (spec §7, Option B;
ruling R-S6-1 transitional routing). Equivalence with the pre-change
behavior, the transitional clause's anti-silent-drop coverage, and its
enforced endpoint. All identities synthetic; amounts from params.

Spec §7.2 hazard box (the checklist): an EIC-possible head-of-household
return must never compute natively — the childless credit is zero for head
of household, so it would print a blank line 27 and drop a credit the filer
may be owed, silently. The pre-split predicate refuse_eic_with_child_candidate
closes it; (a)-(d) below keep it closed.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import years
from tenforty.mappings.f1040 import F1040
from tenforty.models import FilingStatus, Scenario
from tenforty.orchestrator import (
    DEPENDENTS_REFUSAL,
    ReturnOrchestrator,
    eic_possible,
)
from tenforty.params.federal import load as load_params
from tests.fixtures.eic_battery import favorable_eligibility
from tests.fixtures.spine_battery import _battery_config, _w2
from tests.helpers import SPREADSHEETS_DIR, hoh_facts

SINGLE, MFJ, HOH = (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY,
                    FilingStatus.HEAD_OF_HOUSEHOLD)

# The head-of-household refusal text BEFORE the routing change (0267e03,
# refuse_hoh_possible_eic), carried over verbatim by spec §7.1.
HOH_EIC_REFUSAL_0267E03 = (
    "This head_of_household return may be eligible for the Earned Income "
    "Credit with a qualifying child: its earned income and estimated AGI "
    "are below the tax year's EIC income ceiling for one qualifying "
    "child, counting the head-of-household qualifying person. tenforty "
    "does not compute the EIC with a qualifying child on any path: the "
    "native 1040 spine performs no EIC math, and the workbook path would "
    "compute the credit as if you had no qualifying child. A qualifying "
    "child whose dependency exemption you released to the other parent "
    "on Form 8332 still counts for your EIC as the custodial parent (IRS "
    "Pub. 596, Rule 9). There is no acknowledge-and-proceed: the return "
    "would miss a refundable credit you may be owed. File this return by "
    "hand.")


class _WorkbookRouted(Exception):
    """Raised by the patched workbook path: the return left the spine."""


def _orch(test) -> ReturnOrchestrator:
    tmp = tempfile.TemporaryDirectory()
    test.addCleanup(tmp.cleanup)
    return ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                              work_dir=Path(tmp.name))


def _eic_possible_childless(year: int, status: FilingStatus) -> Scenario:
    """Low wages (under every year's no-child ceiling), no child candidate,
    favorable facts."""
    wages = float(load_params(year).eic_income_ceiling[0] // 3)
    joint = status is MFJ
    return Scenario(
        config=_battery_config(year, status),
        w2s=[_w2(year, "Synthetic Employer R", wages, 0.0,
                 owner="taxpayer" if joint else None)],
        eic_eligibility=favorable_eligibility(status.value))


def _hoh(year: int, **config) -> Scenario:
    ceilings = load_params(year).eic_income_ceiling
    wages = float(round((ceilings[0] + ceilings[1]) / 2))
    return Scenario(config=_battery_config(year, HOH, **config),
                    w2s=[_w2(year, "Synthetic Employer R", wages, 0.0)])


def _spine_cells(statuses=(SINGLE, MFJ)):
    return [(year, status) for year in sorted(years.NATIVE_SPINE_STATUSES)
            for status in statuses
            if years.native_spine_supports(year, status.value)]


def _route(test, scenario) -> str | dict:
    """'workbook' if the return leaves the spine, else the native result."""
    with mock.patch.object(ReturnOrchestrator, "_compute_1040_via_workbook",
                           side_effect=_WorkbookRouted):
        try:
            return _orch(test).compute_federal(scenario)
        except _WorkbookRouted:
            return "workbook"


class HohEicEquivalenceTests(unittest.TestCase):
    """(a) Every EIC-possible head-of-household return refuses, with the
    pre-change message verbatim, on every declared year."""

    def test_refuses_with_todays_message_every_declared_year(self):
        for year, status in _spine_cells((HOH,)):
            with self.subTest(year=year):
                scenario = _hoh(year)
                self.assertTrue(eic_possible(scenario))
                with self.assertRaises(NotImplementedError) as ctx:
                    _route(self, scenario)
                self.assertEqual(str(ctx.exception), HOH_EIC_REFUSAL_0267E03)

    def test_the_emit_chokepoint_refuses_too(self):
        scenario = _hoh(2025, head_of_household=hoh_facts(2025))
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NotImplementedError) as ctx:
                _orch(self).emit_pdfs(scenario, {}, Path(tmp))
        self.assertEqual(str(ctx.exception), HOH_EIC_REFUSAL_0267E03)


class DependentsOrderTests(unittest.TestCase):
    """(b) A dependent-bearing return still refuses via refuse_dependents,
    which runs ahead of the child-candidate predicate."""

    def test_dependents_name_their_own_cause_first(self):
        for status in (SINGLE, HOH):
            with self.subTest(status=status.value):
                scenario = _hoh(2025) if status is HOH else (
                    _eic_possible_childless(2025, SINGLE))
                scenario = dataclasses.replace(
                    scenario, config=dataclasses.replace(
                        scenario.config, dependents=["Example Child"]))
                with self.assertRaises(NotImplementedError) as ctx:
                    _route(self, scenario)
                self.assertTrue(str(ctx.exception).startswith(
                    DEPENDENTS_REFUSAL.split("{", 1)[0]))
                self.assertNotEqual(str(ctx.exception),
                                    HOH_EIC_REFUSAL_0267E03)


class DeclaredCellComputesNativelyTests(unittest.TestCase):
    """(c) On every DECLARED EIC cell, an EIC-possible childless return
    computes natively — no workbook call — and carries its credit. Grows
    with the ladder."""

    def test_every_declared_eic_cell(self):
        cells = [(y, FilingStatus(s)) for y, statuses in
                 sorted(years.NATIVE_EIC_STATUSES.items()) for s in statuses]
        self.assertGreater(len(cells), 0)
        for year, status in cells:
            with self.subTest(year=year, status=status.value):
                result = _route(self, _eic_possible_childless(year, status))
                self.assertIsInstance(result, dict)
                self.assertGreater(result["eic"], 0)


class TransitionalCoverageTests(unittest.TestCase):
    """Ruling R-S6-1: no EIC-possible return may EVER produce a native
    result with the credit absent. On a SINGLE/MFJ spine cell not yet in
    years.NATIVE_EIC_STATUSES it keeps the workbook route (which harvests
    line 27 — the oracle tier proves the printed credit); on a declared one
    the native result carries the credit's determination. Each undeclared
    cell's instance dies when that cell lands."""

    def test_no_eic_possible_return_computes_natively_without_the_credit(self):
        for year, status in _spine_cells():
            with self.subTest(year=year, status=status.value):
                scenario = _eic_possible_childless(year, status)
                self.assertTrue(eic_possible(scenario))
                result = _route(self, scenario)
                if years.native_eic_supports(year, status.value):
                    self.assertIn("eic_determination", result)
                else:
                    self.assertEqual(result, "workbook")
                    self.assertEqual(F1040.get_outputs(year).get("eic"),
                                     "EIC")


class TransitionalRoutingEndpointTests(unittest.TestCase):
    """Ruling R-S6-1's enforced endpoint. The transitional clause in
    ReturnOrchestrator._scenario_in_spine_scope exists only while some
    SINGLE/MFJ spine cell has no native childless credit. When
    years.NATIVE_EIC_STATUSES covers them all, this goes RED: delete the
    clause (scope becomes the pure grid lookup of spec §7.1), the
    undeclared-cell branch of TransitionalCoverageTests, and this test, in
    that same commit."""

    def test_some_single_or_mfj_cell_still_lacks_the_native_credit(self):
        missing = [(y, s.value) for y, s in _spine_cells()
                   if not years.native_eic_supports(y, s.value)]
        self.assertNotEqual(missing, [])
