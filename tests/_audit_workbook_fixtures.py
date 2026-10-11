"""Synthetic scenarios shared by the depreciation audit tests.

Every name, address and figure here is invented. The hand figures below are
table cell x basis, IRS-rounded:

  building   27.5-year, January 2019, basis 200,000
             2019: 3.485% = 6,970; 2020-2024: 3.636% = 7,272 each
             prior through 2024 = 6,970 + 5 x 7,272 = 43,330; 2025 = 7,272
  appliance  5-year half-year, 2023, basis 10,000
             2023: 20% = 2,000; 2024: 32% = 3,200; prior = 5,200
             2025: 19.2% = 1,920
  furniture  7-year half-year, placed 2025, basis 7,000
             2025: 14.29% = 1,000.3 -> 1,000

Form 4562 line 17 = 7,272 + 1,920 = 9,192; line 19c = 1,000; line 22 = 10,192;
Schedule E line 18 = 10,192.
"""
import dataclasses
from datetime import date

from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tests.helpers import make_simple_scenario

YEAR = 2025
RENTAL_ADDRESS = "100 Example Street"

BUILDING = DepreciableAsset(
    description="Rental building", date_placed_in_service=date(2019, 1, 15),
    basis=200_000.0, recovery_class="27.5-year", prior_depreciation=43_330.0)
APPLIANCE = DepreciableAsset(
    description="Appliance set", date_placed_in_service=date(2023, 6, 1),
    basis=10_000.0, recovery_class="5-year", prior_depreciation=5_200.0,
    no_bonus_or_section_179_history=True, convention="half-year")
FURNITURE = DepreciableAsset(
    description="Furniture", date_placed_in_service=date(2025, 3, 10),
    basis=7_000.0, recovery_class="7-year",
    no_bonus_or_section_179_history=True)

LINE_17 = 9_192
LINE_19C = 1_000
LINE_22 = 10_192
SCH_E_LINE_18 = 10_192


def scenario(*, rental_assets=(BUILDING, APPLIANCE, FURNITURE),
             business_assets=None, rental_override=None,
             rental_stated=0.0, year: int = YEAR, form_3115=None):
    """A single filer with one rental (and, when ``business_assets`` is
    given, one Schedule C business)."""
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, first_name="Test", last_name="Filer",
        ssn="000-00-0000", acknowledges_no_source_documents=True)
    businesses = []
    if business_assets is not None:
        businesses = [ScheduleCBusiness(
            description="Consulting", business_code="541990",
            gross_receipts=50_000.0,
            depreciable_assets=tuple(business_assets))]
    return dataclasses.replace(
        base, config=config, acknowledges_no_listed_property=True,
        form_3115=form_3115,
        rental_properties=[RentalProperty(
            address=RENTAL_ADDRESS, property_type=1,
            fair_rental_days=365, personal_use_days=0,
            rents_received=24_000.0,
            depreciation=rental_stated,
            acknowledges_depreciation_stated_outside_macrs=bool(rental_stated),
            depreciation_override=rental_override,
            depreciable_assets=list(rental_assets))],
        schedule_c_businesses=businesses)


def override(amount: float, restates: float) -> DepreciationOverride:
    return DepreciationOverride(
        amount=amount, restates_engine_amount=restates, acknowledgment=True)
