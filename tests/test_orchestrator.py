import tempfile
import unittest
from pathlib import Path

from tenforty.models import Scenario, TaxReturnConfig, W2
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice


@needs_libreoffice
class TestReturnOrchestrator(unittest.TestCase):
    def test_federal_return(self):
        tmp_path = Path(tempfile.mkdtemp())
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
            ),
            w2s=[
                W2(
                    employer="Test Corp",
                    wages=80000,
                    federal_tax_withheld=12000,
                    ss_wages=80000,
                    ss_tax_withheld=4960,
                    medicare_wages=80000,
                    medicare_tax_withheld=1160,
                ),
            ],
        )

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=tmp_path,
        )
        results = orchestrator.compute_federal(scenario)

        self.assertEqual(results["wages"], 80000)
        self.assertEqual(results["agi"], 80000)
        # 80000 - 15750 = 64250
        self.assertEqual(results["taxable_income"], 64250)
        self.assertEqual(results["federal_withheld"], 12000)
