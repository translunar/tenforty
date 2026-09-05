"""Air-gapped oracle values for Schedule SE self-employment tax.

The EXACT SE-tax (line 12) and half-deduction (line 13) integers below are
hand-derived by a separate air-gapped tax-law author with NO access to the
implementation code or the plan text. The production compute must REACH these
via the load-bearing carry-unrounded rounding convention (intermediate line
values stay unrounded; irs_round applies only at emit). If a rate/percentage
regresses, these assertions go red (falsifiability is mutation-checked).

Plain unittest.TestCase, FAST tier — NOT @pytest.mark.oracle (that marker is
soffice-gated; these are pure-Python hand-derived values, not a workbook drive).

Synthetic inputs only. Tax year 2024, single Schedule C business, long method.
"""
import dataclasses
import unittest

from tenforty.forms import sch_se
from tenforty.models import Scenario, W2
from tests.helpers import make_simple_scenario


def _scn(net_profit, ss_wages=0.0, year=2024):
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


class SchSeOracleTests(unittest.TestCase):
    def test_case_a_no_w2_ss_wages(self):
        # Net profit 90,000; W-2 ss_wages 0; year 2024 (wage base does not bind).
        scn, up = _scn(90_000.0, ss_wages=0.0, year=2024)
        out = sch_se.compute(scn, up)
        self.assertEqual(out["sch_se_line_12_se_tax"], 12_717)
        self.assertEqual(out["sch_se_line_13_half_deduction"], 6_358)

    def test_case_b_wage_base_binding(self):
        # Net profit 100,000; W-2 ss_wages 150,000; year 2024. The SS wage base
        # (168,600) binds: only 18,600 of net earnings is subject to the SS
        # portion; Medicare applies to all of it.
        scn, up = _scn(100_000.0, ss_wages=150_000.0, year=2024)
        out = sch_se.compute(scn, up)
        self.assertEqual(out["sch_se_line_12_se_tax"], 4_985)
        self.assertEqual(out["sch_se_line_13_half_deduction"], 2_492)


if __name__ == "__main__":
    unittest.main()
