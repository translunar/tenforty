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
            # 1040 line 3a TOTAL (1099-DIV + K-1), which f8995.compute reads
            # strictly. This fixture's TRUE total is 0: make_k1_scenario()
            # carries no 1099-DIV, and the K-1 constructed above sets no
            # qualified dividends (hence qualified_dividends_aggregate=0.0
            # on the fanout). 0 is scenario-faithful here, not a value
            # chosen to satisfy the strict read.
            "qualified_dividends": 0.0,
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


class F8995NetCapitalGainFloorBoundaryTests(unittest.TestCase):
    """Pins the max(0, net_cap_gain) guard at the upstream dict boundary.

    Today's producers (both the compute path's `_preamble.net_capital_gain`
    and the emit path) already floor net_capital_gain at 0 before it reaches
    f8995, so a negative value can never arrive here in production. But
    `upstream` is a public boundary any caller can populate, and the guard
    matches the form itself: a net capital LOSS contributes nothing to line
    12, it never subtracts. Unit tests build the upstream stub directly, so
    they can reach this boundary even though production producers cannot.
    """

    def test_negative_net_capital_gain_floored_at_upstream_boundary(self):
        """qualified_dividends=5,000, net_capital_gain=-8,000.

        line_12 = irs_round(max(0, net_cap_gain) + qualified_divs)
                = irs_round(max(0, -8_000) + 5_000)
                = irs_round(0 + 5_000)
                = 5_000

        The negative net_capital_gain contributes 0 -- it must NOT subtract
        from qualified_divs (which would wrongly yield -3,000).
        """
        s, upstream = _scenario_with_qbi(qbi=0.0, taxable_income=100_000.0,
                                          net_cap_gain=-8_000.0)
        upstream["f1040"]["qualified_dividends"] = 5_000.0
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_12_net_capital_gain"], 5_000)


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


class F8995QbiLossZeroFloorTests(unittest.TestCase):
    """Pins the zero-floor on combined QBI (IRS Form 8995 line 4: "Total
    qualified business income. Combine lines 2 and 3. If zero or less, enter
    -0-.") and the companion loss-carryforward output (IRS line 16).

    Reproduces the defect: a loss-year S-corp (QBI = -30,000) previously
    produced a NEGATIVE deduction that increased taxable income instead of
    reducing it. The fix floors the combined QBI at 0 before it feeds the 20%
    component, so the deduction can never go negative, and surfaces the
    floored-off loss as a write-only carryforward (negative, per the sign
    convention documented in tenforty/forms/f8995.py).
    """

    def test_negative_qbi_deduction_floors_at_zero_not_negative(self):
        s, upstream = _scenario_with_qbi(
            qbi=-30_000.0, taxable_income=100_000.0, net_cap_gain=0.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)

    def test_printed_line_2_shows_the_unfloored_loss(self):
        """Line 2 is a PRINTED, PDF-mapped line (field f1_18 in both era
        mappings of tenforty/mappings/pdf_f8995.py) whose IRS caption is
        "Total qualified business income or (loss)" -- it must print the TRUE
        combine, loss and all. A prior fix floored it at zero, which made the
        emitted form contradict itself: line 1 showed -30,000 while line 2
        claimed 0. The zero floor belongs strictly DOWNSTREAM, at the 20%
        component (line 3) and everything fed from it, never at line 2's
        printed value."""
        s, upstream = _scenario_with_qbi(
            qbi=-30_000.0, taxable_income=100_000.0, net_cap_gain=0.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_1_qbi"], -30_000)
        self.assertEqual(out["f8995_line_2_total_qbi"], -30_000)
        self.assertEqual(out["f8995_line_3_component"], 0)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)

    def test_negative_qbi_carryforward_carries_the_loss(self):
        """SIGN CONVENTION under test: the carryforward is stored NEGATIVE,
        mirroring whatever the DOWNSTREAM floor (`floored_qbi`) removes from
        the combined QBI. (Line 2 itself is no longer floored -- it prints
        the loss; see test_printed_line_2_shows_the_unfloored_loss.) A
        -30,000 QBI year must carry forward exactly -30,000, not +30,000 and
        not the post-floor 0."""
        s, upstream = _scenario_with_qbi(
            qbi=-30_000.0, taxable_income=100_000.0, net_cap_gain=0.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], -30_000)

    def test_zero_qbi_deduction_and_carryforward_both_zero(self):
        """Boundary: QBI exactly 0 is neither a gain nor a loss year -- the
        deduction is 0 (nothing to deduct) and there is no loss to carry."""
        s, upstream = _scenario_with_qbi(
            qbi=0.0, taxable_income=100_000.0, net_cap_gain=0.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], 0)

    def test_positive_qbi_deduction_and_carryforward_unchanged(self):
        """Regression guard: the floor must be a no-op on the normal
        (positive-QBI) path. Same figures as
        F8995SimpleTests.test_below_threshold_basic -- real computed values,
        not tautologies -- plus the new line_16 key, which must be 0 (no
        loss to carry forward in a profit year)."""
        s, upstream = _scenario_with_qbi(
            qbi=20_000.0, taxable_income=100_000.0, net_cap_gain=0.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_1_qbi"], 20_000)
        self.assertEqual(out["f8995_line_2_total_qbi"], 20_000)
        self.assertEqual(out["f8995_line_3_component"], 4_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 4_000)
        self.assertEqual(out["f8995_line_16_qbi_loss_carryforward"], 0)


if __name__ == "__main__":
    unittest.main()
