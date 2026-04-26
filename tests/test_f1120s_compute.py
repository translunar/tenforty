"""Unit tests for tenforty.forms.f1120s.compute — native Form 1120-S.

Expected values come from manual arithmetic over the IRS 2025 Form 1120-S
instructions. These tests do NOT import or reference any oracle module.
"""

import unittest

from tenforty.forms import f1120s

from tests._scorp_fixtures import _make_v1_scenario


class IncomeSectionTests(unittest.TestCase):
    def test_line_1a_matches_gross_receipts(self):
        s = _make_v1_scenario(gross_receipts=100000.0)
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_1a_gross_receipts"], 100000.0)

    def test_line_1c_equals_1a_minus_1b(self):
        """IRS line 1c = line 1a − line 1b (returns and allowances)."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.returns_and_allowances = 500.0
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_1c_net_receipts"], 99500.0)

    def test_line_3_equals_1c_minus_2(self):
        """IRS line 3 gross profit = line 1c − line 2 (COGS)."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.cogs_aggregate = 20000.0
        out = f1120s.compute(s, upstream={})
        # 1c = 100000 - 0 = 100000; 3 = 100000 - 20000 = 80000
        self.assertEqual(out["f1120s_line_3_gross_profit"], 80000.0)

    def test_line_6_total_income_sums_3_4_5(self):
        """IRS line 6 = line 3 + line 4 + line 5."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.net_gain_loss_4797 = 2000.0
        s.s_corp_return.income.other_income = 500.0
        out = f1120s.compute(s, upstream={})
        # 3 = 100000; 4 = 2000; 5 = 500; total = 102500
        self.assertEqual(out["f1120s_line_6_total_income"], 102500.0)


class DeductionsSectionTests(unittest.TestCase):
    def test_line_20_total_deductions_sums_7_through_19(self):
        s = _make_v1_scenario()
        s.s_corp_return.deductions.compensation_of_officers = 30000.0
        s.s_corp_return.deductions.salaries_wages = 5000.0
        s.s_corp_return.deductions.rents = 12000.0
        s.s_corp_return.deductions.taxes_licenses = 1500.0
        s.s_corp_return.deductions.other_deductions = 2500.0
        out = f1120s.compute(s, upstream={})
        # 30000 + 5000 + 12000 + 1500 + 2500 = 51000
        self.assertEqual(out["f1120s_line_20_total_deductions"], 51000.0)

    def test_line_21_ordinary_business_income_equals_6_minus_20(self):
        """IRS line 21 (OBI) = line 6 − line 20."""
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out = f1120s.compute(s, upstream={})
        # line 6 = 100000, line 20 = 30000, OBI = 70000
        self.assertEqual(out["f1120s_line_21_ordinary_business_income"], 70000.0)

    def test_line_21_obi_can_be_negative(self):
        """Ordinary business loss flows through as a negative line 21."""
        s = _make_v1_scenario(
            gross_receipts=30000.0,
            compensation_of_officers=50000.0,
        )
        out = f1120s.compute(s, upstream={})
        # line 6 = 30000, line 20 = 50000, OBI = -20000
        self.assertEqual(out["f1120s_line_21_ordinary_business_income"], -20000.0)

    def test_all_thirteen_deduction_lines_emitted(self):
        s = _make_v1_scenario()
        s.s_corp_return.deductions.compensation_of_officers = 30000.0
        s.s_corp_return.deductions.salaries_wages = 1.0
        s.s_corp_return.deductions.repairs_maintenance = 2.0
        s.s_corp_return.deductions.bad_debts = 3.0
        s.s_corp_return.deductions.rents = 4.0
        s.s_corp_return.deductions.taxes_licenses = 5.0
        s.s_corp_return.deductions.interest = 6.0
        s.s_corp_return.deductions.depreciation = 7.0
        s.s_corp_return.deductions.depletion = 8.0
        s.s_corp_return.deductions.advertising = 9.0
        s.s_corp_return.deductions.pension_profit_sharing_plans = 10.0
        s.s_corp_return.deductions.employee_benefits = 11.0
        s.s_corp_return.deductions.other_deductions = 12.0
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_7_compensation_of_officers"], 30000.0)
        self.assertEqual(out["f1120s_line_8_salaries_wages"], 1.0)
        self.assertEqual(out["f1120s_line_9_repairs_maintenance"], 2.0)
        self.assertEqual(out["f1120s_line_10_bad_debts"], 3.0)
        self.assertEqual(out["f1120s_line_11_rents"], 4.0)
        self.assertEqual(out["f1120s_line_12_taxes_licenses"], 5.0)
        self.assertEqual(out["f1120s_line_13_interest"], 6.0)
        self.assertEqual(out["f1120s_line_14_depreciation"], 7.0)
        self.assertEqual(out["f1120s_line_15_depletion"], 8.0)
        self.assertEqual(out["f1120s_line_16_advertising"], 9.0)
        self.assertEqual(out["f1120s_line_17_pension_profit_sharing"], 10.0)
        self.assertEqual(out["f1120s_line_18_employee_benefits"], 11.0)
        self.assertEqual(out["f1120s_line_19_other_deductions"], 12.0)


class TotalTaxTests(unittest.TestCase):
    def test_line_22_is_sum_of_scope_out_amounts(self):
        """IRS line 22 (total tax) = line 22a + 22b + 22c.

        All three are scope-out values supplied by the caller; tenforty v1
        does not compute §1375, §1374, or §453 interest itself. The v1
        fixture's `acknowledges_no_section_137{4,5}_tax = True` defaults
        affirm the scope-out posture; supplying a nonzero scope_outs value
        is then accepted (gate fires only when ack=False AND nonzero).
        """
        s = _make_v1_scenario()
        s.s_corp_return.scope_outs.net_passive_income_tax = 1000.0
        s.s_corp_return.scope_outs.built_in_gains_tax = 500.0
        s.s_corp_return.scope_outs.interest_on_453_deferred = 50.0
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_22a_net_passive_income_tax"], 1000.0)
        self.assertEqual(out["f1120s_line_22b_built_in_gains_tax"], 500.0)
        self.assertEqual(out["f1120s_line_22c_interest_on_453_deferred"], 50.0)
        self.assertEqual(out["f1120s_line_22_total_tax"], 1550.0)

    def test_line_22_is_zero_when_all_scope_out_amounts_zero(self):
        s = _make_v1_scenario()
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_22_total_tax"], 0.0)
