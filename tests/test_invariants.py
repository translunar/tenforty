import unittest

from tenforty.models import (
    Form1099B,
    Form1099DIV,
    Form1099INT,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tests.invariants import (
    assert_agi_consistent,
    assert_all_income_accounted_for,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)


def _make_scenario_with_interest_and_dividends() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1990-06-15", state="CA",
        ),
        w2s=[W2(
            employer="Acme Corp", wages=100000,
            federal_tax_withheld=15000,
            ss_wages=100000, ss_tax_withheld=6200,
            medicare_wages=100000, medicare_tax_withheld=1450,
        )],
        form1099_int=[Form1099INT(payer="Bank of Example", interest=500)],
        form1099_div=[Form1099DIV(
            payer="Brokerage Inc",
            ordinary_dividends=2000, qualified_dividends=1500,
        )],
    )


class TestAssertAgiConsistent(unittest.TestCase):
    def test_passes_when_agi_equals_income_sum(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {
            "wages": 100000,
            "interest_income": 500,
            "dividend_income": 2000,
            "agi": 102500,
        }
        assert_agi_consistent(self, results, scenario)

    def test_fails_when_agi_wrong(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {
            "wages": 100000,
            "interest_income": 500,
            "dividend_income": 2000,
            "agi": 999999,
        }
        with self.assertRaises(AssertionError):
            assert_agi_consistent(self, results, scenario)


class TestAssertTaxableIncomeConsistent(unittest.TestCase):
    def test_passes_when_consistent(self):
        results = {
            "agi": 100000,
            "total_deductions": 15750,
            "taxable_income": 84250,
        }
        assert_taxable_income_consistent(self, results)

    def test_fails_when_negative(self):
        results = {
            "agi": 100000,
            "total_deductions": 15750,
            "taxable_income": -5000,
        }
        with self.assertRaises(AssertionError):
            assert_taxable_income_consistent(self, results)


class TestAssertTaxIsNonNegative(unittest.TestCase):
    def test_passes_when_positive(self):
        results = {"total_tax": 13500}
        assert_tax_is_non_negative(self, results)

    def test_passes_when_zero(self):
        results = {"total_tax": 0}
        assert_tax_is_non_negative(self, results)

    def test_fails_when_negative(self):
        results = {"total_tax": -100}
        with self.assertRaises(AssertionError):
            assert_tax_is_non_negative(self, results)


class TestAssertRefundOrOwedConsistent(unittest.TestCase):
    def test_passes_with_refund(self):
        results = {
            "total_payments": 15000,
            "total_tax": 13500,
            "overpaid": 1500,
        }
        assert_refund_or_owed_consistent(self, results)

    def test_passes_when_owed(self):
        results = {
            "total_payments": 10000,
            "total_tax": 13500,
            "overpaid": 0,
        }
        assert_refund_or_owed_consistent(self, results)

    def test_fails_when_inconsistent(self):
        results = {
            "total_payments": 10000,
            "total_tax": 13500,
            "overpaid": 5000,
        }
        with self.assertRaises(AssertionError):
            assert_refund_or_owed_consistent(self, results)


class TestAssertWithholdingMatchesInput(unittest.TestCase):
    def test_passes_when_matching(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {"federal_withheld_w2": 15000}
        assert_withholding_matches_input(self, results, scenario)

    def test_fails_when_mismatched(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {"federal_withheld_w2": 99999}
        with self.assertRaises(AssertionError):
            assert_withholding_matches_input(self, results, scenario)


class TestAssertAllIncomeAccountedFor(unittest.TestCase):
    def test_passes_when_all_income_in_agi(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {"agi": 102500}  # 100000 + 500 + 2000
        assert_all_income_accounted_for(self, results, scenario)

    def test_passes_when_agi_slightly_less_due_to_adjustments(self):
        """AGI can be less than total income (adjustments reduce it)."""
        scenario = _make_scenario_with_interest_and_dividends()
        # Total income is 102500, adjustments reduce it a bit
        results = {"agi": 102000}
        assert_all_income_accounted_for(self, results, scenario)

    def test_fails_when_income_missing(self):
        """If AGI is way below expected minimum, income was probably dropped."""
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            w2s=[W2(
                employer="Acme Corp", wages=100000,
                federal_tax_withheld=15000,
                ss_wages=100000, ss_tax_withheld=6200,
                medicare_wages=100000, medicare_tax_withheld=1450,
            )],
            form1099_b=[Form1099B(
                broker="Brokerage Inc", description="shares",
                date_acquired="2023-01-01", date_sold="2025-06-01",
                proceeds=50000, cost_basis=30000, gain_loss=20000,
            )],
        )
        # AGI of 100000 is missing the $20k capital gain
        results = {"agi": 100000}
        with self.assertRaises(AssertionError):
            assert_all_income_accounted_for(self, results, scenario)
