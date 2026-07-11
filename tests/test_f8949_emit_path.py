# tests/test_f8949_emit_path.py
"""The 8949 emit path (non-basis-reported lot) produces a filled f8949 PDF.
Regression pin: the blank template was absent from the repo for both years
while the orchestrator resolved it — any scenario on this path crashed."""
import tempfile
import unittest
from pathlib import Path

from tenforty.models import Form1099B, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import _battery_config, _w2
from tests.helpers import REPO_ROOT, needs_libreoffice


def _scenario_with_8949_lot(year: int) -> Scenario:
    return Scenario(
        config=_battery_config(year),
        w2s=[_w2(year, employer="Synthetic Employer A", wages=150_000.0,
                 federal_tax_withheld=28_000.0)],
        form1099_b=[Form1099B(
            broker="Synthetic Broker",
            description="Synthetic Legacy Fund",
            date_acquired="2020-02-10",
            date_sold=f"{year}-08-15",
            proceeds=30_000.0, cost_basis=21_000.0,
            short_term=False,
            basis_reported_to_irs=False,  # ← forces the 8949 path
        )],
    )


@needs_libreoffice
class F8949EmitPathTests(unittest.TestCase):
    def test_emits_f8949_for_both_years(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                scenario = _scenario_with_8949_lot(year)
                with tempfile.TemporaryDirectory() as tmp:
                    orch = ReturnOrchestrator(
                        spreadsheets_dir=REPO_ROOT / "spreadsheets",
                        work_dir=Path(tmp),
                    )
                    results, emitted = orch.run_full_return(scenario, Path(tmp))
                    self.assertIn("f8949", emitted)
                    self.assertTrue(emitted["f8949"].exists())
