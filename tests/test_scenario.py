import unittest
from pathlib import Path

from tenforty.models import Scenario, W2, Form1099INT, TaxReturnConfig
from tenforty.scenario import load_scenario
from tests.helpers import (
    FIXTURES_DIR,
    scope_out_attestation_defaults,
)


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


class TestFixtureAttestationMigration(unittest.TestCase):
    def test_every_yaml_fixture_loads(self) -> None:
        """Post-migration, every YAML fixture must load without raising."""
        fixtures = Path("tests/fixtures").glob("*.yaml")
        loaded = 0
        for fx in fixtures:
            load_scenario(fx)  # must not raise
            loaded += 1
        self.assertGreater(loaded, 0, "expected to find fixtures")

    def test_defaults_helper_includes_new_attestations(self) -> None:
        d = scope_out_attestation_defaults()
        for key in (
            "acknowledges_no_wash_sale_adjustments",
            "acknowledges_no_other_basis_adjustments",
            "acknowledges_no_28_rate_gain",
            "acknowledges_no_unrecaptured_section_1250",
        ):
            self.assertIn(key, d)
        self.assertNotIn("acknowledges_form_8949_unsupported", d)

