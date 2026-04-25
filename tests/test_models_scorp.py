"""Unit tests for 1120-S data model dataclasses."""

import unittest

from tenforty.models import (
    AccountingMethod,
    Address,
    SCorpDeductions,
    SCorpIncome,
    SCorpPayments,
    SCorpScheduleBAnswers,
    SCorpScopeOuts,
    SCorpShareholder,
)

from tests._scorp_fixtures import _example_address


class AddressTests(unittest.TestCase):
    def test_construct_with_all_fields(self):
        a = _example_address()
        self.assertEqual(a.street, "1 Example Ave")
        self.assertEqual(a.city, "Example City")
        self.assertEqual(a.state, "EX")
        self.assertEqual(a.zip_code, "00000")


class SCorpShareholderTests(unittest.TestCase):
    def test_construct_with_all_fields(self):
        sh = SCorpShareholder(
            name="Taxpayer A",
            ssn_or_ein="000-00-0000",
            address=_example_address(),
            ownership_percentage=100.0,
        )
        self.assertEqual(sh.name, "Taxpayer A")
        self.assertEqual(sh.ownership_percentage, 100.0)
        self.assertEqual(sh.address.street, "1 Example Ave")

    def test_ownership_percentage_is_float(self):
        sh = SCorpShareholder(
            name="Taxpayer A",
            ssn_or_ein="000-00-0000",
            address=_example_address(),
            ownership_percentage=50.0,
        )
        self.assertIsInstance(sh.ownership_percentage, float)

    def test_address_is_address_dataclass(self):
        sh = SCorpShareholder(
            name="Taxpayer A",
            ssn_or_ein="000-00-0000",
            address=_example_address(),
            ownership_percentage=100.0,
        )
        self.assertIsInstance(sh.address, Address)


class SCorpScheduleBAnswersTests(unittest.TestCase):
    def test_construct_with_all_fields(self):
        sb = SCorpScheduleBAnswers(
            accounting_method=AccountingMethod.CASH,
            business_activity_code="541990",
            business_activity_description="Services",
            product_or_service="Consulting",
            any_c_corp_subsidiaries=False,
            has_any_foreign_shareholders=False,
            owns_foreign_entity=False,
        )
        self.assertEqual(sb.accounting_method, AccountingMethod.CASH)
        self.assertEqual(sb.business_activity_code, "541990")

    def test_accounting_method_accepts_all_three_values(self):
        for m in (AccountingMethod.CASH, AccountingMethod.ACCRUAL,
                  AccountingMethod.OTHER):
            sb = SCorpScheduleBAnswers(
                accounting_method=m,
                business_activity_code="541990",
                business_activity_description="Services",
                product_or_service="Consulting",
                any_c_corp_subsidiaries=False,
                has_any_foreign_shareholders=False,
                owns_foreign_entity=False,
            )
            self.assertEqual(sb.accounting_method, m)


class SCorpIncomeTests(unittest.TestCase):
    def test_construct(self):
        inc = SCorpIncome(
            gross_receipts=100000.0,
            returns_and_allowances=0.0,
            cogs_aggregate=0.0,
            net_gain_loss_4797=0.0,
            other_income=0.0,
        )
        self.assertEqual(inc.gross_receipts, 100000.0)


class SCorpDeductionsTests(unittest.TestCase):
    def test_construct(self):
        d = SCorpDeductions(
            compensation_of_officers=30000.0,
            salaries_wages=0.0,
            repairs_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes_licenses=0.0,
            interest=0.0,
            depreciation=0.0,
            depletion=0.0,
            advertising=0.0,
            pension_profit_sharing_plans=0.0,
            employee_benefits=0.0,
            other_deductions=0.0,
        )
        self.assertEqual(d.compensation_of_officers, 30000.0)


class SCorpScopeOutsTests(unittest.TestCase):
    def test_defaults_are_zero(self):
        s = SCorpScopeOuts()
        self.assertEqual(s.net_passive_income_tax, 0.0)
        self.assertEqual(s.built_in_gains_tax, 0.0)
        self.assertEqual(s.interest_on_453_deferred, 0.0)


class SCorpPaymentsTests(unittest.TestCase):
    def test_defaults_are_zero(self):
        p = SCorpPayments()
        self.assertEqual(p.estimated_tax_payments, 0.0)
        self.assertEqual(p.prior_year_overpayment_credited, 0.0)
        self.assertEqual(p.tax_deposited_with_7004, 0.0)
        self.assertEqual(p.credit_for_federal_excise_tax, 0.0)
        self.assertEqual(p.refundable_credits, 0.0)
