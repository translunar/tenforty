import unittest
from pathlib import Path

from tenforty.models import (
    Form1098,
    Form1099DIV,
    Form1099INT,
    RentalProperty,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.scenario import load_scenario

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestW2(unittest.TestCase):
    def test_create_w2(self):
        w2 = W2(
            employer="Acme Corp",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        self.assertEqual(w2.wages, 100000.00)
        self.assertEqual(w2.employer, "Acme Corp")

    def test_w2_optional_fields_default_to_zero(self):
        w2 = W2(
            employer="Acme Corp",
            wages=50000.00,
            federal_tax_withheld=5000.00,
            ss_wages=50000.00,
            ss_tax_withheld=3100.00,
            medicare_wages=50000.00,
            medicare_tax_withheld=725.00,
        )
        self.assertEqual(w2.state_wages, 0.0)
        self.assertEqual(w2.state_tax_withheld, 0.0)
        self.assertEqual(w2.local_tax_withheld, 0.0)


class TestForm1099INT(unittest.TestCase):
    def test_create_1099_int(self):
        f = Form1099INT(payer="Bank of Example", interest=250.00)
        self.assertEqual(f.interest, 250.00)
        self.assertEqual(f.federal_tax_withheld, 0.0)


class TestForm1099DIV(unittest.TestCase):
    def test_create_1099_div(self):
        f = Form1099DIV(
            payer="Brokerage Inc",
            ordinary_dividends=1200.00,
            qualified_dividends=800.00,
        )
        self.assertEqual(f.ordinary_dividends, 1200.00)
        self.assertEqual(f.qualified_dividends, 800.00)


class TestForm1098(unittest.TestCase):
    def test_create_1098(self):
        f = Form1098(lender="Mortgage Co", mortgage_interest=8400.00)
        self.assertEqual(f.mortgage_interest, 8400.00)
        self.assertEqual(f.property_tax, 0.0)


class TestTaxReturnConfig(unittest.TestCase):
    def test_create_config(self):
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        self.assertEqual(config.year, 2025)
        self.assertEqual(config.filing_status, "single")

    def test_filing_status_rejects_invalid(self):
        with self.assertRaises(ValueError):
            TaxReturnConfig(
                year=2025,
                filing_status="married filing jointly",  # wrong string
                birthdate="1990-06-15",
                state="CA",
            )

    def test_filing_status_accepts_valid(self):
        for status in ["single", "married_jointly", "married_separately",
                        "head_of_household", "qualifying_widow"]:
            config = TaxReturnConfig(
                year=2025,
                filing_status=status,
                birthdate="1990-06-15",
                state="CA",
            )
            self.assertEqual(config.filing_status, status)

    def test_personal_info_fields_are_optional_and_preserve_state(self):
        blank = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-01-01",
            state="CA",
        )
        self.assertEqual(blank.first_name, "")
        self.assertEqual(blank.ssn, "")
        self.assertEqual(blank.address_state, "")

        populated = TaxReturnConfig(
            year=2025,
            filing_status="married_jointly",
            birthdate="1985-03-20",
            state="TX",
            first_name="Jane",
            last_name="Doe",
            ssn="000-12-3456",
            spouse_first_name="John",
            spouse_last_name="Doe",
            spouse_ssn="000-98-7654",
            address="123 Main St",
            address_city="Austin",
            address_state="TX",
            address_zip="78701",
        )
        self.assertEqual(populated.state, "TX")

    def test_existing_fixtures_still_load(self):
        scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.assertEqual(scenario.config.year, 2025)
        self.assertEqual(scenario.config.first_name, "")
        self.assertEqual(scenario.config.address_state, "")


class TestRentalProperty(unittest.TestCase):
    def test_create_rental_property(self):
        prop = RentalProperty(
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
        )
        self.assertEqual(prop.rents_received, 24000)
        self.assertEqual(prop.auto_and_travel, 800)
        self.assertEqual(prop.depreciation, 5500)
        self.assertEqual(prop.property_type, 2)
        self.assertEqual(prop.address, "42 Test Blvd, Faketown TX 99999")

    def test_optional_expense_fields_default_to_zero(self):
        prop = RentalProperty(
            address="456 Test Ave",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
            rents_received=24000,
        )
        self.assertEqual(prop.advertising, 0.0)
        self.assertEqual(prop.auto_and_travel, 0.0)
        self.assertEqual(prop.cleaning_and_maintenance, 0.0)
        self.assertEqual(prop.commissions, 0.0)
        self.assertEqual(prop.insurance, 0.0)
        self.assertEqual(prop.legal_and_professional_fees, 0.0)
        self.assertEqual(prop.management_fees, 0.0)
        self.assertEqual(prop.mortgage_interest, 0.0)
        self.assertEqual(prop.other_interest, 0.0)
        self.assertEqual(prop.repairs, 0.0)
        self.assertEqual(prop.supplies, 0.0)
        self.assertEqual(prop.taxes, 0.0)
        self.assertEqual(prop.utilities, 0.0)
        self.assertEqual(prop.depreciation, 0.0)
        self.assertEqual(prop.other_expenses, 0.0)

    def test_scenario_has_rental_properties(self):
        config = TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1990-06-15", state="CA",
        )
        prop = RentalProperty(
            address="123 Example St",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
            rents_received=24000,
        )
        scenario = Scenario(config=config, rental_properties=[prop])
        self.assertEqual(len(scenario.rental_properties), 1)


class TestScenario(unittest.TestCase):
    def test_create_scenario(self):
        w2 = W2(
            employer="Acme",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        scenario = Scenario(config=config, w2s=[w2])
        self.assertEqual(len(scenario.w2s), 1)
        self.assertEqual(scenario.config.year, 2025)
        self.assertEqual(scenario.form1099_int, [])
