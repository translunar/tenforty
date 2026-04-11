import socket
import tempfile
import unittest
from pathlib import Path

from tenforty.mappings.f1040 import F1040
from tenforty.uno_engine import UnoEngine
from tests.helpers import SPREADSHEETS_DIR


def unoserver_available() -> bool:
    try:
        sock = socket.create_connection(("127.0.0.1", 2002), timeout=2)
        sock.close()
        return True
    except (ConnectionRefusedError, OSError):
        return False


needs_unoserver = unittest.skipUnless(
    unoserver_available(), "unoserver not available",
)


@needs_unoserver
class TestUnoEngine(unittest.TestCase):
    def test_simple_w2_scenario(self):
        xlsx_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not xlsx_path.exists():
            self.skipTest("Federal 1040 spreadsheet not found")

        engine = UnoEngine()
        inputs = {
            "filing_status_single": "X",
            "birthdate_month": 6, "birthdate_day": 15, "birthdate_year": 1990,
            "w2_wages_1": 100000, "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000, "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000, "w2_medicare_withheld_1": 1450,
        }
        results = engine.compute(
            spreadsheet_path=xlsx_path, mapping=F1040, year=2025, inputs=inputs,
        )
        self.assertEqual(results["wages"], 100000)
        self.assertEqual(results["agi"], 100000)
        self.assertEqual(results["taxable_income"], 84250)
        self.assertEqual(results["federal_withheld"], 15000)
        self.assertGreater(results["total_tax"], 13000)
        self.assertLess(results["total_tax"], 14000)
        self.assertGreater(results["overpaid"], 0)

    def test_two_scenarios_same_engine(self):
        xlsx_path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
        if not xlsx_path.exists():
            self.skipTest("Federal 1040 spreadsheet not found")

        engine = UnoEngine()
        inputs_100k = {
            "filing_status_single": "X",
            "birthdate_month": 6, "birthdate_day": 15, "birthdate_year": 1990,
            "w2_wages_1": 100000, "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000, "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000, "w2_medicare_withheld_1": 1450,
        }
        inputs_200k = {
            "filing_status_single": "X",
            "birthdate_month": 6, "birthdate_day": 15, "birthdate_year": 1990,
            "w2_wages_1": 200000, "w2_fed_withheld_1": 40000,
            "w2_ss_wages_1": 176100, "w2_ss_withheld_1": 10950,
            "w2_medicare_wages_1": 200000, "w2_medicare_withheld_1": 2900,
        }
        results_100k = engine.compute(
            spreadsheet_path=xlsx_path, mapping=F1040, year=2025, inputs=inputs_100k,
        )
        results_200k = engine.compute(
            spreadsheet_path=xlsx_path, mapping=F1040, year=2025, inputs=inputs_200k,
        )
        self.assertEqual(results_100k["wages"], 100000)
        self.assertEqual(results_200k["wages"], 200000)
        self.assertGreater(results_200k["agi"], results_100k["agi"])
