import subprocess
import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = unittest.skipUnless(
    libreoffice_available(), "LibreOffice not installed",
)
needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


@needs_libreoffice
class TestE2EItemized(unittest.TestCase):
    """Full pipeline: high earner with mortgage, should itemize."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "itemized_deductions.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.work_dir,
        )

    def test_engine_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)

        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

    def test_uses_itemized_deduction(self):
        """Deduction should exceed the 2025 standard deduction of $15,750."""
        results = self.orchestrator.compute_federal(self.scenario)

        deduction = float(results.get("total_deductions", 0))
        self.assertGreater(
            deduction, 15750,
            f"Expected itemized deduction > $15,750 standard, got ${deduction:,.0f}",
        )

    @needs_pdf
    def test_pdf_output(self):
        results = self.orchestrator.compute_federal(self.scenario)

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_itemized.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---
