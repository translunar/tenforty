"""Form 8995 — Schedule C QBI component tests (Task 6).

The Schedule C QBI component is net profit less the allocable half-SE-tax
deduction and the SE-health deduction; it aggregates alongside the K-1
fanout's qbi_aggregate before the over-threshold gate. All fixtures are
below the QBI simple-path threshold (single, 2025 → 197,300), so the gate
does not fire; taxable income before QBI is fixed at a synthetic 120,000.
"""

import unittest

from tenforty.forms import f8995
from tenforty.models import K1FanoutData

from tests.helpers import make_simple_scenario


def _fanout(qbi_aggregate: float = 0.0) -> K1FanoutData:
    return K1FanoutData(
        sch_b_interest_additions=(),
        sch_b_dividend_additions=(),
        sch_d_short_term_additions=(),
        sch_d_long_term_additions=(),
        qbi_aggregate=qbi_aggregate,
        qualified_dividends_aggregate=0.0,
        passive_activities=(),
    )


def _f1040_stub():
    # STRICT qualified_dividends key required by f8995.compute (else KeyError).
    # Synthetic taxable income below the single-filer QBI threshold.
    return {
        "taxable_income_before_qbi_deduction": 120_000.0,
        "net_capital_gain": 0.0,
        "qualified_dividends": 0.0,
    }


class SchCQbiTests(unittest.TestCase):
    def test_sch_c_qbi_component_enters_line_1(self):
        # net profit 60,000; half-SE 4,000; SE-health 0 → QBI component 56,000.
        up = {
            "k1_fanout": _fanout(0.0),  # no K-1 QBI
            "f1040": _f1040_stub(),
            "sch_c": {"sch_c_line_31_net_profit_total": 60_000},
            "sch_se": {"sch_se_line_13_half_deduction": 4_000},
        }
        scn = make_simple_scenario()  # SE-health deduction defaults to 0
        out = f8995.compute(scn, up)
        self.assertEqual(out["f8995_line_1_qbi"], 56_000)
        self.assertGreater(out["f8995_line_15_qbi_deduction"], 0)

    def test_sch_c_qbi_adds_to_k1_components(self):
        # A K-1 QBI aggregate (10,000) AND a Sch C component (56,000) both land
        # in line 1 → 66,000.
        up = {
            "k1_fanout": _fanout(10_000.0),
            "f1040": _f1040_stub(),
            "sch_c": {"sch_c_line_31_net_profit_total": 60_000},
            "sch_se": {"sch_se_line_13_half_deduction": 4_000},
        }
        scn = make_simple_scenario()
        out = f8995.compute(scn, up)
        self.assertEqual(out["f8995_line_1_qbi"], 66_000)

    def test_se_health_reduces_sch_c_qbi_component(self):
        # Independently pins the `- se_health` term: single-business, nonzero
        # SE-health WITHIN the §162(l) limit (6,000 < 60,000 − 4,000 = 56,000,
        # so Task 7's guard would not refuse). net 60,000 − half_se 4,000 −
        # se_health 6,000 → line 1 == 50,000. Below the QBI threshold (single
        # 2025 → 197,300 vs taxable 120,000), so no ack needed.
        up = {
            "k1_fanout": _fanout(0.0),
            "f1040": _f1040_stub(),
            "sch_c": {"sch_c_line_31_net_profit_total": 60_000},
            "sch_se": {"sch_se_line_13_half_deduction": 4_000},
        }
        scn = make_simple_scenario()
        scn.config.self_employed_health_insurance_deduction = 6_000.0
        out = f8995.compute(scn, up)
        self.assertEqual(out["f8995_line_1_qbi"], 50_000)

    def test_no_sch_c_leaves_qbi_unchanged(self):
        # No sch_c/sch_se in upstream → component is 0 → line 1 is exactly the
        # K-1 aggregate (no-regression contract for existing f8995 callers).
        up = {
            "k1_fanout": _fanout(10_000.0),
            "f1040": _f1040_stub(),
        }
        scn = make_simple_scenario()
        out = f8995.compute(scn, up)
        self.assertEqual(out["f8995_line_1_qbi"], 10_000)


if __name__ == "__main__":
    unittest.main()
