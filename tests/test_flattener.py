import unittest

from tenforty.flattener import flatten_scenario
from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    Scenario,
    ScheduleK1,
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

    def test_1099_div_capital_gain_distributions(self):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            form1099_div=[Form1099DIV(
                payer="Brokerage Inc",
                ordinary_dividends=500,
                qualified_dividends=500,
                capital_gain_distributions=5000,
            )],
        )
        flat = flatten_scenario(scenario)
        self.assertEqual(flat["capital_gain_distributions_1"], 5000)

    def test_multiple_1098s_summed(self):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            form1098s=[
                Form1098(lender="Mortgage Co", mortgage_interest=8000, property_tax=3000),
                Form1098(lender="Home Mortgage Co", mortgage_interest=4000, property_tax=1500),
            ],
        )
        flat = flatten_scenario(scenario)
        self.assertEqual(flat["mortgage_interest"], 12000)
        self.assertEqual(flat["property_tax"], 4500)

    def test_empty_forms_produce_no_keys(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertNotIn("ordinary_dividends_1", flat)
        self.assertNotIn("sche_rents_a", flat)


class TestFlattenerRejectsUnhandledData(unittest.TestCase):
    """The flattener must raise NotImplementedError for form types it can't handle yet."""

    def _base_config(self) -> TaxReturnConfig:
        return TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1990-06-15", state="CA",
        )

    def test_rejects_1099_b(self):
        scenario = Scenario(
            config=self._base_config(),
            form1099_b=[Form1099B(
                broker="Brokerage Inc", description="100 shares ACME",
                date_acquired="2023-01-15", date_sold="2025-03-20",
                proceeds=15000, cost_basis=10000,
            )],
        )
        with self.assertRaises(NotImplementedError) as ctx:
            flatten_scenario(scenario)
        self.assertIn("1099-B", str(ctx.exception))

    def test_rejects_schedule_k1(self):
        scenario = Scenario(
            config=self._base_config(),
            schedule_k1s=[ScheduleK1(
                entity_name="Example LLC", entity_ein="FAKE-EIN",
                rental_income=6000,
            )],
        )
        with self.assertRaises(NotImplementedError) as ctx:
            flatten_scenario(scenario)
        self.assertIn("K-1", str(ctx.exception))
