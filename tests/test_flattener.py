import unittest

from tenforty.oracle.flattener import flatten_scenario
from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    RentalProperty,
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


class TestFlattenRentalProperty(unittest.TestCase):
    def _make_rental_scenario(self) -> Scenario:
        return Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            rental_properties=[RentalProperty(
                address="42 Test Blvd, Faketown TX 99999",
                property_type=2,
                fair_rental_days=350,
                personal_use_days=15,
                rents_received=24000,
                auto_and_travel=800,
                cleaning_and_maintenance=550,
                insurance=1600,
                legal_and_professional_fees=300,
                mortgage_interest=7500,
                repairs=950,
                supplies=350,
                taxes=8500,
                depreciation=5500,
            )],
        )

    def test_rental_rents_received(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_rents_a"], 24000)

    def test_rental_metadata(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_property_type_a"], 2)
        self.assertEqual(flat["sche_fair_rental_days_a"], 350)
        self.assertEqual(flat["sche_personal_use_days_a"], 15)

    def test_rental_all_expenses(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_insurance_a"], 1600)
        self.assertEqual(flat["sche_mortgage_interest_a"], 7500)
        self.assertEqual(flat["sche_repairs_a"], 950)
        self.assertEqual(flat["sche_taxes_a"], 8500)
        self.assertEqual(flat["sche_depreciation_a"], 5500)
        self.assertEqual(flat["sche_auto_and_travel_a"], 800)
        self.assertEqual(flat["sche_cleaning_and_maintenance_a"], 550)
        self.assertEqual(flat["sche_legal_and_professional_fees_a"], 300)
        self.assertEqual(flat["sche_supplies_a"], 350)

    def test_rental_zero_expenses_not_included(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertNotIn("sche_advertising_a", flat)
        self.assertNotIn("sche_commissions_a", flat)
        self.assertNotIn("sche_management_fees_a", flat)
        self.assertNotIn("sche_other_interest_a", flat)
        self.assertNotIn("sche_utilities_a", flat)
        self.assertNotIn("sche_other_expenses_a", flat)


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
