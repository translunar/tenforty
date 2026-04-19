"""Round-trip test: K-1 scenario flows through orchestrator into f1040se.pdf."""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice, needs_pdf


@needs_libreoffice
@needs_pdf
class SchEPartIIRoundTripTests(unittest.TestCase):
    def test_scorp_k1_flows_to_sche_pdf(self):
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            ordinary_business_income=50_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results = orch.compute_federal(s)
            emitted = orch.emit_pdfs(s, results, Path(tmp))
            self.assertIn("sch_e", emitted)
            self.assertGreater(emitted["sch_e"].stat().st_size, 0)
