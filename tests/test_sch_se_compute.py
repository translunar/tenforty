"""Relational/structural tests for Schedule SE self-employment-tax compute.

These pin the STRUCTURE of the Schedule SE math (net-earnings percentage,
half==½ SE tax, uncapped Medicare, the <$400 boundary, and the SS wage-base
coordination below / straddling / above the base) WITHOUT asserting any
hand-derived absolute magnitude — the exact SE-tax integers live in the
air-gapped oracle test (tests/test_sch_se_oracle.py). Synthetic inputs only.
"""
import dataclasses
import unittest

from tenforty.forms import sch_se
from tenforty.models import Scenario, W2
from tests.helpers import make_simple_scenario

_RATE_SS, _RATE_MED, _NE = 0.124, 0.029, 0.9235
_SS_WAGE_BASE_2024 = 168_600


def _scn(net_profit, ss_wages=0.0, year=2024):
    """Build a (scenario, upstream) pair for a single Schedule C net profit.

    The scenario's W-2 list is REPLACED entirely so ss_wages is exactly the
    coordination input (make_simple_scenario's default W-2 does not leak in).
    """
    base = make_simple_scenario()
    cfg = dataclasses.replace(base.config, year=year)
    w2s = (
        [W2(employer="Synthetic Employer", wages=ss_wages,
            federal_tax_withheld=0.0, ss_wages=ss_wages, ss_tax_withheld=0.0,
            medicare_wages=ss_wages, medicare_tax_withheld=0.0)]
        if ss_wages else []
    )
    scn = Scenario(config=cfg, w2s=w2s)
    up = {"sch_c": {"sch_c_line_31_net_profit_total": net_profit}}
    return scn, up


class SchSeStructureTests(unittest.TestCase):
    def test_net_earnings_is_9235_percent(self):
        scn, up = _scn(100_000.0)
        out = sch_se.compute(scn, up)
        self.assertEqual(out["sch_se_line_4c_net_earnings"], round(100_000 * _NE))

    def test_half_deduction_is_half_of_se_tax(self):
        scn, up = _scn(100_000.0)
        out = sch_se.compute(scn, up)
        self.assertEqual(
            out["sch_se_line_13_half_deduction"],
            round(out["sch_se_line_12_se_tax"] / 2),
        )

    def test_medicare_is_uncapped_29_percent_of_net_earnings(self):
        scn, up = _scn(300_000.0)  # well above any SS wage base
        out = sch_se.compute(scn, up)
        self.assertEqual(
            out["sch_se_line_11_medicare_portion"],
            round(out["sch_se_line_6_total_net_earnings"] * _RATE_MED),
        )

    def test_below_400_no_se_tax(self):
        scn, up = _scn(430.0)  # 430 * .9235 = 397.105 < 400
        out = sch_se.compute(scn, up)
        self.assertEqual(out["sch_se_line_12_se_tax"], 0)
        self.assertEqual(out["sch_se_line_13_half_deduction"], 0)

    def test_at_400_threshold_se_tax_positive(self):
        scn, up = _scn(440.0)  # 440 * .9235 = 406.34 >= 400
        out = sch_se.compute(scn, up)
        self.assertGreater(out["sch_se_line_12_se_tax"], 0)

    def test_wage_base_coordination_ss_wages_below_base(self):
        # ss_wages below base: SS portion applies to min(net earnings, base - ss_wages)
        scn, up = _scn(100_000.0, ss_wages=50_000.0, year=2024)
        out = sch_se.compute(scn, up)
        remaining = _SS_WAGE_BASE_2024 - 50_000
        ss_base = min(out["sch_se_line_6_total_net_earnings"], remaining)
        self.assertEqual(out["sch_se_line_10_ss_portion"], round(ss_base * _RATE_SS))

    def test_wage_base_coordination_straddle(self):
        # STRADDLE: 0 < remaining room < net earnings, so the cap BINDS on a
        # partial amount. ss_wages 150,000, net 100,000, 2024: remaining =
        # 168,600 - 150,000 = 18,600; net earnings = 92,350 > 18,600, so the SS
        # portion applies to EXACTLY 18,600 (not the full net earnings, not 0).
        scn, up = _scn(100_000.0, ss_wages=150_000.0, year=2024)
        out = sch_se.compute(scn, up)
        remaining = _SS_WAGE_BASE_2024 - 150_000
        self.assertLess(0, remaining)
        self.assertLess(remaining, out["sch_se_line_6_total_net_earnings"])
        self.assertEqual(out["sch_se_line_10_ss_portion"], round(remaining * _RATE_SS))

    def test_wage_base_coordination_ss_wages_above_base(self):
        # ss_wages already exceed the base: no SS portion, Medicare still applies
        scn, up = _scn(100_000.0, ss_wages=200_000.0, year=2024)
        out = sch_se.compute(scn, up)
        self.assertEqual(out["sch_se_line_10_ss_portion"], 0)
        self.assertGreater(out["sch_se_line_11_medicare_portion"], 0)

    def test_empty_returns_empty(self):
        scn, _ = _scn(0.0)
        self.assertEqual(sch_se.compute(scn, {"sch_c": {}}), {})


if __name__ == "__main__":
    unittest.main()
