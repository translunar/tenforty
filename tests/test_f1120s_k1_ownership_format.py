"""K-1 (1120-S) item G (ownership percentage) renders as a trimmed decimal:
whole percentages are unchanged ("100"), fractions are not dollar-rounded away
("33.333")."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f1120s_k1 import PdfF1120SK1
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.helpers import REPO_ROOT


def _read(pdf: Path, path: str) -> str:
    return str((PdfReader(str(pdf)).get_fields() or {})[path].get("/V") or "")


class OwnershipFormatFillTests(unittest.TestCase):
    def _fill(self, year: int, pct: float) -> str:
        mapping = PdfF1120SK1.get_mapping(year)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "k1.pdf"
            PdfFiller().fill(
                template_path=REPO_ROOT / f"pdfs/federal/{year}/f1120s_k1.pdf",
                output_path=out, field_mapping=mapping,
                values={"ownership_percentage": pct},
                field_formats=PdfF1120SK1.get_field_formats(year),
            )
            return _read(out, mapping["ownership_percentage"])

    def test_whole_percentage_unchanged(self):
        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual(self._fill(year, 100.0), "100")
                self.assertEqual(self._fill(year, 50), "50")

    def test_fractional_percentage_keeps_decimals(self):
        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual(self._fill(year, 33.333), "33.333")
                self.assertEqual(self._fill(year, 12.5), "12.5")


class OwnershipFormatEmitTests(unittest.TestCase):
    def _emit_value(self, year: int, pct: float) -> str:
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.shareholders[0].ownership_percentage = pct
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(tmp))
            out = Path(tmp) / "out"
            orch.run_full_federal_scorp_return(s, out)
            return _read(
                out / f"f1120s_k1_1_{year}.pdf",
                PdfF1120SK1.get_mapping(year)["ownership_percentage"])

    def test_emitted_packet_whole_and_fractional(self):
        for year in years.SCORP_FEDERAL_YEARS:
            if year not in (2023, 2024, 2025):
                continue
            with self.subTest(year=year):
                self.assertEqual(self._emit_value(year, 100.0), "100")
                self.assertEqual(self._emit_value(year, 33.333), "33.333")


if __name__ == "__main__":
    unittest.main()
