import tempfile
import unittest
from pathlib import Path

import yaml

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


class TestEstimatedTaxPayments(unittest.TestCase):
    """Federal estimated-tax-payments verbatim input channel: the filer's
    stated total is carried through as-is (or refused if negative) — never
    computed, capped, or clamped."""

    def _make_config_body(self, **overrides) -> dict:
        body = {
            "year": 2025,
            "filing_status": "single",
            "birthdate": "1985-04-20",
            "state": "CA",
            "has_foreign_accounts": False,
            "prior_year_itemized": False,
            **scope_out_attestation_defaults(),
        }
        body.update(overrides)
        return body

    def _load_with_config(self, config_body: dict) -> Scenario:
        body = {"config": config_body}
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        return load_scenario(path)

    def test_estimated_tax_payments_accepted_verbatim(self) -> None:
        config_body = self._make_config_body(estimated_tax_payments=4500.0)
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.estimated_tax_payments, 4500.0)

    def test_estimated_tax_payments_defaults_to_zero_when_omitted(self) -> None:
        config_body = self._make_config_body()
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.estimated_tax_payments, 0.0)

    def test_negative_estimated_tax_payments_refused(self) -> None:
        config_body = self._make_config_body(estimated_tax_payments=-1.0)
        with self.assertRaises(ValueError):
            self._load_with_config(config_body)


class TestNonitemizerCharitableCash(unittest.TestCase):
    """2021-only CARES/CAA above-the-line cash-charitable deduction for
    non-itemizers (Form 1040 line 12b): the filer's stated amount is
    carried through verbatim (or refused if negative, or refused entirely
    outside the one year the provision existed) — never computed, capped,
    or clamped at load time (field>cap and itemizer gating are compute-time
    concerns handled in a later task)."""

    def _make_config_body(self, **overrides) -> dict:
        body = {
            "year": 2025,
            "filing_status": "single",
            "birthdate": "1985-04-20",
            "state": "CA",
            "has_foreign_accounts": False,
            "prior_year_itemized": False,
            **scope_out_attestation_defaults(),
        }
        body.update(overrides)
        return body

    def _load_with_config(self, config_body: dict) -> Scenario:
        body = {"config": config_body}
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        return load_scenario(path)

    def test_2021_nonitemizer_charitable_cash_accepted_verbatim(self) -> None:
        config_body = self._make_config_body(
            year=2021, charitable_cash_nonitemizer=250.0)
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.charitable_cash_nonitemizer, 250.0)

    def test_nonitemizer_charitable_cash_defaults_to_zero_when_omitted(self) -> None:
        config_body = self._make_config_body(year=2021)
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.charitable_cash_nonitemizer, 0.0)

    def test_negative_nonitemizer_charitable_cash_refused(self) -> None:
        config_body = self._make_config_body(
            year=2021, charitable_cash_nonitemizer=-1.0)
        with self.assertRaises(ValueError):
            self._load_with_config(config_body)

    def test_nonzero_nonitemizer_charitable_cash_refused_outside_2021(self) -> None:
        config_body = self._make_config_body(
            year=2022, charitable_cash_nonitemizer=250.0)
        with self.assertRaises(ValueError):
            self._load_with_config(config_body)

    def test_zero_nonitemizer_charitable_cash_ok_outside_2021(self) -> None:
        config_body = self._make_config_body(
            year=2022, charitable_cash_nonitemizer=0.0)
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.charitable_cash_nonitemizer, 0.0)

    def test_mfj_nonitemizer_charitable_cash_refused_as_out_of_scope(self) -> None:
        config_body = self._make_config_body(
            year=2021, filing_status="married_jointly",
            charitable_cash_nonitemizer=400.0)
        with self.assertRaises(ValueError) as ctx:
            self._load_with_config(config_body)
        message = str(ctx.exception).lower()
        self.assertIn("single", message)
        self.assertTrue(
            "out-of-scope" in message or "certified" in message,
            msg=f"Expected message to name the out-of-scope/certified "
                f"condition, got: {ctx.exception}",
        )

    def test_head_of_household_under_cap_still_refused_as_out_of_scope(self) -> None:
        # Distinguisher: a non-single amount UNDER the single $300 cap must
        # STILL refuse — this is the non-single scope-out, not the cap check.
        config_body = self._make_config_body(
            year=2021, filing_status="head_of_household",
            charitable_cash_nonitemizer=200.0)
        with self.assertRaises(ValueError) as ctx:
            self._load_with_config(config_body)
        message = str(ctx.exception).lower()
        self.assertIn("single", message)
        self.assertTrue(
            "out-of-scope" in message or "certified" in message,
            msg=f"Expected message to name the out-of-scope/certified "
                f"condition, got: {ctx.exception}",
        )

    def test_single_over_cap_refused(self) -> None:
        config_body = self._make_config_body(
            year=2021, charitable_cash_nonitemizer=350.0)
        with self.assertRaises(ValueError) as ctx:
            self._load_with_config(config_body)
        message = str(ctx.exception)
        self.assertIn("300", message)

    def test_single_itemizer_with_nonzero_charitable_refused(self) -> None:
        config_body = self._make_config_body(
            year=2021, charitable_cash_nonitemizer=250.0)
        body = {"config": config_body, "itemized_deductions": {}}
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        with self.assertRaises(ValueError) as ctx:
            load_scenario(path)
        message = str(ctx.exception).lower()
        self.assertTrue(
            "itemiz" in message,
            msg=f"Expected message to mention itemizer/itemized, got: {ctx.exception}",
        )


class TestPriorYearSaltPaid(unittest.TestCase):
    """Prior-year SALT-actually-paid input: required loudly whenever
    prior_year_itemized is true (drives the Sch 1 line-1 true benefit
    limitation), and refused if negative."""

    def _make_config_body(self, **overrides) -> dict:
        body = {
            "year": 2025,
            "filing_status": "single",
            "birthdate": "1985-04-20",
            "state": "CA",
            "has_foreign_accounts": False,
            **scope_out_attestation_defaults(),
            # Explicit True AFTER the scope_out_attestation_defaults() spread:
            # `prior_year_itemized` is itself a registered attestation (defaults
            # False there), so it must be set after the spread or it gets
            # silently overridden back to False.
            "prior_year_itemized": True,
            "prior_year_itemized_deduction_amount": 30_000.0,
            "prior_year_standard_deduction_amount": 14_600.0,
        }
        body.update(overrides)
        return body

    def _load_with_config(self, config_body: dict) -> Scenario:
        body = {"config": config_body}
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(body, f)
            path = Path(f.name)
        self.addCleanup(path.unlink)
        return load_scenario(path)

    def test_prior_year_itemized_without_salt_paid_raises(self) -> None:
        config_body = self._make_config_body()
        with self.assertRaisesRegex(
            ValueError, r"\bprior_year_salt_paid\b",
        ):
            self._load_with_config(config_body)

    def test_prior_year_itemized_with_salt_paid_loads(self) -> None:
        config_body = self._make_config_body(prior_year_salt_paid=12_000.0)
        scenario = self._load_with_config(config_body)
        self.assertEqual(scenario.config.prior_year_salt_paid, 12_000.0)

    def test_negative_prior_year_salt_paid_refused(self) -> None:
        config_body = self._make_config_body(prior_year_salt_paid=-1.0)
        with self.assertRaises(ValueError):
            self._load_with_config(config_body)

