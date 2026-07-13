"""Loader tests for the optional s_corp_return.ca sub-block."""

import tempfile
import textwrap
import unittest
from pathlib import Path

from tenforty.scenario import load_scenario


_YAML_WITH_SCORP_NO_CA = textwrap.dedent("""\
    config:
      year: 2025
      filing_status: single
      birthdate: "01-01-1980"
      state: EX
      first_name: "Taxpayer"
      last_name: "A"
      ssn: "000-00-0000"
      # Pre-existing attestations from Plan D / Sub-plan 1 (all required
      # to be non-None at load time). Mirrors the helper
      # `tests.helpers.scope_out_attestation_defaults()`.
      has_foreign_accounts: false
      prior_year_itemized: false
      acknowledges_sch_a_sales_tax_unsupported: false
      acknowledges_qbi_below_threshold: false
      acknowledges_unlimited_at_risk: true
      basis_tracked_externally: true
      acknowledges_no_partnership_se_earnings: false
      acknowledges_no_section_1231_gain: false
      acknowledges_no_more_than_four_k1s: false
      acknowledges_no_k1_credits: true
      acknowledges_no_section_179: false
      acknowledges_no_estate_trust_k1: false
      acknowledges_no_wash_sale_adjustments: false
      acknowledges_no_other_basis_adjustments: false
      acknowledges_no_28_rate_gain: false
      acknowledges_no_unrecaptured_section_1250: false
      # 1120-S-specific attestations introduced by Sub-plan 2.
      acknowledges_no_1120s_schedule_l_needed: true
      acknowledges_no_1120s_schedule_m_needed: true
      acknowledges_constant_shareholder_ownership: true
      acknowledges_no_section_1375_tax: true
      acknowledges_no_section_1374_tax: true
      acknowledges_cogs_aggregate_only: true
      acknowledges_officer_comp_aggregate_only: true
      acknowledges_no_elective_payment_election: true
      # CA-specific scope-out attestations (Sub-plan 3, Task 3)
      acknowledges_no_540nr_filing: false
      acknowledges_no_ca_amt_preferences: false
      acknowledges_no_ca_nol_carryover: false
      acknowledges_no_ca_depreciation_divergence: false
      acknowledges_no_ca_ira_basis_divergence: false
      acknowledges_no_ca_rdp_status: false
      acknowledges_no_excess_business_loss_carryover: false
      acknowledges_no_1031_personal_property_divergence: false
      acknowledges_no_ic_worker_reclassification: false
      acknowledges_no_other_state_tax_credit: false
      acknowledges_no_railroad_retirement_benefits: false
      acknowledges_no_paid_family_leave_benefits: false
    s_corp_return:
      name: "Example S-Corp Inc."
      ein: "00-0000000"
      address:
        street: "1 Example Ave"
        city: "Example City"
        state: "EX"
        zip_code: "00000"
      date_incorporated: 2020-01-01
      s_election_effective_date: 2020-01-01
      total_assets: 50000.0
      income:
        gross_receipts: 100000.0
        returns_and_allowances: 0.0
        cogs_aggregate: 0.0
        net_gain_loss_4797: 0.0
        other_income: 0.0
      deductions:
        compensation_of_officers: 30000.0
        salaries_wages: 0.0
        repairs_maintenance: 0.0
        bad_debts: 0.0
        rents: 0.0
        taxes_licenses: 0.0
        interest: 0.0
        depreciation: 0.0
        depletion: 0.0
        advertising: 0.0
        pension_profit_sharing_plans: 0.0
        employee_benefits: 0.0
        other_deductions: 0.0
      schedule_b_answers:
        accounting_method: cash
        business_activity_code: "541990"
        business_activity_description: "Services"
        product_or_service: "Consulting"
        any_c_corp_subsidiaries: false
        has_any_foreign_shareholders: false
        owns_foreign_entity: false
      shareholders:
        - name: "Taxpayer A"
          ssn_or_ein: "000-00-0000"
          address:
            street: "1 Example Ave"
            city: "Example City"
            state: "EX"
            zip_code: "00000"
          ownership_percentage: 100.0
""")


# NOTE: `_YAML_WITH_SCORP_NO_CA` is `textwrap.dedent`-ed, which strips the
# common 4-space source indent. In the resulting YAML the direct children of
# `s_corp_return` (name/income/shareholders) sit at 2-space indent, and the
# shareholder-mapping keys sit at 6-space indent. The brief's 6-space `ca:`
# collided with the shareholder keys and PyYAML absorbed `ca` into the last
# shareholder. Placing `ca:` at 2-space indent (fields at 4) makes it a true
# sibling of `s_corp_return`'s keys.
_CA_BLOCK = (
    "  ca:\n"
    "    first_year: false\n"
    "    estimated_tax_payments: 0.0\n"
    "    prior_year_overpayment_applied: 0.0\n"
    "    state_tax_deducted_federally: 0.0\n"
    "    depreciation_adjustment: 0.0\n"
    "    apportionment_ca_only: true\n"
)
_YAML_WITH_SCORP_CA = _YAML_WITH_SCORP_NO_CA + _CA_BLOCK


class ScorpCALoaderTests(unittest.TestCase):
    def _write_and_load(self, yaml_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario.yaml"
            path.write_text(yaml_text)
            return load_scenario(path)

    def test_ca_block_loads(self):
        s = self._write_and_load(_YAML_WITH_SCORP_CA)
        self.assertIsNotNone(s.s_corp_return.ca)
        self.assertTrue(s.s_corp_return.ca.apportionment_ca_only)
        self.assertFalse(s.s_corp_return.ca.first_year)

    def test_unknown_key_fails_closed(self):
        bad = _YAML_WITH_SCORP_CA.replace(
            "    apportionment_ca_only: true\n",
            "    apportionment_ca_only: true\n    typo_key: 1\n")
        with self.assertRaises(ValueError):
            self._write_and_load(bad)

    def test_missing_required_key_raises_valueerror(self):
        # Dropping a required key must fail-closed with ValueError (contract
        # consistency with the docstring), not fall through to a bare KeyError.
        bad = _YAML_WITH_SCORP_CA.replace(
            "    depreciation_adjustment: 0.0\n", "")
        with self.assertRaises(ValueError):
            self._write_and_load(bad)

    def test_absent_ca_block_is_none(self):
        s = self._write_and_load(_YAML_WITH_SCORP_NO_CA)
        self.assertIsNone(s.s_corp_return.ca)

    def test_non_ca_apportionment_raises_at_load(self):
        bad = _YAML_WITH_SCORP_CA.replace(
            "apportionment_ca_only: true", "apportionment_ca_only: false")
        with self.assertRaises(ValueError):
            self._write_and_load(bad)
