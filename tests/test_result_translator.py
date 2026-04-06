import unittest

from tests.conftest import make_simple_scenario
from tenforty.result_translator import ResultTranslator, TranslationSpec


class TestTranslationSpec(unittest.TestCase):
    def test_create_spec(self):
        spec = TranslationSpec(
            renames={"interest_income": "taxable_interest"},
            expansions={"agi": ["agi", "agi_page2"]},
            scenario_fields={"first_name": lambda s: "John"},
        )
        self.assertEqual(spec.renames["interest_income"], "taxable_interest")
        self.assertEqual(spec.expansions["agi"], ["agi", "agi_page2"])


class TestTranslationSpecValidation(unittest.TestCase):
    def test_overlapping_renames_and_expansions_raises(self):
        with self.assertRaises(ValueError) as ctx:
            TranslationSpec(
                renames={"agi": "adjusted_gross_income"},
                expansions={"agi": ["agi", "agi_page2"]},
            )
        self.assertIn("agi", str(ctx.exception))


class TestResultTranslator(unittest.TestCase):
    def _make_spec(self) -> TranslationSpec:
        return TranslationSpec(
            renames={
                "interest_income": "taxable_interest",
                "dividend_income": "ordinary_dividends",
            },
            expansions={
                "agi": ["agi", "agi_page2"],
            },
            scenario_fields={
                "state": lambda s: s.config.state,
            },
        )

    def test_direct_passthrough(self):
        """Keys not in renames or expansions pass through unchanged."""
        spec = TranslationSpec()
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000, "overpaid": 1500}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result["wages"], 100000)
        self.assertEqual(result["overpaid"], 1500)

    def test_renames(self):
        """Keys in renames are translated to the new key name."""
        spec = self._make_spec()
        translator = ResultTranslator(spec)
        engine_results = {
            "interest_income": 250,
            "dividend_income": 2000,
        }

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result["taxable_interest"], 250)
        self.assertEqual(result["ordinary_dividends"], 2000)
        self.assertNotIn("interest_income", result)
        self.assertNotIn("dividend_income", result)

    def test_expansions(self):
        """Keys in expansions produce multiple output keys with the same value."""
        spec = self._make_spec()
        translator = ResultTranslator(spec)
        engine_results = {"agi": 100250}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result["agi"], 100250)
        self.assertEqual(result["agi_page2"], 100250)

    def test_scenario_fields(self):
        """Scenario fields are extracted from the scenario and added to results."""
        spec = self._make_spec()
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result["state"], "CA")

    def test_engine_results_override_scenario_fields(self):
        """If an engine result conflicts with a scenario field, engine wins."""
        spec = TranslationSpec(
            scenario_fields={"wages": lambda s: 0},
        )
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result["wages"], 100000)

    def test_empty_spec_is_passthrough(self):
        """A TranslationSpec with no renames/expansions/scenario_fields is identity."""
        spec = TranslationSpec()
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000, "agi": 100000}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertEqual(result, engine_results)

    def test_none_values_not_included(self):
        """Engine results with None values are excluded."""
        spec = TranslationSpec()
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000, "schd_line16": None}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertIn("wages", result)
        self.assertNotIn("schd_line16", result)

    def test_rename_missing_key_is_skipped(self):
        """If a rename source key is not in engine results, it's just skipped."""
        spec = TranslationSpec(
            renames={"interest_income": "taxable_interest"},
        )
        translator = ResultTranslator(spec)
        engine_results = {"wages": 100000}

        result = translator.translate(engine_results, make_simple_scenario())

        self.assertNotIn("taxable_interest", result)
        self.assertEqual(result["wages"], 100000)

    def test_scenario_field_returning_none_is_excluded(self):
        """Scenario fields that return None are not included in results."""
        spec = TranslationSpec(
            scenario_fields={"missing_field": lambda s: None},
        )
        translator = ResultTranslator(spec)

        result = translator.translate({}, make_simple_scenario())

        self.assertNotIn("missing_field", result)
