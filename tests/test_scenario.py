import unittest
from pathlib import Path

from tenforty.models import Scenario, W2, Form1099INT, TaxReturnConfig
from tenforty.scenario import load_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestLoadScenario(unittest.TestCase):
    def test_loads_simple_w2_scenario(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertIsInstance(scenario, Scenario)
        self.assertEqual(scenario.config.year, 2025)
        self.assertEqual(scenario.config.filing_status, "single")
        self.assertEqual(scenario.config.birthdate, "1990-06-15")
        self.assertEqual(scenario.config.state, "CA")

    def test_w2s_loaded(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertEqual(len(scenario.w2s), 1)
        w2 = scenario.w2s[0]
        self.assertIsInstance(w2, W2)
        self.assertEqual(w2.employer, "Acme Corp")
        self.assertEqual(w2.wages, 100000.00)
        self.assertEqual(w2.federal_tax_withheld, 15000.00)

    def test_1099_int_loaded(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertEqual(len(scenario.form1099_int), 1)
        f = scenario.form1099_int[0]
        self.assertIsInstance(f, Form1099INT)
        self.assertEqual(f.interest, 250.00)

    def test_empty_lists_for_unused_forms(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertEqual(scenario.form1099_div, [])
        self.assertEqual(scenario.form1099_b, [])
        self.assertEqual(scenario.form1098s, [])
        self.assertEqual(scenario.schedule_k1s, [])

    def test_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            load_scenario(Path("/nonexistent/scenario.yaml"))
