"""Unit tests for tenforty.forms.f1120s.compute — native Form 1120-S.

Expected values come from manual arithmetic over the IRS 2025 Form 1120-S
instructions. These tests do NOT import or reference any oracle module.
"""

import unittest

from tenforty.forms import f1120s
from tenforty.models import (
    AccountingMethod, Address, K1Allocation, K1AllocationEntity,
    K1AllocationShareholder, SCorpShareholder,
)

from tests._scorp_fixtures import _example_address, _make_v1_scenario


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


class PaymentsAndBalanceTests(unittest.TestCase):
    def test_line_23_total_payments_sums_23a_through_23e(self):
        s = _make_v1_scenario()
        s.s_corp_return.payments.estimated_tax_payments = 600.0
        s.s_corp_return.payments.prior_year_overpayment_credited = 100.0
        s.s_corp_return.payments.tax_deposited_with_7004 = 200.0
        s.s_corp_return.payments.credit_for_federal_excise_tax = 50.0
        s.s_corp_return.payments.refundable_credits = 25.0
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_23_total_payments"], 975.0)

    def test_line_24_amount_owed_when_tax_exceeds_payments(self):
        """IRS line 24 (amount owed) = line 22 − line 23 when positive.
        Uses the v1 fixture's ack=True default; sets a nonzero §1375
        scope-out and a smaller payments total."""
        s = _make_v1_scenario()
        s.s_corp_return.scope_outs.net_passive_income_tax = 1000.0
        s.s_corp_return.payments.estimated_tax_payments = 600.0
        out = f1120s.compute(s, upstream={})
        # tax 1000, payments 600, owed 400
        self.assertEqual(out["f1120s_line_24_amount_owed"], 400.0)
        self.assertEqual(out["f1120s_line_26_overpayment"], 0.0)

    def test_line_26_overpayment_when_payments_exceed_tax(self):
        s = _make_v1_scenario()
        s.s_corp_return.scope_outs.net_passive_income_tax = 100.0
        s.s_corp_return.payments.estimated_tax_payments = 400.0
        out = f1120s.compute(s, upstream={})
        # tax 100, payments 400, overpayment 300
        self.assertEqual(out["f1120s_line_24_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_line_26_overpayment"], 300.0)

    def test_line_24_and_26_both_zero_when_exactly_balanced(self):
        s = _make_v1_scenario()
        out = f1120s.compute(s, upstream={})
        # tax 0, payments 0, owed 0, overpayment 0
        self.assertEqual(out["f1120s_line_24_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_line_26_overpayment"], 0.0)

    def test_lines_25_and_27_emit_zero_placeholders(self):
        """Line 25 (Form 2220 penalty) and line 27 (overpayment credited
        to next year) are scope-out placeholders in v1; emit 0.0 so the
        PDF mapping has compute keys for both fields."""
        s = _make_v1_scenario()
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_25_estimated_tax_penalty"], 0.0)
        self.assertEqual(out["f1120s_line_27_credited_to_next_year"], 0.0)


class ScheduleBPassthroughTests(unittest.TestCase):
    def test_schedule_b_answers_appear_verbatim_in_output(self):
        s = _make_v1_scenario()
        sb = s.s_corp_return.schedule_b_answers
        sb.accounting_method = AccountingMethod.ACCRUAL
        sb.business_activity_code = "999999"
        sb.business_activity_description = "Other services"
        sb.product_or_service = "Consulting services"
        sb.any_c_corp_subsidiaries = False
        sb.has_any_foreign_shareholders = False
        sb.owns_foreign_entity = False
        out = f1120s.compute(s, upstream={})
        # accounting_method explodes into three exclusive booleans for
        # PDF checkbox fill.
        self.assertFalse(out["f1120s_sch_b_accounting_method_cash"])
        self.assertTrue(out["f1120s_sch_b_accounting_method_accrual"])
        self.assertFalse(out["f1120s_sch_b_accounting_method_other"])
        self.assertEqual(out["f1120s_sch_b_business_activity_code"], "999999")
        self.assertEqual(
            out["f1120s_sch_b_business_activity_description"],
            "Other services",
        )
        self.assertEqual(
            out["f1120s_sch_b_product_or_service"],
            "Consulting services",
        )
        self.assertFalse(out["f1120s_sch_b_any_c_corp_subsidiaries"])
        self.assertFalse(out["f1120s_sch_b_has_any_foreign_shareholders"])
        self.assertFalse(out["f1120s_sch_b_owns_foreign_entity"])

    def test_accounting_method_cash_explodes_correctly(self):
        s = _make_v1_scenario()
        s.s_corp_return.schedule_b_answers.accounting_method = (
            AccountingMethod.CASH
        )
        out = f1120s.compute(s, upstream={})
        self.assertTrue(out["f1120s_sch_b_accounting_method_cash"])
        self.assertFalse(out["f1120s_sch_b_accounting_method_accrual"])
        self.assertFalse(out["f1120s_sch_b_accounting_method_other"])

    def test_accounting_method_other_explodes_correctly(self):
        s = _make_v1_scenario()
        s.s_corp_return.schedule_b_answers.accounting_method = (
            AccountingMethod.OTHER
        )
        out = f1120s.compute(s, upstream={})
        self.assertFalse(out["f1120s_sch_b_accounting_method_cash"])
        self.assertFalse(out["f1120s_sch_b_accounting_method_accrual"])
        self.assertTrue(out["f1120s_sch_b_accounting_method_other"])


class ScheduleKTotalsTests(unittest.TestCase):
    def test_sch_k_line_1_equals_main_form_line_21(self):
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out = f1120s.compute(s, upstream={})
        self.assertEqual(
            out["f1120s_sch_k_line_1_ordinary_business_income"],
            70000.0,
        )
        self.assertEqual(
            out["f1120s_sch_k_line_1_ordinary_business_income"],
            out["f1120s_line_21_ordinary_business_income"],
        )

    def test_sch_k_lines_2_through_18_present_and_zero_for_v1_profile(self):
        s = _make_v1_scenario()
        out = f1120s.compute(s, upstream={})
        for line_number_field in (
            "f1120s_sch_k_line_2_net_rental_real_estate",
            "f1120s_sch_k_line_3c_other_net_rental_income",
            "f1120s_sch_k_line_4_interest_income",
            "f1120s_sch_k_line_5a_ordinary_dividends",
            "f1120s_sch_k_line_6_royalties",
            "f1120s_sch_k_line_7_net_short_term_capital_gain",
            "f1120s_sch_k_line_8a_net_long_term_capital_gain",
            "f1120s_sch_k_line_9_net_section_1231_gain",
            "f1120s_sch_k_line_10_other_income",
            "f1120s_sch_k_line_11_section_179_deduction",
            "f1120s_sch_k_line_12a_charitable_contributions",
            "f1120s_sch_k_line_13a_low_income_housing_credit",
            "f1120s_sch_k_line_14_foreign_transactions",
            "f1120s_sch_k_line_15_amt_items",
            "f1120s_sch_k_line_16a_tax_exempt_interest",
            "f1120s_sch_k_line_17a_investment_income",
            "f1120s_sch_k_line_18_income_loss_reconciliation",
        ):
            self.assertEqual(out[line_number_field], 0.0,
                             f"{line_number_field} should be 0.0")


class ScheduleK1AllocationTests(unittest.TestCase):
    def test_single_shareholder_at_100_gets_full_obi(self):
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        out = f1120s.compute(s, upstream={})
        k1s = out["f1120s_sch_k1_allocations"]
        self.assertEqual(len(k1s), 1)
        self.assertIsInstance(k1s[0], K1Allocation)
        self.assertEqual(k1s[0].shareholder.name, "Taxpayer A")
        self.assertEqual(k1s[0].ownership_percentage, 100.0)
        # OBI = 70000, 100% share = 70000
        self.assertEqual(k1s[0].box_1_ordinary_business_income, 70000.0)

    def test_two_shareholders_60_40_split(self):
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        # Replace sole shareholder with two shareholders 60/40.
        s.s_corp_return.shareholders = [
            SCorpShareholder(
                name="Taxpayer A", ssn_or_ein="000-00-0000",
                address=_example_address(), ownership_percentage=60.0,
            ),
            SCorpShareholder(
                name="Taxpayer B", ssn_or_ein="000-00-0001",
                address=Address(
                    street="2 Example Ave", city="Example City",
                    state="EX", zip_code="00000",
                ),
                ownership_percentage=40.0,
            ),
        ]
        out = f1120s.compute(s, upstream={})
        k1s = out["f1120s_sch_k1_allocations"]
        self.assertEqual(len(k1s), 2)
        # OBI = 70000; A gets 60% = 42000; B gets 40% = 28000
        self.assertEqual(k1s[0].box_1_ordinary_business_income, 42000.0)
        self.assertEqual(k1s[1].box_1_ordinary_business_income, 28000.0)

    def test_allocations_sum_equals_sch_k_line_1(self):
        """Pro-rata invariant: sum of shareholder box-1 = Sch K line 1."""
        s = _make_v1_scenario(
            gross_receipts=100000.0,
            compensation_of_officers=30000.0,
        )
        s.s_corp_return.shareholders = [
            SCorpShareholder(
                name="Taxpayer A", ssn_or_ein="000-00-0000",
                address=_example_address(), ownership_percentage=33.333,
            ),
            SCorpShareholder(
                name="Taxpayer B", ssn_or_ein="000-00-0001",
                address=_example_address(), ownership_percentage=33.333,
            ),
            SCorpShareholder(
                name="Taxpayer C", ssn_or_ein="000-00-0002",
                address=_example_address(), ownership_percentage=33.334,
            ),
        ]
        out = f1120s.compute(s, upstream={})
        k1s = out["f1120s_sch_k1_allocations"]
        total = sum(k.box_1_ordinary_business_income for k in k1s)
        # Pro-rata invariant must hold to within $0.01 (float accumulation
        # on percentages summing to exactly 100.0). The OBI of $70,000
        # split 33.333/33.333/33.334 should sum back to $70,000 ± 0.01.
        self.assertAlmostEqual(
            total, out["f1120s_sch_k_line_1_ordinary_business_income"],
            places=2,
        )

    def test_shareholder_and_entity_identity_passed_through_nested(self):
        s = _make_v1_scenario()
        out = f1120s.compute(s, upstream={})
        k1 = out["f1120s_sch_k1_allocations"][0]
        # Typed nested structure: K1Allocation with entity/shareholder
        # sub-dataclasses; address is the shared Address dataclass.
        self.assertIsInstance(k1.shareholder, K1AllocationShareholder)
        self.assertIsInstance(k1.entity, K1AllocationEntity)
        self.assertIsInstance(k1.shareholder.address, Address)
        self.assertEqual(k1.shareholder.name, "Taxpayer A")
        self.assertEqual(k1.shareholder.ssn_or_ein, "000-00-0000")
        self.assertEqual(k1.shareholder.address.street, "1 Example Ave")
        self.assertEqual(k1.shareholder.address.city, "Example City")
        self.assertEqual(k1.entity.name, "Example S-Corp Inc.")
        self.assertEqual(k1.entity.ein, "00-0000000")
        self.assertEqual(k1.entity.address.street, "1 Example Ave")
        self.assertEqual(k1.entity.address.zip_code, "00000")
