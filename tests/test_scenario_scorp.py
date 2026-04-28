"""Loader tests for YAML scenarios with s_corp_return sub-object."""

import datetime
import tempfile
import textwrap
import unittest
from pathlib import Path

from tenforty.models import AccountingMethod, Address
from tenforty.scenario import load_scenario


_YAML_WITH_SCORP = textwrap.dedent("""\
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


_MINIMAL_NO_SCORP_YAML = textwrap.dedent("""\
    config:
      year: 2025
      filing_status: single
      birthdate: "01-01-1980"
      state: EX
      first_name: "Taxpayer"
      last_name: "A"
      ssn: "000-00-0000"
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
      # 1120-S attestations are universally declared on TaxReturnConfig
      # (load-time validation iterates the registry unconditionally), so
      # the eight 1120-S keys must appear here even when s_corp_return is
      # absent.
      acknowledges_no_1120s_schedule_l_needed: true
      acknowledges_no_1120s_schedule_m_needed: true
      acknowledges_constant_shareholder_ownership: true
      acknowledges_no_section_1375_tax: true
      acknowledges_no_section_1374_tax: true
      acknowledges_cogs_aggregate_only: true
      acknowledges_officer_comp_aggregate_only: true
      acknowledges_no_elective_payment_election: true
""")


class SCorpYamlLoaderTests(unittest.TestCase):
    def _write_and_load(self, yaml_text: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scenario.yaml"
            path.write_text(yaml_text)
            return load_scenario(path)

    def test_loads_s_corp_return_nested(self):
        s = self._write_and_load(_YAML_WITH_SCORP)
        self.assertIsNotNone(s.s_corp_return)
        self.assertEqual(s.s_corp_return.name, "Example S-Corp Inc.")
        self.assertEqual(s.s_corp_return.income.gross_receipts, 100000.0)
        self.assertEqual(len(s.s_corp_return.shareholders), 1)
        self.assertEqual(
            s.s_corp_return.shareholders[0].ownership_percentage, 100.0,
        )

    def test_loads_addresses_as_address_dataclass(self):
        s = self._write_and_load(_YAML_WITH_SCORP)
        self.assertIsInstance(s.s_corp_return.address, Address)
        self.assertEqual(s.s_corp_return.address.street, "1 Example Ave")
        self.assertEqual(s.s_corp_return.address.zip_code, "00000")
        self.assertIsInstance(
            s.s_corp_return.shareholders[0].address, Address,
        )

    def test_loads_dates_as_date_objects(self):
        s = self._write_and_load(_YAML_WITH_SCORP)
        self.assertEqual(
            s.s_corp_return.date_incorporated, datetime.date(2020, 1, 1),
        )
        self.assertIsInstance(
            s.s_corp_return.s_election_effective_date, datetime.date,
        )

    def test_loads_quoted_iso_dates_as_date_objects(self):
        """PyYAML returns str for quoted ISO dates; the loader must
        coerce them to datetime.date so SCorpReturn's typed fields hold."""
        quoted_yaml = _YAML_WITH_SCORP.replace(
            "date_incorporated: 2020-01-01",
            'date_incorporated: "2020-01-01"',
        ).replace(
            "s_election_effective_date: 2020-01-01",
            's_election_effective_date: "2020-01-01"',
        )
        s = self._write_and_load(quoted_yaml)
        self.assertEqual(
            s.s_corp_return.date_incorporated, datetime.date(2020, 1, 1),
        )
        self.assertIsInstance(
            s.s_corp_return.s_election_effective_date, datetime.date,
        )

    def test_loads_accounting_method_as_enum(self):
        s = self._write_and_load(_YAML_WITH_SCORP)
        self.assertEqual(
            s.s_corp_return.schedule_b_answers.accounting_method,
            AccountingMethod.CASH,
        )

    def test_missing_s_corp_return_is_none(self):
        s = self._write_and_load(_MINIMAL_NO_SCORP_YAML)
        self.assertIsNone(s.s_corp_return)
