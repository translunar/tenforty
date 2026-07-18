import dataclasses
import unittest

from tenforty.forms.f1040_spine import compute_income_preamble, compute_spine
from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import Form1099DIV
from tenforty.params.federal import load
from tests.helpers import make_simple_scenario


class SpineAssemblyTests(unittest.TestCase):
    def test_standard_deduction_selected_when_larger(self):
        scenario = make_simple_scenario()  # synthetic single W-2 only
        params = load(2025)
        # No itemized inputs -> sch_a_line_17_total small -> standard applied.
        schedule_results = {"sch_a": {"sch_a_line_17_total": 0}}
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
                            {"sch_a": {"sch_a_line_17_total": 0},
                             "f8995": {"f8995_line_15_qbi_deduction": qbi_deduction}})
        self.assertEqual(
            out["taxable_income_before_qbi_deduction"],
            out["taxable_income"] + qbi_deduction,
        )
        # Guard: the QBI deduction actually moved the numbers (not a no-op).
        self.assertGreater(
            out["taxable_income_before_qbi_deduction"],
            out["taxable_income"],
        )


def _scenario_with_qualified_divs(qualified: float, ordinary: float):
    """make_simple_scenario() (single filer, $100k wages) plus a synthetic
    1099-DIV, for QDCGT tests that need qualified dividends alongside a
    Sch D capital-gain shape."""
    return dataclasses.replace(
        make_simple_scenario(),
        form1099_div=[
            Form1099DIV(
                payer="Synthetic Brokerage",
                ordinary_dividends=ordinary,
                qualified_dividends=qualified,
            ),
        ],
    )


class QdcgtNetCapitalGainBugTests(unittest.TestCase):
    """Bug #10 (found 2026-07-18): the QDCGT worksheet's preferential base
    must be capped at Sch D line 15 (net LONG-term gain), NOT line 16 (net
    ST + LT). A net SHORT-term gain must stay ORDINARY income; only the net
    LONG-term gain (plus qualified dividends) gets the preferential
    0/15/20% rates. net_capital_gain = max(0, min(line 15, line 16))."""

    def setUp(self):
        self.params = load(2025)

    def test_net_short_term_gain_stays_ordinary_not_preferential(self):
        """NET-ST-GAIN case (the bug).

        Sch D line 15 (net LTCG)          = $2,000
        Sch D line 7  (net ST gain)       =   $500
        Sch D line 16 (line 7 + line 15)  = $2,500
        Qualified dividends               = $1,000

        IRS QDCGT worksheet: net_capital_gain = min(line 15, line 16)
                                              = min(2,000, 2,500) = $2,000
        Preferential income = qual_div + net_capital_gain
                            = 1,000 + 2,000 = $3,000.
        The $500 net ST gain is NOT preferential; it stays ordinary income
        (it already entered AGI via Sch D line 16 in total_income -- only
        the QDCGT SPLIT between ordinary/preferential changes here).

        This must FAIL on the current (buggy) code, which computes
        net_capital_gain = max(0, line 16) = $2,500 -- over-including the
        $500 ST gain in the preferential bucket (an undertaxation bug).
        """
        schedule_results = {
            "sch_d": {
                "sch_d_line_15_net_long": 2_000,
                "sch_d_line_16_total": 2_500,
            },
        }
        scenario = _scenario_with_qualified_divs(qualified=1_000, ordinary=1_000)

        preamble = compute_income_preamble(scenario, self.params, schedule_results)
        self.assertEqual(
            preamble.net_capital_gain, 2_000,
            "QDCGT net_capital_gain must be min(line 15, line 16) = "
            "min(2,000, 2,500) = 2,000, capping the $500 net ST gain out "
            "of the preferential base",
        )

        out = compute_spine(
            scenario, self.params,
            {**schedule_results, "sch_a": {"sch_a_line_17_total": 0}},
        )
        self.assertEqual(out["net_capital_gain"], 2_000)

        # taxable_income = wages(100,000) + ordinary_divs(1,000)
        #                + schd_line16(2,500) - standard_deduction(15,750)
        #                = 87,750. (Unaffected by the bug -- only the QDCGT
        # ordinary/preferential SPLIT of this figure changes, not AGI/TI.)
        taxable_income = out["taxable_income"]
        self.assertEqual(taxable_income, 87_750)

        # Worksheet arithmetic (corrected): preferential = 1,000 qual div +
        # 2,000 net_capital_gain = 3,000; ordinary = 87,750 - 3,000 = 84,750
        # -- already above the 2025 single 0%-band top ($48,350), so all
        # $3,000 of preferential income falls in the 15% band:
        #   income_tax = ordinary_tax(84,750) + round(3,000 * 0.15)
        #             = ordinary_tax(84,750) + 450.
        # `total_tax` is the spine's line-16 QDCGT-worksheet tax output key
        # (== income_tax here, since this scenario has no f8959/f8962 to add).
        expected_tax = qdcgt_tax(
            taxable_income, qualified_dividends=1_000, net_capital_gain=2_000,
            params=self.params, filing_status=scenario.config.filing_status,
        )
        self.assertEqual(out["total_tax"], expected_tax)

        # Demonstrate the bug's direction and magnitude: the buggy
        # net_capital_gain=2,500 puts the $500 ST gain in the 15% bucket
        # instead of its ~22% ordinary bracket, UNDERtaxing the return.
        buggy_tax = qdcgt_tax(
            taxable_income, qualified_dividends=1_000, net_capital_gain=2_500,
            params=self.params, filing_status=scenario.config.filing_status,
        )
        self.assertGreater(
            out["total_tax"], buggy_tax,
            "the fixed (correct) tax must exceed the old buggy "
            "(undertaxed) figure -- a net ST gain taxed at ordinary rates "
            "owes more than the same gain mistakenly taxed at 15%",
        )

    def test_net_short_term_loss_still_caps_at_line_16(self):
        """NET-ST-LOSS case (the accidentally-right branch; must stay right
        after the fix).

        Sch D line 15 (net LTCG)              = $2,000
        Sch D line 7  (net ST loss)            =  -$800
        Sch D line 16 (line 7 + line 15)       = $1,200

        min(line 15, line 16) = min(2,000, 1,200) = $1,200 -- the ST loss
        REDUCES the preferential base below the LTCG amount, which is
        correct (the loss offsets the LTCG for QDCGT purposes too). Both
        the pre-fix max(0, line 16) and the fixed min(line 15, line 16)
        give $1,200 here, so this pins that the fix does not disturb this
        branch (must PASS both before and after the fix).
        """
        schedule_results = {
            "sch_d": {
                "sch_d_line_15_net_long": 2_000,
                "sch_d_line_16_total": 1_200,
            },
        }
        scenario = _scenario_with_qualified_divs(qualified=500, ordinary=500)

        preamble = compute_income_preamble(scenario, self.params, schedule_results)
        self.assertEqual(preamble.net_capital_gain, 1_200)

        out = compute_spine(
            scenario, self.params,
            {**schedule_results, "sch_a": {"sch_a_line_17_total": 0}},
        )
        self.assertEqual(out["net_capital_gain"], 1_200)
