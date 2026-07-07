# tests/test_fetch_year_assets.py
"""URL-plan construction and download validation for year assets.

Network access is NOT tested here (downloads are a user-approved step);
these tests cover the deterministic parts: URL construction and the
fetched-file validation that guards against 404 HTML pages.
"""
import tempfile
import unittest
from pathlib import Path

from scripts.fetch_year_assets import build_download_plan, validate_pdf


class DownloadPlanTests(unittest.TestCase):
    def test_federal_plan_uses_irs_prior_year_scheme(self):
        plan = build_download_plan("federal", 2023)
        by_dest = {d.dest.name: d.url for d in plan}
        self.assertEqual(
            by_dest["f1040.pdf"],
            "https://www.irs.gov/pub/irs-prior/f1040--2023.pdf")
        self.assertEqual(
            by_dest["i1040tt.pdf"],
            "https://www.irs.gov/pub/irs-prior/i1040tt--2023.pdf")
        # Every federal destination lands under pdfs/federal/2023/.
        for d in plan:
            self.assertIn("pdfs/federal/2023", str(d.dest))

    def test_federal_plan_covers_all_templates_plus_tax_table(self):
        plan = build_download_plan("federal", 2023)
        names = {d.dest.name for d in plan}
        self.assertEqual(names, {
            "f1040.pdf", "f1040s1.pdf", "f1040sa.pdf", "f1040sb.pdf",
            "f1040sd.pdf", "f1040se.pdf", "f8949.pdf", "f4562.pdf",
            "f4868.pdf", "f8582.pdf", "f8959.pdf", "f8995.pdf",
            "f1120s.pdf", "f1120s_k1.pdf", "i1040tt.pdf",
        })

    def test_california_plan_uses_ftb_scheme(self):
        plan = build_download_plan("california", 2023)
        by_dest = {d.dest.name: d.url for d in plan}
        self.assertEqual(
            by_dest["f540.pdf"],
            "https://www.ftb.ca.gov/forms/2023/2023-540.pdf")
        self.assertIn("tax_table.pdf", by_dest)

    def test_unknown_jurisdiction_raises(self):
        with self.assertRaises(ValueError):
            build_download_plan("texas", 2023)


class ValidatePdfTests(unittest.TestCase):
    def test_rejects_html_masquerading_as_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "x.pdf"
            bad.write_bytes(b"<html>Not Found</html>" * 5_000)
            with self.assertRaises(ValueError):
                validate_pdf(bad)

    def test_rejects_tiny_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "x.pdf"
            small.write_bytes(b"%PDF-1.7 tiny")
            with self.assertRaises(ValueError):
                validate_pdf(small)

    def test_accepts_pdf_magic_over_50kb(self):
        with tempfile.TemporaryDirectory() as tmp:
            ok = Path(tmp) / "x.pdf"
            ok.write_bytes(b"%PDF-1.7" + b"\x00" * 60_000)
            validate_pdf(ok)  # no raise
