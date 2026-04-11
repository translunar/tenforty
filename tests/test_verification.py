import tempfile
import unittest
from pathlib import Path

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.scenario import load_scenario
from tests.conftest import FIXTURES_DIR, SPREADSHEETS_DIR, needs_libreoffice


@needs_libreoffice
class TestRealisticScenario(unittest.TestCase):
    def test_w2_with_interest_dividends_mortgage(self):
        """Higher-income filer with investment income and mortgage."""
        federal_1040_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not federal_1040_path.exists():
            self.skipTest(f"Federal 1040 spreadsheet not found at {federal_1040_path}")

        tmp_path = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "realistic_w2_rental.yaml")
        flat_inputs = flatten_scenario(scenario)

        engine = SpreadsheetEngine()
        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
            work_dir=tmp_path,
        )

        # Wages should be $150,000
        self.assertEqual(results["wages"], 150000)

        # AGI = 150000 + 500 (interest) + 2000 (dividends) = 152500
        self.assertEqual(results["agi"], 152500)

        # Interest and dividends should flow through
        self.assertEqual(results["interest_income"], 500)
        self.assertEqual(results["dividend_income"], 2000)

        # Withholding
        self.assertEqual(results["federal_withheld"], 28000)

        # Should have meaningful tax
        self.assertIsNotNone(results["total_tax"])
        self.assertGreater(results["total_tax"], 0)

        # Should get a refund (withheld a lot)
        self.assertIsNotNone(results["overpaid"])
        self.assertGreater(results["overpaid"], 0)
