"""forms.f4562.compute — Form 4562 Part III Section B (MACRS by class)."""

import unittest
from datetime import date

from tenforty.forms import f4562 as form_f4562
from tenforty.models import DepreciableAsset
from tests import _audit_workbook_fixtures as fx
from tests._f4562_helpers import compute_copy
from tests.helpers import make_simple_scenario

def _nest_assets(scenario, assets):
    """Assets nest under an activity; hang them on one rental property."""
    from tenforty.models import RentalProperty
    scenario.rental_properties = [RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=0.0,
        depreciable_assets=list(assets))]


def _scenario_with_assets(*assets):
    s = make_simple_scenario()
    s.config.first_name = "Test"
    s.config.last_name = "Filer"
    s.config.ssn = "000-00-0000"
    s.config.year = 2025
    _nest_assets(s, assets)
    return s


class F4562ComputeTests(unittest.TestCase):
    def test_empty_assets_total_zero(self):
        r = form_f4562.compute(_scenario_with_assets(), upstream={})
        self.assertEqual(r["f4562_line_22_total_depreciation"], 0)
        self.assertEqual(r["f4562_part_iii_section_b_rows"], [])

    def test_one_rental_building_emits_19i_row(self):
        asset = DepreciableAsset(
            description="Cedar Court",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
        )
        r = form_f4562.compute(_scenario_with_assets(asset), upstream={})
        self.assertEqual(len(r["f4562_part_iii_section_b_rows"]), 1)
        row = r["f4562_part_iii_section_b_rows"][0]
        self.assertEqual(row["row_label"], "i")
        self.assertEqual(row["recovery_class"], "27.5-year")
        self.assertEqual(row["basis"], 200_000.0)
        self.assertEqual(row["deduction"], 6_970)
        self.assertEqual(row["method"], "S/L")
        self.assertEqual(r["f4562_line_19i_basis"], 200_000)
        self.assertEqual(r["f4562_line_19i_deduction"], 6_970)
        self.assertEqual(r["f4562_line_19i_date_placed_in_service"], "01/2025")
        self.assertEqual(r["f4562_line_19i_recovery_period"], "27.5 yrs.")
        self.assertEqual(r["f4562_line_19i_convention"], "MM")
        self.assertEqual(r["f4562_line_19i_method"], "S/L")
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970)

    def test_building_and_laptop_emit_two_rows_summed(self):
        building = DepreciableAsset(
            description="Building",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
        )
        laptop = DepreciableAsset(
            description="Laptop",
            date_placed_in_service=date(2025, 3, 1),
            basis=2_500.0,
            recovery_class="5-year",
        )
        r = form_f4562.compute(
            _scenario_with_assets(building, laptop), upstream={},
        )
        # 5-year → 19b, 27.5-year → 19i.
        self.assertEqual(r["f4562_line_19b_basis"], 2_500)
        self.assertEqual(r["f4562_line_19b_deduction"], 500)
        self.assertEqual(r["f4562_line_19b_method"], "200 DB")
        self.assertEqual(r["f4562_line_19b_convention"], "HY")
        self.assertEqual(r["f4562_line_19i_basis"], 200_000)
        self.assertEqual(r["f4562_line_19i_deduction"], 6_970)
        self.assertEqual(r["f4562_line_22_total_depreciation"], 6_970 + 500)

    def test_multiple_5_year_assets_aggregate_into_one_19b_row(self):
        a = DepreciableAsset(
            description="Laptop A", date_placed_in_service=date(2025, 3, 1),
            basis=2_500.0, recovery_class="5-year",
        )
        b = DepreciableAsset(
            description="Laptop B", date_placed_in_service=date(2025, 7, 1),
            basis=1_500.0, recovery_class="5-year",
        )
        r = form_f4562.compute(_scenario_with_assets(a, b), upstream={})
        self.assertEqual(len(r["f4562_part_iii_section_b_rows"]), 1)
        # Column (b) is shaded on a personal-property row: no date key.
        self.assertNotIn("f4562_line_19b_date_placed_in_service", r)
        self.assertEqual(r["f4562_line_19b_basis"], 4_000)
        # 20.00% × 4,000 = 800.
        self.assertEqual(r["f4562_line_19b_deduction"], 800)

    def test_identity_fields_from_config(self):
        r = form_f4562.compute(_scenario_with_assets(), upstream={})
        self.assertEqual(r["taxpayer_name"], "Test Filer")
        self.assertEqual(r["taxpayer_ssn"], "000-00-0000")

    def test_propagates_disposition_not_implemented(self):
        a = DepreciableAsset(
            description="Sold asset",
            date_placed_in_service=date(2022, 1, 1),
            basis=10_000.0,
            recovery_class="5-year",
            disposed=date(2025, 6, 1),
        )
        with self.assertRaisesRegex(NotImplementedError, "disposition"):
            form_f4562.compute(_scenario_with_assets(a), upstream={})

    def test_basis_rounding_at_half_boundary_follows_irs_half_up(self):
        # Python's built-in round() uses banker's rounding: round(200_000.5) == 200_000
        # (rounds to nearest even). The IRS rule is always round half up, so 200_000.5
        # must become 200_001. Two assets whose bases sum to exactly X.5 exercise this
        # boundary and expose any banker's-rounding bug.
        a = DepreciableAsset(
            description="Main equipment", date_placed_in_service=date(2025, 3, 1),
            basis=200_000.0, recovery_class="5-year",
        )
        b = DepreciableAsset(
            description="Accessory", date_placed_in_service=date(2025, 4, 1),
            basis=0.5, recovery_class="5-year",
        )
        r = form_f4562.compute(_scenario_with_assets(a, b), upstream={})
        # IRS half-up: 200_000.5 → 200_001. Banker's rounding would yield 200_000.
        self.assertEqual(r["f4562_line_19b_basis"], 200_001)


RENTAL = ("rental_properties", 0)
BUSINESS = ("schedule_c_businesses", 0)
LINE_22 = "f4562_line_22_total_depreciation"
ROWS = "f4562_part_iii_section_b_rows"

# 5-year half-year, placed February 2025, basis 10,000: 20% = 2,000.
NEW_EQUIPMENT = DepreciableAsset(
    description="Equipment", date_placed_in_service=date(2025, 2, 1),
    basis=10_000.0, recovery_class="5-year",
    no_bonus_or_section_179_history=True)


def _two_activity_scenario(business_assets=(fx.APPLIANCE, NEW_EQUIPMENT),
                           rental_assets=(fx.BUILDING, fx.FURNITURE)):
    """A rental holding a prior-year building (7,272 this year) and a 7-year
    asset placed this year (1,000); a business holding a prior-year 5-year
    asset (1,920) and a 5-year asset placed this year (2,000). Every
    placement is in the first quarter, so the return is half-year."""
    return fx.scenario(
        rental_assets=rental_assets, business_assets=business_assets)


class OneCopyPerActivityTests(unittest.TestCase):
    # What a single form over both activities would total.
    MERGED_TOTAL = 7_272 + 1_000 + 1_920 + 2_000

    def test_a_copy_carries_only_its_own_activitys_assets(self):
        scenario = _two_activity_scenario()
        rental = compute_copy(scenario, *RENTAL)
        self.assertEqual(rental[form_f4562.LINE_17_KEY], 7_272)
        self.assertEqual(
            [row["recovery_class"] for row in rental[ROWS]], ["7-year"])
        self.assertEqual(rental["f4562_line_19c_deduction"], 1_000)
        self.assertNotIn("f4562_line_19b_deduction", rental)
        self.assertEqual(rental[LINE_22], 8_272)

        business = compute_copy(scenario, *BUSINESS)
        self.assertEqual(business[form_f4562.LINE_17_KEY], 1_920)
        self.assertEqual(
            [row["recovery_class"] for row in business[ROWS]], ["5-year"])
        self.assertEqual(business["f4562_line_19b_deduction"], 2_000)
        self.assertNotIn("f4562_line_19c_deduction", business)
        self.assertEqual(business[LINE_22], 3_920)

        self.assertEqual(self.MERGED_TOTAL, 12_192)
        self.assertNotEqual(rental[LINE_22], self.MERGED_TOTAL)
        self.assertNotEqual(business[LINE_22], self.MERGED_TOTAL)

    def test_is_required_for_asks_one_activity(self):
        scenario = _two_activity_scenario(business_assets=(fx.APPLIANCE,))
        rental = scenario.rental_properties[0]
        business = scenario.schedule_c_businesses[0]
        self.assertIs(form_f4562.is_required_for(rental, fx.YEAR), True)
        self.assertIs(form_f4562.is_required_for(business, fx.YEAR), False)
        self.assertIs(form_f4562.is_required(scenario), True)
        # Twin: no placement this year on either activity.
        ongoing = _two_activity_scenario(
            rental_assets=(fx.BUILDING,), business_assets=(fx.APPLIANCE,))
        self.assertIs(form_f4562.is_required_for(
            ongoing.rental_properties[0], fx.YEAR), False)
        self.assertIs(form_f4562.is_required_for(
            ongoing.schedule_c_businesses[0], fx.YEAR), False)
        self.assertIs(form_f4562.is_required(ongoing), False)

    def test_line_22_is_line_17_plus_the_rows(self):
        scenario = _two_activity_scenario()
        for activity, line_17, rows, line_22 in (
                (RENTAL, 7_272, [1_000], 8_272),
                (BUSINESS, 1_920, [2_000], 3_920)):
            with self.subTest(activity=activity):
                copy = compute_copy(scenario, *activity)
                self.assertEqual(copy[form_f4562.LINE_17_KEY], line_17)
                self.assertEqual(
                    [row["deduction"] for row in copy[ROWS]], rows)
                self.assertEqual(copy[LINE_22], line_22)
                self.assertEqual(
                    copy[LINE_22],
                    copy[form_f4562.LINE_17_KEY]
                    + sum(row["deduction"] for row in copy[ROWS]))


if __name__ == "__main__":
    unittest.main()
