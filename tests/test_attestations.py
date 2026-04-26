"""Tests for the data-driven _ATTESTATIONS table."""

import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.attestations import Attestation, _ATTESTATIONS, enforce_compute_time
from tenforty.models import Form1099B, Scenario, TaxReturnConfig
from tenforty.scenario import load_scenario
from tests.helpers import scope_out_attestation_defaults


class TestAttestationsTable(unittest.TestCase):
    def test_table_is_non_empty(self) -> None:
        self.assertGreaterEqual(len(_ATTESTATIONS), 16)

    def test_each_entry_has_required_fields(self) -> None:
        for a in _ATTESTATIONS:
            self.assertIsInstance(a, Attestation)
            self.assertTrue(a.field)
            self.assertTrue(callable(a.triggered_when))
            self.assertTrue(a.load_error)
            # compute_error is optional for pure load-time gates
            # (has_foreign_accounts raises NotImplementedError
            # immediately on True, so no compute-time gate needed).

    def test_covers_plan_b_and_plan_d_fields(self) -> None:
        fields = {a.field for a in _ATTESTATIONS}
        expected = {
            "has_foreign_accounts",
            "acknowledges_sch_a_sales_tax_unsupported",
            "acknowledges_qbi_below_threshold",
            "acknowledges_unlimited_at_risk",
            "basis_tracked_externally",
            "acknowledges_no_partnership_se_earnings",
            "acknowledges_no_section_1231_gain",
            "acknowledges_no_more_than_four_k1s",
            "acknowledges_no_k1_credits",
            "acknowledges_no_section_179",
            "acknowledges_no_estate_trust_k1",
            "prior_year_itemized",
            "acknowledges_no_wash_sale_adjustments",
            "acknowledges_no_other_basis_adjustments",
            "acknowledges_no_28_rate_gain",
            "acknowledges_no_unrecaptured_section_1250",
            # 1120-S scope-out attestations (Sub-plan 2, Task 5)
            "acknowledges_no_1120s_schedule_l_needed",
            "acknowledges_no_1120s_schedule_m_needed",
            "acknowledges_constant_shareholder_ownership",
            "acknowledges_no_section_1375_tax",
            "acknowledges_no_section_1374_tax",
            "acknowledges_cogs_aggregate_only",
            "acknowledges_officer_comp_aggregate_only",
            "acknowledges_no_elective_payment_election",
        }
        self.assertEqual(expected, fields)


class TestLoadTimeValidation(unittest.TestCase):
    def test_missing_has_foreign_accounts_raises(self) -> None:
        from tenforty.models import TaxReturnConfig
        from tenforty.scenario import _validate_scenario_config
        cfg = TaxReturnConfig(
            year=2025, filing_status="single", birthdate="1990-06-15",
            state="CA",
        )
        with self.assertRaises(ValueError) as ctx:
            _validate_scenario_config(cfg)
        self.assertIn("has_foreign_accounts", str(ctx.exception))

    def test_all_answered_passes(self) -> None:
        from tenforty.models import TaxReturnConfig
        from tenforty.scenario import _validate_scenario_config
        kw = dict(
            year=2025, filing_status="single", birthdate="1990-06-15",
            state="CA", has_foreign_accounts=False,
            acknowledges_sch_a_sales_tax_unsupported=False,
            acknowledges_qbi_below_threshold=False,
            acknowledges_unlimited_at_risk=False,
            basis_tracked_externally=False,
            acknowledges_no_partnership_se_earnings=False,
            acknowledges_no_section_1231_gain=False,
            acknowledges_no_more_than_four_k1s=False,
            acknowledges_no_k1_credits=False,
            acknowledges_no_section_179=False,
            acknowledges_no_estate_trust_k1=False,
            prior_year_itemized=False,
            acknowledges_no_wash_sale_adjustments=False,
            acknowledges_no_other_basis_adjustments=False,
            acknowledges_no_28_rate_gain=False,
            acknowledges_no_unrecaptured_section_1250=False,
            # 1120-S scope-out attestations (Sub-plan 2, Task 5)
            acknowledges_no_1120s_schedule_l_needed=False,
            acknowledges_no_1120s_schedule_m_needed=False,
            acknowledges_constant_shareholder_ownership=False,
            acknowledges_no_section_1375_tax=False,
            acknowledges_no_section_1374_tax=False,
            acknowledges_cogs_aggregate_only=False,
            acknowledges_officer_comp_aggregate_only=False,
            acknowledges_no_elective_payment_election=False,
        )
        cfg = TaxReturnConfig(**kw)
        _validate_scenario_config(cfg)  # no raise


class TestComputeTimeGate(unittest.TestCase):
    def test_k1_present_but_unlimited_at_risk_false_raises(self) -> None:
        from tenforty.forms import sch_e_part_ii
        from tenforty.models import EntityType, ScheduleK1
        from tests.helpers import make_simple_scenario
        scenario = make_simple_scenario()
        scenario.config.acknowledges_unlimited_at_risk = False
        scenario.config.basis_tracked_externally = True
        scenario.config.acknowledges_no_k1_credits = True
        scenario.schedule_k1s = [ScheduleK1(
            entity_name="X", entity_ein="00-0000000",
            entity_type=EntityType.S_CORP, material_participation=True,
            ordinary_business_income=1000.0,
        )]
        with self.assertRaises(NotImplementedError) as ctx:
            sch_e_part_ii.compute(scenario, upstream={})
        self.assertIn("at_risk", str(ctx.exception).lower())


class TestDefaultsAfterMigration(unittest.TestCase):
    """Task 12 (SP1-M2 part 2) migrates three defaults from False to True so
    that a bare in-memory test scenario matches the spec's target posture for
    K-1-bearing returns."""

    def test_unlimited_at_risk_defaults_true(self) -> None:
        from tests.helpers import scope_out_attestation_defaults
        self.assertIs(scope_out_attestation_defaults()["acknowledges_unlimited_at_risk"], True)

    def test_basis_tracked_externally_defaults_true(self) -> None:
        from tests.helpers import scope_out_attestation_defaults
        self.assertIs(scope_out_attestation_defaults()["basis_tracked_externally"], True)

    def test_acknowledges_no_k1_credits_defaults_true(self) -> None:
        from tests.helpers import scope_out_attestation_defaults
        self.assertIs(scope_out_attestation_defaults()["acknowledges_no_k1_credits"], True)

    def test_other_defaults_remain_false(self) -> None:
        """Only the three K-1-posture fields migrate. Everything else stays
        all-False — their triggers are more specific (per-K-1-field) so the
        pessimal default is still safe."""
        from tests.helpers import scope_out_attestation_defaults
        d = scope_out_attestation_defaults()
        for f in (
            "has_foreign_accounts",
            "acknowledges_sch_a_sales_tax_unsupported",
            "acknowledges_qbi_below_threshold",
            "acknowledges_no_partnership_se_earnings",
            "acknowledges_no_section_1231_gain",
            "acknowledges_no_more_than_four_k1s",
            "acknowledges_no_section_179",
            "acknowledges_no_estate_trust_k1",
            "prior_year_itemized",
        ):
            self.assertIs(d[f], False, f"{f} should default to False")

    def test_make_simple_scenario_with_k1_does_not_raise(self) -> None:
        """The motivating use case for the migration: constructing a scenario
        with an S-corp K-1 via make_simple_scenario() should succeed end-to-end
        now that the three K-1-posture attestations default to True."""
        from tenforty.forms import sch_e_part_ii
        from tenforty.models import EntityType, ScheduleK1
        from tests.helpers import make_simple_scenario
        scenario = make_simple_scenario()
        scenario.schedule_k1s = [ScheduleK1(
            entity_name="X", entity_ein="00-0000000",
            entity_type=EntityType.S_CORP, material_participation=True,
            ordinary_business_income=1000.0,
        )]
        sch_e_part_ii.compute(scenario, upstream={})


class TestNewForm8949Attestations(unittest.TestCase):
    """Four Form 8949 scope-out attestations — wash-sale, other-basis-adj, 28%-rate, §1250."""

    def _base_config_kwargs(self) -> dict:
        """Return a kwargs dict that sets every attestation to a safe default,
        including the 4 lot-level gates as False. Individual test methods
        override the specific attestation under test via `_make_scenario`'s
        **config_overrides."""
        return scope_out_attestation_defaults()

    def _make_scenario(self, lot_kwargs: dict, **config_overrides):
        """Build a Scenario with a single 1099-B lot and config overrides."""
        kwargs = self._base_config_kwargs()
        kwargs.update(config_overrides)
        # has_foreign_accounts and prior_year_itemized come from
        # scope_out_attestation_defaults(); no need to pass them separately.
        cfg = TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1985-04-20", state="CA",
            **kwargs,
        )
        lot = Form1099B(
            broker="Brokerage Inc", description="X",
            date_acquired="2024-01-15", date_sold="2025-03-20",
            proceeds=1000.0, cost_basis=800.0,
            **lot_kwargs,
        )
        return Scenario(config=cfg, form1099_b=[lot])

    def test_wash_sale_gate_raises_at_compute_when_false(self) -> None:
        scenario = self._make_scenario(
            lot_kwargs={"wash_sale_loss_disallowed": 50.0},
            acknowledges_no_wash_sale_adjustments=False,
        )
        with self.assertRaises(NotImplementedError) as ctx:
            enforce_compute_time(scenario)
        self.assertIn("wash_sale", str(ctx.exception))

    def test_wash_sale_gate_passes_when_true(self) -> None:
        scenario = self._make_scenario(
            lot_kwargs={"wash_sale_loss_disallowed": 50.0},
            acknowledges_no_wash_sale_adjustments=True,
        )
        enforce_compute_time(scenario)  # no raise

    def test_wash_sale_gate_passes_when_no_trigger(self) -> None:
        """No wash sale on any lot → attestation value is irrelevant at compute."""
        scenario = self._make_scenario(
            lot_kwargs={},
            acknowledges_no_wash_sale_adjustments=False,
        )
        enforce_compute_time(scenario)

    def test_other_basis_adjustment_gate_raises_when_false(self) -> None:
        scenario = self._make_scenario(
            lot_kwargs={"other_basis_adjustment": -25.0},
            acknowledges_no_other_basis_adjustments=False,
        )
        with self.assertRaises(NotImplementedError):
            enforce_compute_time(scenario)

    def test_other_basis_adjustment_gate_passes_when_true(self) -> None:
        """ack=True + trigger proceeds (no silent skip)."""
        scenario = self._make_scenario(
            lot_kwargs={"other_basis_adjustment": -25.0},
            acknowledges_no_other_basis_adjustments=True,
        )
        enforce_compute_time(scenario)  # no raise

    def test_other_basis_adjustment_gate_passes_when_no_trigger(self) -> None:
        """No other basis adjustment on any lot → attestation value is irrelevant at compute."""
        scenario = self._make_scenario(
            lot_kwargs={},
            acknowledges_no_other_basis_adjustments=False,
        )
        enforce_compute_time(scenario)

    def test_28_rate_gate_raises_when_false(self) -> None:
        scenario = self._make_scenario(
            lot_kwargs={
                "is_28_rate_collectible": True,
                "short_term": False,
            },
            acknowledges_no_28_rate_gain=False,
        )
        with self.assertRaises(NotImplementedError):
            enforce_compute_time(scenario)

    def test_28_rate_gate_passes_when_true(self) -> None:
        """ack=True + trigger proceeds (no silent skip)."""
        scenario = self._make_scenario(
            lot_kwargs={
                "is_28_rate_collectible": True,
                "short_term": False,
            },
            acknowledges_no_28_rate_gain=True,
        )
        enforce_compute_time(scenario)  # no raise

    def test_28_rate_gate_passes_when_no_trigger(self) -> None:
        """No 28%-rate collectible on any lot → attestation value is irrelevant at compute."""
        scenario = self._make_scenario(
            lot_kwargs={"short_term": False},
            acknowledges_no_28_rate_gain=False,
        )
        enforce_compute_time(scenario)

    def test_section_1250_gate_raises_when_false(self) -> None:
        scenario = self._make_scenario(
            lot_kwargs={
                "is_section_1250": True,
                "short_term": False,
            },
            acknowledges_no_unrecaptured_section_1250=False,
        )
        with self.assertRaises(NotImplementedError):
            enforce_compute_time(scenario)

    def test_section_1250_gate_passes_when_true(self) -> None:
        """ack=True + trigger proceeds (no silent skip)."""
        scenario = self._make_scenario(
            lot_kwargs={
                "is_section_1250": True,
                "short_term": False,
            },
            acknowledges_no_unrecaptured_section_1250=True,
        )
        enforce_compute_time(scenario)  # no raise

    def test_section_1250_gate_passes_when_no_trigger(self) -> None:
        """No section 1250 on any lot → attestation value is irrelevant at compute."""
        scenario = self._make_scenario(
            lot_kwargs={"short_term": False},
            acknowledges_no_unrecaptured_section_1250=False,
        )
        enforce_compute_time(scenario)

    def test_load_error_when_attestation_none(self) -> None:
        """Scenario load raises ValueError when any of the 4 new lot
        attestations is left as None."""
        for missing_key in (
            "acknowledges_no_wash_sale_adjustments",
            "acknowledges_no_other_basis_adjustments",
            "acknowledges_no_28_rate_gain",
            "acknowledges_no_unrecaptured_section_1250",
        ):
            with self.subTest(missing=missing_key):
                defaults = scope_out_attestation_defaults()
                defaults.pop(missing_key, None)
                body = {
                    "config": {
                        "year": 2025, "filing_status": "single",
                        "birthdate": "1985-04-20", "state": "CA",
                        "has_foreign_accounts": False,
                        "prior_year_itemized": False,
                        **defaults,
                    },
                }
                with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
                    yaml.safe_dump(body, f)
                    path = Path(f.name)
                self.addCleanup(path.unlink)
                with self.assertRaises(ValueError) as ctx:
                    load_scenario(path)
                self.assertIn(missing_key, str(ctx.exception))
