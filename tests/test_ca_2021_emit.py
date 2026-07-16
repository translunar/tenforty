"""Synthetic 2021 CA-resident emit test.

Proves the whole 2021 CA path end-to-end: synthetic CA-resident scenario
with year=2021 → run_full_california_return → the 2021 CA packet
(f540 + sch_ca + sch_d_540) emits with non-trivial size onto the 2021
templates.

Ports tests/test_ca_2023_emit.py with year overridden to 2021 via
dataclasses.replace — the final Step-7 check that 2021's promotion to the
fully-supported CA tier (CALIFORNIA_YEARS) drives a real emit, not just the
per-form mapping unit tests.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.models import W2
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_v1_smoke_scenario, _write_ca_yaml

REPO_ROOT = Path(__file__).parent.parent


class CA2021EmitTests(unittest.TestCase):
    def test_2021_ca_packet_emits(self):
        base = _make_ca_v1_smoke_scenario()
        scenario = dataclasses.replace(
            base,
            config=dataclasses.replace(base.config, year=2021),
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
        # The emitted files must be the 2021 templates.
        self.assertTrue(str(ca_pdfs["f540"]).endswith("f540_2021.pdf"))


class CAWithholdingOrchestratorEmitTests(unittest.TestCase):
    """Orchestrator e2e: a CA-attributed W-2 with box-17 withholding flows
    through run_full_california_return into f540_line71_ca_withholding and
    reduces f540_total_liability by the same amount.

    Regression pin for the line-71 wiring (finding, 2026-07-16): forms/f540
    had no withholding term in the balance at all. This is the native
    (no soffice) orchestrator-level check that scenario.w2s (not
    scenario.config) is the CA-withholding source and that the sum is
    plumbed all the way from the W-2 to the emitted results dict.
    """

    _W2_COMMON = dict(
        employer="Acme Corp",
        wages=50_000.0,
        federal_tax_withheld=5_000.0,
        ss_wages=50_000.0,
        ss_tax_withheld=3_100.0,
        medicare_wages=50_000.0,
        medicare_tax_withheld=725.0,
        state_wages=50_000.0,
    )

    def _run_with_w2(self, w2: W2) -> dict:
        base = _make_ca_v1_smoke_scenario()
        # ca540=None: run_full_california_return sources CA data from the
        # separate ca_yaml_path below; Scenario.ca540 being populated too
        # would trip the mutually-exclusive-loading-mode guard.
        scenario = dataclasses.replace(base, w2s=[w2], ca540=None)
        tmp_dir = Path(tempfile.mkdtemp())
        ca_yaml_path = _write_ca_yaml(
            {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0}}, tmp_dir=tmp_dir,
        )
        output_dir = Path(tempfile.mkdtemp())
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=output_dir / "work",
        )
        ca_results, _ = orch.run_full_california_return(
            scenario=scenario,
            ca_yaml_path=ca_yaml_path,
            output_dir=output_dir,
        )
        return ca_results

    def test_ca_w2_withholding_flows_into_line71_and_reduces_liability(self):
        baseline = self._run_with_w2(
            W2(**self._W2_COMMON, state_tax_withheld=0.0, state=None)
        )
        with_wh = self._run_with_w2(
            W2(**self._W2_COMMON, state_tax_withheld=4_000.0, state="CA")
        )
        self.assertEqual(baseline["f540_line71_ca_withholding"], 0)
        self.assertEqual(with_wh["f540_line71_ca_withholding"], 4_000)
        self.assertEqual(
            with_wh["f540_total_liability"],
            baseline["f540_total_liability"] - 4_000,
        )


if __name__ == "__main__":
    unittest.main()
