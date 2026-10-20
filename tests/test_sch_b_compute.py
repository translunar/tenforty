"""Schedule B native-Python compute tests."""

import unittest

from tenforty.forms.sch_b import compute
import dataclasses

from tenforty.mappings.pdf_sch_b import dividend_max_rows, interest_max_rows
from tenforty.models import Form1099DIV, Form1099INT

from tests.helpers import make_simple_scenario


class SchBInterestTests(unittest.TestCase):
    def test_interest_totals_and_payers(self):
        scenario = make_simple_scenario()
        scenario.form1099_int = [
            Form1099INT(payer="Bank A", interest=500.0),
            Form1099INT(payer="Bank B", interest=300.0),
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["total_interest"], 800)
        self.assertEqual(result["taxable_interest"], 800)
        self.assertEqual(result["excludable_savings_bond"], 0)
        self.assertEqual(
            result["interest_payers"],
            [
                {"payer": "Bank A", "amount": 500},
                {"payer": "Bank B", "amount": 300},
            ],
        )


class SchBDividendTests(unittest.TestCase):
    def test_dividends_summed_across_payers(self):
        scenario = make_simple_scenario()
        scenario.form1099_div = [
            Form1099DIV(payer="Broker X", ordinary_dividends=1200.0),
            Form1099DIV(payer="Broker Y", ordinary_dividends=400.0),
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["total_ordinary_dividends"], 1600)


class SchBBothPartsTests(unittest.TestCase):
    def test_both_parts_populated(self):
        scenario = make_simple_scenario()
        scenario.form1099_int = [Form1099INT(payer="Bank A", interest=100.0)]
        scenario.form1099_div = [
            Form1099DIV(payer="Broker X", ordinary_dividends=200.0),
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["total_interest"], 100)
        self.assertEqual(result["total_ordinary_dividends"], 200)
        self.assertEqual(len(result["interest_payers"]), 1)
        self.assertEqual(len(result["dividend_payers"]), 1)


class SchBTaxpayerHeaderTests(unittest.TestCase):
    def test_taxpayer_header_pulled_from_config(self):
        scenario = make_simple_scenario()
        scenario.config.first_name = "Alex"
        scenario.config.last_name = "Rivera"
        scenario.config.ssn = "000-12-3456"
        scenario.form1099_int = [Form1099INT(payer="Bank", interest=100.0)]
        result = compute(scenario, upstream={})
        self.assertEqual(result["taxpayer_name"], "Alex Rivera")
        self.assertEqual(result["taxpayer_ssn"], "000-12-3456")

    def test_taxpayer_name_trims_blanks_when_unset(self):
        scenario = make_simple_scenario()
        result = compute(scenario, upstream={})
        self.assertEqual(result["taxpayer_name"], "")
        self.assertEqual(result["taxpayer_ssn"], "")


class SchBEmptyTests(unittest.TestCase):
    def test_empty_scenario_yields_zero_totals_and_empty_lists(self):
        scenario = make_simple_scenario()
        result = compute(scenario, upstream={})
        self.assertEqual(result["total_interest"], 0)
        self.assertEqual(result["total_ordinary_dividends"], 0)
        self.assertEqual(result["interest_payers"], [])
        self.assertEqual(result["dividend_payers"], [])


class SchBOverflowTests(unittest.TestCase):
    def test_too_many_interest_payers_raises(self):
        scenario = make_simple_scenario()
        scenario.form1099_int = [
            Form1099INT(payer=f"Bank {i}", interest=10.0)
            for i in range(interest_max_rows(scenario.config.year) + 1)
        ]
        with self.assertRaisesRegex(NotImplementedError, "multi-page"):
            compute(scenario, upstream={})

    def test_too_many_dividend_payers_raises(self):
        scenario = make_simple_scenario()
        scenario.form1099_div = [
            Form1099DIV(payer=f"Broker {i}", ordinary_dividends=10.0)
            for i in range(dividend_max_rows(scenario.config.year) + 1)
        ]
        with self.assertRaisesRegex(NotImplementedError, "multi-page"):
            compute(scenario, upstream={})

    def _dividends(self, year, count):
        scenario = make_simple_scenario()
        scenario.config = dataclasses.replace(scenario.config, year=year)
        scenario.form1099_div = [
            Form1099DIV(payer=f"Broker {i}", ordinary_dividends=10.0)
            for i in range(count)]
        return scenario

    def test_a_16th_dividend_payer_refuses_from_2022(self):
        # The 2022-2025 paper prints 15 dividend rows.
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year), self.assertRaisesRegex(
                    NotImplementedError, "15 rows"):
                compute(self._dividends(year, 16), upstream={})

    def test_16_dividend_payers_fit_in_2021(self):
        result = compute(self._dividends(2021, 16), upstream={})
        self.assertEqual(len(result["dividend_payers"]), 16)


if __name__ == "__main__":
    unittest.main()
