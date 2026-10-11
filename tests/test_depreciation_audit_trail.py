"""The resolver's audit trail: the engine's own arithmetic, exposed per asset
and per year, for the depreciation audit workbook to transcribe.

Expected figures are hand-computed in tests/_audit_workbook_fixtures.py.
"""
import dataclasses
import unittest
from datetime import date

from tenforty.forms.depreciation import macrs, resolver
from tenforty.forms.depreciation.tables import TABLE_A_1, TABLE_A_6, TABLE_A_7a
from tenforty.models import DepreciableAsset
from tenforty.params import macrs_mid_quarter
from tenforty.rounding import irs_round
from tests import _audit_workbook_fixtures as fx


def _trail(scenario):
    return resolver.audit_trail(scenario)


def _assets(scenario):
    return [a for activity in _trail(scenario) for a in activity.assets]


class AuditTrailTests(unittest.TestCase):
    def test_one_activity_with_three_assets_in_order(self):
        trail = _trail(fx.scenario())
        self.assertEqual(len(trail), 1)
        self.assertEqual(trail[0].section, "rental_properties")
        self.assertEqual(trail[0].index, 0)
        self.assertEqual(trail[0].mode, resolver.MODE_ASSETS)
        self.assertEqual(
            [a.description for a in trail[0].assets],
            ["Rental building", "Appliance set", "Furniture"])
        self.assertEqual([a.asset_index for a in trail[0].assets], [0, 1, 2])

    def test_current_amounts_are_the_hand_figures(self):
        building, appliance, furniture = _assets(fx.scenario())
        self.assertEqual(building.current.amount, 7_272)
        self.assertEqual(appliance.current.amount, 1_920)
        self.assertEqual(furniture.current.amount, 1_000)
        self.assertEqual(_trail(fx.scenario())[0].engine_amount, 10_192)

    def test_current_amount_equals_resolver_amount(self):
        scenario = fx.scenario()
        sources = scenario.rental_properties[0].depreciable_assets
        for audit, asset in zip(_assets(scenario), sources, strict=True):
            with self.subTest(asset=asset.description):
                amount, table = resolver.asset_amount(
                    asset, fx.YEAR, mid_quarter=False)
                self.assertEqual(audit.current.amount, amount)
                self.assertEqual(audit.current.table_amount, table)

    def test_current_rates_are_the_table_cells(self):
        building, appliance, furniture = _assets(fx.scenario())
        self.assertEqual(building.current.rate, 0.03636)
        self.assertEqual(building.current.recovery_year, 7)
        self.assertEqual(appliance.current.rate, 0.1920)
        self.assertEqual(appliance.current.recovery_year, 3)
        self.assertEqual(furniture.current.rate, 0.1429)
        self.assertEqual(furniture.current.recovery_year, 1)

    def test_table_identity_per_convention(self):
        building, appliance, furniture = _assets(fx.scenario())
        self.assertEqual(building.table, "A-6")
        self.assertEqual(appliance.table, "A-1")
        self.assertEqual(furniture.table, "A-1")
        office = DepreciableAsset(
            description="Office", date_placed_in_service=date(2020, 5, 1),
            basis=100_000.0, recovery_class="39-year",
            prior_depreciation=0.0,
            acknowledges_prior_depreciation_as_stated=True)
        self.assertEqual(
            _assets(fx.scenario(rental_assets=(office,)))[0].table, "A-7a")
        # A lone fourth-quarter placement trips the 40% test.
        late = dataclasses.replace(
            fx.FURNITURE, date_placed_in_service=date(2025, 11, 3))
        [mid_quarter] = _assets(fx.scenario(rental_assets=(late,)))
        self.assertEqual(mid_quarter.table, "A-5")
        self.assertEqual(mid_quarter.convention, macrs.MID_QUARTER)
        self.assertEqual(mid_quarter.quarter, 4)
        self.assertEqual(mid_quarter.current.rate, 0.0357)

    def test_year_rows_run_from_placement_to_the_return_year(self):
        building, appliance, furniture = _assets(fx.scenario())
        self.assertEqual(
            [y.tax_year for y in building.years], list(range(2019, 2026)))
        self.assertEqual(
            [y.recovery_year for y in building.years], list(range(1, 8)))
        self.assertEqual(
            [y.amount for y in building.years],
            [6_970, 7_272, 7_272, 7_272, 7_272, 7_272, 7_272])
        self.assertEqual(
            [y.amount for y in appliance.years], [2_000, 3_200, 1_920])
        self.assertEqual([y.amount for y in furniture.years], [1_000])

    def test_year_rows_reconstruct_prior(self):
        scenario = fx.scenario()
        sources = scenario.rental_properties[0].depreciable_assets
        for audit, asset in zip(_assets(scenario), sources, strict=True):
            with self.subTest(asset=asset.description):
                self.assertEqual(
                    sum(y.amount for y in audit.years[:-1]),
                    resolver.reconstruct_prior_depreciation(
                        asset, fx.YEAR, mid_quarter=False))
                self.assertEqual(
                    [y.taken_before for y in audit.years],
                    [sum(z.amount for z in audit.years[:i])
                     for i in range(len(audit.years))])

    def test_rate_times_basis_rounds_to_table_amount(self):
        seen = 0
        for audit in _assets(fx.scenario()):
            for year in audit.years:
                with self.subTest(asset=audit.description, year=year.tax_year):
                    self.assertIsNotNone(year.rate)
                    self.assertEqual(
                        irs_round(audit.basis * year.rate), year.table_amount)
                    seen += 1
        self.assertEqual(seen, 7 + 3 + 1)

    def test_elapsed_schedule_has_no_rate(self):
        old = DepreciableAsset(
            description="Old computer", date_placed_in_service=date(2015, 4, 1),
            basis=3_000.0, recovery_class="5-year", prior_depreciation=3_000.0,
            no_bonus_or_section_179_history=True, convention="half-year")
        [audit] = _assets(fx.scenario(rental_assets=(old,)))
        self.assertIsNone(audit.current.rate)
        self.assertEqual(audit.current.amount, 0)
        self.assertEqual(audit.current.table_amount, 0)
        self.assertEqual(audit.current.recovery_year, 11)
        # 2015-2020 are on the table (six recovery years); 2021+ are not.
        self.assertEqual(
            [y.rate is None for y in audit.years], [False] * 6 + [True] * 5)

    def test_stated_prior_is_carried_as_stated(self):
        building, appliance, furniture = _assets(fx.scenario())
        self.assertEqual(building.prior_depreciation, 43_330.0)
        self.assertFalse(building.prior_acknowledged)
        self.assertEqual(building.current.taken_before, 43_330)
        self.assertIsNone(furniture.prior_depreciation)
        self.assertEqual(furniture.current.taken_before, 0)

    def test_acknowledged_prior_is_the_taken_figure(self):
        # Ran ahead of the tables: 9,500 taken against the tables' 5,200.
        ahead = dataclasses.replace(
            fx.APPLIANCE, prior_depreciation=9_500.0,
            acknowledges_prior_depreciation_as_stated=True)
        [audit] = _assets(fx.scenario(rental_assets=(ahead,)))
        self.assertTrue(audit.prior_acknowledged)
        self.assertEqual(audit.current.taken_before, 9_500)
        self.assertEqual(audit.current.table_amount, 1_920)
        self.assertEqual(audit.current.amount, 500)
        # The year rows stay the TABLE reconstruction.
        self.assertEqual(audit.years[-1].taken_before, 5_200)
        self.assertEqual(audit.years[-1].amount, 1_920)

    def test_stated_mode_activity_absent(self):
        self.assertEqual(
            _trail(fx.scenario(rental_assets=(), rental_stated=4_000.0)), ())

    def test_no_depreciation_activity_absent(self):
        self.assertEqual(_trail(fx.scenario(rental_assets=())), ())

    def test_overridden_activity_carries_both_figures(self):
        prior_only = (fx.BUILDING, fx.APPLIANCE)
        [activity] = _trail(fx.scenario(
            rental_assets=prior_only,
            rental_override=fx.override(9_000.0, 9_192.0)))
        self.assertEqual(activity.mode, resolver.MODE_ASSETS_OVERRIDDEN)
        self.assertEqual(activity.used_amount, 9_000.0)
        self.assertEqual(activity.engine_amount, 9_192)
        self.assertEqual(activity.override_amount, 9_000.0)
        self.assertEqual(activity.restates_engine_amount, 9_192.0)

    def test_plain_activity_carries_no_override(self):
        [activity] = _trail(fx.scenario())
        self.assertIsNone(activity.override_amount)
        self.assertIsNone(activity.restates_engine_amount)
        self.assertEqual(activity.used_amount, 10_192)

    def test_schedule_c_activity_follows_the_rental(self):
        equipment = dataclasses.replace(fx.APPLIANCE, description="Equipment")
        trail = _trail(fx.scenario(business_assets=(equipment,)))
        self.assertEqual(
            [(a.section, a.index) for a in trail],
            [("rental_properties", 0), ("schedule_c_businesses", 0)])
        self.assertEqual(trail[1].assets[0].description, "Equipment")
        self.assertIn("Consulting", trail[1].label)


class MacrsRateRefactorTests(unittest.TestCase):
    """`macrs_deduction` is `irs_round(basis x table cell)`, the cell read
    here straight from the tables (never through `macrs_rate`)."""

    BASIS = 123_457.0

    def _asset(self, recovery_class, placed, **kw):
        return DepreciableAsset(
            description="Probe", date_placed_in_service=placed,
            basis=self.BASIS, recovery_class=recovery_class, **kw)

    def test_half_year_table_cells(self):
        checked = 0
        for cls, column in TABLE_A_1.items():
            asset = self._asset(cls, date(2000, 6, 1), convention="half-year")
            for recovery_year, cell in column.items():
                tax_year = 2000 + recovery_year - 1
                with self.subTest(cls=cls, recovery_year=recovery_year):
                    self.assertEqual(
                        macrs.macrs_deduction(
                            asset, tax_year, return_year=2060,
                            mid_quarter=False),
                        irs_round(self.BASIS * cell))
                    self.assertEqual(
                        macrs.macrs_rate(
                            asset, tax_year, return_year=2060,
                            mid_quarter=False), cell)
                    checked += 1
        self.assertEqual(checked, 4 + 6 + 8 + 11 + 16 + 21)

    def test_mid_quarter_table_cells(self):
        checked = 0
        for quarter, table in macrs_mid_quarter.TABLES_BY_QUARTER.items():
            for class_years, column in table.items():
                asset = self._asset(
                    f"{class_years}-year", date(2000, 6, 1),
                    convention="mid-quarter", quarter=quarter)
                for recovery_year, cell in column.items():
                    with self.subTest(quarter=quarter, cls=class_years,
                                      recovery_year=recovery_year):
                        self.assertEqual(
                            macrs.macrs_deduction(
                                asset, 2000 + recovery_year - 1,
                                return_year=2060, mid_quarter=False),
                            irs_round(self.BASIS * cell))
                        checked += 1
        self.assertEqual(checked, 4 * (4 + 6 + 8 + 11 + 16 + 21))

    def test_mid_month_table_cells(self):
        checked = 0
        for cls, table in (("27.5-year", TABLE_A_6["27.5-year"]),
                           ("39-year", TABLE_A_7a["39-year"])):
            for recovery_year, months in table.items():
                for month, cell in months.items():
                    asset = self._asset(cls, date(2000, month, 1))
                    with self.subTest(cls=cls, recovery_year=recovery_year,
                                      month=month):
                        self.assertEqual(
                            macrs.macrs_deduction(
                                asset, 2000 + recovery_year - 1,
                                return_year=2060, mid_quarter=False),
                            irs_round(self.BASIS * cell))
                        checked += 1
        self.assertEqual(checked, 29 * 12 + 40 * 12)

    def test_no_rate_outside_the_table(self):
        asset = self._asset("5-year", date(2000, 6, 1), convention="half-year")
        for tax_year in (1999, 2006, 2030):
            with self.subTest(tax_year=tax_year):
                self.assertIsNone(macrs.macrs_rate(
                    asset, tax_year, return_year=2060, mid_quarter=False))
                self.assertEqual(macrs.macrs_deduction(
                    asset, tax_year, return_year=2060, mid_quarter=False), 0)

    def test_every_table_identity(self):
        self.assertEqual(macrs.table_identity(
            self._asset("27.5-year", date(2000, 6, 1)),
            return_year=2060, mid_quarter=False), "A-6")
        self.assertEqual(macrs.table_identity(
            self._asset("39-year", date(2000, 6, 1)),
            return_year=2060, mid_quarter=False), "A-7a")
        self.assertEqual(macrs.table_identity(
            self._asset("7-year", date(2000, 6, 1), convention="half-year"),
            return_year=2060, mid_quarter=False), "A-1")
        for quarter, table in ((1, "A-2"), (2, "A-3"), (3, "A-4"), (4, "A-5")):
            with self.subTest(quarter=quarter):
                self.assertEqual(macrs.table_identity(
                    self._asset("7-year", date(2000, 6, 1),
                                convention="mid-quarter", quarter=quarter),
                    return_year=2060, mid_quarter=False), table)


if __name__ == "__main__":
    unittest.main()
