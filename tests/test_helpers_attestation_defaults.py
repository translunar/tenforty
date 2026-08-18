"""Regression snapshot for the scope-out attestation defaults helper.

The helper is auto-derived from `tenforty.attestations._ATTESTATIONS`, but
this test pins the exact dict the helper produces today as a hardcoded
golden value. If a future registry change silently shifts what
`scope_out_attestation_defaults()` returns, this test fails loudly. The
hardcoded `True` set documents the four "common test posture" affirmations
that override the auto-derived `False` default."""

import unittest

from tests.helpers import scope_out_attestation_defaults


class ScopeOutAttestationDefaultsSnapshotTests(unittest.TestCase):
    def test_returns_exact_expected_dict(self):
        expected = {
            "has_foreign_accounts": False,
            "acknowledges_sch_a_sales_tax_unsupported": False,
            "acknowledges_qbi_below_threshold": False,
            "acknowledges_unlimited_at_risk": True,
            "basis_tracked_externally": True,
            "acknowledges_no_partnership_se_earnings": False,
            "acknowledges_no_section_1231_gain": False,
            "acknowledges_no_more_than_four_k1s": False,
            "acknowledges_no_k1_credits": True,
            "acknowledges_no_section_179": False,
            "acknowledges_no_estate_trust_k1": False,
            "prior_year_itemized": False,
            "acknowledges_no_wash_sale_adjustments": False,
            "acknowledges_no_other_basis_adjustments": False,
            "acknowledges_no_28_rate_gain": False,
            "acknowledges_no_unrecaptured_section_1250": False,
            "acknowledges_no_1120s_schedule_l_needed": False,
            "acknowledges_no_1120s_schedule_m_needed": False,
            "acknowledges_constant_shareholder_ownership": False,
            "acknowledges_no_section_1375_tax": False,
            "acknowledges_no_section_1374_tax": False,
            "acknowledges_cogs_aggregate_only": False,
            "acknowledges_officer_comp_aggregate_only": False,
            "acknowledges_no_elective_payment_election": False,
            "acknowledges_no_540nr_filing": False,
            "acknowledges_no_ca_amt_preferences": False,
            "acknowledges_no_ca_nol_carryover": False,
            "acknowledges_no_ca_depreciation_divergence": False,
            "acknowledges_no_ca_ira_basis_divergence": False,
            "acknowledges_no_ca_rdp_status": False,
            "acknowledges_no_excess_business_loss_carryover": False,
            "acknowledges_no_1031_personal_property_divergence": False,
            "acknowledges_no_ic_worker_reclassification": False,
            "acknowledges_no_other_state_tax_credit": False,
            "acknowledges_no_railroad_retirement_benefits": False,
            "acknowledges_no_paid_family_leave_benefits": False,
            "acknowledges_no_capital_loss_carryforward": True,
            "acknowledges_no_federal_amt": True,
        }
        self.assertEqual(expected, scope_out_attestation_defaults())
