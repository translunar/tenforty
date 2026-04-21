"""Tests for the data-driven _ATTESTATIONS table."""

import unittest

from tenforty.attestations import Attestation, _ATTESTATIONS


class TestAttestationsTable(unittest.TestCase):
    def test_table_is_non_empty(self) -> None:
        self.assertGreaterEqual(len(_ATTESTATIONS), 13)

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
            "acknowledges_form_8949_unsupported",
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
            acknowledges_form_8949_unsupported=False,
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
        from tests.helpers import plan_d_attestation_defaults
        self.assertIs(plan_d_attestation_defaults()["acknowledges_unlimited_at_risk"], True)

    def test_basis_tracked_externally_defaults_true(self) -> None:
        from tests.helpers import plan_d_attestation_defaults
        self.assertIs(plan_d_attestation_defaults()["basis_tracked_externally"], True)

    def test_acknowledges_no_k1_credits_defaults_true(self) -> None:
        from tests.helpers import plan_d_attestation_defaults
        self.assertIs(plan_d_attestation_defaults()["acknowledges_no_k1_credits"], True)

    def test_other_defaults_remain_false(self) -> None:
        """Only the three K-1-posture fields migrate. Everything else stays
        all-False — their triggers are more specific (per-K-1-field) so the
        pessimal default is still safe."""
        from tests.helpers import plan_d_attestation_defaults
        d = plan_d_attestation_defaults()
        for f in (
            "has_foreign_accounts",
            "acknowledges_form_8949_unsupported",
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
