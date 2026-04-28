"""Unit tests for 1120-S data model dataclasses."""

import datetime
import unittest

from tenforty.models import (
    AccountingMethod,
    Address,
    FilingStatus,
    SCorpDeductions,
    SCorpIncome,
    SCorpPayments,
    SCorpReturn,
    SCorpScheduleBAnswers,
    SCorpScopeOuts,
    SCorpShareholder,
    Scenario,
    TaxReturnConfig,
)

from tests._scorp_fixtures import (
    _example_address,
    _make_scorp_return,
)


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


class SCorpReturnTests(unittest.TestCase):
    def test_construct_minimal(self):
        r = _make_scorp_return()
        self.assertEqual(r.name, "Example S-Corp Inc.")
        self.assertEqual(len(r.shareholders), 1)
        self.assertEqual(r.scope_outs.net_passive_income_tax, 0.0)
        self.assertEqual(r.payments.estimated_tax_payments, 0.0)

    def test_dates_are_date_objects(self):
        r = _make_scorp_return()
        self.assertIsInstance(r.date_incorporated, datetime.date)
        self.assertIsInstance(r.s_election_effective_date, datetime.date)

    def test_address_is_address_dataclass(self):
        r = _make_scorp_return()
        self.assertIsInstance(r.address, Address)


class ScenarioSCorpFieldTests(unittest.TestCase):
    def test_s_corp_return_defaults_to_none(self):
        s = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status=FilingStatus.SINGLE,
                birthdate="01-01-1980", state="EX",
            ),
        )
        self.assertIsNone(s.s_corp_return)

    def test_s_corp_return_accepts_instance(self):
        s = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status=FilingStatus.SINGLE,
                birthdate="01-01-1980", state="EX",
            ),
            s_corp_return=_make_scorp_return(),
        )
        self.assertIsNotNone(s.s_corp_return)
        self.assertEqual(s.s_corp_return.ein, "00-0000000")
