"""Unit tests for tests/oracles/sch_p_540_reference.py.

Follows project convention: ``unittest.TestCase`` subclasses, imports at top,
no silent fallthrough. See tests/oracles/README.md for oracle scope.
"""

import unittest
from dataclasses import replace

from tests.oracles.sch_p_540_reference import (
    SchP540Input,
    compute_sch_p_540,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
def _make_minimal_input() -> SchP540Input:
    """Baseline input: std-ded single filer, CA-TI below any phaseout, no
    adjustments/NOL/exclusion/AMT-NOL. Represents the 'nothing weird' case
    the oracle must handle first."""
    return SchP540Input(
        filing_status="single",
        federal_agi=50_000.0,
        ca_taxable_income=44_294.0,       # 50k − 5_706 std ded
        ca_regular_tax_before_credits=1_000.0,
        itemized_deduction_used=False,
        standard_deduction_amount=5_706.0,
    )


# ---------------------------------------------------------------------------
# Part I — AMTI build-up (std-ded branch baseline)
# ---------------------------------------------------------------------------
class PartIStandardDeductionBaselineTests(unittest.TestCase):
    def test_line_1_equals_standard_deduction_when_not_itemizing(self):
        """Form face: 'If you did not itemize, enter your standard deduction
        from Form 540 line 18.' Std-ded branch puts std_ded on line 1 and
        skips the itemized add-back section."""
        inp = _make_minimal_input()
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_1_std_ded_or_zero"], 5_706.0)

    def test_line_15_equals_ca_taxable_income(self):
        """Form face line 15: 'Taxable income from Form 540, line 19'."""
        inp = _make_minimal_input()
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_15_ca_taxable_income"], 44_294.0)

    def test_line_21_amti_is_std_ded_plus_ca_taxable_income(self):
        """Baseline: no adjustments, no NOL, no exclusion, no AMT-NOL.
        Line 14 = line 1 (only line populated). Line 19 = line 14 + line 15.
        Line 21 = line 19 − 0. So AMTI = std_ded + ca_taxable_income,
        which equals CA AGI (pre-std-ded starting point)."""
        inp = _make_minimal_input()
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_21_amti"], 5_706.0 + 44_294.0)

    def test_amti_key_matches_line_21(self):
        """Summary key is the same number as the form-face line."""
        inp = _make_minimal_input()
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_amti"], out["schp_540_line_21_amti"])


if __name__ == "__main__":
    unittest.main()
