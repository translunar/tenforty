"""Form 8995 simple-QBI compute tests."""

import unittest

from tenforty.forms import f8995
from tenforty.models import K1FanoutData, ScheduleK1

from tests.helpers import make_k1_scenario


def _scenario_with_qbi(qbi: float = 20_000.0, taxable_income: float = 100_000.0,
                       net_cap_gain: float = 0.0):
    s = make_k1_scenario()
    s.schedule_k1s = [ScheduleK1(
        entity_name="Fake S-Corp Inc",
        entity_ein="00-0000000",
        entity_type="s_corp",
        material_participation=True,
        qbi_amount=qbi,
    )]
    fanout = K1FanoutData(
        sch_b_interest_additions=(),
        sch_b_dividend_additions=(),
        sch_d_short_term_additions=(),
        sch_d_long_term_additions=(),
        qbi_aggregate=qbi,
        qualified_dividends_aggregate=0.0,
        passive_activities=(),
    )
    upstream = {
        "f1040": {
            "taxable_income_before_qbi_deduction": taxable_income,
            "net_capital_gain": net_cap_gain,
        },
        "k1_fanout": fanout,
    }
    return s, upstream


class F8995SimpleTests(unittest.TestCase):
    def test_below_threshold_basic(self):
        s, upstream = _scenario_with_qbi()
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_1_qbi"], 20_000)
        self.assertEqual(out["f8995_line_3_component"], 4_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 4_000)

    def test_income_limit_binds(self):
        s, upstream = _scenario_with_qbi(
            qbi=100_000.0, taxable_income=50_000.0, net_cap_gain=10_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        # line_13 = 50_000 - 10_000 = 40_000
        # line_14 = 0.20 * 40_000 = 8_000
        # line_6  = 0.20 * 100_000 = 20_000
        # line_15 = min(20_000, 8_000) = 8_000
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 8_000)


class F8995ThresholdGateTests(unittest.TestCase):
    def test_above_threshold_with_qbi_raises(self):
        s, upstream = _scenario_with_qbi(
            qbi=20_000.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_qbi_below_threshold"
        ):
            f8995.compute(s, upstream=upstream)

    def test_above_threshold_with_qbi_ok_when_attestation_true(self):
        s, upstream = _scenario_with_qbi(
            qbi=20_000.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = True
        out = f8995.compute(s, upstream=upstream)
        self.assertIn("f8995_line_15_qbi_deduction", out)

    def test_above_threshold_but_no_qbi_never_raises(self):
        """High-earner return with no QBI — the 8995-A scope gate must
        not fire, because there is no QBI to deduct at all."""
        s, upstream = _scenario_with_qbi(
            qbi=0.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)


class F8995QbiThresholdYearAwarenessTests(unittest.TestCase):
    """Verify f8995.compute uses year-correct QBI threshold from FederalParams."""

    def test_2024_threshold_191950_gates_correctly(self):
        """2024 single threshold is $191,950. Taxable income of $195k exceeds it
        → NotImplementedError when QBI > 0 and attestation is False."""
        s, upstream = _scenario_with_qbi(qbi=20_000.0, taxable_income=195_000.0)
        s.config.year = 2024
        s.config.acknowledges_qbi_below_threshold = False
        with self.assertRaisesRegex(NotImplementedError, "acknowledges_qbi_below_threshold"):
            f8995.compute(s, upstream=upstream)

    def test_2025_threshold_197300_does_not_gate_at_195k(self):
        """2025 single threshold is $197,300. Taxable income of $195k is below it
        → should NOT raise; deduction computed normally."""
        s, upstream = _scenario_with_qbi(qbi=20_000.0, taxable_income=195_000.0)
        s.config.year = 2025
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertIn("f8995_line_15_qbi_deduction", out)
        self.assertGreater(out["f8995_line_15_qbi_deduction"], 0)


if __name__ == "__main__":
    unittest.main()
