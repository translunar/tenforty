"""Messy-History Fixtures: the synthetic species a real residential-rental
ledger produces, driven end to end from YAML.

All values are invented. `prior_depreciation` figures that reconcile were
taken from the engine's own reconstruction (they are INPUTS that must
reconcile, not expected outputs); expected deductions are asked of
`macrs_deduction` on the loaded asset, except the 6,970 legacy regression pin
(January 27.5-year building on 200,000).
"""

import copy
import tempfile
import unittest
from datetime import date
from pathlib import Path

import yaml

from tenforty.forms.depreciation.macrs import macrs_deduction
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR

YEAR = 2025
BONUS_LINE = date(2017, 9, 27)


class _FixtureCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _raw(self, name: str) -> dict:
        return yaml.safe_load((FIXTURES_DIR / name).read_text())

    def _load_variant(self, raw: dict):
        path = self.tmp / "variant.yaml"
        path.write_text(yaml.safe_dump(raw))
        return load_scenario(path)

    def _compute(self, scenario) -> dict:
        return ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.tmp / "work").compute_federal(scenario)


class WrongPriorHistoryTests(_FixtureCase):
    """An appliance-class asset whose prior years ran a wrong class/method."""

    NAME = "macrs_prior_history_mismatch.yaml"

    def test_fixture_refuses_naming_form_3115(self):
        with self.assertRaisesRegex(
                ValueError,
                r"asset 'Refrigerator' on rental property #0 "
                r"\('100 Example Street'\) states `prior_depreciation` of "
                r"196 but the MACRS tables reconstruct [\d,]+.*Form 3115.*"
                r"section 481\(a\).*CPA territory"):
            load_scenario(FIXTURES_DIR / self.NAME)

    def test_acknowledgment_is_the_entry_path_and_forward_is_table_driven(self):
        raw = self._raw(self.NAME)
        asset = raw["rental_properties"][0]["depreciable_assets"][0]
        asset["acknowledges_prior_depreciation_as_stated"] = True
        scenario = self._load_variant(raw)
        loaded = scenario.rental_properties[0].depreciable_assets[0]
        self.assertEqual(loaded.prior_depreciation, 196.0)
        expected = macrs_deduction(loaded, YEAR)
        self.assertGreater(expected, 0)
        results = self._compute(scenario)
        self.assertEqual(
            results["depreciation_recon_rental_0_engine_amount"], expected)
        self.assertEqual(
            results["depreciation_recon_rental_0_used_amount"], expected)
        self.assertEqual(results["sche_line26"], 24_000 - 3_000 - expected)


class SupersededComponentTests(_FixtureCase):
    """A component superseded by a later whole-structure replacement is a
    partial disposition: the disposed refusal fires from a full load."""

    NAME = "macrs_superseded_component_disposed.yaml"

    def test_fixture_refuses_from_a_full_scenario_load(self):
        with self.assertRaisesRegex(
                NotImplementedError,
                r"asset 'Roof section' on rental property #0 "
                r"\('100 Example Street'\) is marked `disposed`.*"
                r"partial dispositions.*follow-on"):
            load_scenario(FIXTURES_DIR / self.NAME)

    def test_the_replacement_alone_loads_and_computes(self):
        raw = self._raw(self.NAME)
        assets = raw["rental_properties"][0]["depreciable_assets"]
        raw["rental_properties"][0]["depreciable_assets"] = [
            a for a in assets if "disposed" not in a]
        scenario = self._load_variant(raw)
        (replacement,) = scenario.rental_properties[0].depreciable_assets
        self.assertEqual(replacement.description, "Full roof replacement")
        results = self._compute(scenario)
        self.assertEqual(
            results["depreciation_recon_rental_0_used_amount"],
            macrs_deduction(replacement, YEAR))


class BonusLineTests(_FixtureCase):
    """Personal property on both sides of the 9/27/2017 line. The FIELD is
    the trigger; the date is not."""

    NAME = "macrs_bonus_line_both_sides.yaml"

    def test_fixture_straddles_the_line(self):
        raw = self._raw(self.NAME)
        placed = [a["date_placed_in_service"]
                  for a in raw["rental_properties"][0]["depreciable_assets"]]
        self.assertLess(placed[0], BONUS_LINE)
        self.assertGreater(placed[1], BONUS_LINE)

    def test_field_true_on_both_sides_computes(self):
        scenario = load_scenario(FIXTURES_DIR / self.NAME)
        assets = scenario.rental_properties[0].depreciable_assets
        expected = sum(macrs_deduction(a, YEAR) for a in assets)
        for a in assets:
            self.assertGreater(macrs_deduction(a, YEAR), 0)
        results = self._compute(scenario)
        self.assertEqual(
            results["depreciation_recon_rental_0_used_amount"], expected)

    def test_field_false_or_absent_refuses_on_either_side(self):
        for index, side in ((0, "before the line"), (1, "after the line")):
            for label in ("false", "absent"):
                with self.subTest(side=side, field=label):
                    raw = copy.deepcopy(self._raw(self.NAME))
                    asset = (
                        raw["rental_properties"][0]["depreciable_assets"][index])
                    if label == "false":
                        asset["no_bonus_or_section_179_history"] = False
                    else:
                        del asset["no_bonus_or_section_179_history"]
                    with self.assertRaisesRegex(
                            NotImplementedError,
                            rf"asset '{asset['description']}' on rental "
                            r"property #0 \('100 Example Street'\) is "
                            r"\d+-year personal property without "
                            r"`no_bonus_or_section_179_history: true`"):
                        self._load_variant(raw)


class MixedActivityTests(_FixtureCase):
    """One rental in asset mode, one business in stated mode: the resolver
    scopes per activity through the whole pipeline."""

    NAME = "macrs_mixed_activity.yaml"

    def test_each_activity_takes_its_own_source(self):
        scenario = load_scenario(FIXTURES_DIR / self.NAME)
        results = self._compute(scenario)
        # Rental: asset mode.
        self.assertEqual(
            results["depreciation_recon_rental_0_mode"], "assets")
        self.assertEqual(
            results["depreciation_recon_rental_0_used_amount"], 6_970)
        self.assertEqual(results["sche_line26"], 24_000 - 3_000 - 6_970)
        # Business: stated mode -- no recon group, the stated figure counts.
        self.assertEqual(
            [k for k in results if k.startswith("depreciation_recon_sch_c")],
            [])
        self.assertEqual(
            results["sch_1_line_3_business_income"], 50_000 - 5_000 - 1_200)

    def test_the_two_sources_do_not_leak_into_each_other(self):
        """Removing the rental's assets leaves the business figure alone,
        and removing the business's stated amount leaves the rental alone."""
        raw = self._raw(self.NAME)
        no_assets = copy.deepcopy(raw)
        del no_assets["rental_properties"][0]["depreciable_assets"]
        r = self._compute(self._load_variant(no_assets))
        self.assertEqual(r["sche_line26"], 24_000 - 3_000)
        self.assertEqual(
            r["sch_1_line_3_business_income"], 50_000 - 5_000 - 1_200)

        no_stated = copy.deepcopy(raw)
        biz = no_stated["schedule_c_businesses"][0]
        del biz["depreciation"]
        del biz["acknowledges_depreciation_stated_outside_macrs"]
        r = self._compute(self._load_variant(no_stated))
        self.assertEqual(r["sche_line26"], 24_000 - 3_000 - 6_970)
        self.assertEqual(r["sch_1_line_3_business_income"], 50_000 - 5_000)


class DualSourceTests(_FixtureCase):
    NAME = "macrs_dual_source.yaml"

    def test_fixture_refuses(self):
        with self.assertRaisesRegex(
                ValueError,
                r"rental property #0 \('100 Example Street'\) carries both "
                r"`depreciable_assets` and a stated `depreciation` amount.*"
                r"never added together"):
            load_scenario(FIXTURES_DIR / self.NAME)

    def test_either_source_alone_loads_from_the_same_fixture(self):
        raw = self._raw(self.NAME)
        assets_only = copy.deepcopy(raw)
        del assets_only["rental_properties"][0]["depreciation"]
        del assets_only["rental_properties"][0][
            "acknowledges_depreciation_stated_outside_macrs"]
        self.assertEqual(
            self._compute(self._load_variant(assets_only))["sche_line26"],
            24_000 - 3_000 - 6_970)
        stated_only = copy.deepcopy(raw)
        del stated_only["rental_properties"][0]["depreciable_assets"]
        self.assertEqual(
            self._compute(self._load_variant(stated_only))["sche_line26"],
            24_000 - 3_000 - 5_000)


if __name__ == "__main__":
    unittest.main()
