"""Load-time and compute-time gate tests for the 1120-S attestations."""

import unittest

from tenforty.attestations import _ATTESTATIONS


_EXPECTED_SCORP_FIELDS = frozenset({
    "acknowledges_no_1120s_schedule_l_needed",
    "acknowledges_no_1120s_schedule_m_needed",
    "acknowledges_constant_shareholder_ownership",
    "acknowledges_no_section_1375_tax",
    "acknowledges_no_section_1374_tax",
    "acknowledges_cogs_aggregate_only",
    "acknowledges_officer_comp_aggregate_only",
})

# Per existing attestations.py convention, attestations whose
# triggered_when=_never have compute_error="" because their gate fires
# only at load time. The runtime-triggered ones must have non-empty
# compute_error.
_RUNTIME_TRIGGERED_SCORP_FIELDS = frozenset({
    "acknowledges_no_1120s_schedule_l_needed",
    "acknowledges_no_1120s_schedule_m_needed",
    "acknowledges_no_section_1375_tax",
    "acknowledges_no_section_1374_tax",
})


class SCorpAttestationsTests(unittest.TestCase):
    def test_all_seven_are_registered(self):
        registered = {a.field for a in _ATTESTATIONS}
        missing = _EXPECTED_SCORP_FIELDS - registered
        self.assertEqual(missing, set(),
                         f"Missing 1120-S attestations: {missing}")

    def test_each_scorp_attestation_has_load_error(self):
        for a in _ATTESTATIONS:
            if a.field not in _EXPECTED_SCORP_FIELDS:
                continue
            self.assertTrue(
                a.load_error,
                f"{a.field} has empty load_error",
            )

    def test_runtime_triggered_attestations_have_compute_errors(self):
        for a in _ATTESTATIONS:
            if a.field not in _EXPECTED_SCORP_FIELDS:
                continue
            if a.field in _RUNTIME_TRIGGERED_SCORP_FIELDS:
                self.assertTrue(
                    a.compute_error,
                    f"{a.field} is runtime-triggered but has empty compute_error",
                )
            else:
                self.assertEqual(
                    a.compute_error, "",
                    f"{a.field} has triggered_when=_never; compute_error "
                    f"should be empty per convention.",
                )


class SCorpAttestationGateFiringTests(unittest.TestCase):
    """End-to-end: each attestation gate actually raises when the
    underlying triggered_when predicate fires AND the attestation is False."""

    def test_schedule_l_gate_fires_on_high_total_assets(self):
        """When total_assets >= 250000 and the attestation is False,
        compute-time enforcement raises NotImplementedError."""
        from tenforty.attestations import enforce_compute_time
        from tests._scorp_fixtures import _make_scorp_return
        from tenforty.models import (
            FilingStatus, Scenario, TaxReturnConfig,
        )
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="01-01-1980", state="EX",
            has_foreign_accounts=False, prior_year_itemized=False,
            acknowledges_no_1120s_schedule_l_needed=False,  # gate is FALSE
            acknowledges_no_1120s_schedule_m_needed=True,
            acknowledges_constant_shareholder_ownership=True,
            acknowledges_no_section_1375_tax=True,
            acknowledges_no_section_1374_tax=True,
            acknowledges_cogs_aggregate_only=True,
            acknowledges_officer_comp_aggregate_only=True,
        )
        r = _make_scorp_return()
        r.total_assets = 500000.0  # over the $250k threshold
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("Schedule L", str(cm.exception))

    def test_section_1375_gate_fires_on_nonzero_passive_income_tax(self):
        from tenforty.attestations import enforce_compute_time
        from tests._scorp_fixtures import _make_scorp_return
        from tenforty.models import (
            FilingStatus, Scenario, TaxReturnConfig,
        )
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="01-01-1980", state="EX",
            has_foreign_accounts=False, prior_year_itemized=False,
            acknowledges_no_1120s_schedule_l_needed=True,
            acknowledges_no_1120s_schedule_m_needed=True,
            acknowledges_constant_shareholder_ownership=True,
            acknowledges_no_section_1375_tax=False,  # gate is FALSE
            acknowledges_no_section_1374_tax=True,
            acknowledges_cogs_aggregate_only=True,
            acknowledges_officer_comp_aggregate_only=True,
        )
        r = _make_scorp_return()
        r.scope_outs.net_passive_income_tax = 100.0  # triggers the gate
        s = Scenario(config=cfg, s_corp_return=r)
        with self.assertRaises(NotImplementedError) as cm:
            enforce_compute_time(s)
        self.assertIn("1375", str(cm.exception))

    def test_section_1375_gate_does_not_fire_when_attestation_true(self):
        """Sanity-check the inverse: ack=True + nonzero scope-out value
        runs cleanly. Confirms the gate is not over-eager."""
        from tenforty.attestations import enforce_compute_time
        from tests._scorp_fixtures import _make_scorp_return
        from tenforty.models import (
            FilingStatus, Scenario, TaxReturnConfig,
        )
        cfg = TaxReturnConfig(
            year=2025, filing_status=FilingStatus.SINGLE,
            birthdate="01-01-1980", state="EX",
            has_foreign_accounts=False, prior_year_itemized=False,
            acknowledges_no_1120s_schedule_l_needed=True,
            acknowledges_no_1120s_schedule_m_needed=True,
            acknowledges_constant_shareholder_ownership=True,
            acknowledges_no_section_1375_tax=True,  # ack=True
            acknowledges_no_section_1374_tax=True,
            acknowledges_cogs_aggregate_only=True,
            acknowledges_officer_comp_aggregate_only=True,
        )
        r = _make_scorp_return()
        r.scope_outs.net_passive_income_tax = 100.0  # nonzero, but acked
        s = Scenario(config=cfg, s_corp_return=r)
        # No raise expected.
        enforce_compute_time(s)
