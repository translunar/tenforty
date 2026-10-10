"""Prior-year personal property STATES its convention.

The 40% test that settled an asset's convention ran in the year the asset
was placed in service, over everything placed in service that year. A later
return does not hold that year's placements (whatever has since been disposed
of is gone from its list), so the test is never re-run: the asset states
`convention` (half-year | mid-quarter) and, for mid-quarter, `quarter`.

  - a prior-year personal asset with no convention refuses (half-year is
    never assumed);
  - an unusable stated value refuses;
  - an asset placed in the RETURN year, or real property, stating either
    refuses (the engine computes those);
  - the stated prior depreciation reconciles against the tables of the
    STATED convention, and the acknowledged-history path composes with it.

Amounts under the mid-quarter convention are derived from the table module
itself (`TABLES_BY_QUARTER`), never restated here: what the publication
prints is pinned by tests/test_macrs_mid_quarter_table_attestation.py.
"""

import datetime
import unittest

from tenforty.forms.depreciation.resolver import (
    mid_quarter_applies, mid_quarter_bases, reconstruct_prior_depreciation,
    resolve,
)
from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tenforty.params.macrs_mid_quarter import TABLES_BY_QUARTER
from tenforty.rounding import irs_round
from tests.test_asset_nest_loading import (
    YEAR, _appliance, _building, _business, _doc, _load, _old_building,
    _rental,
)

BASIS = 10_000.0
# 5-year property, 10,000 basis, placed two years before the return year.
HALF_YEAR_PRIOR = 2_000 + 3_200                      # legacy half-year pin
HALF_YEAR_THIS_YEAR = 1_920


def _mid_quarter_year(quarter: int, recovery_year: int) -> int:
    return irs_round(BASIS * TABLES_BY_QUARTER[quarter][5][recovery_year])


def _mid_quarter_prior(quarter: int) -> int:
    return _mid_quarter_year(quarter, 1) + _mid_quarter_year(quarter, 2)


def _old_appliance(month: int = 11, **extra) -> dict:
    """Five-year personal property placed in service two years ago."""
    return {
        "description": "Refrigerator",
        "date_placed_in_service": datetime.date(YEAR - 2, month, 15),
        "basis": BASIS, "recovery_class": "5-year",
        "no_bonus_or_section_179_history": True, **extra,
    }


def _load_rental(*assets):
    return _load(_doc(rental_properties=[
        _rental(depreciable_assets=list(assets))]))


def _only_row(scenario):
    resolved = resolve(
        scenario.rental_properties[0], YEAR,
        mid_quarter=mid_quarter_applies(scenario))
    (row,) = resolved.per_asset
    return row


class ConventionIsStatedOnlyOnPriorYearPersonalPropertyTests(
        unittest.TestCase):
    REFUSAL = r"carries `convention` or `quarter`"

    def test_return_year_asset_stating_a_convention_refuses(self):
        for stated in ({"convention": "half-year"},
                       {"convention": "mid-quarter", "quarter": 1},
                       {"quarter": 1}):
            with self.subTest(stated=stated):
                with self.assertRaisesRegex(
                        ValueError,
                        r"asset 'Refrigerator' on rental property #0 "
                        r"\('100 Example Street'\) was placed in service in "
                        rf"{YEAR}, not before the {YEAR} return year.*"
                        + self.REFUSAL):
                    _load_rental(_appliance(**stated))

    def test_real_property_stating_a_convention_refuses(self):
        for asset in (_building(convention="mid-month"),
                      _old_building(convention="half-year"),
                      _old_building(quarter=2)):
            with self.subTest(asset=asset["date_placed_in_service"].year):
                with self.assertRaisesRegex(
                        ValueError,
                        r"is 27\.5-year real property \(mid-month by "
                        r"statute\).*" + self.REFUSAL):
                    _load_rental(asset)

    def test_the_same_assets_without_the_keys_load(self):
        s = _load_rental(_appliance(), _building())
        for asset in s.rental_properties[0].depreciable_assets:
            self.assertIsNone(asset.convention)
            self.assertIsNone(asset.quarter)
        _load_rental(_old_building())

    def test_schedule_c_assets_are_covered_too(self):
        with self.assertRaisesRegex(ValueError, self.REFUSAL):
            _load(_doc(schedule_c_businesses=[_business(
                depreciable_assets=[_appliance(convention="half-year")])]))


class MissingPriorYearConventionTests(unittest.TestCase):
    def test_prior_year_personal_asset_without_a_convention_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Refrigerator' on rental property #0 "
                rf"\('100 Example Street'\), placed in service in {YEAR - 2}, "
                r"states no `convention`.*does not assume half-year.*"
                r"`convention: half-year`.*`convention: mid-quarter` with "
                r"`quarter:`"):
            _load_rental(_old_appliance(
                prior_depreciation=float(HALF_YEAR_PRIOR)))

    def test_it_is_not_lifted_by_acknowledging_the_prior_figure(self):
        """The acknowledgment accepts a prior AMOUNT; it does not say which
        table this year reads."""
        with self.assertRaisesRegex(ValueError, r"states no `convention`"):
            _load_rental(_old_appliance(
                prior_depreciation=0.0,
                acknowledges_prior_depreciation_as_stated=True))

    def test_stating_it_loads(self):
        s = _load_rental(_old_appliance(
            convention="half-year",
            prior_depreciation=float(HALF_YEAR_PRIOR)))
        asset = s.rental_properties[0].depreciable_assets[0]
        self.assertEqual((asset.convention, asset.quarter),
                         ("half-year", None))

    def test_prior_year_real_property_needs_none(self):
        _load_rental(_old_building())

    def test_return_year_personal_property_needs_none(self):
        _load_rental(_appliance())


class InvalidStatedConventionTests(unittest.TestCase):
    def test_mid_quarter_without_its_quarter_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Refrigerator' on rental property #0 "
                r"\('100 Example Street'\) states `convention: mid-quarter` "
                r"without the `quarter`"):
            _load_rental(_old_appliance(
                convention="mid-quarter",
                prior_depreciation=float(_mid_quarter_prior(4))))

    def test_each_unusable_value_refuses(self):
        cases = (
            ({"convention": "mid-quarter", "quarter": 5},
             r"`quarter: 5`; it must be one of \[1, 2, 3, 4\]"),
            ({"convention": "mid-quarter", "quarter": 0},
             r"`quarter: 0`; it must be one of"),
            ({"convention": "mid-quarter", "quarter": -1},
             r"`quarter: -1`; it must be one of"),
            ({"convention": "half-year", "quarter": 4},
             r"`quarter` with `convention: half-year`"),
            ({"convention": "mid-month"}, r"`convention: mid-month`"),
            ({"convention": "HY"}, r"`convention: HY`"),
            # Placed in November: the fourth quarter.
            ({"convention": "mid-quarter", "quarter": 3},
             r"`quarter: 3` but its `date_placed_in_service` "
             rf"\({YEAR - 2}-11-15\) is in quarter 4"),
        )
        for stated, pattern in cases:
            with self.subTest(stated=stated):
                with self.assertRaisesRegex(ValueError, pattern):
                    _load_rental(_old_appliance(
                        prior_depreciation=0.0,
                        acknowledges_prior_depreciation_as_stated=True,
                        **stated))

    def test_each_quarter_loads_when_it_matches_the_placement_date(self):
        for quarter, month in ((1, 1), (1, 3), (2, 4), (2, 6), (3, 7),
                               (3, 9), (4, 10), (4, 12)):
            with self.subTest(quarter=quarter, month=month):
                s = _load_rental(_old_appliance(
                    month=month, convention="mid-quarter", quarter=quarter,
                    prior_depreciation=float(_mid_quarter_prior(quarter))))
                asset = s.rental_properties[0].depreciable_assets[0]
                self.assertEqual((asset.convention, asset.quarter),
                                 ("mid-quarter", quarter))

    def test_loader_rejects_values_of_the_wrong_type(self):
        cases = (
            ({"convention": 4}, r"convention must be text"),
            ({"convention": True}, r"convention must be text"),
            ({"convention": "mid-quarter", "quarter": "4"},
             r"quarter must be a whole number"),
            ({"convention": "mid-quarter", "quarter": 4.0},
             r"quarter must be a whole number"),
            ({"convention": "mid-quarter", "quarter": True},
             r"quarter must be a whole number"),
        )
        for stated, pattern in cases:
            with self.subTest(stated=stated):
                with self.assertRaisesRegex(ValueError, pattern):
                    _load_rental(_old_appliance(
                        prior_depreciation=0.0, **stated))


class ReconciliationUsesTheStatedConventionTests(unittest.TestCase):
    """The stated prior depreciation is checked against the tables of the
    convention the asset STATES, quarter included."""

    MISMATCH = r"states `prior_depreciation` of {stated:,} but the MACRS " \
               r"tables reconstruct {tables:,}"

    def test_the_two_histories_differ_in_every_quarter(self):
        """Reachability: were they equal, the tests below would not tell a
        mid-quarter reconstruction from a half-year one."""
        for quarter in (1, 2, 3, 4):
            with self.subTest(quarter=quarter):
                self.assertNotEqual(
                    _mid_quarter_prior(quarter), HALF_YEAR_PRIOR)
        self.assertEqual(
            len({_mid_quarter_prior(q) for q in (1, 2, 3, 4)}), 4)

    def test_mid_quarter_history_reconciles_in_each_quarter(self):
        for quarter, month in ((1, 2), (2, 5), (3, 8), (4, 11)):
            with self.subTest(quarter=quarter):
                s = _load_rental(_old_appliance(
                    month=month, convention="mid-quarter", quarter=quarter,
                    prior_depreciation=float(_mid_quarter_prior(quarter))))
                row = _only_row(s)
                self.assertEqual(
                    (row.convention, row.quarter), ("mid-quarter", quarter))
                self.assertEqual(row.amount, _mid_quarter_year(quarter, 3))

    def test_half_year_figure_on_a_mid_quarter_asset_refuses(self):
        with self.assertRaisesRegex(
                ValueError, self.MISMATCH.format(
                    stated=HALF_YEAR_PRIOR, tables=_mid_quarter_prior(4))):
            _load_rental(_old_appliance(
                convention="mid-quarter", quarter=4,
                prior_depreciation=float(HALF_YEAR_PRIOR)))

    def test_mid_quarter_figure_on_a_half_year_asset_refuses(self):
        with self.assertRaisesRegex(
                ValueError, self.MISMATCH.format(
                    stated=_mid_quarter_prior(4), tables=HALF_YEAR_PRIOR)):
            _load_rental(_old_appliance(
                convention="half-year",
                prior_depreciation=float(_mid_quarter_prior(4))))

    def test_another_quarters_figure_refuses(self):
        """A fourth-quarter asset whose history ran on the third-quarter
        table (possible only by stating quarter 4 with a quarter-3 amount)."""
        with self.assertRaisesRegex(
                ValueError, self.MISMATCH.format(
                    stated=_mid_quarter_prior(3),
                    tables=_mid_quarter_prior(4))):
            _load_rental(_old_appliance(
                convention="mid-quarter", quarter=4,
                prior_depreciation=float(_mid_quarter_prior(3))))

    def test_half_year_history_still_reconciles(self):
        s = _load_rental(_old_appliance(
            convention="half-year",
            prior_depreciation=float(HALF_YEAR_PRIOR)))
        row = _only_row(s)
        self.assertEqual((row.convention, row.quarter), ("half-year", None))
        self.assertEqual(row.amount, HALF_YEAR_THIS_YEAR)


class AcknowledgedHistoryComposesTests(unittest.TestCase):
    """`acknowledges_prior_depreciation_as_stated` accepts a prior AMOUNT
    that the tables do not reproduce -- for instance because the earlier
    years' figures cannot be rebuilt from what this return lists. It
    composes with the stated convention: this year still reads the stated
    convention's table, held to the basis left after the stated prior."""

    def _load(self, prior: float, **stated):
        return _load_rental(_old_appliance(
            prior_depreciation=prior,
            acknowledges_prior_depreciation_as_stated=True, **stated))

    def test_mid_quarter_asset_with_an_unreproducible_prior(self):
        s = self._load(1_234.0, convention="mid-quarter", quarter=4)
        row = _only_row(s)
        self.assertEqual((row.convention, row.quarter), ("mid-quarter", 4))
        self.assertEqual(row.amount, _mid_quarter_year(4, 3))
        self.assertEqual(row.table_amount, _mid_quarter_year(4, 3))
        self.assertIs(row.basis_ceiling_bound, False)

    def test_the_table_is_the_stated_one_not_half_year(self):
        self.assertNotEqual(_mid_quarter_year(4, 3), HALF_YEAR_THIS_YEAR)
        half_year = _only_row(self._load(1_234.0, convention="half-year"))
        self.assertEqual(half_year.amount, HALF_YEAR_THIS_YEAR)

    def test_basis_ceiling_binds_on_the_mid_quarter_table_amount(self):
        table = _mid_quarter_year(4, 3)
        row = _only_row(self._load(
            BASIS - 100.0, convention="mid-quarter", quarter=4))
        self.assertGreater(table, 100)
        self.assertEqual((row.amount, row.table_amount), (100, table))
        self.assertIs(row.basis_ceiling_bound, True)

    def test_the_acknowledgment_does_not_stand_in_for_the_convention(self):
        with self.assertRaisesRegex(ValueError, r"states no `convention`"):
            self._load(1_234.0)


class FortyPercentTestIsNeverRunOnAnEarlierYearTests(unittest.TestCase):
    """This return's list is not an earlier year's complete placements, so
    nothing about an earlier year is inferred from it."""

    def test_earlier_cohort_that_would_trip_stays_half_year_as_stated(self):
        """Everything listed for two years ago was placed in the fourth
        quarter. Read as a complete cohort that is 100% -- but the asset
        states half-year, and half-year it is."""
        s = _load_rental(
            _old_appliance(month=11, convention="half-year",
                           prior_depreciation=float(HALF_YEAR_PRIOR)),
            _old_appliance(month=12, description="Freezer",
                           convention="half-year",
                           prior_depreciation=float(HALF_YEAR_PRIOR)))
        self.assertIs(mid_quarter_applies(s), False)
        self.assertEqual(mid_quarter_bases(s), (0.0, 0.0))
        resolved = resolve(s.rental_properties[0], YEAR, mid_quarter=False)
        self.assertEqual(
            [row.convention for row in resolved.per_asset],
            ["half-year", "half-year"])

    def test_earlier_cohort_that_would_not_trip_stays_mid_quarter(self):
        """The mirror: one asset listed for that year, placed in the first
        quarter (0% late), stating mid-quarter."""
        s = _load_rental(_old_appliance(
            month=2, convention="mid-quarter", quarter=1,
            prior_depreciation=float(_mid_quarter_prior(1))))
        row = _only_row(s)
        self.assertEqual((row.convention, row.quarter), ("mid-quarter", 1))

    def test_this_years_answer_does_not_reach_an_earlier_asset(self):
        """This year trips (a lone November placement); the earlier asset
        states half-year and its amount is the half-year one either way."""
        old = _old_appliance(convention="half-year",
                             prior_depreciation=float(HALF_YEAR_PRIOR))
        s = _load_rental(old, _appliance(
            date_placed_in_service=datetime.date(YEAR, 11, 1)))
        self.assertIs(mid_quarter_applies(s), True)
        rows = resolve(
            s.rental_properties[0], YEAR, mid_quarter=True).per_asset
        self.assertEqual(
            [(row.convention, row.quarter) for row in rows],
            [("half-year", None), ("mid-quarter", 4)])
        self.assertEqual(rows[0].amount, HALF_YEAR_THIS_YEAR)

    def test_reconstruction_ignores_this_years_answer(self):
        asset = DepreciableAsset(
            description="Refrigerator",
            date_placed_in_service=datetime.date(YEAR - 2, 11, 15),
            basis=BASIS, recovery_class="5-year", convention="half-year")
        self.assertEqual(
            reconstruct_prior_depreciation(asset, YEAR, mid_quarter=True),
            reconstruct_prior_depreciation(asset, YEAR, mid_quarter=False))


class SingleActivityRunCarriesTheReturnsAnswerTests(unittest.TestCase):
    """`resolve` re-runs the ledger over the one activity it was handed.
    The ledger predicates that need the engine must use the RETURN's 40%
    answer there, not one recomputed from that activity alone.

    The business below places 1,000 in November: alone that is 100% (the
    year would trip), but its caller says the return does not trip. Its
    override restates the HALF-YEAR engine figure, 200. With the return's
    answer the override is current, and the refusal that fires is the one
    about overriding in a placement year. Recomputed from the lone
    activity, the engine figure would be the mid-quarter one and the
    override would be reported stale instead."""

    def _business(self):
        return ScheduleCBusiness(
            description="Consulting", gross_receipts=50_000.0,
            depreciable_assets=(DepreciableAsset(
                description="Laptop",
                date_placed_in_service=datetime.date(YEAR, 11, 15),
                basis=1_000.0, recovery_class="5-year",
                no_bonus_or_section_179_history=True),),
            depreciation_override=DepreciationOverride(
                amount=150.0, restates_engine_amount=200.0,
                acknowledgment=True))

    def test_the_two_figures_differ(self):
        self.assertNotEqual(
            irs_round(1_000.0 * TABLES_BY_QUARTER[4][5][1]), 200)

    def test_override_is_judged_against_the_returns_answer(self):
        with self.assertRaisesRegex(
                NotImplementedError,
                r"Property placed in service this year requires Form 4562"):
            resolve(self._business(), YEAR, mid_quarter=False)

    def test_twin_under_the_other_answer_is_stale(self):
        with self.assertRaisesRegex(
                ValueError, r"restating the engine's figure as 200"):
            resolve(self._business(), YEAR, mid_quarter=True)


class UnexpressibleInputsTests(unittest.TestCase):
    """The tables here are the general depreciation system on a full
    calendar tax year. The alternative depreciation system and a short tax
    year would each need different figures -- and neither can be written
    into a scenario at all, so there is no wrong-number path to refuse.
    These tests keep it that way: a key for either is rejected by the
    loader, wherever it is put. (A refusal for an input that cannot be
    expressed would have nothing to fire on.)

    The corporate return carries its own `tax_year_beginning` /
    `tax_year_ending` (models.SCorpReturn); that is the entity's header and
    reaches no asset here."""

    def _doc(self):
        return _doc(rental_properties=[
            _rental(depreciable_assets=[_appliance()])])

    def test_the_scenario_loads_without_any_such_key(self):
        _load(self._doc())

    def test_asset_cannot_state_a_depreciation_system_or_method(self):
        for key, value in (("ads", True),
                           ("alternative_depreciation_system", True),
                           ("depreciation_system", "ADS"),
                           ("method", "S/L"), ("recovery_period", 12)):
            with self.subTest(key=key):
                with self.assertRaisesRegex(
                        ValueError, rf"Unknown key\(s\).*'{key}'"):
                    _load_rental(_appliance(**{key: value}))

    def test_no_level_accepts_a_short_or_fiscal_tax_year(self):
        values = (("tax_year_beginning", datetime.date(YEAR, 4, 1)),
                  ("tax_year_ending", datetime.date(YEAR, 9, 30)),
                  ("short_tax_year", True), ("fiscal_year_end", "06-30"))
        for key, value in values:
            with self.subTest(key=key, where="config"):
                doc = self._doc()
                doc["config"][key] = value
                with self.assertRaisesRegex(TypeError, key):
                    _load(doc)
            with self.subTest(key=key, where="top level"):
                doc = self._doc()
                doc[key] = value
                with self.assertRaisesRegex(
                        ValueError, rf"Unknown top-level key\(s\).*'{key}'"):
                    _load(doc)
            with self.subTest(key=key, where="activity"):
                with self.assertRaisesRegex(TypeError, key):
                    _load(_doc(rental_properties=[_rental(
                        depreciable_assets=[_appliance()], **{key: value})]))
            with self.subTest(key=key, where="asset"):
                with self.assertRaisesRegex(
                        ValueError, rf"Unknown key\(s\).*'{key}'"):
                    _load_rental(_appliance(**{key: value}))


class RentalPropertyModelTests(unittest.TestCase):
    def test_model_defaults(self):
        asset = DepreciableAsset(
            description="Refrigerator",
            date_placed_in_service=datetime.date(YEAR, 2, 1),
            basis=3_000.0, recovery_class="5-year")
        self.assertIsNone(asset.convention)
        self.assertIsNone(asset.quarter)
        self.assertIsInstance(
            RentalProperty(
                address="100 Example Street", property_type=1,
                fair_rental_days=365, personal_use_days=0,
                rents_received=0.0, depreciable_assets=[asset]),
            RentalProperty)


if __name__ == "__main__":
    unittest.main()
