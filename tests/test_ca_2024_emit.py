"""Synthetic 2024 CA-resident emit test (SP3-T6 port).

Proves the whole 2024 CA path end-to-end: synthetic CA-resident scenario
with year=2024 → run_full_california_return → the 2024 CA packet
(f540 + sch_ca + sch_d_540) emits with non-trivial size.

Mirrors the proven 2025 happy-path test
tests/test_orchestrator_california.py::RunFullCaliforniaReturnTests.test_full_pipeline_renders_state_pdfs
with year overridden to 2024 via dataclasses.replace.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_v1_smoke_scenario, _write_ca_yaml

REPO_ROOT = Path(__file__).parent.parent


class CA2024EmitTests(unittest.TestCase):
    def test_2024_ca_packet_emits(self):
        base = _make_ca_v1_smoke_scenario()
        scenario = dataclasses.replace(
            base,
            config=dataclasses.replace(base.config, year=2024),
            ca540=None,
        )
        tmp_dir = Path(tempfile.mkdtemp())
        ca_yaml_path = _write_ca_yaml(
            {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0}}, tmp_dir=tmp_dir,
        )
        output_dir = Path(tempfile.mkdtemp())
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work",
        )
        ca_results, ca_pdfs = orch.run_full_california_return(
            scenario=scenario,
            ca_yaml_path=ca_yaml_path,
            output_dir=output_dir,
        )
        self.assertIn("f540_total_liability", ca_results)
        self.assertEqual(set(ca_pdfs.keys()), {"f540", "sch_ca", "sch_d_540"})
        for basename, path in ca_pdfs.items():
            self.assertTrue(path.exists(), f"PDF not written: {path}")
            self.assertGreater(path.stat().st_size, 1_000)
        # The emitted files must be the 2024 templates.
        self.assertTrue(str(ca_pdfs["f540"]).endswith("f540_2024.pdf"))


if __name__ == "__main__":
    unittest.main()
