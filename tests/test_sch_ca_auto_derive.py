"""Tests for derive_auto_divergences — T6 auto-derived divergence catalog."""

import unittest
from tenforty.forms.sch_ca import derive_auto_divergences
from tenforty.models import DivergenceDirection, DivergenceSource


class AutoDerivedCatalogTests(unittest.TestCase):

    def test_unemployment_compensation_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 50_000.0,
            "schedule_1_unemployment_compensation": 4_200.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 4_200.0)
        self.assertIn("R&TC 17083", d.description)

    def test_social_security_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 80_000.0,
            "form_1040_taxable_social_security": 12_000.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §A 6")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 12_000.0)
        self.assertIn("Social Security", d.description)

    def test_state_income_tax_refund_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 65_000.0,
            "schedule_1_state_local_tax_refund": 800.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 1")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 800.0)
        self.assertIn("refund", d.description)

    def test_railroad_retirement_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 70_000.0,
            "form_1040_railroad_retirement_tier_1_2": 9_000.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §A 5b")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 9_000.0)
        self.assertIn("Railroad retirement", d.description)

    def test_pfl_benefits_yields_subtraction(self):
        result = derive_auto_divergences(federal_results={
            "agi": 60_000.0,
            "schedule_1_pfl_benefits": 3_500.0,
        })
        self.assertEqual(len(result), 1)
        d = result[0]
        self.assertEqual(d.source, DivergenceSource.AUTO_DERIVED)
        self.assertEqual(d.sch_ca_line, "Part I §B 7")
        self.assertEqual(d.direction, DivergenceDirection.SUBTRACTION)
        self.assertEqual(d.amount, 3_500.0)
        self.assertIn("Paid Family Leave", d.description)

    def test_no_signals_yields_empty(self):
        result = derive_auto_divergences(federal_results={"agi": 100_000.0})
        self.assertEqual(len(result), 0)

    def test_multiple_signals_yield_multiple_divergences(self):
        result = derive_auto_divergences(federal_results={
            "agi": 90_000.0,
            "schedule_1_unemployment_compensation": 5_000.0,
            "form_1040_taxable_social_security": 8_000.0,
            "schedule_1_state_local_tax_refund": 600.0,
        })
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
