"""IRC §461(l) excess-business-loss guard (Form 461 is not modeled).

tenforty does not compute the excess-business-loss limitation. Instead a
return REFUSES when its business losses could reach the limit: the guard adds
up every loss-positioned business item -- each Schedule C loss, each K-1
business loss box, each rental property loss -- WITHOUT netting any business
income against them, and refuses when that sum exceeds the year's threshold
for the filing status. The un-netted sum is never smaller than the true
excess-business-loss base, so the guard can over-refuse but cannot let a
limited loss through.

The threshold is read from params (`excess_business_loss_threshold`), never
hardcoded here. Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty import orchestrator
from tenforty.models import (
    RentalProperty, ScheduleCBusiness, ScheduleK1, Scenario,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params
from tests.helpers import REPO_ROOT, make_k1_scenario

_YEARS = (2021, 2022, 2023, 2024, 2025)
_HIGH_WAGES = 900_000.0   # keeps the filer far above the EIC routing ceiling


def _threshold(year, status="single"):
    return load_federal_params(year).excess_business_loss_threshold[status]


def _scenario(year=2025, businesses=(), k1s=(), rentals=()):
    base = make_k1_scenario()
    config = dataclasses.replace(
        base.config, year=year,
        acknowledges_sch_c_all_investment_at_risk=True,
        acknowledges_form_7203_attached_separately=True)
    w2 = dataclasses.replace(
        base.w2s[0], wages=_HIGH_WAGES, medicare_wages=_HIGH_WAGES)
    return Scenario(config=config, w2s=[w2],
                    schedule_c_businesses=list(businesses),
                    schedule_k1s=list(k1s), rental_properties=list(rentals))


def _sch_c_loss(amount):
    return ScheduleCBusiness(description="Synthetic Loss Shop",
                             gross_receipts=0.0, supplies=float(amount))


def _k1_loss(amount, entity_type="s_corp"):
    return ScheduleK1(
        entity_name="Synthetic S Corp", entity_ein="00-0000000",
        entity_type=entity_type, material_participation=True,
        ordinary_business_income=-float(amount), qbi_amount=-float(amount))


def _rental_loss(amount):
    return RentalProperty(
        address="1 Example Ave, Example City, EX 00000", property_type=1,
        fair_rental_days=365, personal_use_days=0, rents_received=0.0,
        repairs=float(amount))


class AggregateBusinessLossTests(unittest.TestCase):
    def test_sums_loss_items_from_all_three_lanes(self):
        scn = _scenario(businesses=[_sch_c_loss(100)], k1s=[_k1_loss(200)],
                        rentals=[_rental_loss(400)])
        self.assertEqual(orchestrator.aggregate_business_losses(scn), 700)

    def test_business_income_is_not_netted_against_the_losses(self):
        profit_biz = ScheduleCBusiness(description="Synthetic Profit",
                                       gross_receipts=50_000.0)
        profit_k1 = dataclasses.replace(
            _k1_loss(0), ordinary_business_income=80_000.0, qbi_amount=0.0)
        scn = _scenario(businesses=[_sch_c_loss(100), profit_biz],
                        k1s=[_k1_loss(200), profit_k1])
        self.assertEqual(orchestrator.aggregate_business_losses(scn), 300)

    def test_schedule_c_contributes_its_printed_line_31_loss(self):
        # Entry lines round individually, so the PRINTED loss can exceed the
        # raw one: 1,000.5 + 2,000.5 - 1.0 is 3,000 raw, but the form prints
        # 1,001 + 2,001 - 1 = 3,001 on line 31.
        biz = ScheduleCBusiness(description="Synthetic Loss Shop",
                                gross_receipts=1.0, supplies=1_000.5,
                                advertising=2_000.5)
        self.assertEqual(
            orchestrator.aggregate_business_losses(_scenario(businesses=[biz])),
            3_001)

    def test_k1_and_rental_fractions_round_up_never_down(self):
        k1 = dataclasses.replace(
            _k1_loss(0), ordinary_business_income=0.0, qbi_amount=0.0,
            net_rental_real_estate=-0.4, other_net_rental=-0.4)
        # Two loss boxes of 0.4 print as one combined rental loss of 1; the
        # un-netted sum must not come out below that.
        self.assertEqual(
            orchestrator.aggregate_business_losses(_scenario(k1s=[k1])), 2)
        rental = _rental_loss(0)
        rental = dataclasses.replace(rental, repairs=100.5, taxes=200.5,
                                     rents_received=1.0)
        self.assertEqual(
            orchestrator.aggregate_business_losses(_scenario(rentals=[rental])),
            301)  # the Schedule E line 21 the form prints: 101 + 201 - 1

    def test_no_losses_is_zero(self):
        self.assertEqual(orchestrator.aggregate_business_losses(_scenario()), 0)


class ExcessBusinessLossGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")

    def _assert_refused(self, scenario):
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scenario)
        message = str(ctx.exception)
        self.assertIn("461(l)", message)
        self.assertIn("Form 461", message)

    def test_threshold_is_defined_for_every_guarded_year_and_status(self):
        for year in _YEARS:
            with self.subTest(year=year):
                thresholds = load_federal_params(
                    year).excess_business_loss_threshold
                self.assertGreater(thresholds["single"], 0)
                self.assertEqual(thresholds["married_jointly"],
                                 2 * thresholds["single"])

    def test_schedule_c_loss_over_the_threshold_refuses(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self._assert_refused(_scenario(
                    year, businesses=[_sch_c_loss(_threshold(year) + 1)]))

    def test_schedule_c_loss_at_the_threshold_computes(self):
        for year in _YEARS:
            with self.subTest(year=year):
                limit = _threshold(year)
                out = self.orch.compute_federal(
                    _scenario(year, businesses=[_sch_c_loss(limit)]))
                self.assertEqual(out["sch_1_line_3_business_income"], -limit)

    def test_k1_loss_over_the_threshold_refuses(self):
        self._assert_refused(_scenario(k1s=[_k1_loss(_threshold(2025) + 1)]))

    def test_k1_loss_at_the_threshold_computes(self):
        limit = _threshold(2025)
        out = self.orch.compute_federal(_scenario(k1s=[_k1_loss(limit)]))
        self.assertEqual(out["sch_1_line_5_rental_re_royalty"], -limit)

    def test_rental_loss_over_the_threshold_refuses(self):
        self._assert_refused(
            _scenario(rentals=[_rental_loss(_threshold(2025) + 1)]))

    def test_lanes_each_under_but_together_over_refuse(self):
        third = _threshold(2025) // 3 + 1
        self._assert_refused(_scenario(
            businesses=[_sch_c_loss(third)], k1s=[_k1_loss(third)],
            rentals=[_rental_loss(third)]))

    def test_offsetting_business_income_does_not_lift_the_refusal(self):
        profit_k1 = dataclasses.replace(
            _k1_loss(0), entity_name="Synthetic Profit Corp",
            ordinary_business_income=400_000.0, qbi_amount=0.0)
        self._assert_refused(_scenario(
            businesses=[_sch_c_loss(_threshold(2025) + 1)], k1s=[profit_k1]))

    def test_printed_loss_one_dollar_over_refuses_though_raw_is_at_threshold(self):
        limit = _threshold(2025)
        biz = ScheduleCBusiness(
            description="Synthetic Loss Shop", gross_receipts=1.0,
            supplies=limit - 1_000 + 0.5, advertising=1_000.5)
        # Raw arithmetic lands exactly ON the threshold ...
        self.assertEqual(biz.supplies + biz.advertising - biz.gross_receipts,
                         limit)
        # ... but line 31 prints one dollar over it.
        self._assert_refused(_scenario(businesses=[biz]))

    def test_guard_fires_before_the_workbook_route(self):
        """A married-jointly return routes to the workbook path, not the
        native spine. The guard must refuse it too -- BEFORE the workbook is
        evaluated."""
        scn = _scenario(rentals=[_rental_loss(
            _threshold(2025, "married_jointly") + 1)])
        mfj = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, filing_status="married_jointly"))
        self.assertFalse(self.orch._scenario_in_spine_scope(mfj))
        with mock.patch.object(
                self.orch, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook route was reached"),
        ) as workbook:
            with self.assertRaises(NotImplementedError) as ctx:
                self.orch._compute_1040_pipeline(mfj)
        workbook.assert_not_called()
        self.assertIn("461(l)", str(ctx.exception))

    def test_workbook_route_under_the_threshold_reaches_the_workbook(self):
        # Reachability of the route the test above protects: the same joint
        # return UNDER the threshold does go to the workbook.
        scn = _scenario(rentals=[_rental_loss(1_000)])
        mfj = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, filing_status="married_jointly"))
        with mock.patch.object(
                self.orch, "_compute_1040_via_workbook",
                return_value={"taxable_income": 0}) as workbook:
            try:
                self.orch._compute_1040_pipeline(mfj)
            except Exception:
                pass  # downstream of the mocked workbook is not under test
        workbook.assert_called_once()

    def test_married_jointly_uses_its_own_threshold(self):
        single_limit = _threshold(2025)
        scn = _scenario(k1s=[_k1_loss(single_limit + 1)])
        mfj = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, filing_status="married_jointly"))
        # Over the single threshold, under the joint one: the guard itself
        # must not fire for the joint filer.
        self.orch._refuse_possible_excess_business_loss(mfj)
        with self.assertRaises(NotImplementedError):
            self.orch._refuse_possible_excess_business_loss(scn)


if __name__ == "__main__":
    unittest.main()
