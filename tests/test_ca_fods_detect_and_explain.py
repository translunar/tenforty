"""Detect-and-explain guard for the retired `.ca.fods` worksheet (spec §3).

Part RETIRE removed the FODS worksheet round-trip. For one release, a
leftover `<basename>.ca.fods` next to the federal YAML must NOT be silently
ignored (that would drop the user's divergence amounts) — it raises a loud,
educational error that names the `.ca.yaml` `divergences:` / `reviewed:`
replacement and the redesign spec. These tests pin that behavior.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_v1_smoke_scenario, _write_ca_yaml

REPO_ROOT = Path(__file__).parent.parent


class RejectLegacyFodsGuardTests(unittest.TestCase):
    """Unit-level: the guard method itself."""

    def setUp(self):
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()),
        )
        self.tmp = Path(tempfile.mkdtemp())
        self.federal_yaml = self.tmp / "alice_2025.yaml"

    def test_leftover_ca_fods_raises_detect_and_explain(self):
        legacy = self.federal_yaml.with_suffix(".ca.fods")
        legacy.write_text("<legacy worksheet>")
        with self.assertRaises(ValueError) as cm:
            self.orch._reject_legacy_fods(self.federal_yaml)
        msg = str(cm.exception)
        # Names the offending file...
        self.assertIn(legacy.name, msg)
        # ...says it is RETIRED...
        self.assertIn("RETIRED", msg)
        # ...and points at the .ca.yaml replacement format (divergences/reviewed).
        self.assertIn(".ca.yaml", msg)
        self.assertIn("divergences", msg)
        self.assertIn("reviewed", msg)
        # ...citing the redesign spec.
        self.assertIn("ca-divergence-catalog-redesign", msg)

    def test_no_legacy_fods_is_a_noop(self):
        # No `<basename>.ca.fods` sibling present → guard returns without raising.
        self.assertIsNone(self.orch._reject_legacy_fods(self.federal_yaml))


class RunFullCaliforniaReturnRejectsFodsTests(unittest.TestCase):
    """Integration: the `ca` entry point refuses when a `.ca.fods` is present."""

    def test_run_full_california_return_raises_on_leftover_fods(self):
        tmp = Path(tempfile.mkdtemp())
        federal_yaml = tmp / "alice_2025.yaml"
        federal_yaml.write_text("placeholder")  # never read: guard fires first
        legacy = federal_yaml.with_suffix(".ca.fods")
        legacy.write_text("<legacy worksheet>")

        # ca540 sourced from the YAML (scenario.ca540=None so the loader uses
        # the file, not the in-memory block).
        scenario = dataclasses.replace(_make_ca_v1_smoke_scenario(), ca540=None)
        ca_yaml = _write_ca_yaml(
            {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0}}, tmp_dir=tmp)
        output_dir = tmp / "out"
        output_dir.mkdir()

        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work",
        )
        with self.assertRaisesRegex(ValueError, "RETIRED"):
            orch.run_full_california_return(
                scenario=scenario,
                ca_yaml_path=ca_yaml,
                output_dir=output_dir,
                federal_yaml_path=federal_yaml,
            )


if __name__ == "__main__":
    unittest.main()
