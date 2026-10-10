"""The mid-quarter convention refusal: the computed 40% test.

tenforty has no mid-quarter tables, so when the test says the mid-quarter
convention applies, the return refuses. The test is a scenario-level check
(taxpayer-wide), not part of the per-activity resolver.

All bases are invented round figures chosen to sit on either side of the
threshold.
"""

import copy
import unittest
from datetime import date

from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms.depreciation.resolver import mid_quarter_bases
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


MID_QUARTER = r"mid-quarter convention applies"


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

    def test_fires_over_the_threshold(self):
        s = _scenario(rentals=[_rental(
            _personal(5_999.0, 3), _personal(4_001.0, 11))])
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER) as cm:
            _check(s)
        # 4,001 of 10,000.
        self.assertRegex(str(cm.exception), r"4,001 of 10,000")

    def test_silent_at_exactly_forty_percent(self):
        """ "more than 40%" / "exceed ... 40 percent": equality is silent."""
        _check(_scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11))]))

    def test_silent_just_under(self):
        _check(_scenario(rentals=[_rental(
            _personal(6_001.0, 3), _personal(3_999.0, 11))]))

    def test_last_three_months_are_october_through_december(self):
        for month, fires in ((9, False), (10, True), (11, True), (12, True)):
            with self.subTest(month=month):
                s = _scenario(rentals=[_rental(
                    _personal(5_000.0, 3), _personal(5_000.0, month))])
                if fires:
                    with self.assertRaisesRegex(
                            NotImplementedError, MID_QUARTER):
                        _check(s)
                else:
                    _check(s)

    def test_only_property_placed_this_year_counts(self):
        """A prior-year fourth-quarter placement is not in either total."""
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11),
            _personal(50_000.0, 12, year=YEAR - 1, description="Old"))])
        _check(s)
        # Twin: the same asset placed THIS December tips the test.
        s.rental_properties[0].depreciable_assets[2] = _personal(
            50_000.0, 12, description="New")
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER):
            _check(s)

    def test_bases_helper_reports_both_totals(self):
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11))])
        self.assertEqual(mid_quarter_bases(s), (4_000.0, 10_000.0))


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
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER):
            _check(_scenario(businesses=[business]))
        # On the whole return it is 1,000 of 10,000.
        _check(_scenario(rentals=[rental], businesses=[business]))

    def test_activity_silent_alone_fires_when_pooled(self):
        rental = _rental(_personal(6_000.0, 3), _personal(3_000.0, 11))
        business = _business(_personal(3_000.0, 12, description="Laptop"))
        _check(_scenario(rentals=[rental]))            # 3,000 of 9,000
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER) as cm:
            _check(_scenario(rentals=[rental], businesses=[business]))
        self.assertRegex(str(cm.exception), r"6,000 of 12,000")


    def test_resolving_one_activity_does_not_run_the_test_on_it_alone(self):
        """The per-activity resolver re-runs the ledger on the activity it
        is handed. The 40% test is a whole-return question and must not be
        asked of one activity: the business below is over the threshold
        alone and under it on the return, so the return computes."""
        import tempfile
        from pathlib import Path
        from tenforty.forms.depreciation.resolver import resolve
        from tenforty.orchestrator import ReturnOrchestrator
        from tests.helpers import SPREADSHEETS_DIR
        business = _business(_personal(1_000.0, 11, description="Laptop"))
        rental = _rental(_personal(9_000.0, 3))
        scenario = _scenario(rentals=[rental], businesses=[business])
        self.assertGreater(resolve(business, YEAR, mid_quarter_years=frozenset()).amount, 0)
        with tempfile.TemporaryDirectory() as tmp:
            results = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR,
                work_dir=Path(tmp)).compute_federal(scenario)
        self.assertGreater(
            results["depreciation_recon_sch_c_0_used_amount"], 0)
        # Twin: the same business as the only activity refuses at compute.
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(NotImplementedError, MID_QUARTER):
                ReturnOrchestrator(
                    spreadsheets_dir=SPREADSHEETS_DIR,
                    work_dir=Path(tmp)).compute_federal(
                        _scenario(businesses=[business]))


class RealPropertyExcludedTests(unittest.TestCase):
    def test_late_year_real_property_does_not_move_the_share(self):
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                _check(_scenario(rentals=[_rental(
                    _personal(6_000.0, 3), _personal(4_000.0, 11),
                    _real(500_000.0, 12, cls))]))

    def test_the_same_basis_as_personal_property_does(self):
        s = _scenario(rentals=[_rental(
            _personal(6_000.0, 3), _personal(4_000.0, 11),
            _personal(500_000.0, 12, description="Machine"))])
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER):
            _check(s)

    def test_current_year_building_is_absent_from_both_totals(self):
        """THE DISCRIMINATING TEST for the statutory reading. A building
        placed EARLY in the year plus fourth-quarter personal property:

          statute (controls): building in neither total
              -> 4,001 of 10,000 -> fires.
          publication's sentence read literally (REJECTED): the exclusion
              parenthetical modifies only the last-3-months total, so the
              building would enlarge the entire-year total
              -> 4,001 of 210,000 -> silent.
        """
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                s = _scenario(rentals=[_rental(
                    _real(200_000.0, 2, cls),
                    _personal(5_999.0, 3), _personal(4_001.0, 11))])
                self.assertEqual(mid_quarter_bases(s), (4_001.0, 10_000.0))
                with self.assertRaisesRegex(
                        NotImplementedError, MID_QUARTER) as cm:
                    _check(s)
                self.assertRegex(str(cm.exception), r"4,001 of 10,000")

    def test_real_property_alone_never_fires(self):
        _check(_scenario(rentals=[_rental(_real(200_000.0, 12, "27.5-year"))]))


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
        s.rental_properties[0].depreciable_assets.append(
            _personal(6_000.0, 11, description="Late"))
        with self.assertRaisesRegex(NotImplementedError, MID_QUARTER):
            _check(s)

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
