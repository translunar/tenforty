# tests/test_ca_pdf_templates_present.py
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PDFS_DIR = REPO_ROOT / "pdfs" / "california"

EXPECTED_TEMPLATES = {
    year: ["f540.pdf", "sch_ca.pdf", "sch_d_540.pdf"]
    for year in (2021, 2022, 2023, 2024, 2025)
}


class CaliforniaPdfTemplatesTests(unittest.TestCase):
    def test_per_year_templates_present(self):
        for year, files in EXPECTED_TEMPLATES.items():
            year_dir = PDFS_DIR / str(year)
            for filename in files:
                path = year_dir / filename
                with self.subTest(year=year, file=filename):
                    self.assertTrue(
                        path.exists(),
                        f"Expected CA template {path} present, missing.",
                    )
                    self.assertGreater(
                        path.stat().st_size, 50_000,
                        f"{path} is suspiciously small (likely 404 HTML or empty).",
                    )
