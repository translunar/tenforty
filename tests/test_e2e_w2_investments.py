import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.conftest import (
    F1040_PDF,
    FIXTURES_DIR,
    SPREADSHEETS_DIR,
    needs_libreoffice,
    needs_pdf,
)
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)


@needs_libreoffice
class TestE2EW2Investments(unittest.TestCase):
    """Full pipeline: W-2 + interest + dividends, standard deduction."""

    def setUp(self):
        if not hasattr(self.__class__, '_results'):
            self.__class__._work_dir = Path(tempfile.mkdtemp())
            self.__class__._scenario = load_scenario(FIXTURES_DIR / "w2_with_investments.yaml")
            orchestrator = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR,
                work_dir=self.__class__._work_dir,
            )
            self.__class__._results = orchestrator.compute_federal(self.__class__._scenario)
        self.work_dir = self.__class__._work_dir
        self.scenario = self.__class__._scenario
        self.results = self.__class__._results

    def test_engine_invariants(self):
        assert_agi_consistent(self, self.results, self.scenario)
        assert_taxable_income_consistent(self, self.results)
        assert_tax_is_non_negative(self, self.results)
        assert_refund_or_owed_consistent(self, self.results)
        assert_withholding_matches_input(self, self.results, self.scenario)

        # Investment income should be reflected in AGI
        self.assertGreater(
            float(self.results["agi"]), 120000,
            "AGI should exceed wages alone due to investment income",
        )

    @needs_pdf
    def test_pdf_output(self):

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(self.results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_investments.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---
