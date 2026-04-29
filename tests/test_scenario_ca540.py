"""Loader tests for YAML scenarios with ca540 sub-object."""

import tempfile
import textwrap
import unittest
from pathlib import Path

from tenforty.models import CA540Return, DivergenceDirection, DivergenceSource
from tenforty.scenario import load_scenario


_YAML_WITHOUT_CA540 = textwrap.dedent("""\
    config:
      year: 2025
      filing_status: single
      birthdate: "01-01-1980"
      state: CA
      first_name: "Taxpayer"
      last_name: "A"
      ssn: "000-00-0000"
      has_foreign_accounts: false
      prior_year_itemized: false
      acknowledges_sch_a_sales_tax_unsupported: false
      acknowledges_qbi_below_threshold: false
      acknowledges_unlimited_at_risk: false
      basis_tracked_externally: false
      acknowledges_no_partnership_se_earnings: false
      acknowledges_no_section_1231_gain: false
      acknowledges_no_more_than_four_k1s: false
      acknowledges_no_k1_credits: false
      acknowledges_no_section_179: false
      acknowledges_no_estate_trust_k1: false
      acknowledges_no_wash_sale_adjustments: false
      acknowledges_no_other_basis_adjustments: false
      acknowledges_no_28_rate_gain: false
      acknowledges_no_unrecaptured_section_1250: false
      acknowledges_no_1120s_schedule_l_needed: false
      acknowledges_no_1120s_schedule_m_needed: false
      acknowledges_constant_shareholder_ownership: false
      acknowledges_no_section_1375_tax: false
      acknowledges_no_section_1374_tax: false
      acknowledges_cogs_aggregate_only: false
      acknowledges_officer_comp_aggregate_only: false
      acknowledges_no_elective_payment_election: false
      acknowledges_no_540nr_filing: false
      acknowledges_no_ca_amt_preferences: false
      acknowledges_no_ca_sch_d_federal_state_divergence: false
      acknowledges_no_ca_nol_carryover: false
      acknowledges_no_ca_depreciation_divergence: false
      acknowledges_no_ca_ira_basis_divergence: false
      acknowledges_no_ca_rdp_status: false
      acknowledges_no_excess_business_loss_carryover: false
      acknowledges_no_1031_personal_property_divergence: false
      acknowledges_no_ic_worker_reclassification: false
      acknowledges_no_other_state_tax_credit: false
""")


_YAML_WITH_CA540 = textwrap.dedent("""\
    config:
      year: 2025
      filing_status: single
      birthdate: "01-01-1980"
      state: CA
      first_name: "Taxpayer"
      last_name: "A"
      ssn: "000-00-0000"
      has_foreign_accounts: false
      prior_year_itemized: false
      acknowledges_sch_a_sales_tax_unsupported: false
      acknowledges_qbi_below_threshold: false
      acknowledges_unlimited_at_risk: false
      basis_tracked_externally: false
      acknowledges_no_partnership_se_earnings: false
      acknowledges_no_section_1231_gain: false
      acknowledges_no_more_than_four_k1s: false
      acknowledges_no_k1_credits: false
      acknowledges_no_section_179: false
      acknowledges_no_estate_trust_k1: false
      acknowledges_no_wash_sale_adjustments: false
      acknowledges_no_other_basis_adjustments: false
      acknowledges_no_28_rate_gain: false
      acknowledges_no_unrecaptured_section_1250: false
      acknowledges_no_1120s_schedule_l_needed: false
      acknowledges_no_1120s_schedule_m_needed: false
      acknowledges_constant_shareholder_ownership: false
      acknowledges_no_section_1375_tax: false
      acknowledges_no_section_1374_tax: false
      acknowledges_cogs_aggregate_only: false
      acknowledges_officer_comp_aggregate_only: false
      acknowledges_no_elective_payment_election: false
      acknowledges_no_540nr_filing: false
      acknowledges_no_ca_amt_preferences: false
      acknowledges_no_ca_sch_d_federal_state_divergence: false
      acknowledges_no_ca_nol_carryover: false
      acknowledges_no_ca_depreciation_divergence: false
      acknowledges_no_ca_ira_basis_divergence: false
      acknowledges_no_ca_rdp_status: false
      acknowledges_no_excess_business_loss_carryover: false
      acknowledges_no_1031_personal_property_divergence: false
      acknowledges_no_ic_worker_reclassification: false
      acknowledges_no_other_state_tax_credit: false
    ca540:
      estimated_payments: 1500.0
      use_tax: 25.0
      divergences:
        - source: worksheet
          sch_ca_line: "Part I §C 13"
          direction: subtraction
          amount: 4300.0
          description: "HSA contribution disallowed"
          pub1001_ref: "p.9"
""")


class CA540YamlLoaderTests(unittest.TestCase):
    def _write_and_load(self, yaml_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario.yaml"
            path.write_text(yaml_text)
            return load_scenario(path)

    def test_load_scenario_without_ca540_block(self):
        scenario = self._write_and_load(_YAML_WITHOUT_CA540)
        self.assertIsNone(scenario.ca540)

    def test_load_scenario_with_ca540_block(self):
        scenario = self._write_and_load(_YAML_WITH_CA540)
        self.assertIsInstance(scenario.ca540, CA540Return)
        self.assertEqual(scenario.ca540.estimated_payments, 1500.0)
        self.assertEqual(scenario.ca540.use_tax, 25.0)
        self.assertEqual(len(scenario.ca540.divergences), 1)
        self.assertEqual(scenario.ca540.divergences[0].source, DivergenceSource.WORKSHEET)
        self.assertEqual(scenario.ca540.divergences[0].direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(scenario.ca540.divergences[0].sch_ca_line, "Part I §C 13")
        self.assertEqual(scenario.ca540.divergences[0].amount, 4300.0)
        self.assertEqual(scenario.ca540.divergences[0].description, "HSA contribution disallowed")
        self.assertEqual(scenario.ca540.divergences[0].pub1001_ref, "p.9")
