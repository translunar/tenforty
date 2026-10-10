"""Reader Rewire: every reader of a rental's depreciation goes through the
resolver.

Each test drives an ASSET-MODE rental whose stated `depreciation` scalar is
zero. A reader still on the raw field sees 0 there and gives a different,
wrong answer -- which is what made these red before the rewire, and what
makes each of them go red again when the resolver is made to return zero.

The 6,970 figure is a legacy regression pin (a January 27.5-year building on
a 200,000 basis, from the pre-existing depreciation tests), not a hand oracle.
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from tenforty import ca_divergences
from tenforty.forms import sch_e
from tenforty.models import DepreciableAsset, RentalProperty
from tenforty.oracle.flattener import flatten_scenario
from tenforty.orchestrator import (
    ReturnOrchestrator, _rental_net_income, aggregate_business_losses,
)
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

YEAR = 2025
BUILDING_DEPRECIATION = 6_970


def _building(basis: float = 200_000.0) -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=basis, recovery_class="27.5-year")


def _rental(*, rents: float, assets=(), **extra) -> RentalProperty:
    return RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=rents,
        depreciable_assets=list(assets), **extra)


def _scenario(*rentals: RentalProperty, year: int = YEAR):
    s = make_simple_scenario()
    s.config.year = year
    s.rental_properties = list(rentals)
    return s


class _OrchestratorCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(self._tmp.name))


class ScheduleELinesTests(unittest.TestCase):
    def test_lines_18_20_21_carry_the_resolved_amount(self):
        s = _scenario(_rental(
            rents=24_000.0, taxes=3_000.0, mortgage_interest=8_000.0,
            assets=[_building()]))
        r = sch_e.compute(s, upstream={})
        self.assertEqual(
            r["sch_e_property_a_depreciation"], BUILDING_DEPRECIATION)
        self.assertEqual(
            r["sch_e_property_a_total_expenses"],
            3_000 + 8_000 + BUILDING_DEPRECIATION)
        self.assertEqual(
            r["sch_e_property_a_income_loss"],
            24_000 - (3_000 + 8_000 + BUILDING_DEPRECIATION))
        self.assertEqual(
            r["sch_e_line_26_total"], r["sch_e_property_a_income_loss"])

    def test_rental_with_no_depreciation_prints_no_line_18(self):
        s = _scenario(_rental(rents=24_000.0, taxes=3_000.0))
        r = sch_e.compute(s, upstream={})
        self.assertNotIn("sch_e_property_a_depreciation", r)
        self.assertEqual(r["sch_e_property_a_total_expenses"], 3_000)

    def test_stated_mode_line_18_is_the_stated_scalar_rounded(self):
        s = _scenario(_rental(
            rents=24_000.0, depreciation=5_000.5,
            acknowledges_depreciation_stated_outside_macrs=True))
        r = sch_e.compute(s, upstream={})
        self.assertEqual(r["sch_e_property_a_depreciation"], 5_001)

    def test_overridden_activity_prints_the_override_amount(self):
        from tenforty.forms.depreciation.macrs import macrs_deduction
        from tenforty.forms.depreciation.resolver import (
            reconstruct_prior_depreciation,
        )
        from tenforty.models import DepreciationOverride
        old = DepreciableAsset(
            description="Rental building",
            date_placed_in_service=date(2019, 6, 1),
            basis=200_000.0, recovery_class="27.5-year")
        old.prior_depreciation = float(
            reconstruct_prior_depreciation(old, YEAR, mid_quarter=False))
        engine = macrs_deduction(old, YEAR, return_year=YEAR, mid_quarter=False)
        self.assertNotEqual(engine, 6_500)
        s = _scenario(_rental(
            rents=24_000.0, assets=[old],
            depreciation_override=DepreciationOverride(
                amount=6_500.0, restates_engine_amount=float(engine),
                acknowledgment=True)))
        r = sch_e.compute(s, upstream={})
        self.assertEqual(r["sch_e_property_a_depreciation"], 6_500)


class PrintedRentalNetTests(unittest.TestCase):
    def test_printed_rental_net_reflects_resolved_depreciation(self):
        rp = _rental(rents=5_000.0, assets=[_building()])
        self.assertEqual(
            sch_e.printed_rental_net(rp, YEAR, mid_quarter=False), 5_000 - BUILDING_DEPRECIATION)

    def test_aggregate_business_losses_counts_the_asset_mode_loss(self):
        s = _scenario(_rental(rents=5_000.0, assets=[_building()]))
        self.assertEqual(
            aggregate_business_losses(s), BUILDING_DEPRECIATION - 5_000)


class ExcessBusinessLossGuardTests(_OrchestratorCase):
    """The IRC 461(l) guard crosses its threshold on a scenario that crosses
    ONLY because of asset-mode depreciation."""

    def _big(self):
        return _scenario(_rental(
            rents=10_000.0, assets=[_building(basis=20_000_000.0)]))

    def test_guard_refuses_when_asset_depreciation_pushes_over(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"excess-business-loss threshold"):
            self.orchestrator._refuse_possible_excess_business_loss(
                self._big())

    def test_same_rental_without_the_assets_passes_the_guard(self):
        s = self._big()
        s.rental_properties[0].depreciable_assets = []
        self.orchestrator._refuse_possible_excess_business_loss(s)


class NetLossPredicateTests(_OrchestratorCase):
    def test_loss_only_after_resolved_depreciation_is_a_net_loss(self):
        s = _scenario(_rental(rents=5_000.0, assets=[_building()]))
        self.assertTrue(sch_e.has_any_net_loss(s))

    def test_non_loss_twin(self):
        s = _scenario(_rental(rents=24_000.0, assets=[_building()]))
        self.assertFalse(sch_e.has_any_net_loss(s))

    def test_8582_emit_predicate_follows(self):
        loss = _scenario(_rental(rents=5_000.0, assets=[_building()]))
        gain = _scenario(_rental(rents=24_000.0, assets=[_building()]))
        for scenario, expected in ((loss, True), (gain, False)):
            with self.subTest(expected=expected):
                # No K-1s: the fanout carries no passive activity, so the
                # rental net-loss leg alone decides.
                _schedules, fanout = (
                    self.orchestrator._compute_native_schedules(scenario))
                self.assertEqual(len(fanout.passive_activities), 0)
                self.assertIs(
                    self.orchestrator._should_emit_8582(
                        scenario, {"k1_fanout": fanout}), expected)


class RentalNetIncomeEstimateTests(unittest.TestCase):
    def test_estimate_reflects_resolved_depreciation(self):
        rp = _rental(rents=24_000.0, taxes=3_000.0, assets=[_building()])
        self.assertEqual(
            _rental_net_income(rp, YEAR, mid_quarter=False),
            24_000.0 - 3_000.0 - BUILDING_DEPRECIATION)


class FlattenerTests(unittest.TestCase):
    def test_flattener_emits_resolved_depreciation(self):
        flat = flatten_scenario(
            _scenario(_rental(rents=5_000.0, assets=[_building()])))
        self.assertEqual(flat["sche_depreciation_a"], BUILDING_DEPRECIATION)

    def test_8582_net_block_agrees_with_it(self):
        flat = flatten_scenario(
            _scenario(_rental(rents=5_000.0, assets=[_building()])))
        self.assertEqual(
            flat["sche_8582_net_loss"], BUILDING_DEPRECIATION - 5_000)
        self.assertNotIn("sche_8582_net_income", flat)

    def test_non_loss_twin_reports_net_income(self):
        flat = flatten_scenario(
            _scenario(_rental(rents=24_000.0, assets=[_building()])))
        self.assertEqual(
            flat["sche_8582_net_income"], 24_000 - BUILDING_DEPRECIATION)
        self.assertNotIn("sche_8582_net_loss", flat)

    def test_rental_with_no_depreciation_emits_no_key(self):
        flat = flatten_scenario(_scenario(_rental(rents=5_000.0)))
        self.assertNotIn("sche_depreciation_a", flat)


class CaliforniaTriggerTests(unittest.TestCase):
    def test_asset_mode_rental_trips_the_trigger(self):
        s = _scenario(_rental(rents=24_000.0, assets=[_building()]))
        self.assertTrue(ca_divergences.has_rental_depreciation(s))

    def test_rental_with_neither_source_does_not(self):
        s = _scenario(_rental(rents=24_000.0))
        self.assertFalse(ca_divergences.has_rental_depreciation(s))

    def test_stated_mode_rental_trips_it(self):
        s = _scenario(_rental(
            rents=24_000.0, depreciation=5_000.0,
            acknowledges_depreciation_stated_outside_macrs=True))
        self.assertTrue(ca_divergences.has_rental_depreciation(s))


class DownstreamAgreementTests(_OrchestratorCase):
    """Forms fed BY Schedule E see the same number: Form 8582's passive
    loss, Schedule 1 line 5 and the spine's line 26 all move with it."""

    def test_income_rental(self):
        s = _scenario(_rental(
            rents=24_000.0, taxes=3_000.0, assets=[_building()]))
        net = 24_000 - 3_000 - BUILDING_DEPRECIATION
        results = self.orchestrator.compute_federal(s)
        self.assertEqual(results["sche_line26"], net)
        self.assertEqual(results["sch_1_line_5_rental_re_royalty"], net)

    def test_loss_rental_reaches_form_8582(self):
        s = _scenario(_rental(rents=5_000.0, assets=[_building()]))
        loss = BUILDING_DEPRECIATION - 5_000
        schedules, _fanout = self.orchestrator._compute_native_schedules(s)
        self.assertEqual(
            schedules["sch_e"]["sch_e_property_a_income_loss"], -loss)
        self.assertEqual(
            schedules["f8582"]["f8582_line_1b_activities_with_loss"], loss)
        # Twin: with the asset removed there is no passive loss at all.
        s.rental_properties[0].depreciable_assets = []
        schedules, _fanout = self.orchestrator._compute_native_schedules(s)
        self.assertEqual(
            schedules["f8582"]["f8582_line_1b_activities_with_loss"], 0)

    def test_spine_scope_estimate_sees_the_asset_mode_loss(self):
        """`_scenario_in_spine_scope` estimates AGI from positive rental net
        income; resolved depreciation enters that estimate."""
        from unittest import mock
        s = _scenario(_rental(rents=24_000.0, assets=[_building()]))
        seen = []
        real = _rental_net_income

        def spy(r, tax_year, *, mid_quarter):
            seen.append(real(r, tax_year, mid_quarter=mid_quarter))
            return seen[-1]

        with mock.patch("tenforty.orchestrator._rental_net_income", spy):
            self.orchestrator._scenario_in_spine_scope(s)
        self.assertEqual(seen, [24_000.0 - BUILDING_DEPRECIATION])


if __name__ == "__main__":
    unittest.main()
