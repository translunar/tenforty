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


    def test_snapshot_records_user_and_auto_provenance(self):
        """The resolved snapshot records each materialized adjustment's origin:
        a USER (id-keyed) divergence lands with source=USER and catalog_id set,
        and a CATALOG_AUTO divergence (here the RRB Tier 1/2 auto row) lands with
        source=CATALOG_AUTO and catalog_id set."""
        # Overwrite the CA YAML with a user id-keyed divergence + an RRB amount
        # (the RRB ca540_field auto row fires on the positive amount).
        ca_yaml = self.tmp / "main.ca.yaml"
        ca_yaml.write_text(
            "ca540:\n"
            "  estimated_payments: 0.0\n"
            "  use_tax: 0.0\n"
            "  rrb_tier_1_2_amount: 5000.0\n"
            "  divergences:\n"
            "    - id: moving-expense-suspended-federally-except-active-duty\n"
            "      amount: 800.0\n"
            "      note: 2025 PCS move\n"
        )
        scenario = load_scenario(self.federal)
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )
        orchestrator.run_full_california_return(
            scenario=scenario,
            ca_yaml_path=ca_yaml,
            output_dir=self.output_dir,
            federal_yaml_path=self.federal,
        )
        data = yaml.safe_load(
            (self.output_dir / "main.ca-resolved.yaml").read_text())
        divs = data["ca540"]["divergences"]

        user_rows = [d for d in divs if d.get("source") == "USER"]
        self.assertEqual(len(user_rows), 1)
        self.assertEqual(
            user_rows[0]["catalog_id"],
            "moving-expense-suspended-federally-except-active-duty")
        self.assertEqual(user_rows[0]["note"], "2025 PCS move")
        self.assertEqual(user_rows[0]["amount"], 800.0)

        auto_rows = [d for d in divs if d.get("source") == "CATALOG_AUTO"]
        self.assertTrue(auto_rows, "expected a catalog_auto divergence in snapshot")
        rrb = [d for d in auto_rows
               if d["catalog_id"] == "railroad-retirement-tier-1-2-ca-excludes-rtc-17087"]
        self.assertEqual(len(rrb), 1)
        self.assertEqual(rrb[0]["amount"], 5000.0)

    def test_sch_d_540_worksheet_entry_affects_net(self):
        """An e2e scenario with a Sch D 540 worksheet subtraction
        produces a divergent net capital gain in ca_results."""
        shutil.copy(
            FIXTURES / "single_tab_sch_d_540.fods", self.tmp / "main.ca.fods"
        )
        scenario = load_scenario(self.federal)
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )
        ca_results, _ = orchestrator.run_full_california_return(
            scenario=scenario,
            ca_yaml_path=self.tmp / "main.ca.yaml",
            output_dir=self.output_dir,
            federal_yaml_path=self.federal,
        )
        # The fixture's federal Sch D net is 0 (no 1099-B in e2e_main),
        # so a 750 subtraction yields net = -750.
        self.assertEqual(ca_results["sch_d_540_net_capital_gain"], -750)
        self.assertEqual(ca_results["sch_d_540_total_subtractions"], 750)
        self.assertEqual(ca_results["sch_d_540_total_additions"], 0)


if __name__ == "__main__":
    unittest.main()
