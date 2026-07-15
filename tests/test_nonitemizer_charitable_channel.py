import unittest

from tenforty.forms.f1040_spine import compute_spine
from tenforty.params.federal import load
from tests.helpers import make_simple_scenario


class NonitemizerCharitableChannelTests(unittest.TestCase):
    """2021-only CARES/CAA above-the-line cash-charitable deduction for
    non-itemizers (Form 1040 line 12b), single-filer spine defense-in-depth.
    Non-single and over-cap are refused at LOAD (see test_scenario.py); these
    tests call compute_spine directly, bypassing load, to exercise the
    spine's own guards."""

    def test_hand_computed_taxable_income(self):
        # Hand computation (independent of the implementation under test):
        #   AGI = wages = 100,000 (single W-2, no other income/adjustments,
        #   per make_simple_scenario()).
        #   2021 single standard deduction = params.standard_deduction["single"]
        #   (read from params, not hardcoded, so this stays correct if the
        #   params module changes).
        #   charitable_cash_nonitemizer = 250 (<= $300 cap, passes through
        #   verbatim).
        #   QBI deduction = 0 (no QBI-eligible income in this scenario).
        #   taxable_income = AGI - std_deduction - charitable - QBI
        params = load(2021)
        std_single = params.standard_deduction["single"]
        agi = 100000
        charitable = 250
        expected_taxable_income = agi - std_single - charitable

        scenario = make_simple_scenario()
        scenario.config.year = 2021
        scenario.config.charitable_cash_nonitemizer = charitable
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}

        out = compute_spine(scenario, params, schedule_results)

        self.assertEqual(out["charitable_nonitemizer"], 250)
        self.assertEqual(out["taxable_income"], expected_taxable_income)

    def test_zero_field_byte_identical(self):
        params = load(2021)
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}

        scenario_default = make_simple_scenario()
        scenario_default.config.year = 2021
        # charitable_cash_nonitemizer defaults to 0.0
        out_default = compute_spine(scenario_default, params, schedule_results)

        scenario_explicit_zero = make_simple_scenario()
        scenario_explicit_zero.config.year = 2021
        scenario_explicit_zero.config.charitable_cash_nonitemizer = 0.0
        out_explicit_zero = compute_spine(
            scenario_explicit_zero, params, schedule_results
        )

        self.assertEqual(out_default, out_explicit_zero)
        self.assertEqual(out_default["charitable_nonitemizer"], 0)

        std_single = params.standard_deduction["single"]
        self.assertEqual(out_default["taxable_income"], 100000 - std_single)

    def test_itemizing_with_nonzero_refused(self):
        params = load(2021)
        std_single = params.standard_deduction["single"]
        # Itemized total ABOVE the standard deduction -> itemizing selected.
        schedule_results = {
            "sch_a": {"sch_a_line_17_total": std_single + 1000}
        }

        scenario = make_simple_scenario()
        scenario.config.year = 2021
        scenario.config.charitable_cash_nonitemizer = 250

        with self.assertRaises(ValueError) as ctx:
            compute_spine(scenario, params, schedule_results)

        message = str(ctx.exception).lower()
        self.assertTrue(
            "non-itemizer" in message or "itemizes" in message,
            msg=f"Expected message to mention non-itemizer/itemizes, got: {ctx.exception}",
        )

    def test_single_over_cap_refused(self):
        params = load(2021)
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}

        scenario = make_simple_scenario()
        scenario.config.year = 2021
        scenario.config.charitable_cash_nonitemizer = 400

        with self.assertRaises(ValueError) as ctx:
            compute_spine(scenario, params, schedule_results)

        message = str(ctx.exception)
        self.assertIn("300", message)


if __name__ == "__main__":
    unittest.main()
