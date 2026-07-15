import textwrap
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tenforty.scenario import load_scenario

_BASE = """
config:
  year: %d
  filing_status: single
  birthdate: "01-01-1980"
  state: CA
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
form_1095a:
  months:
    jan: {premium: 0, slcsp: 0, aptc: 0}
    feb: {premium: 0, slcsp: 0, aptc: 0}
    mar: {premium: 0, slcsp: 0, aptc: 0}
    apr: {premium: 0, slcsp: 0, aptc: 0}
    may: {premium: 0, slcsp: 0, aptc: 0}
    jun: {premium: 0, slcsp: 0, aptc: 0}
    jul: {premium: 0, slcsp: 0, aptc: 0}
    aug: {premium: 500.00, slcsp: 450.00, aptc: 450.00}
    sep: {premium: 500.00, slcsp: 450.00, aptc: 450.00}
    oct: {premium: 500.00, slcsp: 450.00, aptc: 450.00}
    nov: {premium: 500.00, slcsp: 450.00, aptc: 450.00}
    dec: {premium: 500.00, slcsp: 450.00, aptc: 450.00}
  received_unemployment_2021: %s
"""

# Config-only YAML (no form_1095a block) for the absent-block test. Same
# required TaxReturnConfig fields as _BASE's config, minus the form_1095a
# block, so load_scenario reaches past config parsing/attestation
# validation and exercises the absent-block None-return path.
_MINIMAL_CONFIG = _BASE.split("form_1095a:")[0] % 2024


class Form1095AScenarioTests(unittest.TestCase):
    def _load(self, text):
        with TemporaryDirectory() as d:
            p = Path(d) / "s.yaml"
            p.write_text(textwrap.dedent(text))
            return load_scenario(p)

    def test_partial_year_block_loads(self):
        s = self._load(_BASE % (2021, "true"))
        self.assertEqual(len(s.form_1095a.months), 12)
        self.assertEqual(s.form_1095a.months[7].premium, 500.00)
        self.assertTrue(s.form_1095a.received_unemployment_2021)

    def test_absent_block_is_none(self):
        s = self._load(_MINIMAL_CONFIG)
        self.assertIsNone(s.form_1095a)

    def test_missing_month_refuses(self):
        broken = (_BASE % (2021, "true")).replace(
            "    mar: {premium: 0, slcsp: 0, aptc: 0}\n", "")
        with self.assertRaisesRegex(ValueError, "mar"):
            self._load(broken)

    def test_unknown_month_row_key_refuses(self):
        broken = (_BASE % (2021, "true")).replace(
            "dec: {premium: 500.00", "dec: {premum: 500.00")
        with self.assertRaises(ValueError):
            self._load(broken)

    def test_ui_flag_outside_2021_refuses(self):
        with self.assertRaisesRegex(ValueError, "2021"):
            self._load(_BASE % (2024, "true"))
