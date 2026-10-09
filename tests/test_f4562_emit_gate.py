"""When Form 4562 is emitted, and when the merged form cannot be.

Instructions for Form 4562 (2025), page 2, "Who Must File": "complete and
file Form 4562 if you are claiming any of the following. - Depreciation for
property placed in service during the 2025 tax year. ..." The other listed
triggers (a section 179 deduction, listed property, amortization beginning
this year, a corporate return) are all out of scope and refuse or have no
input. So: no placement this year anywhere on the return, no Form 4562 --
the depreciation still prints on Schedule E line 18 / Schedule C line 13.

On this branch the form is still ONE merged form per return listing every
asset with the engine's figures. That cannot print consistently when any
activity's deduction is an override amount, so a placement year with an
override anywhere refuses.

Field paths are literals (see the provenance note on each). 6,970 is a legacy
regression pin (January 27.5-year building on 200,000).
"""

import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.attestations import enforce_scoped_refusals
from tenforty.forms import f4562, sch_e
from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.resolver import (
    reconstruct_prior_depreciation,
)
from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty, ScheduleCBusiness,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

YEAR = 2025
SCH_E_LINE_18_PROPERTY_A = (
    "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]")
# PROVENANCE, stated plainly: unlike the Schedule E path above (probed on
# the template), this literal was copied from mappings/pdf_4562.py's 2025
# entry -- the Part IV summary sits on page 2 in the 2025 revision and my
# label probe did not locate it. It is a literal here so a mapping change
# breaks this test, but it is NOT independent evidence that the field is
# line 22; tests/test_4562_round_trip.py and the 4562 mapping tests own that.
F4562_LINE_22 = "topmostSubform[0].Page2[0].f2_2[0]"


def _read(pdf_path, field_path) -> str:
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "").replace(",", "").strip()


def _old_building() -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Rental building", date_placed_in_service=date(2019, 6, 1),
        basis=200_000.0, recovery_class="27.5-year")
    asset.prior_depreciation = float(
        reconstruct_prior_depreciation(asset, YEAR))
    return asset


def _new_building() -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=200_000.0, recovery_class="27.5-year")


def _new_equipment() -> DepreciableAsset:
    return DepreciableAsset(
        description="Equipment", date_placed_in_service=date(YEAR, 2, 1),
        basis=10_000.0, recovery_class="5-year",
        no_bonus_or_section_179_history=True)


def _rental(*assets, override_amount=None) -> RentalProperty:
    rental = RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=list(assets))
    if override_amount is not None:
        engine = sum(macrs_deduction(a, YEAR) for a in assets)
        rental.depreciation_override = DepreciationOverride(
            amount=override_amount, restates_engine_amount=float(engine),
            acknowledgment=True)
    return rental


def _scenario(rentals=(), businesses=()):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=YEAR, first_name="Test", last_name="Filer",
        ssn="000-00-0000", acknowledges_no_source_documents=True)
    return dataclasses.replace(
        base, config=config, rental_properties=list(rentals),
        schedule_c_businesses=list(businesses))


class _EmitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.tmp / "work")
        self._n = 0

    def _emit(self, scenario) -> dict:
        self._n += 1
        results = self.orchestrator.compute_federal(scenario)
        return self.orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out{self._n}")


class EmitOnlyInAPlacementYearTests(_EmitCase):
    def test_predicate_false_with_only_prior_year_assets(self):
        s = _scenario(rentals=[_rental(_old_building())])
        self.assertFalse(self.orchestrator._should_emit_4562(s, {}))

    def test_predicate_true_with_a_placement_this_year(self):
        s = _scenario(rentals=[_rental(_old_building(), _new_building())])
        self.assertTrue(self.orchestrator._should_emit_4562(s, {}))

    def test_predicate_sees_a_placement_on_any_activity(self):
        s = _scenario(
            rentals=[_rental(_old_building())],
            businesses=[ScheduleCBusiness(
                description="Consulting", gross_receipts=50_000.0,
                depreciable_assets=(_new_equipment(),))])
        self.assertTrue(self.orchestrator._should_emit_4562(s, {}))

    def test_ongoing_year_emits_no_form_and_schedule_e_still_carries_it(self):
        building = _old_building()
        expected = macrs_deduction(building, YEAR)
        self.assertGreater(expected, 0)
        emitted = self._emit(_scenario(rentals=[_rental(building)]))
        self.assertNotIn("f4562", emitted)
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), str(expected))

    def test_placement_year_emits_and_line_22_equals_schedule_e_line_18(self):
        """The twin: the form IS emitted in a placement year, and its line
        22 is the figure Schedule E line 18 prints."""
        emitted = self._emit(_scenario(rentals=[_rental(_new_building())]))
        self.assertIn("f4562", emitted)
        line_18 = _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A)
        self.assertEqual(line_18, "6970")
        self.assertEqual(_read(emitted["f4562"], F4562_LINE_22), line_18)


class OverriddenActivityTests(_EmitCase):
    """The reviewer's reproduction: a mid-stream overridden rental printed
    the override on Schedule E and the engine's figure on Form 4562."""

    def test_overridden_mid_stream_rental_emits_no_4562(self):
        building = _old_building()
        self.assertNotEqual(macrs_deduction(building, YEAR), 7_000)
        emitted = self._emit(_scenario(
            rentals=[_rental(building, override_amount=7_000.0)]))
        self.assertEqual(
            _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), "7000")
        self.assertNotIn("f4562", emitted)

    def test_no_printed_4562_can_disagree_with_schedule_e(self):
        """Stated directly as the cross-form identity: for an overridden
        return either no Form 4562 exists, or its line 22 equals the
        depreciation the activity prints."""
        scenario = _scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)])
        emitted = self._emit(scenario)
        line_18 = sch_e.compute(scenario, upstream={})[
            "sch_e_property_a_depreciation"]
        if "f4562" in emitted:
            self.assertEqual(
                _read(emitted["f4562"], F4562_LINE_22), str(line_18))
        # The engine-only total the merged form WOULD have printed differs,
        # which is why it must not be emitted here.
        self.assertNotEqual(
            f4562.compute(scenario, upstream={})[
                "f4562_line_22_total_depreciation"], line_18)


class MergedFormWithOverrideRefusalTests(unittest.TestCase):
    REFUSAL = (r"Form 4562 is required this year.*one merged form.*"
               r"per-activity")

    def _business(self, *assets):
        return ScheduleCBusiness(
            description="Consulting", gross_receipts=50_000.0,
            depreciable_assets=tuple(assets))

    def test_placement_on_one_activity_and_override_on_another_refuses(self):
        s = _scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)],
            businesses=[self._business(_new_equipment())])
        with self.assertRaisesRegex(NotImplementedError, self.REFUSAL) as cm:
            enforce_scoped_refusals(s, "load")
        self.assertIn("rental property #0 ('100 Example Street')",
                      str(cm.exception))

    def test_override_with_no_placement_anywhere_is_silent(self):
        enforce_scoped_refusals(_scenario(
            rentals=[_rental(_old_building(), override_amount=7_000.0)],
            businesses=[self._business()]), "load")

    def test_placement_with_no_override_anywhere_is_silent(self):
        enforce_scoped_refusals(_scenario(
            rentals=[_rental(_old_building())],
            businesses=[self._business(_new_equipment())]), "load")

    def test_resolving_the_overridden_activity_alone_does_not_refuse(self):
        """Whole-return question: not asked of a single activity."""
        from tenforty.forms.depreciation.resolver import resolve
        rental = _rental(_old_building(), override_amount=7_000.0)
        self.assertEqual(resolve(rental, YEAR).amount, 7_000.0)


if __name__ == "__main__":
    unittest.main()
