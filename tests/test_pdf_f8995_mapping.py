"""PDF field mapping for Form 8995 — scalar fields only in v1."""

import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.models import ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice, needs_pdf


class PdfF8995MappingTests(unittest.TestCase):
    def test_has_2025_mapping(self):
        mapping = PdfF8995.get_mapping(2025)
        self.assertIn("scalars", mapping)
        for key in (
            "f8995_line_1_qbi",
            "f8995_line_3_component",
            "f8995_line_15_qbi_deduction",
            "taxpayer_name",
            "taxpayer_ssn",
        ):
            self.assertIn(key, mapping["scalars"])

    def test_raises_for_unknown_year(self):
        with self.assertRaises(ValueError):
            PdfF8995.get_mapping(1999)


@needs_libreoffice
class PdfF8995RoundTripTests(unittest.TestCase):
    @unittest.skipUnless(
        (REPO_ROOT / "pdfs/federal/2025/f8995.pdf").exists(),
        "f8995 template not present",
    )
    def test_emit_produces_nonempty_pdf(self):
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=50_000.0, qbi_amount=50_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results = orch.compute_federal(s)
            emitted = orch.emit_pdfs(s, results, Path(tmp))
            self.assertIn("f8995", emitted)
            self.assertGreater(emitted["f8995"].stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
