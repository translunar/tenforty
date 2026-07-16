"""PDF field mapping for Form 8995 — scalar fields only in v1."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
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

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022 (which itself
        # carries the line-6 Line6_ReadOrder-unwrapped path); 2021 inherits it.
        self.assertIs(PdfF8995.get_mapping(2021), PdfF8995.get_mapping(2022))


@unittest.skipUnless(
    (REPO_ROOT / "pdfs/federal/2021/f8995.pdf").exists(),
    "2021 Form 8995 template not present",
)
class PdfF89952021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Form 8995 template with distinctive values and read
    the cells back directly with pypdf — no soffice."""

    def test_distinctive_values_round_trip(self):
        scalars = PdfF8995.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct 8995 Filer",
            "taxpayer_ssn": "444-00-2021",
            "f8995_line_1_qbi": 51_000,
            "f8995_line_6_total_before_limit": 52_000,
            "f8995_line_15_qbi_deduction": 13_000,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f8995_2021.pdf"
            PdfFiller().fill(
                template_path=REPO_ROOT / "pdfs/federal/2021/f8995.pdf",
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))


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
