"""Asset Nest: depreciable assets nest under their activity, and the load-time
shape rules that fence the asset model.

Every refusal here is a refusal-ledger entry (tenforty.attestations) and has a
firing test asserting its SPECIFIC message plus a neighbouring twin that
loads, so a different refusal firing first does not count as proof.

All figures are invented. Prior-year assets carry the per-asset
prior-as-stated acknowledgment so these shape tests do not depend on the
prior-depreciation reconciliation.
"""

import copy
import datetime
import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tenforty.scenario import load_scenario
from tests.helpers import scope_out_attestation_defaults

YEAR = 2025


def _config() -> dict:
    return {
        "year": YEAR, "filing_status": "single", "birthdate": "1980-01-01",
        "state": "CA", "first_name": "Test", "last_name": "Filer",
        "ssn": "000-00-0000", "has_foreign_accounts": False,
        "prior_year_itemized": False,
        **scope_out_attestation_defaults(),
    }


def _rental(**extra) -> dict:
    return {
        "address": "100 Example Street", "property_type": 1,
        "fair_rental_days": 365, "personal_use_days": 0,
        "rents_received": 24_000.0, **extra,
    }


def _business(**extra) -> dict:
    return {"description": "Consulting", "gross_receipts": 50_000.0, **extra}


def _building(**extra) -> dict:
    """Residential rental building placed in service THIS year."""
    return {
        "description": "Rental building",
        "date_placed_in_service": datetime.date(YEAR, 3, 1),
        "basis": 200_000.0, "recovery_class": "27.5-year", **extra,
    }


def _old_building(**extra) -> dict:
    """Residential rental building placed in service in a PRIOR year."""
    return {
        "description": "Rental building",
        "date_placed_in_service": datetime.date(2019, 6, 1),
        "basis": 200_000.0, "recovery_class": "27.5-year",
        "prior_depreciation": 40_000.0,
        "acknowledges_prior_depreciation_as_stated": True, **extra,
    }


def _appliance(**extra) -> dict:
    """Five-year personal property placed in service THIS year."""
    return {
        "description": "Refrigerator",
        "date_placed_in_service": datetime.date(YEAR, 2, 1),
        "basis": 3_000.0, "recovery_class": "5-year",
        "no_bonus_or_section_179_history": True, **extra,
    }


def _load(doc: dict):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.yaml"
        path.write_text(yaml.safe_dump(doc))
        return load_scenario(path)


def _doc(**sections) -> dict:
    return {"config": _config(), **copy.deepcopy(sections)}


class AssetModelTests(unittest.TestCase):
    def test_asset_has_no_convention_field(self):
        with self.assertRaises(TypeError):
            DepreciableAsset(
                description="Rental building",
                date_placed_in_service=datetime.date(2019, 6, 1),
                basis=200_000.0, recovery_class="27.5-year",
                convention="mid-month")

    def test_asset_new_field_defaults(self):
        a = DepreciableAsset(
            description="Rental building",
            date_placed_in_service=datetime.date(2019, 6, 1),
            basis=200_000.0, recovery_class="27.5-year")
        self.assertIsNone(a.prior_depreciation)
        self.assertIsNone(a.no_bonus_or_section_179_history)
        self.assertIs(a.acknowledges_prior_depreciation_as_stated, False)
        self.assertIsNone(a.disposed)

    def test_activities_default_to_no_assets_no_override(self):
        rp = RentalProperty(
            address="100 Example Street", property_type=1,
            fair_rental_days=365, personal_use_days=0, rents_received=1.0)
        biz = ScheduleCBusiness()
        for activity in (rp, biz):
            with self.subTest(activity=type(activity).__name__):
                self.assertEqual(len(activity.depreciable_assets), 0)
                self.assertIsNone(activity.depreciation_override)
                self.assertIs(
                    activity.acknowledges_depreciation_stated_outside_macrs,
                    False)

    def test_scenario_has_no_top_level_asset_list(self):
        from tests.helpers import make_simple_scenario
        self.assertFalse(
            hasattr(make_simple_scenario(), "depreciable_assets"))


class NestedLoadingTests(unittest.TestCase):
    def test_rental_assets_load_nested(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_building(), _appliance()])]))
        assets = s.rental_properties[0].depreciable_assets
        self.assertEqual(len(assets), 2)
        self.assertIsInstance(assets[0], DepreciableAsset)
        self.assertEqual(assets[0].recovery_class, "27.5-year")
        self.assertEqual(
            assets[0].date_placed_in_service, datetime.date(YEAR, 3, 1))
        self.assertEqual(assets[0].basis, 200_000.0)
        self.assertIs(assets[1].no_bonus_or_section_179_history, True)

    def test_schedule_c_assets_load_nested(self):
        s = _load(_doc(schedule_c_businesses=[
            _business(depreciable_assets=[_appliance()])]))
        assets = s.schedule_c_businesses[0].depreciable_assets
        self.assertEqual(len(assets), 1)
        self.assertIsInstance(assets[0], DepreciableAsset)
        self.assertEqual(assets[0].description, "Refrigerator")

    def test_quoted_iso_date_is_coerced(self):
        s = _load(_doc(rental_properties=[_rental(depreciable_assets=[
            _building(date_placed_in_service=f"{YEAR}-03-01")])]))
        self.assertEqual(
            s.rental_properties[0].depreciable_assets[0]
            .date_placed_in_service, datetime.date(YEAR, 3, 1))

    def test_prior_year_asset_carries_prior_depreciation(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_old_building()])]))
        a = s.rental_properties[0].depreciable_assets[0]
        self.assertEqual(a.prior_depreciation, 40_000.0)
        self.assertIs(a.acknowledges_prior_depreciation_as_stated, True)

    def test_override_block_loads(self):
        s = _load(_doc(rental_properties=[_rental(
            depreciable_assets=[_old_building()],
            depreciation_override={
                "amount": 7_000.0, "restates_engine_amount": 7_272.0,
                "acknowledgment": True})]))
        ov = s.rental_properties[0].depreciation_override
        self.assertIsInstance(ov, DepreciationOverride)
        self.assertEqual(ov.amount, 7_000.0)
        self.assertEqual(ov.restates_engine_amount, 7_272.0)
        self.assertIs(ov.acknowledgment, True)

    def test_unknown_asset_key_is_refused(self):
        with self.assertRaisesRegex(
                ValueError, r"Unknown key\(s\) in rental_properties\[0\]"
                            r"\.depreciable_assets\[0\]: \['salvage_value'\]"):
            _load(_doc(rental_properties=[_rental(depreciable_assets=[
                _building(salvage_value=1.0)])]))

    def test_unknown_override_key_is_refused(self):
        with self.assertRaisesRegex(
                ValueError, r"Unknown key\(s\) in rental_properties\[0\]"
                            r"\.depreciation_override: \['reason'\]"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[_old_building()],
                depreciation_override={
                    "amount": 7_000.0, "restates_engine_amount": 7_272.0,
                    "acknowledgment": True, "reason": "books"})]))

    def test_override_missing_restatement_is_refused(self):
        with self.assertRaisesRegex(
                ValueError, r"depreciation_override is missing "
                            r"\['restates_engine_amount'\]"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[_old_building()],
                depreciation_override={
                    "amount": 7_000.0, "acknowledgment": True})]))

    def test_non_boolean_acknowledgment_is_refused(self):
        """A quoted "no" is truthy; strings are refused, never coerced."""
        cases = {
            "asset history field": _doc(rental_properties=[_rental(
                depreciable_assets=[
                    _appliance(no_bonus_or_section_179_history="no")])]),
            "asset prior-as-stated": _doc(rental_properties=[_rental(
                depreciable_assets=[_old_building(
                    acknowledges_prior_depreciation_as_stated="no")])]),
            "activity stated figure": _doc(rental_properties=[_rental(
                depreciation=5_000.0,
                acknowledges_depreciation_stated_outside_macrs="no")]),
            "override acknowledgment": _doc(rental_properties=[_rental(
                depreciable_assets=[_old_building()],
                depreciation_override={
                    "amount": 7_000.0, "restates_engine_amount": 7_272.0,
                    "acknowledgment": "no"})]),
        }
        for label, doc in cases.items():
            with self.subTest(case=label):
                with self.assertRaisesRegex(ValueError, "must be true or false"):
                    _load(doc)


class TopLevelAssetListRefusalTests(unittest.TestCase):
    def test_top_level_list_refuses_with_migration_pointer(self):
        with self.assertRaisesRegex(
                ValueError,
                r"top-level `depreciable_assets:`.*"
                r"rental_properties\[n\]\.depreciable_assets.*"
                r"schedule_c_businesses\[n\]\.depreciable_assets") as cm:
            _load(_doc(depreciable_assets=[_building()]))
        self.assertNotIn("Unknown top-level key", str(cm.exception))

    def test_shipped_fixture_is_this_refusals_test(self):
        from tests.helpers import FIXTURES_DIR
        with self.assertRaisesRegex(
                ValueError, r"top-level `depreciable_assets:`"):
            load_scenario(FIXTURES_DIR / "rental_with_depreciation.yaml")

    def test_same_assets_nested_under_a_rental_load(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_building()])]))
        self.assertEqual(len(s.rental_properties[0].depreciable_assets), 1)


class StatedConventionRefusalTests(unittest.TestCase):
    def test_asset_carrying_convention_refuses(self):
        for section, activity in (
                ("rental_properties", _rental), ("schedule_c_businesses",
                                                 _business)):
            with self.subTest(section=section):
                asset = (_building(convention="mid-month")
                         if section == "rental_properties"
                         else _appliance(convention="half-year"))
                with self.assertRaisesRegex(
                        ValueError,
                        rf"{section}\[0\]\.depreciable_assets\[0\].*"
                        r"convention is computed, not stated"):
                    _load(_doc(**{section: [
                        activity(depreciable_assets=[asset])]}))

    def test_same_asset_without_convention_loads(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_building()])]))
        self.assertEqual(len(s.rental_properties[0].depreciable_assets), 1)


class DualSourceRefusalTests(unittest.TestCase):
    def test_assets_and_stated_scalar_on_one_activity_refuse(self):
        with self.assertRaisesRegex(
                ValueError,
                r"rental property #0 \('100 Example Street'\) carries both "
                r"`depreciable_assets` and a stated `depreciation`"):
            _load(_doc(rental_properties=[_rental(
                depreciation=5_000.0,
                acknowledges_depreciation_stated_outside_macrs=True,
                depreciable_assets=[_building()])]))

    def test_schedule_c_dual_source_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"Schedule C business #0 \('Consulting'\) carries both "
                r"`depreciable_assets` and a stated `depreciation`"):
            _load(_doc(schedule_c_businesses=[_business(
                depreciation=500.0,
                acknowledges_depreciation_stated_outside_macrs=True,
                depreciable_assets=[_appliance()])]))

    def test_either_source_alone_loads(self):
        assets_only = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_building()])]))
        self.assertEqual(assets_only.rental_properties[0].depreciation, 0.0)
        stated_only = _load(_doc(rental_properties=[_rental(
            depreciation=5_000.0,
            acknowledges_depreciation_stated_outside_macrs=True)]))
        self.assertEqual(
            len(stated_only.rental_properties[0].depreciable_assets), 0)
        self.assertEqual(stated_only.rental_properties[0].depreciation, 5_000.0)


class UnacknowledgedStatedFigureRefusalTests(unittest.TestCase):
    def test_stated_scalar_without_acknowledgment_refuses(self):
        for label, extra in (("absent", {}), ("false", {
                "acknowledges_depreciation_stated_outside_macrs": False})):
            with self.subTest(acknowledgment=label):
                with self.assertRaisesRegex(
                        ValueError,
                        r"rental property #0 \('100 Example Street'\) states "
                        r"`depreciation`.*"
                        r"acknowledges_depreciation_stated_outside_macrs"):
                    _load(_doc(rental_properties=[
                        _rental(depreciation=5_000.0, **extra)]))

    def test_schedule_c_stated_scalar_without_acknowledgment_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"Schedule C business #0 \('Consulting'\) states "
                r"`depreciation`"):
            _load(_doc(schedule_c_businesses=[
                _business(depreciation=500.0)]))

    def test_with_acknowledgment_loads(self):
        s = _load(_doc(rental_properties=[_rental(
            depreciation=5_000.0,
            acknowledges_depreciation_stated_outside_macrs=True)]))
        self.assertEqual(s.rental_properties[0].depreciation, 5_000.0)

    def test_zero_depreciation_needs_no_acknowledgment(self):
        """No filer without depreciation is taxed by the acknowledgment."""
        s = _load(_doc(rental_properties=[_rental()],
                       schedule_c_businesses=[_business()]))
        self.assertEqual(s.rental_properties[0].depreciation, 0.0)


class MissingPriorDepreciationRefusalTests(unittest.TestCase):
    def test_prior_year_asset_without_prior_depreciation_refuses(self):
        asset = _old_building()
        del asset["prior_depreciation"]
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Rental building' on rental property #0 "
                r"\('100 Example Street'\) was placed in service in 2019, "
                r"before the 2025 return year, but states no "
                r"`prior_depreciation`"):
            _load(_doc(rental_properties=[
                _rental(depreciable_assets=[asset])]))

    def test_current_year_asset_without_it_loads(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_building()])]))
        self.assertIsNone(
            s.rental_properties[0].depreciable_assets[0].prior_depreciation)


class BonusHistoryRefusalTests(unittest.TestCase):
    def test_personal_property_without_true_history_field_refuses(self):
        absent = _appliance()
        del absent["no_bonus_or_section_179_history"]
        for label, asset in (
                ("absent", absent),
                ("false", _appliance(no_bonus_or_section_179_history=False))):
            with self.subTest(field=label):
                with self.assertRaisesRegex(
                        NotImplementedError,
                        r"asset 'Refrigerator' on rental property #0 "
                        r"\('100 Example Street'\) is 5-year personal "
                        r"property without "
                        r"`no_bonus_or_section_179_history: true`"):
                    _load(_doc(rental_properties=[
                        _rental(depreciable_assets=[asset])]))

    def test_field_true_loads(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_appliance()])]))
        self.assertIs(
            s.rental_properties[0].depreciable_assets[0]
            .no_bonus_or_section_179_history, True)

    def test_refusal_names_both_outs(self):
        with self.assertRaisesRegex(
                NotImplementedError,
                r"add a `depreciation_override` to the activity.*"
                r"or remove the activity's asset list and state.*"
                r"acknowledges_depreciation_stated_outside_macrs"):
            _load(_doc(rental_properties=[_rental(depreciable_assets=[
                _appliance(no_bonus_or_section_179_history=False)])]))

    def _tainted_prior_year_asset(self, **extra) -> dict:
        """Five-year property placed in a PRIOR year (an override cannot
        coexist with a current-year placement), history field false."""
        return {
            "description": "Refrigerator",
            "date_placed_in_service": datetime.date(2023, 3, 15),
            "basis": 10_000.0, "recovery_class": "5-year",
            "no_bonus_or_section_179_history": False,
            "prior_depreciation": 9_000.0,
            "acknowledges_prior_depreciation_as_stated": True, **extra}

    def _engine_figure(self) -> float:
        from tenforty.forms.depreciation.macrs import macrs_deduction
        return float(macrs_deduction(DepreciableAsset(
            description="Refrigerator",
            date_placed_in_service=datetime.date(2023, 3, 15),
            basis=10_000.0, recovery_class="5-year"), YEAR))

    def test_activity_override_lifts_the_refusal(self):
        """Ruling: the refusal is per asset but the override is per
        activity; a valid override keeps the activity in asset mode."""
        override = {"amount": 400.0,
                    "restates_engine_amount": self._engine_figure(),
                    "acknowledgment": True}
        for label in ("false", "absent"):
            with self.subTest(field=label):
                asset = self._tainted_prior_year_asset()
                if label == "absent":
                    del asset["no_bonus_or_section_179_history"]
                s = _load(_doc(rental_properties=[_rental(
                    depreciable_assets=[asset],
                    depreciation_override=override)]))
                self.assertIsNot(
                    s.rental_properties[0].depreciable_assets[0]
                    .no_bonus_or_section_179_history, True)

    def test_same_asset_without_the_override_refuses(self):
        with self.assertRaisesRegex(
                NotImplementedError,
                r"asset 'Refrigerator' on rental property #0 .* is 5-year "
                r"personal property without"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[self._tainted_prior_year_asset()])]))

    def test_unacknowledged_override_does_not_lift_it(self):
        with self.assertRaisesRegex(
                NotImplementedError, r"is 5-year personal property without"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[self._tainted_prior_year_asset()],
                depreciation_override={
                    "amount": 400.0,
                    "restates_engine_amount": self._engine_figure(),
                    "acknowledgment": False})]))


class HistoryFieldOnRealPropertyRefusalTests(unittest.TestCase):
    def test_real_property_carrying_the_field_refuses(self):
        for cls in ("27.5-year", "39-year"):
            for value in (True, False):
                with self.subTest(recovery_class=cls, value=value):
                    with self.assertRaisesRegex(
                            ValueError,
                            r"asset 'Rental building' on rental property #0 "
                            r"\('100 Example Street'\) is "
                            + cls.replace(".", r"\.") +
                            r" real property and must not carry "
                            r"`no_bonus_or_section_179_history`"):
                        _load(_doc(rental_properties=[_rental(
                            depreciable_assets=[_building(
                                recovery_class=cls,
                                no_bonus_or_section_179_history=value)])]))

    def test_same_asset_without_the_field_loads(self):
        for cls in ("27.5-year", "39-year"):
            with self.subTest(recovery_class=cls):
                s = _load(_doc(rental_properties=[_rental(
                    depreciable_assets=[_building(recovery_class=cls)])]))
                self.assertEqual(
                    s.rental_properties[0].depreciable_assets[0]
                    .recovery_class, cls)


class UnknownRecoveryClassRefusalTests(unittest.TestCase):
    def test_class_outside_the_supported_eight_refuses(self):
        for cls in ("25-year", "50-year", "5 year", "31.5-year"):
            with self.subTest(recovery_class=cls):
                with self.assertRaisesRegex(
                        NotImplementedError,
                        r"asset 'Rental building' on rental property #0 "
                        r"\('100 Example Street'\) has recovery_class "
                        + repr(cls).replace(".", r"\.")):
                    _load(_doc(rental_properties=[_rental(
                        depreciable_assets=[
                            _building(recovery_class=cls)])]))

    def test_each_supported_class_loads(self):
        personal = ("3-year", "5-year", "7-year", "10-year", "15-year",
                    "20-year")
        real = ("27.5-year", "39-year")
        for cls in personal:
            with self.subTest(recovery_class=cls):
                s = _load(_doc(rental_properties=[_rental(
                    depreciable_assets=[_appliance(recovery_class=cls)])]))
                self.assertEqual(
                    s.rental_properties[0].depreciable_assets[0]
                    .recovery_class, cls)
        for cls in real:
            with self.subTest(recovery_class=cls):
                s = _load(_doc(rental_properties=[_rental(
                    depreciable_assets=[_building(recovery_class=cls)])]))
                self.assertEqual(
                    s.rental_properties[0].depreciable_assets[0]
                    .recovery_class, cls)


class DisposedRefusalTests(unittest.TestCase):
    def test_disposed_asset_refuses_naming_partial_dispositions(self):
        with self.assertRaisesRegex(
                NotImplementedError,
                r"asset 'Rental building' on rental property #0 "
                r"\('100 Example Street'\) is marked `disposed`.*"
                r"partial dispositions.*follow-on"):
            _load(_doc(rental_properties=[_rental(depreciable_assets=[
                _old_building(disposed=datetime.date(YEAR, 8, 14))])]))

    def test_same_asset_undisposed_loads(self):
        s = _load(_doc(rental_properties=[
            _rental(depreciable_assets=[_old_building()])]))
        self.assertIsNone(
            s.rental_properties[0].depreciable_assets[0].disposed)


class OverrideOutsideAssetModeRefusalTests(unittest.TestCase):
    _OVERRIDE = {"amount": 7_000.0, "restates_engine_amount": 7_272.0,
                 "acknowledgment": True}

    def test_override_on_an_activity_with_no_assets_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"rental property #0 \('100 Example Street'\) carries a "
                r"`depreciation_override` but no `depreciable_assets`"):
            _load(_doc(rental_properties=[
                _rental(depreciation_override=self._OVERRIDE)]))

    def test_override_with_assets_loads(self):
        s = _load(_doc(rental_properties=[_rental(
            depreciable_assets=[_old_building()],
            depreciation_override=self._OVERRIDE)]))
        self.assertIsNotNone(s.rental_properties[0].depreciation_override)


class UnacknowledgedOverrideRefusalTests(unittest.TestCase):
    def test_override_without_acknowledgment_refuses(self):
        for label, block in (
                ("absent", {"amount": 7_000.0,
                            "restates_engine_amount": 7_272.0}),
                ("false", {"amount": 7_000.0,
                           "restates_engine_amount": 7_272.0,
                           "acknowledgment": False})):
            with self.subTest(acknowledgment=label):
                with self.assertRaisesRegex(
                        ValueError,
                        r"rental property #0 \('100 Example Street'\) "
                        r"carries a `depreciation_override` without "
                        r"`acknowledgment: true`"):
                    _load(_doc(rental_properties=[_rental(
                        depreciable_assets=[_old_building()],
                        depreciation_override=block)]))

    def test_acknowledged_override_loads(self):
        s = _load(_doc(rental_properties=[_rental(
            depreciable_assets=[_old_building()],
            depreciation_override={
                "amount": 7_000.0, "restates_engine_amount": 7_272.0,
                "acknowledgment": True})]))
        self.assertIs(
            s.rental_properties[0].depreciation_override.acknowledgment, True)


class UnprintedRentalRefusalTests(unittest.TestCase):
    def test_assets_on_a_rental_other_than_the_first_refuse(self):
        second = _rental(address="200 Example Street",
                         depreciable_assets=[_building()])
        with self.assertRaisesRegex(
                NotImplementedError,
                r"rental property #1 \('200 Example Street'\) carries "
                r"`depreciable_assets`.*Schedule E prints only the first "
                r"rental property.*lifts when Schedule E prints beyond "
                r"property A"):
            _load(_doc(rental_properties=[_rental(), second]))

    def test_same_assets_on_the_first_rental_load(self):
        first = _rental(depreciable_assets=[_building()])
        s = _load(_doc(rental_properties=[
            first, _rental(address="200 Example Street")]))
        self.assertEqual(len(s.rental_properties[0].depreciable_assets), 1)
        self.assertEqual(len(s.rental_properties[1].depreciable_assets), 0)


class NegativeAssetAmountRefusalTests(unittest.TestCase):
    def test_negative_basis_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Rental building' on rental property #0 "
                r"\('100 Example Street'\) has a negative `basis`"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[_building(basis=-1.0)])]))

    def test_negative_prior_depreciation_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Rental building' on rental property #0 "
                r"\('100 Example Street'\) has a negative "
                r"`prior_depreciation`"):
            _load(_doc(rental_properties=[_rental(depreciable_assets=[
                _old_building(prior_depreciation=-1.0)])]))

    def test_negative_override_amount_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"rental property #0 \('100 Example Street'\) has a "
                r"negative `depreciation_override.amount`"):
            _load(_doc(rental_properties=[_rental(
                depreciable_assets=[_old_building()],
                depreciation_override={
                    "amount": -1.0, "restates_engine_amount": 7_272.0,
                    "acknowledgment": True})]))

    def test_zero_amounts_load(self):
        s = _load(_doc(rental_properties=[_rental(depreciable_assets=[
            _old_building(prior_depreciation=0.0)])]))
        self.assertEqual(
            s.rental_properties[0].depreciable_assets[0].prior_depreciation,
            0.0)


if __name__ == "__main__":
    unittest.main()
