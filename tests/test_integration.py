import tempfile
import unittest
from pathlib import Path

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR, needs_libreoffice


@needs_libreoffice
class TestEndToEnd(unittest.TestCase):
    def test_simple_w2_yaml_to_results(self):
        """Full pipeline: YAML → Scenario → flat inputs → engine → results."""
        federal_1040_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not federal_1040_path.exists():
            self.skipTest(f"Federal 1040 spreadsheet not found at {federal_1040_path}")

        tmp_path = Path(tempfile.mkdtemp())
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        flat_inputs = flatten_scenario(scenario)

        engine = SpreadsheetEngine()
        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
            work_dir=tmp_path,
        )

        # $100k wages + $250 interest
        self.assertEqual(results["wages"], 100000)
        self.assertEqual(results["agi"], 100250)  # wages + interest
        self.assertEqual(results["interest_income"], 250)
        self.assertEqual(results["federal_withheld"], 15000)

        # Standard deduction for single 2025 is $15,750
        # Taxable income = 100250 - 15750 = 84500
        self.assertEqual(results["taxable_income"], 84500)

        # Tax should be in the $13k-$14k range
        self.assertGreater(results["total_tax"], 13000)
        self.assertLess(results["total_tax"], 14000)

        # Should get a refund (withheld $15k, tax ~$13.5k)
        self.assertGreater(results["overpaid"], 0)
