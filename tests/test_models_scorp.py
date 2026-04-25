"""Unit tests for 1120-S data model dataclasses."""

import unittest

from tenforty.models import AccountingMethod, Address, SCorpScheduleBAnswers, SCorpShareholder

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
