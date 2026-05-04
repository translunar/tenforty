import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario

REPO_ROOT = Path(__file__).parent.parent
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "sch_ca_fods"


class ResolvedSnapshotE2ETests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        # Copy the three fixture files into a working dir so basename
        # discovery resolves correctly.
        self.federal = self.tmp / "main.yaml"
        shutil.copy(FIXTURES / "e2e_main.yaml", self.federal)
        shutil.copy(FIXTURES / "e2e_main.ca.yaml", self.tmp / "main.ca.yaml")
        shutil.copy(FIXTURES / "e2e_main.ca.fods", self.tmp / "main.ca.fods")
        self.output_dir = self.tmp / "out"
        self.output_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_resolved_snapshot_emitted_with_merged_divergences(self):
        scenario = load_scenario(self.federal)
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )
        ca_yaml_path = self.tmp / "main.ca.yaml"
        orchestrator.run_full_california_return(
            scenario=scenario,
            ca_yaml_path=ca_yaml_path,
            output_dir=self.output_dir,
            federal_yaml_path=self.federal,
        )
        snapshot = self.output_dir / "main.ca-resolved.yaml"
        self.assertTrue(snapshot.exists(), f"expected snapshot at {snapshot}")
        data = yaml.safe_load(snapshot.read_text())
        self.assertIn("ca540", data)
        self.assertIn("divergences", data["ca540"])
        # The fods fixture provides exactly one Part I §A 2 subtraction
        # of $123. Confirm it's flattened into the snapshot.
        sub_lines = [
            d for d in data["ca540"]["divergences"]
            if d.get("source") == "WORKSHEET"
            and d.get("sch_ca_line") == "Part I §A 2"
            and d.get("direction") == "SUBTRACTION"
        ]
        self.assertEqual(len(sub_lines), 1)
        self.assertEqual(sub_lines[0]["amount"], 123.0)


if __name__ == "__main__":
    unittest.main()
