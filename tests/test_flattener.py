import unittest

from tenforty.flattener import flatten_scenario
from tenforty.models import (
    Form1098,
    Form1099INT,
    Scenario,
    TaxReturnConfig,
    W2,
)


def _simple_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        ),
        w2s=[
            W2(
                employer="Acme",
                wages=100000,
                federal_tax_withheld=15000,
                ss_wages=100000,
                ss_tax_withheld=6200,
                medicare_wages=100000,
                medicare_tax_withheld=1450,
                state_wages=100000,
                state_tax_withheld=5000,
            ),
        ],
        form1099_int=[Form1099INT(payer="Bank", interest=250)],
        form1098s=[Form1098(lender="Mortgage Co", mortgage_interest=8400)],
    )


class TestFlattenScenario(unittest.TestCase):
    def test_filing_status_single(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["filing_status_single"], "X")
        self.assertNotIn("filing_status_married_jointly", flat)

    def test_birthdate_split(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["birthdate_month"], 6)
        self.assertEqual(flat["birthdate_day"], 15)
        self.assertEqual(flat["birthdate_year"], 1990)

    def test_w2_fields(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["w2_wages_1"], 100000)
        self.assertEqual(flat["w2_fed_withheld_1"], 15000)
        self.assertEqual(flat["w2_ss_wages_1"], 100000)
        self.assertEqual(flat["w2_state_wages_1"], 100000)
        self.assertEqual(flat["w2_state_withheld_1"], 5000)

    def test_1099_int_fields(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["interest_1"], 250)

    def test_1098_mortgage(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["mortgage_interest"], 8400)

    def test_empty_forms_produce_no_keys(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertNotIn("ordinary_dividends_1", flat)
        self.assertNotIn("sche_rents_a", flat)
