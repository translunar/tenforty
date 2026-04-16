"""Unit tests for tests/oracles/sch_d_540_reference.py (CA FTB Schedule D (540)).

unittest.TestCase convention, imports at top, no silent fallthrough.
TDD discipline: each test-function is written and observed to fail before
its implementation lands.
"""

import unittest

from tests.oracles.sch_d_540_reference import (
    SchD540Input,
    Transaction,
    compute_sch_d_540,
)


class EmptyInputTests(unittest.TestCase):
    """Degenerate case: no transactions, no carryover — should produce a
    zero CA-federal delta and a well-formed output dict."""

    def test_empty_input_produces_zero_ca_delta(self):
        inp = SchD540Input(
            filing_status="single",
            transactions=(),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=0.0,
        )
        out = compute_sch_d_540(inp)
        # The key that downstream CA 540 oracle consumes on
        # SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions
        # should be zero when there are no deltas to report.
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 0.0)


class IdentityCaseTests(unittest.TestCase):
    """CA recognizes identical gain/loss to federal on every transaction.
    Lines 4, 8, 10, 11 all equal; lines 12a and 12b both zero; aggregate
    delta to Sch CA line 7 is zero. This exercises the full line 1-12
    structure without any nonconformity delta."""

    def test_single_gain_transaction_identity_produces_zero_delta(self):
        # One CA transaction with a $60 gain. Federal 1040 line 7a
        # aggregates to the same $60 (pure-identity case — no federal
        # inclusion adjustments, no other federal capital gain items).
        t = Transaction(
            description="Identity stock sale",
            ca_gain_or_loss=60.0,
        )
        inp = SchD540Input(
            filing_status="single",
            transactions=(t,),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=60.0,
        )
        out = compute_sch_d_540(inp)

        # Line 4: total 2025 gains from all sources (col (e) amounts).
        self.assertEqual(out["schd_540_line_4_total_gains"], 60.0)
        # Line 5: total 2025 losses (col (d) amounts). Identity gain → zero.
        self.assertEqual(out["schd_540_line_5_total_losses"], 0.0)
        # Line 6: CA capital loss carryover from prior year.
        self.assertEqual(out["schd_540_line_6_ca_carryover_from_prior_year"], 0.0)
        # Line 7: total 2025 loss = line 5 + line 6.
        self.assertEqual(out["schd_540_line_7_total_losses_with_carryover"], 0.0)
        # Line 8: net gain or (loss) = line 4 + line 7 (combine with signs).
        self.assertEqual(out["schd_540_line_8_net_gain_or_loss"], 60.0)
        # Line 10: federal 1040 line 7a amount (scalar pass-through).
        self.assertEqual(out["schd_540_line_10_federal_1040_line_7a"], 60.0)
        # Line 11: CA gain from line 8 (or loss from line 9 if net loss).
        self.assertEqual(out["schd_540_line_11_ca_gain_or_loss"], 60.0)
        # Line 12a: subtraction to Sch CA 540 Part I line 7 col B
        # (positive when fed > CA). Identity → zero.
        self.assertEqual(out["schd_540_line_12a_subtraction_col_b"], 0.0)
        # Line 12b: addition to Sch CA 540 Part I line 7 col C
        # (positive when CA > fed). Identity → zero.
        self.assertEqual(out["schd_540_line_12b_addition_col_c"], 0.0)
        # Aggregate signed delta (the integration-stable key).
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 0.0)


if __name__ == "__main__":
    unittest.main()
