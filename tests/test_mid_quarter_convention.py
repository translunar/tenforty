"""The mid-quarter convention: the computed 40% test, and what it decides.

When the test says the mid-quarter convention applies to a placement year,
every personal-property asset placed in that year is depreciated from the
table for the quarter it was placed in. The test is a scenario-level check
(taxpayer-wide), not part of the per-activity resolver; the resolver is
handed its answer.

All bases are invented round figures chosen to sit on either side of the
threshold. Where an amount is asserted under the mid-quarter convention the
tables are patched with SENTINEL percentages (tests/test_mid_quarter_engine):
these tests pin which convention and which quarter an asset takes, not what
the publication prints.
"""

import copy
import unittest
from datetime import date

from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms.depreciation.resolver import (
    mid_quarter_applies, mid_quarter_bases, resolve,
)
from tenforty.rounding import irs_round
from tests.test_mid_quarter_engine import _patched, _sentinel
from tenforty.models import (
    DepreciableAsset, RentalProperty, ScheduleCBusiness,
)
from tests.helpers import make_simple_scenario

YEAR = 2025


def _personal(basis: float, month: int, *, year: int = YEAR,
              description: str = "Equipment") -> DepreciableAsset:
    asset = DepreciableAsset(
        description=description, date_placed_in_service=date(year, month, 15),
        basis=basis, recovery_class="5-year",
        no_bonus_or_section_179_history=True)
    if year < YEAR:
        asset.acknowledges_prior_depreciation_as_stated = True
        asset.prior_depreciation = 0.0
        asset.convention = "half-year"
    return asset


def _real(basis: float, month: int, recovery_class: str) -> DepreciableAsset:
    return DepreciableAsset(
        description="Building", date_placed_in_service=date(YEAR, month, 15),
        basis=basis, recovery_class=recovery_class)


def _rental(*assets, **extra) -> RentalProperty:
    return RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=list(assets), **extra)


def _business(*assets, **extra) -> ScheduleCBusiness:
    return ScheduleCBusiness(
        description="Consulting", gross_receipts=50_000.0,
        depreciable_assets=tuple(assets), **extra)


def _scenario(rentals=(), businesses=(), acknowledgment=None):
    s = make_simple_scenario()
    s.config.year = YEAR
    s.rental_properties = list(rentals)
    s.schedule_c_businesses = list(businesses)
    s.acknowledges_no_personal_property_behind_stated_depreciation = (
        acknowledgment)
    s.acknowledges_no_listed_property = True
    return s


def _check(scenario) -> None:
    enforce_scoped_refusals(scenario, "load")


TRIPS = True
SILENT = False


def _answer(scenario) -> bool:
    """The return's 40% answer, after the load ledger has accepted the
    scenario (the convention is computed, never refused)."""
    _check(scenario)
    return mid_quarter_applies(scenario)


def _amounts(activity, scenario) -> list[int]:
    """Each asset's current-year amount, through the one door, under the
    return's own answer."""
    resolved = resolve(
        activity, YEAR, mid_quarter=mid_quarter_applies(scenario))
    return [row.amount for row in resolved.per_asset]


def _conventions(activity, scenario) -> list[str]:
    """Each asset's convention. The tables are patched for the call: which
    convention an asset takes does not depend on any percentage."""
    with _patched():
        resolved = resolve(
            activity, YEAR, mid_quarter=mid_quarter_applies(scenario))
    return [row.convention for row in resolved.per_asset]


class FortyPercentTestTests(unittest.TestCase):
    """THE RULE, transcribed from the sources.

    Publication 946 (2025), "How To Depreciate Property", chapter 4, section
    "Which Convention Applies?", page 34 (irs.gov/pub/irs-pdf/p946.pdf):

        "The mid-quarter convention. Use this convention if the mid-month
        convention does not apply and the total depreciable bases of MACRS
        property you placed in service during the last 3 months of the tax
        year (excluding nonresidential real property, residential rental
        property, any railroad grading or tunnel bore, property placed in
        service and disposed of in the same year, and property that is
        being depreciated under a method other than MACRS) are more than
        40% of the total depreciable bases of all MACRS property you placed
        in service during the entire year."

      and the Caution beneath it:

        "For purposes of determining whether the mid-quarter convention
        applies, the depreciable basis of property you placed in service
        during the tax year reflects the reduction in basis for amounts
        expensed under section 179 and the part of the basis of property
        attributable to personal use. However, it does not reflect any
        reduction in basis for any special depreciation allowance."

    26 U.S.C. section 168(d)(3) (law.cornell.edu/uscode/text/26/168, read
    2026-10-09):

        "(A) In general. Except as provided in regulations, if during any
        taxable year-- (i) the aggregate bases of property to which this
        section applies placed in service during the last 3 months of the
        taxable year, exceed (ii) 40 percent of the aggregate bases of
        property to which this section applies placed in service during
        such taxable year, the applicable convention for all property to
        which this section applies placed in service during such taxable
        year shall be the mid-quarter convention.
        (B) Certain property not taken into account. For purposes of
        subparagraph (A), there shall not be taken into account-- (i) any
        nonresidential real property, residential rental property, and
        railroad grading or tunnel bore, and (ii) any other property placed
        in service and disposed of during the same taxable year."

    WHERE THE TWO DIVERGE, THE STATUTE CONTROLS. The publication's sentence
    hangs its exclusion parenthetical on the last-3-months total only; read
    literally, real property would still count in the entire-year total.
    The statute's "For purposes of subparagraph (A)" scopes the exclusions
    over BOTH (A)(i) and (A)(ii). Ruled 2026-10-09: the exclusions come out
    of both totals. `test_current_year_building_is_absent_from_both_totals`
    is the test that tells the two readings apart.

    The five exclusions, and which are reachable here:
      - nonresidential real property, residential rental property: tested.
      - railroad grading or tunnel bore: no such recovery class exists in
        the asset model (an unknown class refuses at load).
      - property placed in service and disposed of in the same year: any
        `disposed` asset refuses at load.
      - property depreciated under a method other than MACRS: the statute's
        own "property to which this section applies"; the model has no
        non-MACRS method.
      The last three are unreachable by construction, so there are NO tests
      asserting them (a negative assertion over unreachable space proves
      nothing).

    The Caution's basis definition is inert here, and stays inert only while
    these hold: a section 179 or bonus election cannot be stated (assets
    with such history refuse via `bonus_or_section_179_history` unless an
    activity override pins the figure), and the asset model has no
    personal-use field. Lifting either makes the Caution an obligation on
    the basis this test uses.

    The rule is about the TAXPAYER ("you" / "any taxable year"), not an
    activity: the totals run across every activity on the return.
    """

    def test_trips_over_the_threshold_and_computes(self):
        """4,001 of 10,000: mid-quarter, each asset from its own quarter."""
        rental = _rental(_personal(5_999.0, 3), _personal(4_001.0, 11))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), TRIPS)
        self.assertEqual(mid_quarter_bases(s), (4_001.0, 10_000.0))
        self.assertEqual(
            _conventions(rental, s), ["mid-quarter", "mid-quarter"])
        with _patched():
            self.assertEqual(_amounts(rental, s), [
                irs_round(5_999.0 * _sentinel(1, 5, 1)),
                irs_round(4_001.0 * _sentinel(4, 5, 1))])

    def test_exactly_forty_percent_is_half_year(self):
        """ "more than 40%" / "exceed ... 40 percent": equality does not
        trip, and both assets take the half-year table."""
        rental = _rental(_personal(6_000.0, 3), _personal(4_000.0, 11))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), SILENT)
        self.assertEqual(_conventions(rental, s), ["half-year", "half-year"])
        self.assertEqual(_amounts(rental, s), [1_200, 800])

    def test_one_dollar_over_forty_percent_trips(self):
        """The smallest whole-dollar step past equality, and a fraction of
        a cent past it: both trip."""
        for late in (4_001.0, 4_000.01):
            with self.subTest(late=late):
                self.assertEqual(_answer(_scenario(rentals=[_rental(
                    _personal(10_000.0 - late, 3),
                    _personal(late, 11))])), TRIPS)

    def test_exactly_forty_percent_in_cents_is_half_year(self):
        """Money is compared in whole cents, never as floats. 20,780.06 is
        exactly two fifths of 51,950.15, so the year does not trip -- but
        as binary floats 20780.06 * 100 comes out a hair over 40 * 51950.15,
        and a float comparison calls that "more than 40%"."""
        self.assertGreater(20_780.06 * 100, 2_078_006.0)     # the hazard
        self.assertEqual(2_078_006 * 100, 40 * 5_195_015)    # exactly 40%
        rental = _rental(_personal(31_170.09, 3), _personal(20_780.06, 11))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), SILENT)
        self.assertEqual(_conventions(rental, s), ["half-year", "half-year"])
        self.assertEqual(_amounts(rental, s), [6_234, 4_156])

    def test_one_cent_over_forty_percent_trips(self):
        s = _scenario(rentals=[_rental(
            _personal(31_170.09, 3), _personal(20_780.07, 11))])
        self.assertEqual(_answer(s), TRIPS)

    def test_one_cent_under_forty_percent_is_half_year(self):
        s = _scenario(rentals=[_rental(
            _personal(31_170.09, 3), _personal(20_780.05, 11))])
        self.assertEqual(_answer(s), SILENT)

    def test_exact_forty_percent_cent_pairs_never_trip(self):
        """A sweep of exact-40% pairs (late = 2k cents, early = 3k cents):
        none trips, and each trips with one more cent late."""
        for k in range(1_000_001, 1_000_400):
            late, early = 2 * k / 100, 3 * k / 100
            with self.subTest(late=late):
                self.assertIs(mid_quarter_applies(_scenario(rentals=[_rental(
                    _personal(early, 3), _personal(late, 11))])), False)
                self.assertIs(mid_quarter_applies(_scenario(rentals=[_rental(
                    _personal(early, 3),
                    _personal((2 * k + 1) / 100, 11))])), True)

    def test_each_basis_is_converted_to_cents_on_its_own(self):
        """Ruled: per-asset bases are converted once, then summed as
        integers. Two late assets of 0.004 each are 0 cents apiece, so
        4,000.00 of 10,000.00 is exactly 40% and does not trip. Summing the
        dollars first (4,000.008 -> 400,001 cents of 1,000,001) would."""
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11),
            _personal(0.004, 11, description="Scrap A"),
            _personal(0.004, 12, description="Scrap B"))])
        self.assertEqual(round((4_000.0 + 0.004 + 0.004) * 100), 400_001)
        self.assertIs(mid_quarter_applies(s), False)

    def test_the_year_total_is_summed_in_cents_too(self):
        """The same rule on the other side of the comparison. Early: 6,000.01
        plus two assets of 0.006 (one cent apiece) is 600,003 cents; late
        is 400,002; the total 1,000,005 makes that exactly 40%. Summing the
        early dollars first (6,000.022 -> 600,002) would lose a cent from
        the total and trip."""
        s = _scenario(rentals=[_rental(
            _personal(6_000.01, 3),
            _personal(0.006, 2, description="Scrap A"),
            _personal(0.006, 5, description="Scrap B"),
            _personal(4_000.02, 11))])
        self.assertEqual(400_002 * 100, 40 * 1_000_005)
        self.assertEqual(
            round((6_000.01 + 0.006 + 0.006 + 4_000.02) * 100), 1_000_004)
        self.assertIs(mid_quarter_applies(s), False)

    def test_just_under_is_half_year(self):
        self.assertEqual(_answer(_scenario(rentals=[_rental(
            _personal(6_001.0, 3), _personal(3_999.0, 11))])), SILENT)

    def test_last_three_months_are_october_through_december(self):
        for month, trips in ((9, False), (10, True), (11, True), (12, True)):
            with self.subTest(month=month):
                s = _scenario(rentals=[_rental(
                    _personal(5_000.0, 3), _personal(5_000.0, month))])
                self.assertEqual(_answer(s), TRIPS if trips else SILENT)

    def test_only_property_placed_this_year_counts(self):
        """A prior-year fourth-quarter placement is not in either total."""
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11),
            _personal(50_000.0, 12, year=YEAR - 1, description="Old"))])
        self.assertEqual(_answer(s), SILENT)
        # Twin: the same asset placed THIS December tips the test.
        s.rental_properties[0].depreciable_assets[2] = _personal(
            50_000.0, 12, description="New")
        self.assertEqual(_answer(s), TRIPS)

    def test_the_whole_cohort_takes_the_convention(self):
        """ "the applicable convention for ALL property ... placed in
        service during such taxable year": a first-quarter asset in a
        tripped year is mid-quarter too, from the first-quarter table."""
        rental = _rental(
            _personal(1_000.0, 2, description="Early"),
            _personal(1_000.0, 5, description="Spring"),
            _personal(1_000.0, 8, description="Summer"),
            _personal(9_000.0, 12, description="Late"))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), TRIPS)
        with _patched():
            self.assertEqual(_amounts(rental, s), [
                irs_round(1_000.0 * _sentinel(1, 5, 1)),
                irs_round(1_000.0 * _sentinel(2, 5, 1)),
                irs_round(1_000.0 * _sentinel(3, 5, 1)),
                irs_round(9_000.0 * _sentinel(4, 5, 1))])

    def test_an_earlier_years_asset_keeps_its_stated_convention(self):
        """This year trips; the asset placed last year states half-year and
        still reads the half-year table."""
        old = _personal(10_000.0, 12, year=YEAR - 1, description="Old")
        old.prior_depreciation = 2_000.0
        old.acknowledges_prior_depreciation_as_stated = False
        rental = _rental(old, _personal(4_000.0, 11, description="New"))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), TRIPS)
        self.assertEqual(
            _conventions(rental, s), ["half-year", "mid-quarter"])
        with _patched():
            self.assertEqual(_amounts(rental, s), [
                3_200, irs_round(4_000.0 * _sentinel(4, 5, 1))])

    def test_an_earlier_mid_quarter_asset_does_not_make_this_year_trip(self):
        """The mirror: last year's asset states mid-quarter, this year's
        placements do not trip. Each keeps its own convention, and the
        earlier asset is in neither of this year's totals."""
        old = _personal(10_000.0, 12, year=YEAR - 1, description="Old")
        old.convention, old.quarter = "mid-quarter", 4
        with _patched():
            old.prior_depreciation = float(
                irs_round(10_000.0 * _sentinel(4, 5, 1)))
            old.acknowledges_prior_depreciation_as_stated = False
            rental = _rental(old, _personal(4_000.0, 3, description="New"))
            s = _scenario(rentals=[rental])
            self.assertEqual(_answer(s), SILENT)
            self.assertEqual(mid_quarter_bases(s), (0.0, 4_000.0))
            self.assertEqual(
                _conventions(rental, s), ["mid-quarter", "half-year"])
            self.assertEqual(_amounts(rental, s), [
                irs_round(10_000.0 * _sentinel(4, 5, 2)), 800])

    def test_no_personal_property_placed_this_year_is_false(self):
        """Both totals zero: the test is false and nothing is divided."""
        old = _personal(10_000.0, 12, year=YEAR - 1, description="Old")
        for rentals in ([], [_rental()], [_rental(old)],
                        [_rental(_real(200_000.0, 12, "39-year"))]):
            s = _scenario(rentals=rentals)
            with self.subTest(assets=len(rentals)):
                self.assertEqual(mid_quarter_bases(s)[1], 0.0)
                self.assertIs(_answer(s), False)


class TaxpayerWideTests(unittest.TestCase):
    """The totals run across the whole return, not per activity.

    "Neither activity over alone, over together" cannot be constructed: a
    pooled share is a weighted average of the two shares and so lies between
    them. The shape that separates the two implementations is the opposite
    one -- an activity over the threshold ALONE whose property, pooled with
    the rest of the return, is under it. Taxpayer-wide is silent there; a
    per-activity implementation refuses, and so fails the first test."""

    def test_activity_over_alone_is_silent_when_the_return_is_under(self):
        business = _business(_personal(1_000.0, 11, description="Laptop"))
        rental = _rental(_personal(9_000.0, 3))
        # Alone the business is 1,000 of 1,000.
        self.assertEqual(_answer(_scenario(businesses=[business])), TRIPS)
        # On the whole return it is 1,000 of 10,000.
        self.assertEqual(
            _answer(_scenario(rentals=[rental], businesses=[business])),
            SILENT)

    def test_activity_silent_alone_trips_when_pooled(self):
        rental = _rental(_personal(6_000.0, 3), _personal(3_000.0, 11))
        business = _business(_personal(3_000.0, 12, description="Laptop"))
        self.assertEqual(_answer(_scenario(rentals=[rental])), SILENT)
        pooled = _scenario(rentals=[rental], businesses=[business])
        self.assertEqual(_answer(pooled), TRIPS)       # 6,000 of 12,000
        self.assertEqual(mid_quarter_bases(pooled), (6_000.0, 12_000.0))
        # Pooled, the RENTAL's assets are mid-quarter too, though the
        # rental alone is under the threshold.
        self.assertEqual(
            _conventions(rental, pooled), ["mid-quarter", "mid-quarter"])
        self.assertEqual(
            _conventions(rental, _scenario(rentals=[rental])),
            ["half-year", "half-year"])


    def test_resolving_one_activity_does_not_run_the_test_on_it_alone(self):
        """The per-activity resolver is handed the RETURN's answer and never
        re-derives it from the one activity: the business below is over the
        threshold alone and under it on the return, so on the return it is
        half-year -- through the orchestrator and through a direct call."""
        import tempfile
        from pathlib import Path
        from tenforty.orchestrator import ReturnOrchestrator
        from tests.helpers import SPREADSHEETS_DIR
        business = _business(_personal(1_000.0, 11, description="Laptop"))
        rental = _rental(_personal(9_000.0, 3))
        scenario = _scenario(rentals=[rental], businesses=[business])
        half_year = 200                                   # 1,000 x 20%
        with _patched():
            mid_quarter = irs_round(1_000.0 * _sentinel(4, 5, 1))
            self.assertNotEqual(mid_quarter, half_year)
            self.assertEqual(_amounts(business, scenario), [half_year])
            with tempfile.TemporaryDirectory() as tmp:
                results = ReturnOrchestrator(
                    spreadsheets_dir=SPREADSHEETS_DIR,
                    work_dir=Path(tmp)).compute_federal(scenario)
            self.assertEqual(
                results["depreciation_recon_sch_c_0_used_amount"], half_year)
            # Twin: the same business as the only activity is mid-quarter.
            alone = _scenario(businesses=[business])
            self.assertEqual(_amounts(business, alone), [mid_quarter])
            with tempfile.TemporaryDirectory() as tmp:
                results = ReturnOrchestrator(
                    spreadsheets_dir=SPREADSHEETS_DIR,
                    work_dir=Path(tmp)).compute_federal(alone)
            self.assertEqual(
                results["depreciation_recon_sch_c_0_used_amount"],
                mid_quarter)


class ReadersUseTheReturnsAnswerTests(unittest.TestCase):
    """Every reader of an activity's depreciation hands the engine the
    return's answer. One 5-year asset placed in November is the whole
    cohort, so the year trips: 10,000 x the fourth-quarter sentinel is
    4,050 where the half-year table gives 2,000. Against 3,000 of income
    that is a 1,050 loss under mid-quarter and a 1,000 profit under
    half-year, so a reader that dropped the answer is visible in the sign
    as well as the amount."""

    MID_QUARTER_AMOUNT = 4_050
    HALF_YEAR_AMOUNT = 2_000

    def setUp(self):
        patcher = _patched()
        patcher.start()
        self.addCleanup(patcher.stop)
        self.assertEqual(
            irs_round(10_000.0 * _sentinel(4, 5, 1)), self.MID_QUARTER_AMOUNT)

    def _rental_scenario(self):
        rental = _rental(_personal(10_000.0, 11))
        rental.rents_received = 3_000.0
        return _scenario(rentals=[rental])

    def _business_scenario(self):
        business = ScheduleCBusiness(
            description="Consulting", gross_receipts=3_000.0,
            depreciable_assets=(_personal(10_000.0, 11),))
        s = _scenario(businesses=[business])
        # The business runs a loss under mid-quarter; line 32 needs this.
        s.config.acknowledges_sch_c_all_investment_at_risk = True
        return s

    def _orchestrator(self):
        import tempfile
        from pathlib import Path
        from tenforty.orchestrator import ReturnOrchestrator
        from tests.helpers import SPREADSHEETS_DIR
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=Path(tmp.name))

    def test_the_half_year_twin_is_different(self):
        """What each test below would read if the answer were dropped."""
        s = self._rental_scenario()
        self.assertEqual(
            resolve(s.rental_properties[0], YEAR,
                    mid_quarter=False).amount,
            self.HALF_YEAR_AMOUNT)

    def test_schedule_e_line_18_and_line_21(self):
        from tenforty.forms import sch_e
        r = sch_e.compute(self._rental_scenario(), upstream={})
        self.assertEqual(
            r["sch_e_property_a_depreciation"], self.MID_QUARTER_AMOUNT)
        self.assertEqual(r["sch_e_property_a_income_loss"], -1_050)

    def test_schedule_e_net_loss_predicate(self):
        from tenforty.forms import sch_e
        self.assertTrue(sch_e.has_any_net_loss(self._rental_scenario()))

    def test_schedule_c_line_13_and_line_31(self):
        from tenforty.forms import sch_c
        s = self._business_scenario()
        business = sch_c.compute(s, upstream={})["sch_c_businesses"][0]
        self.assertEqual(business[sch_c.LINE_13_KEY], self.MID_QUARTER_AMOUNT)
        self.assertEqual(business["sch_c_line_31_net_profit"], -1_050)
        emitted = sch_c.emit_values(s, 0, business)
        self.assertEqual(emitted[sch_c.LINE_13_KEY], self.MID_QUARTER_AMOUNT)
        # The computed line overwrites emit's own read of line 13; with no
        # computed lines handed in, emit's own read is what is left.
        own_read = sch_c.emit_values(s, 0, {})
        self.assertEqual(
            irs_round(own_read[sch_c.LINE_13_KEY]), self.MID_QUARTER_AMOUNT)

    def test_excess_business_loss_aggregate(self):
        from tenforty.orchestrator import aggregate_business_losses
        self.assertEqual(
            aggregate_business_losses(self._rental_scenario()), 1_050)
        self.assertEqual(
            aggregate_business_losses(self._business_scenario()), 1_050)

    def test_spine_scope_estimates(self):
        from unittest import mock
        from tenforty import orchestrator as module
        from tenforty.forms import sch_c
        seen = []

        def spy(real):
            def wrapper(activity, tax_year, *, mid_quarter):
                seen.append(real(
                    activity, tax_year, mid_quarter=mid_quarter))
                return seen[-1]
            return wrapper

        orchestrator = self._orchestrator()
        with mock.patch.object(
                module, "_rental_net_income", spy(module._rental_net_income)):
            orchestrator._scenario_in_spine_scope(self._rental_scenario())
        with mock.patch.object(
                sch_c, "net_profit_estimate", spy(sch_c.net_profit_estimate)):
            orchestrator._scenario_in_spine_scope(self._business_scenario())
        self.assertEqual(seen, [-1_050.0, -1_050.0])

    def test_workbook_flattener(self):
        from tenforty.oracle.flattener import flatten_scenario
        flat = flatten_scenario(self._rental_scenario())
        self.assertEqual(flat["sche_depreciation_a"], self.MID_QUARTER_AMOUNT)
        self.assertEqual(flat["sche_8582_net_loss"], 1_050)

    def test_recon_keys(self):
        from tenforty.forms.depreciation.resolver import recon_keys
        keys = recon_keys(self._rental_scenario())
        self.assertEqual(
            keys["depreciation_recon_rental_0_engine_amount"],
            self.MID_QUARTER_AMOUNT)

    def test_california_divergence_trigger(self):
        """The trigger is a boolean (any depreciation at all), so it is
        told apart with a table of zeros: mid-quarter then gives no
        depreciation where half-year would give 2,000."""
        from unittest import mock
        from tenforty import ca_divergences
        from tenforty.params import macrs_mid_quarter
        s = self._rental_scenario()
        self.assertTrue(ca_divergences.has_rental_depreciation(s))
        zeros = {quarter: {5: {1: 0.0}} for quarter in (1, 2, 3, 4)}
        with mock.patch.object(
                macrs_mid_quarter, "TABLES_BY_QUARTER", zeros):
            self.assertFalse(ca_divergences.has_rental_depreciation(s))


class RealPropertyExcludedTests(unittest.TestCase):
    def test_late_year_real_property_does_not_move_the_share(self):
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                self.assertEqual(_answer(_scenario(rentals=[_rental(
                    _personal(6_000.0, 3), _personal(4_000.0, 11),
                    _real(500_000.0, 12, cls))])), SILENT)

    def test_the_same_basis_as_personal_property_does(self):
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11),
            _personal(500_000.0, 12, description="Machine"))])
        self.assertEqual(_answer(s), TRIPS)

    def test_current_year_building_is_absent_from_both_totals(self):
        """THE DISCRIMINATING TEST for the statutory reading. A building
        placed EARLY in the year plus fourth-quarter personal property:

          statute (controls): building in neither total
              -> 4,001 of 10,000 -> mid-quarter.
          publication's sentence read literally (REJECTED): the exclusion
              parenthetical modifies only the last-3-months total, so the
              building would enlarge the entire-year total
              -> 4,001 of 210,000 -> half-year.
        """
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                rental = _rental(
                    _real(200_000.0, 2, cls),
                    _personal(5_999.0, 3), _personal(4_001.0, 11))
                s = _scenario(rentals=[rental])
                self.assertEqual(mid_quarter_bases(s), (4_001.0, 10_000.0))
                self.assertEqual(_answer(s), TRIPS)
                # The building stays mid-month in a tripped year.
                self.assertEqual(
                    _conventions(rental, s),
                    ["mid-month", "mid-quarter", "mid-quarter"])

    def test_real_property_alone_never_trips(self):
        rental = _rental(_real(200_000.0, 12, "27.5-year"))
        s = _scenario(rentals=[rental])
        self.assertEqual(_answer(s), SILENT)
        self.assertEqual(_conventions(rental, s), ["mid-month"])


class StatedModeInteractionTests(unittest.TestCase):
    """Fail-closed: the 40% totals need EVERY placement on the return. A
    stated-mode activity's figure hides whatever it placed in service, so if
    an asset-mode activity places personal property this year while a
    stated-mode activity exists, the totals are unverifiable."""

    UNVERIFIABLE = (r"cannot be verified.*"
                    r"acknowledges_no_personal_property_behind_stated_"
                    r"depreciation")

    def _stated_business(self):
        return _business(
            depreciation=1_200.0,
            acknowledges_depreciation_stated_outside_macrs=True)

    def _shape(self, acknowledgment=None):
        return _scenario(
            rentals=[_rental(_personal(6_000.0, 3))],
            businesses=[self._stated_business()],
            acknowledgment=acknowledgment)

    def test_fires_in_exactly_that_shape(self):
        for acknowledgment in (None, False):
            with self.subTest(acknowledgment=acknowledgment):
                with self.assertRaisesRegex(
                        NotImplementedError, self.UNVERIFIABLE) as cm:
                    _check(self._shape(acknowledgment))
                self.assertIn("Schedule C business #0 ('Consulting')",
                              str(cm.exception))

    def test_proceeds_with_the_acknowledgment(self):
        _check(self._shape(acknowledgment=True))

    def test_acknowledgment_does_not_switch_off_the_forty_percent_test(self):
        s = self._shape(acknowledgment=True)
        self.assertEqual(_answer(s), SILENT)
        s.rental_properties[0].depreciable_assets.append(
            _personal(6_000.0, 11, description="Late"))
        self.assertEqual(_answer(s), TRIPS)

    def test_silent_when_the_placement_is_real_property_only(self):
        s = self._shape()
        s.rental_properties[0].depreciable_assets = [
            _real(200_000.0, 3, "27.5-year")]
        _check(s)

    def test_silent_with_only_prior_year_personal_property(self):
        s = self._shape()
        s.rental_properties[0].depreciable_assets = [
            _personal(6_000.0, 3, year=YEAR - 1)]
        _check(s)

    def test_silent_with_no_stated_mode_activity(self):
        s = self._shape()
        s.schedule_c_businesses = [_business()]
        _check(s)

    def test_stated_mode_rental_counts_as_a_stated_mode_activity(self):
        s = _scenario(
            rentals=[_rental(
                depreciation=5_000.0,
                acknowledges_depreciation_stated_outside_macrs=True)],
            businesses=[_business(_personal(6_000.0, 3))])
        with self.assertRaisesRegex(
                NotImplementedError, self.UNVERIFIABLE) as cm:
            _check(s)
        self.assertIn("rental property #0", str(cm.exception))


class AcknowledgmentLoadingTests(unittest.TestCase):
    """The acknowledgment is a scenario-level YAML key required only in the
    data shape that triggers it -- never a config field every scenario must
    carry."""

    def _doc(self):
        from tests.test_asset_nest_loading import (
            _appliance, _business as _yaml_business, _doc, _rental as _yaml_rental,
        )
        return _doc(
            rental_properties=[_yaml_rental(depreciable_assets=[_appliance()])],
            schedule_c_businesses=[_yaml_business(
                depreciation=1_200.0,
                acknowledges_depreciation_stated_outside_macrs=True)])

    def test_yaml_shape_refuses_then_loads_with_the_top_level_key(self):
        from tests.test_asset_nest_loading import _load
        doc = self._doc()
        with self.assertRaisesRegex(NotImplementedError, r"cannot be verified"):
            _load(copy.deepcopy(doc))
        doc["acknowledges_no_personal_property_behind_stated_depreciation"] = (
            True)
        s = _load(doc)
        self.assertIs(
            s.acknowledges_no_personal_property_behind_stated_depreciation,
            True)

    def test_scenarios_outside_the_shape_need_no_key(self):
        from tests.test_asset_nest_loading import _doc, _load, _rental
        s = _load(_doc(rental_properties=[_rental()]))
        self.assertIsNone(
            s.acknowledges_no_personal_property_behind_stated_depreciation)
        from tenforty.models import TaxReturnConfig
        self.assertFalse(hasattr(
            TaxReturnConfig,
            "acknowledges_no_personal_property_behind_stated_depreciation"))

    def test_non_boolean_key_is_refused(self):
        from tests.test_asset_nest_loading import _load
        doc = self._doc()
        doc["acknowledges_no_personal_property_behind_stated_depreciation"] = (
            "yes")
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            _load(doc)


if __name__ == "__main__":
    unittest.main()
