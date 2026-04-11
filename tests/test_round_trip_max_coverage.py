import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
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
    assert_all_income_accounted_for,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
    verify_pdf_round_trip,
)


@needs_libreoffice
class TestMaxIncomeCoverage(unittest.TestCase):
    """Max-income scenario: W-2 + interest + dividends + cap gain distributions."""

    @classmethod
    def setUpClass(cls):
        cls._work_dir = Path(tempfile.mkdtemp())
        cls._scenario = load_scenario(FIXTURES_DIR / "max_income.yaml")
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=cls._work_dir,
        )
        cls._results = orchestrator.compute_federal(cls._scenario)

    def test_invariants(self):
        assert_agi_consistent(self, self._results, self._scenario)
        assert_all_income_accounted_for(self, self._results, self._scenario)
        assert_taxable_income_consistent(self, self._results)
        assert_tax_is_non_negative(self, self._results)
        assert_refund_or_owed_consistent(self, self._results)
        assert_withholding_matches_input(self, self._results, self._scenario)

    def test_interest_in_agi(self):
        self.assertGreater(float(self._results["agi"]), 150000)

    def test_dividends_in_agi(self):
        # Wages (150k) + interest (2k) + ordinary dividends (8k) = 160k AGI
        self.assertGreater(float(self._results["agi"]), 155000)

    @needs_pdf
    def test_round_trip(self):
        verify_pdf_round_trip(
            test=self, results=self._results, scenario=self._scenario,
            translation_spec=F1040_PDF_SPEC, pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF, year=2025, work_dir=self._work_dir,
        )


@needs_libreoffice
class TestMaxDeductions(unittest.TestCase):
    """Max-deductions scenario: high income + mortgage + property tax (itemized)."""

    @classmethod
    def setUpClass(cls):
        cls._work_dir = Path(tempfile.mkdtemp())
        cls._scenario = load_scenario(FIXTURES_DIR / "max_deductions.yaml")
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=cls._work_dir,
        )
        cls._results = orchestrator.compute_federal(cls._scenario)

    def test_invariants(self):
        assert_agi_consistent(self, self._results, self._scenario)
        assert_taxable_income_consistent(self, self._results)
        assert_tax_is_non_negative(self, self._results)
        assert_refund_or_owed_consistent(self, self._results)
        assert_withholding_matches_input(self, self._results, self._scenario)

    def test_itemizes(self):
        deductions = float(self._results.get("total_deductions", 0))
        self.assertGreater(deductions, 15750, "Should itemize with $24k mortgage + $8k SALT")

    @needs_pdf
    def test_round_trip(self):
        verify_pdf_round_trip(
            test=self, results=self._results, scenario=self._scenario,
            translation_spec=F1040_PDF_SPEC, pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF, year=2025, work_dir=self._work_dir,
        )
