import tempfile
import unittest
from pathlib import Path

from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.mappings.f1040 import F1040
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice


@needs_libreoffice
class TestSpreadsheetEngine(unittest.TestCase):

    def test_simple_w2_single_filer(self):
        """$100k wages, single filer, standard deduction."""
        federal_1040_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not federal_1040_path.exists():
            self.skipTest(f"Federal 1040 spreadsheet not found at {federal_1040_path}")

        tmp_path = Path(tempfile.mkdtemp())
        engine = SpreadsheetEngine()

        inputs = {
            "filing_status_single": "X",
            "birthdate_month": 6,
            "birthdate_day": 15,
            "birthdate_year": 1990,
            "w2_wages_1": 100000,
            "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000,
            "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000,
            "w2_medicare_withheld_1": 1450,
        }

        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=inputs,
            work_dir=tmp_path,
        )

        self.assertEqual(results["wages"], 100000)
        self.assertEqual(results["agi"], 100000)
        self.assertEqual(results["taxable_income"], 84250)  # 100000 - 15750 std deduction
        self.assertEqual(results["federal_withheld"], 15000)
        # Tax should be roughly $13,455 (per IRS tax table)
        self.assertGreater(results["total_tax"], 13000)
        self.assertLess(results["total_tax"], 14000)
        self.assertGreater(results["overpaid"], 0)


@needs_libreoffice
class SheetMapFallbackForOutputs(unittest.TestCase):
    """OUTPUTS entries that aren't named ranges should fall back to
    SHEET_MAP routing, mirroring the INPUTS-side behavior in
    _write_inputs. Without the fallback, direct cell-ref OUTPUTS
    silently resolve to None.
    """

    def test_cell_ref_output_resolves_via_sheet_map(self):
        federal_1040_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not federal_1040_path.exists():
            self.skipTest(f"Federal 1040 spreadsheet not found at {federal_1040_path}")

        class _TestMapping:
            INPUTS = {2025: {"w2_wages_1": "C3"}}
            OUTPUTS = {2025: {
                # Named range — control: must continue to work.
                "wages_named": "Wages",
                # Cell ref — exercises the new SHEET_MAP fallback path.
                "wages_cell_ref": "C3",
            }}
            SHEET_MAP = {2025: {
                "w2_wages_1": "W-2s",
                "wages_cell_ref": "W-2s",
            }}

            @classmethod
            def get_inputs(cls, year):
                return cls.INPUTS[year]

            @classmethod
            def get_outputs(cls, year):
                return cls.OUTPUTS[year]

        tmp_path = Path(tempfile.mkdtemp())
        engine = SpreadsheetEngine()
        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=_TestMapping,
            year=2025,
            inputs={"w2_wages_1": 100000},
            work_dir=tmp_path,
        )
        self.assertEqual(results["wages_named"], 100000)
        self.assertEqual(results["wages_cell_ref"], 100000)
