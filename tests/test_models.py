import unittest

from tenforty.models import W2, Form1099INT, Form1099DIV, Form1098, TaxReturnConfig, Scenario


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
