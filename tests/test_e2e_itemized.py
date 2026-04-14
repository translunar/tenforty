import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import (
    F1040_PDF,
    FIXTURES_DIR,
    SPREADSHEETS_DIR,
    needs_libreoffice,
    needs_pdf,
)
from tenforty.models import TaxReturnConfig
from tests.invariants import (
    assert_4868_fills_correctly,
    assert_agi_consistent,
    assert_deduction_choice_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_w2_withholding_matches_input,
)


@needs_libreoffice
class TestE2EItemized(unittest.TestCase):
    """Full pipeline: high earner with mortgage, should itemize."""

    def setUp(self):
        if not hasattr(self.__class__, '_results'):
            self.__class__._work_dir = Path(tempfile.mkdtemp())
            self.__class__._scenario = load_scenario(FIXTURES_DIR / "itemized_deductions.yaml")
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
        assert_w2_withholding_matches_input(self, self.results, self.scenario)

    def test_uses_itemized_deduction(self):
        """Deduction should exceed the 2025 standard deduction of $15,750."""
        deduction = float(self.results.get("total_deductions", 0))
        self.assertGreater(
            deduction, 15750,
            f"Expected itemized deduction > $15,750 standard, got ${deduction:,.0f}",
        )

    @needs_pdf
    def test_pdf_output(self):

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_itemized.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), self.results)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---

    def test_schedule_a_total_matches_inputs(self):
        """itemized_deductions.yaml has mortgage_interest $18,000 and
        property_tax $6,000. Post-OBBBA SALT cap is $40,000, so the
        $6,000 property tax is well under cap. Expected Sch A total:
        $18,000 + $6,000 = $24,000.
        """
        self.assertEqual(int(self.results["schedule_a_total"]), 24000)

    def test_schedule_a_exceeds_standard(self):
        """Sanity: this fixture is supposed to favor itemizing."""
        std = int(self.results["standard_deduction"])
        sch_a = int(self.results["schedule_a_total"])
        self.assertGreater(sch_a, std)

    def test_deduction_choice_invariant(self):
        assert_deduction_choice_consistent(self, self.results)

    def test_4868_fills_correctly(self):
        """4868 lines 4/5/6/7 match engine results; reuses cached _results."""
        cfg = TaxReturnConfig(
            year=self.scenario.config.year,
            filing_status=self.scenario.config.filing_status,
            birthdate=self.scenario.config.birthdate,
            state=self.scenario.config.state,
            dependents=self.scenario.config.dependents,
            first_name="Alice",
            last_name="Example",
            ssn="000-00-0001",
            spouse_first_name="",
            spouse_last_name="",
            spouse_ssn="",
            address="123 Example St",
            address_city="Anywhere",
            address_state="CA",
            address_zip="00000",
        )
        tmp_dir = Path(tempfile.mkdtemp())
        assert_4868_fills_correctly(self, self.results, cfg, tmp_dir)
