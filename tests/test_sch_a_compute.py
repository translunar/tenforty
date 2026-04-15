"""forms.sch_a.compute — Schedule A (Itemized Deductions) with OBBBA SALT."""

import unittest

from tenforty.forms import sch_a as form_sch_a
from tenforty.models import FilingStatus, ItemizedDeductions
from tests.helpers import make_simple_scenario


def _scenario(filing_status=FilingStatus.SINGLE, **itemized):
    s = make_simple_scenario()
    s.config.filing_status = filing_status
    s.config.first_name = "Test"
    s.config.last_name = "Filer"
    s.config.ssn = "000-00-0000"
    s.itemized_deductions = ItemizedDeductions(**itemized)
    return s


class SchAMedicalTests(unittest.TestCase):
    def test_below_floor_produces_zero_medical(self):
        scenario = _scenario(medical_expenses=5_000)
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_3_medical_floor"], 7_500)
        self.assertEqual(r["sch_a_line_4_medical_deductible"], 0)

    def test_above_floor_deducts_excess(self):
        scenario = _scenario(medical_expenses=10_000)
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_4_medical_deductible"], 2_500)


class SchASaltTests(unittest.TestCase):
    def test_below_cap_passes_through(self):
        scenario = _scenario(state_income_tax=5_000, property_tax=3_000)
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_5d_salt_sum"], 8_000)
        self.assertEqual(r["sch_a_line_5e_salt_capped"], 8_000)
        self.assertEqual(r["sch_a_line_7_taxes_total"], 8_000)

    def test_capped_at_40k_single_obbba(self):
        scenario = _scenario(state_income_tax=35_000, property_tax=25_000)
        upstream = {"f1040": {"agi": 250_000, "magi": 250_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_5d_salt_sum"], 60_000)
        self.assertEqual(r["sch_a_line_5e_salt_capped"], 40_000)

    def test_capped_at_20k_mfs_obbba(self):
        scenario = _scenario(
            filing_status=FilingStatus.MARRIED_SEPARATELY,
            state_income_tax=15_000, property_tax=10_000,
        )
        upstream = {"f1040": {"agi": 200_000, "magi": 200_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_5e_salt_capped"], 20_000)

    def test_raises_on_magi_above_phaseout_threshold(self):
        scenario = _scenario(state_income_tax=50_000, property_tax=30_000)
        upstream = {"f1040": {"agi": 600_000, "magi": 600_000}}
        with self.assertRaisesRegex(NotImplementedError, "SALT phaseout"):
            form_sch_a.compute(scenario, upstream=upstream)


class SchATotalsTests(unittest.TestCase):
    def test_line_17_equals_sum_of_components(self):
        scenario = _scenario(
            medical_expenses=10_000,
            state_income_tax=5_000, property_tax=3_000,
            mortgage_interest=12_000,
            charitable_contributions=2_500,
        )
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_17_total"], 2_500 + 8_000 + 12_000 + 2_500)

    def test_identity_fields_populated_from_config(self):
        scenario = _scenario(state_income_tax=1)
        upstream = {"f1040": {"agi": 50_000, "magi": 50_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["taxpayer_name"], "Test Filer")
        self.assertEqual(r["taxpayer_ssn"], "000-00-0000")


class SchASalesTaxGateTests(unittest.TestCase):
    def test_raises_for_no_income_tax_state_without_ack(self):
        scenario = _scenario(state_income_tax=0, property_tax=5_000)
        scenario.config.state = "TX"
        scenario.config.acknowledges_sch_a_sales_tax_unsupported = False
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        with self.assertRaisesRegex(NotImplementedError, "sales tax"):
            form_sch_a.compute(scenario, upstream=upstream)

    def test_proceeds_for_no_income_tax_state_with_ack(self):
        scenario = _scenario(state_income_tax=0, property_tax=5_000)
        scenario.config.state = "TX"
        scenario.config.acknowledges_sch_a_sales_tax_unsupported = True
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_5a_state_income_tax"], 0)
        self.assertEqual(r["sch_a_line_5d_salt_sum"], 5_000)

    def test_proceeds_for_income_tax_state_regardless_of_ack(self):
        scenario = _scenario(state_income_tax=4_000, property_tax=3_000)
        scenario.config.state = "CA"
        scenario.config.acknowledges_sch_a_sales_tax_unsupported = False
        upstream = {"f1040": {"agi": 100_000, "magi": 100_000}}
        r = form_sch_a.compute(scenario, upstream=upstream)
        self.assertEqual(r["sch_a_line_5d_salt_sum"], 7_000)


if __name__ == "__main__":
    unittest.main()
