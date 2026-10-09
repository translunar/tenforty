"""Listed property: a Form 4562 trigger the model cannot see.

Instructions for Form 4562 (2025), "Who Must File" (page 2): file the form
if claiming "Depreciation on any vehicle or other listed property
(regardless of when it was placed in service)."

tenforty emits Form 4562 only in a year property is placed in service, and
has no way to tell whether a personal-property asset is listed property (a
vehicle entered as 5-year property looks like any other). So a return with
ANY personal-property asset must state `acknowledges_no_listed_property:
true`; without it the return refuses rather than silently file no form in a
year the instructions require one.
"""

import copy
import unittest
from datetime import date

from tenforty.attestations import enforce_scoped_refusals
from tenforty.models import (
    DepreciableAsset, RentalProperty, ScheduleCBusiness, TaxReturnConfig,
)
from tests.helpers import make_simple_scenario

YEAR = 2025
REFUSAL = (r"listed property.*regardless of when it was placed in service.*"
           r"acknowledges_no_listed_property: true")


def _vehicle(year: int = 2023) -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Delivery van", date_placed_in_service=date(year, 3, 15),
        basis=30_000.0, recovery_class="5-year",
        no_bonus_or_section_179_history=True)
    if year < YEAR:
        asset.prior_depreciation = 0.0
        asset.acknowledges_prior_depreciation_as_stated = True
    return asset


def _building() -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=200_000.0, recovery_class="27.5-year")


def _scenario(rental_assets=(), business_assets=(), acknowledgment=None):
    s = make_simple_scenario()
    s.config.year = YEAR
    s.rental_properties = [RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=list(rental_assets))]
    s.schedule_c_businesses = [ScheduleCBusiness(
        description="Consulting", gross_receipts=50_000.0,
        depreciable_assets=tuple(business_assets))]
    s.acknowledges_no_listed_property = acknowledgment
    return s


class ListedPropertyAcknowledgmentTests(unittest.TestCase):
    def test_personal_property_without_the_acknowledgment_refuses(self):
        for acknowledgment in (None, False):
            with self.subTest(acknowledgment=acknowledgment):
                with self.assertRaisesRegex(
                        NotImplementedError, REFUSAL) as cm:
                    enforce_scoped_refusals(
                        _scenario(business_assets=[_vehicle()],
                                  acknowledgment=acknowledgment), "load")
                self.assertIn("'Delivery van'", str(cm.exception))

    def test_fires_in_an_ongoing_year_where_no_4562_would_be_emitted(self):
        """The regression this closes: prior-year personal property, so the
        placement-year rule emits no Form 4562 -- exactly when a listed
        asset would still require one."""
        from tenforty.forms import f4562
        s = _scenario(rental_assets=[_vehicle(2023)])
        self.assertFalse(f4562.is_required(s))
        with self.assertRaisesRegex(NotImplementedError, REFUSAL):
            enforce_scoped_refusals(s, "load")

    def test_proceeds_with_the_acknowledgment(self):
        enforce_scoped_refusals(
            _scenario(business_assets=[_vehicle()], acknowledgment=True),
            "load")

    def test_real_property_only_does_not_require_it(self):
        """Reachable negative twin: real property cannot be listed
        property, so a real-property-only return is not asked."""
        enforce_scoped_refusals(
            _scenario(rental_assets=[_building()]), "load")

    def test_no_assets_does_not_require_it(self):
        enforce_scoped_refusals(_scenario(), "load")

    def test_personal_property_on_either_activity_kind_triggers_it(self):
        for kwargs in ({"rental_assets": [_vehicle()]},
                       {"business_assets": [_vehicle()]}):
            with self.subTest(where=next(iter(kwargs))):
                with self.assertRaisesRegex(NotImplementedError, REFUSAL):
                    enforce_scoped_refusals(_scenario(**kwargs), "load")

    def test_it_is_a_scenario_key_not_a_config_field(self):
        self.assertFalse(
            hasattr(TaxReturnConfig, "acknowledges_no_listed_property"))


class ListedPropertyAcknowledgmentLoadingTests(unittest.TestCase):
    def _doc(self):
        from tests.test_asset_nest_loading import _appliance, _doc, _rental
        doc = _doc(rental_properties=[
            _rental(depreciable_assets=[_appliance()])])
        doc.pop("acknowledges_no_listed_property", None)
        return doc

    def test_yaml_refuses_then_loads_with_the_top_level_key(self):
        from tests.test_asset_nest_loading import _load
        with self.assertRaisesRegex(NotImplementedError, REFUSAL):
            _load(copy.deepcopy(self._doc()))
        doc = self._doc()
        doc["acknowledges_no_listed_property"] = True
        self.assertIs(_load(doc).acknowledges_no_listed_property, True)

    def test_non_boolean_key_is_refused(self):
        from tests.test_asset_nest_loading import _load
        doc = self._doc()
        doc["acknowledges_no_listed_property"] = "yes"
        with self.assertRaisesRegex(ValueError, "must be true or false"):
            _load(doc)


if __name__ == "__main__":
    unittest.main()
