import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.helpers import (
    F1040_PDF,
    FIXTURES_DIR,
    SPREADSHEETS_DIR,
    needs_libreoffice,
    needs_pdf,
)
from tests.invariants import (
    assert_agi_consistent,
    assert_deduction_choice_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)


@needs_libreoffice
class TestE2ESimpleW2(unittest.TestCase):
    """Full pipeline: simple W-2 single filer with standard deduction."""

    def setUp(self):
        if not hasattr(self.__class__, '_results'):
            self.__class__._work_dir = Path(tempfile.mkdtemp())
            self.__class__._scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
            orchestrator = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR,
                work_dir=self.__class__._work_dir,
            )
            self.__class__._results = orchestrator.compute_federal(self.__class__._scenario)
        self.work_dir = self.__class__._work_dir
        self.scenario = self.__class__._scenario
        self.results = self.__class__._results

    def test_engine_invariants(self):
        """Run engine and verify structural invariants."""
        assert_agi_consistent(self, self.results, self.scenario)
        assert_taxable_income_consistent(self, self.results)
        assert_tax_is_non_negative(self, self.results)
        assert_refund_or_owed_consistent(self, self.results)
        assert_withholding_matches_input(self, self.results, self.scenario)

    @needs_pdf
    def test_pdf_output(self):
        """Run full pipeline through PDF filling."""

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(self.results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_simple_w2.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---

    def test_standard_deduction_single_2025(self):
        """2025 single-filer standard deduction is $15,750 (OBBBA).

        This is a regression test for the SD_Single -> StdDeduct swap.
        Pre-fix this would have returned $15,750 by coincidence (SD_Single
        happens to be correct for single filers); post-fix it must still
        return $15,750 via the filing-status-aware StdDeduct cell.
        """
        self.assertEqual(int(self.results["standard_deduction"]), 15750)

    def test_schedule_a_total_zero_when_no_sch_a(self):
        """With no 1098 or other Sch A inputs, schedule_a_total must be 0."""
        sch_a = self.results.get("schedule_a_total") or 0
        self.assertEqual(int(sch_a), 0)

    def test_deduction_choice_invariant(self):
        assert_deduction_choice_consistent(self, self.results)
