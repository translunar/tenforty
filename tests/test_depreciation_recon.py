"""The depreciation recon surface (ruling 2).

Per-activity result keys land in the federal results dict -- and therefore
in the results snapshot file, not only on stdout -- for every asset-mode
activity, and the CLI prints a recon section whenever any activity is in
asset mode. An overridden activity carries BOTH figures (engine-computed and
used) on every emit.

The 6,970 figure is a legacy regression pin (January 27.5-year building on a
200,000 basis), not a hand oracle.
"""

import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tenforty.__main__ import print_results
from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.forms.depreciation.resolver import (
    reconstruct_prior_depreciation,
)
from tenforty.models import (
    DepreciableAsset, DepreciationOverride, RentalProperty,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.summary import write_results_snapshot
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

YEAR = 2025
PREFIX = "depreciation_recon_"


def _rental(**extra) -> RentalProperty:
    return RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0, **extra)


def _new_building() -> DepreciableAsset:
    return DepreciableAsset(
        description="Rental building", date_placed_in_service=date(YEAR, 1, 15),
        basis=200_000.0, recovery_class="27.5-year")


def _old_building() -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Rental building", date_placed_in_service=date(2019, 6, 1),
        basis=200_000.0, recovery_class="27.5-year")
    asset.prior_depreciation = float(
        reconstruct_prior_depreciation(asset, YEAR))
    return asset


def _scenario(*rentals):
    s = make_simple_scenario()
    s.config.year = YEAR
    s.rental_properties = list(rentals)
    return s


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _results(self, scenario) -> dict:
        return ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.tmp).compute_federal(scenario)

    def _snapshot_results(self, results) -> dict:
        path = write_results_snapshot(
            results, self.tmp / "results.json", year=YEAR, label="test")
        return json.loads(path.read_text())["results"]

    def _printed(self, results) -> str:
        stream = io.StringIO()
        print_results(results, stream)
        return stream.getvalue()


class AssetModeReconTests(_Case):
    def test_keys_present_in_results_and_in_the_written_snapshot(self):
        results = self._results(_scenario(
            _rental(depreciable_assets=[_new_building()])))
        expected = {
            "depreciation_recon_rental_0_activity":
                "rental property #0 ('100 Example Street')",
            "depreciation_recon_rental_0_mode": "assets",
            "depreciation_recon_rental_0_engine_amount": 6_970,
            "depreciation_recon_rental_0_used_amount": 6_970,
        }
        self.assertEqual(
            {k: v for k, v in results.items() if k.startswith(PREFIX)},
            expected)
        on_disk = self._snapshot_results(results)
        self.assertEqual(
            {k: v for k, v in on_disk.items() if k.startswith(PREFIX)},
            expected)

    def test_cli_prints_a_recon_section(self):
        out = self._printed(self._results(_scenario(
            _rental(depreciable_assets=[_new_building()]))))
        self.assertIn("=== Depreciation Reconciliation ===", out)
        self.assertIn("rental property #0 ('100 Example Street')", out)
        self.assertRegex(out, r"engine computed\s+\$\s*6,970")
        self.assertRegex(out, r"used on return\s+\$\s*6,970")


class OverriddenReconTests(_Case):
    def _overridden(self):
        building = _old_building()
        self.engine = macrs_deduction(building, YEAR)
        self.assertNotEqual(self.engine, 6_500)
        return _scenario(_rental(
            depreciable_assets=[building],
            depreciation_override=DepreciationOverride(
                amount=6_500.0, restates_engine_amount=float(self.engine),
                acknowledgment=True)))

    def test_both_figures_in_the_keys_and_the_snapshot(self):
        results = self._results(self._overridden())
        on_disk = self._snapshot_results(results)
        for source in (results, on_disk):
            self.assertEqual(
                source["depreciation_recon_rental_0_mode"],
                "assets-overridden")
            self.assertEqual(
                source["depreciation_recon_rental_0_engine_amount"],
                self.engine)
            self.assertEqual(
                source["depreciation_recon_rental_0_used_amount"], 6_500)

    def test_both_figures_in_the_cli_section_every_emit(self):
        scenario = self._overridden()
        for attempt in (1, 2):
            with self.subTest(emit=attempt):
                out = self._printed(self._results(scenario))
                self.assertRegex(
                    out, rf"engine computed\s+\$\s*{self.engine:,}")
                self.assertRegex(out, r"used on return\s+\$\s*6,500")
                self.assertIn("OVERRIDE", out)

    def test_unoverridden_activity_is_not_marked_override(self):
        out = self._printed(self._results(_scenario(
            _rental(depreciable_assets=[_new_building()]))))
        self.assertNotIn("OVERRIDE", out)


class LiftedBonusHistoryNoteTests(_Case):
    """When an activity override lifts the bonus / section 179 history
    refusal, the recon carries a note: the engine column there is a
    staleness pin, not a claim of correctness."""

    NOTE_KEY = "depreciation_recon_rental_0_note"

    def _overridden(self, *, history):
        asset = DepreciableAsset(
            description="Refrigerator",
            date_placed_in_service=date(2023, 3, 15), basis=10_000.0,
            recovery_class="5-year", no_bonus_or_section_179_history=history)
        asset.prior_depreciation = float(
            reconstruct_prior_depreciation(asset, YEAR))
        return _scenario(_rental(
            depreciable_assets=[asset],
            depreciation_override=DepreciationOverride(
                amount=400.0,
                restates_engine_amount=float(macrs_deduction(asset, YEAR)),
                acknowledgment=True)))

    def test_note_present_when_the_refusal_was_lifted(self):
        results = self._results(self._overridden(history=False))
        self.assertRegex(
            results[self.NOTE_KEY],
            r"'Refrigerator'.*unmodeled bonus / section 179 history.*"
            r"staleness pin, not a claim of correctness")
        self.assertIn(self.NOTE_KEY, self._snapshot_results(results))
        out = self._printed(results)
        self.assertIn("staleness pin, not a claim of correctness", out)
        self.assertRegex(out, r"used on return\s+\$\s*400")

    def test_note_absent_for_a_clean_history_activity(self):
        results = self._results(self._overridden(history=True))
        self.assertEqual(
            results["depreciation_recon_rental_0_mode"], "assets-overridden")
        self.assertNotIn(self.NOTE_KEY, results)
        self.assertNotIn("staleness pin", self._printed(results))


class NoAssetModeTwinTests(_Case):
    def test_stated_mode_only_carries_no_keys_and_prints_no_section(self):
        results = self._results(_scenario(_rental(
            depreciation=5_000.0,
            acknowledges_depreciation_stated_outside_macrs=True)))
        self.assertEqual([k for k in results if k.startswith(PREFIX)], [])
        self.assertNotIn("Depreciation Reconciliation", self._printed(results))

    def test_no_rental_at_all(self):
        results = self._results(_scenario())
        self.assertEqual([k for k in results if k.startswith(PREFIX)], [])
        self.assertNotIn("Depreciation Reconciliation", self._printed(results))


if __name__ == "__main__":
    unittest.main()
