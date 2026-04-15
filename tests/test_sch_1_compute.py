"""forms.sch_1.compute — Schedule 1 (Additional Income and Adjustments)."""

import unittest

from tenforty.forms import sch_1 as form_sch_1
from tests.helpers import make_simple_scenario


def _scenario_with_identity():
    scenario = make_simple_scenario()
    scenario.config.first_name = "Test"
    scenario.config.last_name = "Filer"
    scenario.config.ssn = "000-00-0000"
    return scenario


class Sch1ComputeTests(unittest.TestCase):
    def test_empty_upstream_produces_zero_totals(self):
        scenario = _scenario_with_identity()
        result = form_sch_1.compute(scenario, upstream={})
        self.assertEqual(result["sch_1_line_5_rental_re_royalty"], 0)
        self.assertEqual(result["sch_1_line_10_total_additional_income"], 0)
        self.assertEqual(result["sch_1_line_26_total_adjustments"], 0)
        self.assertEqual(result["taxpayer_name"], "Test Filer")
        self.assertEqual(result["taxpayer_ssn"], "000-00-0000")

    def test_line_5_pulls_rental_income_from_sch_e(self):
        scenario = _scenario_with_identity()
        upstream = {"sch_e": {"sch_e_line_26_total": 12_345}}
        result = form_sch_1.compute(scenario, upstream=upstream)
        self.assertEqual(result["sch_1_line_5_rental_re_royalty"], 12_345)

    def test_line_10_equals_sum_of_contributing_lines(self):
        scenario = _scenario_with_identity()
        upstream = {"sch_e": {"sch_e_line_26_total": 7_500}}
        result = form_sch_1.compute(scenario, upstream=upstream)
        self.assertEqual(result["sch_1_line_10_total_additional_income"], 7_500)

    def test_line_26_is_zero_in_v1(self):
        scenario = _scenario_with_identity()
        result = form_sch_1.compute(scenario, upstream={})
        self.assertEqual(result["sch_1_line_26_total_adjustments"], 0)

    def test_handles_negative_rental_loss(self):
        scenario = _scenario_with_identity()
        upstream = {"sch_e": {"sch_e_line_26_total": -3_200}}
        result = form_sch_1.compute(scenario, upstream=upstream)
        self.assertEqual(result["sch_1_line_5_rental_re_royalty"], -3_200)
        self.assertEqual(result["sch_1_line_10_total_additional_income"], -3_200)


if __name__ == "__main__":
    unittest.main()
