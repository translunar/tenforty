import unittest

from tenforty.forms.f1040_spine import compute_spine
from tenforty.params.federal import load
from tests.helpers import make_simple_scenario


class EstimatedPaymentsChannelTests(unittest.TestCase):
    def test_passthrough_adds_to_total_payments(self):
        scenario_zero = make_simple_scenario()  # estimated_tax_payments defaults to 0.0
        params = load(2025)
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}
        out_zero = compute_spine(scenario_zero, params, schedule_results)

        scenario_paid = make_simple_scenario()
        scenario_paid.config.estimated_tax_payments = 5000
        out_paid = compute_spine(scenario_paid, params, schedule_results)

        self.assertEqual(out_paid["estimated_tax_payments"], 5000)
        self.assertEqual(
            out_paid["total_payments"],
            out_zero["total_payments"] + 5000,
        )

    def test_zero_field_is_byte_identical(self):
        params = load(2025)
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}

        scenario_default = make_simple_scenario()  # estimated_tax_payments defaults to 0.0
        out_default = compute_spine(scenario_default, params, schedule_results)

        scenario_explicit_zero = make_simple_scenario()
        scenario_explicit_zero.config.estimated_tax_payments = 0.0
        out_explicit_zero = compute_spine(scenario_explicit_zero, params, schedule_results)

        self.assertEqual(out_default, out_explicit_zero)
        self.assertEqual(out_default["estimated_tax_payments"], 0)
        self.assertEqual(out_default["total_payments"], out_default["federal_withheld"])

    def test_overpaid_reflects_estimated_payments(self):
        scenario_zero = make_simple_scenario()  # estimated_tax_payments defaults to 0.0
        params = load(2025)
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}
        out_zero = compute_spine(scenario_zero, params, schedule_results)

        scenario_paid = make_simple_scenario()
        scenario_paid.config.estimated_tax_payments = 50000
        out_paid = compute_spine(scenario_paid, params, schedule_results)

        self.assertEqual(out_paid["overpaid"], out_zero["overpaid"] + 50000)


if __name__ == "__main__":
    unittest.main()
