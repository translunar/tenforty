import unittest

from tenforty.forms.f1040_spine import compute_spine
from tenforty.params.federal import load
from tests.helpers import make_simple_scenario


class SpineAssemblyTests(unittest.TestCase):
    def test_standard_deduction_selected_when_larger(self):
        scenario = make_simple_scenario()  # synthetic single W-2 only
        params = load(2025)
        # No itemized inputs -> schedule_a_total small -> standard applied.
        schedule_results = {"sch_a": {"schedule_a_total": 0}}
        out = compute_spine(scenario, params, schedule_results)
        self.assertEqual(out["standard_deduction"], 15_750)
        self.assertEqual(out["total_deductions"], 15_750)
        self.assertGreaterEqual(out["taxable_income"], 0)

    def test_taxable_income_before_qbi_is_pre_deduction(self):
        # Exercise the invariant with a NONZERO QBI deduction so the
        # assertion is not a tautology: taxable_income must be reduced by
        # exactly the QBI deduction, and the pre-QBI figure is the larger
        # one. With $100k wages, taxable income stays well above zero so the
        # max(0, ...) floor in compute_spine does not interfere.
        scenario = make_simple_scenario()
        params = load(2025)
        qbi_deduction = 1500
        out = compute_spine(scenario, params,
                            {"sch_a": {"schedule_a_total": 0},
                             "f8995": {"f8995_line_15": qbi_deduction}})
        self.assertEqual(
            out["taxable_income_before_qbi_deduction"],
            out["taxable_income"] + qbi_deduction,
        )
        # Guard: the QBI deduction actually moved the numbers (not a no-op).
        self.assertGreater(
            out["taxable_income_before_qbi_deduction"],
            out["taxable_income"],
        )
