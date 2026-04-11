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
from tests.invariants import verify_pdf_round_trip


@needs_libreoffice
@needs_pdf
class TestRoundTripSimpleW2(unittest.TestCase):
    def test_all_filled_fields_match(self):
        work_dir = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=work_dir,
        )
        results = orchestrator.compute_federal(scenario)

        verify_pdf_round_trip(
            test=self,
            results=results,
            scenario=scenario,
            translation_spec=F1040_PDF_SPEC,
            pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF,
            year=2025,
            work_dir=work_dir,
        )


@needs_libreoffice
@needs_pdf
class TestRoundTripItemized(unittest.TestCase):
    def test_all_filled_fields_match(self):
        work_dir = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "itemized_deductions.yaml")

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=work_dir,
        )
        results = orchestrator.compute_federal(scenario)

        verify_pdf_round_trip(
            test=self,
            results=results,
            scenario=scenario,
            translation_spec=F1040_PDF_SPEC,
            pdf_mapping_cls=Pdf1040,
            pdf_template=F1040_PDF,
            year=2025,
            work_dir=work_dir,
        )
