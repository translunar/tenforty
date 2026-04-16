"""Unit tests for tests/oracles/sch_d_540_reference.py (CA FTB Schedule D (540)).

unittest.TestCase convention, imports at top, no silent fallthrough.
TDD discipline: each test-function is written and observed to fail before
its implementation lands.
"""

import unittest

from tests.oracles.sch_d_540_reference import (
    SchD540Input,
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
        )
        out = compute_sch_d_540(inp)
        # The key that downstream CA 540 oracle consumes on
        # SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions
        # should be zero when there are no deltas to report.
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 0.0)


if __name__ == "__main__":
    unittest.main()
