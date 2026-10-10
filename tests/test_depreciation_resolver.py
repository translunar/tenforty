"""One Door: the per-activity depreciation resolver.

`resolve(activity, tax_year, mid_quarter=False)` is the single source of an activity's
depreciation. Dollar literals here are LEGACY regression pins taken from the
pre-existing depreciation tests (a 5-year asset's first two years on a
10,000 basis; a January 27.5-year building on 200,000) -- not hand oracles.
Wherever a test only needs "what the table gives", it asks `macrs_deduction`
rather than restating a figure.
"""

import dataclasses
import unittest
from datetime import date

from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.resolver import (
    reconstruct_prior_depreciation, resolve,
)
from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tests.helpers import make_simple_scenario

YEAR = 2025


def _rental(**extra) -> RentalProperty:
    return RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0, **extra)


def _new_building(basis: float = 200_000.0) -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=basis, recovery_class="27.5-year")


def _old_equipment(basis: float = 10_000.0, **extra) -> DepreciableAsset:
    """Five-year property placed in 2023: two prior years by TY2025."""
    fields = dict(
        description="Equipment", date_placed_in_service=date(2023, 3, 15),
        basis=basis, recovery_class="5-year",
        no_bonus_or_section_179_history=True, convention="half-year")
    fields.update(extra)
    asset = DepreciableAsset(**fields)
    if "prior_depreciation" not in extra:
        asset.prior_depreciation = float(
            reconstruct_prior_depreciation(asset, YEAR, mid_quarter=False))
    return asset


def _old_building(**extra) -> DepreciableAsset:
    fields = dict(
        description="Rental building", date_placed_in_service=date(2019, 6, 1),
        basis=200_000.0, recovery_class="27.5-year")
    fields.update(extra)
    asset = DepreciableAsset(**fields)
    if "prior_depreciation" not in extra:
        asset.prior_depreciation = float(
            reconstruct_prior_depreciation(asset, YEAR, mid_quarter=False))
    return asset


def _scenario(rentals=(), businesses=()):
    s = make_simple_scenario()
    s.config.year = YEAR
    s.rental_properties = list(rentals)
    s.schedule_c_businesses = list(businesses)
    s.acknowledges_no_listed_property = True
    return s


class ResolveModeTests(unittest.TestCase):
    def test_none_mode(self):
        r = resolve(_rental(), YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "none")
        self.assertEqual(r.amount, 0)
        self.assertIsNone(r.engine_amount)
        self.assertEqual(r.per_asset, ())

    def test_stated_mode_returns_the_scalar(self):
        r = resolve(_rental(
            depreciation=5_000.5,
            acknowledges_depreciation_stated_outside_macrs=True), YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "stated")
        self.assertEqual(r.amount, 5_000.5)
        self.assertIsNone(r.engine_amount)
        self.assertEqual(r.per_asset, ())

    def test_asset_mode_sums_per_asset_table_amounts(self):
        building, equipment = _new_building(), _old_equipment()
        r = resolve(_rental(depreciable_assets=[building, equipment]), YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "assets")
        self.assertEqual(
            [row.amount for row in r.per_asset],
            [macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False), macrs_deduction(equipment, YEAR, return_year=YEAR, mid_quarter=False)])
        self.assertEqual(r.amount, sum(row.amount for row in r.per_asset))
        self.assertEqual(r.engine_amount, r.amount)
        # Legacy pin: January 27.5-year building on 200,000.
        self.assertEqual(r.per_asset[0].amount, 6_970)
        self.assertGreater(r.per_asset[1].amount, 0)

    def test_per_asset_rows_carry_what_the_4562_needs(self):
        building, equipment = _new_building(), _old_equipment()
        r = resolve(_rental(depreciable_assets=[building, equipment]), YEAR, mid_quarter=False)
        first, second = r.per_asset
        self.assertEqual(first.description, "Rental building")
        self.assertEqual(first.recovery_class, "27.5-year")
        self.assertEqual(first.date_placed_in_service, date(YEAR, 1, 15))
        self.assertEqual(first.basis, 200_000.0)
        self.assertEqual(first.convention, "mid-month")
        self.assertIs(first.placed_this_year, True)
        self.assertEqual(second.convention, "half-year")
        self.assertIs(second.placed_this_year, False)
        self.assertEqual((first.method, first.quarter), ("S/L", None))
        self.assertEqual((second.method, second.quarter), ("200DB", None))

    def test_row_method_follows_the_class(self):
        fence = DepreciableAsset(
            description="Fence", date_placed_in_service=date(YEAR, 3, 15),
            basis=12_000.0, recovery_class="15-year",
            no_bonus_or_section_179_history=True)
        (row,) = resolve(
            _rental(depreciable_assets=[fence]), YEAR,
            mid_quarter=False).per_asset
        self.assertEqual(row.method, "150DB")

    def test_schedule_c_business_resolves_the_same_way(self):
        equipment = _old_equipment()
        biz = ScheduleCBusiness(
            description="Consulting", gross_receipts=50_000.0,
            depreciable_assets=(equipment,))
        r = resolve(biz, YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "assets")
        self.assertEqual(r.amount, macrs_deduction(equipment, YEAR, return_year=YEAR, mid_quarter=False))

    def test_asset_past_its_recovery_period_resolves_to_zero(self):
        spent = _old_equipment(date_placed_in_service=date(2015, 3, 15))
        live = _old_equipment()
        r = resolve(_rental(depreciable_assets=[spent, live]), YEAR, mid_quarter=False)
        self.assertEqual(r.per_asset[0].amount, 0)
        # Twin: the same class inside its recovery period is nonzero.
        self.assertGreater(r.per_asset[1].amount, 0)
        self.assertEqual(r.amount, r.per_asset[1].amount)


class MixedActivityScopingTests(unittest.TestCase):
    def test_asset_mode_rental_and_stated_mode_business_are_independent(self):
        rental = _rental(depreciable_assets=[_new_building()])
        biz = ScheduleCBusiness(
            description="Consulting", gross_receipts=50_000.0,
            depreciation=1_200.0,
            acknowledges_depreciation_stated_outside_macrs=True)
        r_rental, r_biz = resolve(rental, YEAR, mid_quarter=False), resolve(biz, YEAR, mid_quarter=False)
        self.assertEqual((r_rental.mode, r_rental.amount), ("assets", 6_970))
        self.assertEqual((r_biz.mode, r_biz.amount), ("stated", 1_200.0))
        self.assertEqual(r_biz.per_asset, ())


class ShapeRulesHoldOnDirectCallsTests(unittest.TestCase):
    """`resolve` is fail-closed for a caller that bypassed the loader: it
    raises through the same ledger entries the loader enforces."""

    def test_dual_source_refuses(self):
        with self.assertRaisesRegex(
                ValueError, "carries both `depreciable_assets` and a stated"):
            resolve(_rental(
                depreciation=5_000.0,
                acknowledges_depreciation_stated_outside_macrs=True,
                depreciable_assets=[_new_building()]), YEAR, mid_quarter=False)

    def test_unacknowledged_stated_figure_refuses(self):
        with self.assertRaisesRegex(
                ValueError, "states `depreciation` without an asset list"):
            resolve(_rental(depreciation=5_000.0), YEAR, mid_quarter=False)

    def test_override_without_assets_refuses(self):
        with self.assertRaisesRegex(
                ValueError, "`depreciation_override` but no"):
            resolve(_rental(depreciation_override=DepreciationOverride(
                amount=1.0, restates_engine_amount=1.0,
                acknowledgment=True)), YEAR, mid_quarter=False)


class PriorDepreciationReconciliationTests(unittest.TestCase):
    def test_reconstruction_is_the_sum_of_prior_table_years(self):
        asset = _old_equipment()
        self.assertEqual(
            reconstruct_prior_depreciation(asset, YEAR, mid_quarter=False),
            macrs_deduction(asset, 2023, return_year=2023, mid_quarter=False) + macrs_deduction(asset, 2024, return_year=2024, mid_quarter=False))
        # Legacy pins: 2,000 then 3,200 on a 10,000 five-year asset.
        self.assertEqual(reconstruct_prior_depreciation(asset, YEAR, mid_quarter=False), 5_200)

    def test_current_year_asset_reconstructs_to_zero(self):
        self.assertEqual(
            reconstruct_prior_depreciation(_new_building(), YEAR, mid_quarter=False), 0)

    def test_stated_prior_equal_to_reconstruction_proceeds(self):
        asset = _old_equipment(prior_depreciation=5_200.0)
        r = resolve(_rental(depreciable_assets=[asset]), YEAR, mid_quarter=False)
        self.assertEqual(r.amount, macrs_deduction(asset, YEAR, return_year=YEAR, mid_quarter=False))

    def test_stated_prior_unequal_to_reconstruction_refuses(self):
        for stated in (5_199.0, 5_201.0, 0.0):
            with self.subTest(stated=stated):
                asset = _old_equipment(prior_depreciation=stated)
                with self.assertRaisesRegex(
                        ValueError,
                        r"asset 'Equipment' on rental property "
                        r"\('100 Example Street'\) states "
                        r"`prior_depreciation` of [\d,]+ but the MACRS "
                        r"tables reconstruct 5,200.*Form 3115.*481\(a\).*"
                        r"acknowledges_prior_depreciation_as_stated"):
                    resolve(_rental(depreciable_assets=[asset]), YEAR, mid_quarter=False)

    def test_unequal_with_acknowledgment_proceeds_and_stays_table_driven(self):
        clean = _old_equipment()
        messy = _old_equipment(
            prior_depreciation=1_234.0,
            acknowledges_prior_depreciation_as_stated=True)
        r = resolve(_rental(depreciable_assets=[messy]), YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "assets")
        # The forward year is the table amount, exactly as for an asset whose
        # prior history matches -- the stated prior does not enter it.
        self.assertEqual(r.amount, macrs_deduction(clean, YEAR, return_year=YEAR, mid_quarter=False))
        self.assertGreater(r.amount, 0)

    def test_ledger_fires_on_a_scenario_with_a_mismatched_prior(self):
        asset = _old_equipment(prior_depreciation=5_199.0)
        s = _scenario(rentals=[_rental(depreciable_assets=[asset])])
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Equipment' on rental property #0 "
                r"\('100 Example Street'\) states `prior_depreciation`"):
            enforce_scoped_refusals(s, "load")
        asset.prior_depreciation = 5_200.0
        enforce_scoped_refusals(s, "load")


class BasisCeilingTests(unittest.TestCase):
    """Ruled 2026-10-09: on the acknowledged-mismatch path the forward-year
    deduction is min(table amount, basis - stated prior), so an asset whose
    stated history runs AHEAD of the tables cannot be depreciated past its
    basis. (Within one return year no forward amount has yet been taken, so
    the remaining basis is basis less the stated prior.)"""

    def _messy(self, prior: float) -> DepreciableAsset:
        return _old_equipment(
            prior_depreciation=prior,
            acknowledges_prior_depreciation_as_stated=True)

    def test_ceiling_binds_when_the_stated_prior_leaves_less_than_the_table(self):
        table = macrs_deduction(_old_equipment(), YEAR, return_year=YEAR, mid_quarter=False)
        self.assertGreater(table, 1_000)
        r = resolve(_rental(depreciable_assets=[self._messy(9_000.0)]), YEAR, mid_quarter=False)
        (row,) = r.per_asset
        self.assertEqual(row.amount, 1_000)          # 10,000 - 9,000
        self.assertEqual(row.table_amount, table)
        self.assertIs(row.basis_ceiling_bound, True)
        self.assertEqual(r.amount, 1_000)
        self.assertEqual(r.engine_amount, 1_000)

    def test_stated_prior_at_or_over_basis_leaves_nothing(self):
        for prior in (10_000.0, 10_500.0):
            with self.subTest(prior=prior):
                r = resolve(
                    _rental(depreciable_assets=[self._messy(prior)]), YEAR, mid_quarter=False)
                self.assertEqual(r.amount, 0)
                self.assertIs(r.per_asset[0].basis_ceiling_bound, True)

    def test_ceiling_does_not_bind_when_basis_remains(self):
        table = macrs_deduction(_old_equipment(), YEAR, return_year=YEAR, mid_quarter=False)
        r = resolve(_rental(depreciable_assets=[self._messy(1_234.0)]), YEAR, mid_quarter=False)
        (row,) = r.per_asset
        self.assertEqual(row.amount, table)
        self.assertEqual(row.table_amount, table)
        self.assertIs(row.basis_ceiling_bound, False)

    def test_exactly_the_table_amount_remaining_is_not_binding(self):
        table = macrs_deduction(_old_equipment(), YEAR, return_year=YEAR, mid_quarter=False)
        r = resolve(_rental(depreciable_assets=[
            self._messy(10_000.0 - table)]), YEAR, mid_quarter=False)
        self.assertEqual(r.per_asset[0].amount, table)
        self.assertIs(r.per_asset[0].basis_ceiling_bound, False)

    def _tiny(self, basis: float) -> DepreciableAsset:
        return DepreciableAsset(
            description="Equipment", date_placed_in_service=date(2021, 3, 15),
            basis=basis, recovery_class="5-year",
            no_bonus_or_section_179_history=True, convention="half-year")

    def _table_years(self, asset, years):
        return [macrs_deduction(asset, y, return_year=YEAR + 1,
                                mid_quarter=False) for y in years]

    def test_ceiling_applies_on_a_table_matching_history_too(self):
        """Ruling: lifetime depreciation never exceeds basis, on ANY path.
        Each year's table amount is rounded on its own, so on a basis of 8
        the first four years (2 + 3 + 2 + 1) already recover all of it, yet
        the table still gives 1 for the fifth year. That year is 0."""
        tiny = self._tiny(8.0)
        self.assertEqual(
            self._table_years(tiny, range(2021, 2026)), [2, 3, 2, 1, 1])
        prior = reconstruct_prior_depreciation(tiny, YEAR, mid_quarter=False)
        self.assertEqual(prior, 8)
        tiny.prior_depreciation = float(prior)
        for acknowledged in (False, True):
            with self.subTest(acknowledged=acknowledged):
                tiny.acknowledges_prior_depreciation_as_stated = acknowledged
                r = resolve(_rental(depreciable_assets=[tiny]), YEAR,
                            mid_quarter=False)
                (row,) = r.per_asset
                self.assertEqual(row.table_amount, 1)
                self.assertEqual(row.amount, 0)
                self.assertIs(row.basis_ceiling_bound, True)

    def test_reconstruction_is_itself_held_to_basis(self):
        """A year later the same asset's reconstructed history is still 8,
        not the 9 the raw table years add up to -- so the stated prior a
        return carries forward keeps reconciling."""
        tiny = self._tiny(8.0)
        self.assertEqual(
            sum(self._table_years(tiny, range(2021, 2026))), 9)
        self.assertEqual(
            reconstruct_prior_depreciation(
                tiny, YEAR + 1, mid_quarter=False), 8)

    def test_an_undershoot_is_not_topped_up(self):
        """The asymmetry: on a basis of 12 the six table years come to 11.
        The last year stays at its table amount; the dollar is left."""
        tiny = self._tiny(12.0)
        years = self._table_years(tiny, range(2021, 2027))
        self.assertEqual(years, [2, 4, 2, 1, 1, 1])
        tiny.prior_depreciation = float(reconstruct_prior_depreciation(
            tiny, YEAR + 1, mid_quarter=False))
        self.assertEqual(tiny.prior_depreciation, 10.0)
        r = resolve(_rental(depreciable_assets=[tiny]), YEAR + 1,
                    mid_quarter=False)
        (row,) = r.per_asset
        self.assertEqual((row.amount, row.table_amount), (1, 1))
        self.assertIs(row.basis_ceiling_bound, False)

    def test_override_restates_the_capped_engine_figure(self):
        """The engine figure an override pins is the figure the engine
        would use -- ceiling applied."""
        from tenforty.forms.depreciation.resolver import engine_amount
        rental = _rental(depreciable_assets=[self._messy(9_000.0)])
        self.assertEqual(engine_amount(rental, YEAR, mid_quarter=False), 1_000)


class AssetPlacedAfterReturnYearTests(unittest.TestCase):
    def _future(self) -> DepreciableAsset:
        return DepreciableAsset(
            description="Next year's roof",
            date_placed_in_service=date(YEAR + 1, 2, 1),
            basis=20_000.0, recovery_class="27.5-year")

    def test_resolve_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset \"Next year's roof\" on rental property "
                r"\('100 Example Street'\) was placed in service in 2026, "
                r"after the 2025 return year"):
            resolve(_rental(depreciable_assets=[self._future()]), YEAR, mid_quarter=False)

    def test_ledger_fires_and_twin_in_the_return_year_is_silent(self):
        future = self._future()
        s = _scenario(rentals=[_rental(depreciable_assets=[future])])
        with self.assertRaisesRegex(
                ValueError, r"after the 2025 return year"):
            enforce_scoped_refusals(s, "load")
        future.date_placed_in_service = date(YEAR, 2, 1)
        enforce_scoped_refusals(s, "load")


class ValuePinnedOverrideTests(unittest.TestCase):
    """Ruling 5: the block carries the amount to USE plus a restatement of
    the ENGINE's figure; the engine's figure moving makes the restatement
    stale and the override refuses until re-acknowledged."""

    def _overridden(self, building: DepreciableAsset, *, amount: float,
                    restates: float) -> RentalProperty:
        return _rental(
            depreciable_assets=[building],
            depreciation_override=DepreciationOverride(
                amount=amount, restates_engine_amount=restates,
                acknowledgment=True))

    def test_matching_restatement_uses_the_override_amount(self):
        building = _old_building()
        engine = macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)
        self.assertNotEqual(engine, 6_500)
        r = resolve(self._overridden(
            building, amount=6_500.0, restates=float(engine)), YEAR, mid_quarter=False)
        self.assertEqual(r.mode, "assets-overridden")
        self.assertEqual(r.amount, 6_500.0)
        self.assertEqual(r.engine_amount, engine)
        self.assertEqual(len(r.per_asset), 1)

    def test_books_change_rearms_the_refusal(self):
        building = _old_building()
        engine = macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)
        rental = self._overridden(
            building, amount=6_500.0, restates=float(engine))
        self.assertEqual(resolve(rental, YEAR, mid_quarter=False).amount, 6_500.0)
        # The books change: the building's basis is corrected upward. The
        # prior-year figure is re-stated to match so ONLY the override's
        # restatement is stale.
        building.basis = 210_000.0
        building.prior_depreciation = float(
            reconstruct_prior_depreciation(building, YEAR, mid_quarter=False))
        new_engine = macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)
        self.assertNotEqual(new_engine, engine)
        with self.assertRaisesRegex(
                ValueError,
                r"rental property \('100 Example Street'\) carries a "
                r"`depreciation_override` restating the engine's figure as "
                rf"{engine:,}, but the engine now computes {new_engine:,}.*"
                r"re-acknowledge"):
            resolve(rental, YEAR, mid_quarter=False)
        # Re-acknowledging with the engine's new figure proceeds.
        rental.depreciation_override = DepreciationOverride(
            amount=6_500.0, restates_engine_amount=float(new_engine),
            acknowledgment=True)
        self.assertEqual(resolve(rental, YEAR, mid_quarter=False).amount, 6_500.0)

    def test_ledger_fires_on_a_stale_override(self):
        building = _old_building()
        engine = macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)
        rental = self._overridden(
            building, amount=6_500.0, restates=float(engine + 1))
        s = _scenario(rentals=[rental])
        with self.assertRaisesRegex(
                ValueError,
                r"rental property #0 \('100 Example Street'\) carries a "
                r"`depreciation_override` restating the engine's figure"):
            enforce_scoped_refusals(s, "load")
        rental.depreciation_override = dataclasses.replace(
            rental.depreciation_override,
            restates_engine_amount=float(engine))
        enforce_scoped_refusals(s, "load")

    def test_override_with_a_current_year_placement_refuses(self):
        building = _new_building()
        rental = self._overridden(
            building, amount=6_500.0,
            restates=float(macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)))
        with self.assertRaisesRegex(
                NotImplementedError,
                r"rental property \('100 Example Street'\) carries a "
                r"`depreciation_override` and placed 'Rental building' in "
                r"service in 2025.*Form 4562.*follow-on"):
            resolve(rental, YEAR, mid_quarter=False)

    def test_same_override_with_only_prior_year_assets_proceeds(self):
        building = _old_building()
        rental = self._overridden(
            building, amount=6_500.0,
            restates=float(macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)))
        self.assertEqual(resolve(rental, YEAR, mid_quarter=False).mode, "assets-overridden")

    def test_ledger_fires_on_override_with_current_year_placement(self):
        building = _new_building()
        rental = self._overridden(
            building, amount=6_500.0,
            restates=float(macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)))
        s = _scenario(rentals=[rental])
        with self.assertRaisesRegex(
                NotImplementedError,
                r"rental property #0 \('100 Example Street'\) carries a "
                r"`depreciation_override` and placed 'Rental building'"):
            enforce_scoped_refusals(s, "load")
        building.date_placed_in_service = date(YEAR - 1, 1, 15)
        building.prior_depreciation = float(
            reconstruct_prior_depreciation(building, YEAR, mid_quarter=False))
        rental.depreciation_override = dataclasses.replace(
            rental.depreciation_override,
            restates_engine_amount=float(macrs_deduction(building, YEAR, return_year=YEAR, mid_quarter=False)))
        enforce_scoped_refusals(s, "load")


if __name__ == "__main__":
    unittest.main()
