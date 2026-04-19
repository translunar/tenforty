"""Unit tests for tests/oracles/sch_p_540_reference.py.

Follows project convention: ``unittest.TestCase`` subclasses, imports at top,
no silent fallthrough. See tests/oracles/README.md for oracle scope.
"""

import unittest
from dataclasses import replace

from tests.oracles.sch_p_540_reference import (
    PartIAdjustments,
    SchP540Input,
    compute_sch_p_540,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------
def _make_zero_adjustments() -> PartIAdjustments:
    return PartIAdjustments(
        medical_dental=0.0,
        property_taxes=0.0,
        home_mortgage_interest=0.0,
        misc_itemized=0.0,
        property_tax_refund=0.0,
        investment_interest=0.0,
        post_1986_depreciation=0.0,
        adjusted_gain_or_loss=0.0,
        iso_cqso=0.0,
        passive_activity=0.0,
        estate_trust_beneficiary=0.0,
        other_adjustments_preferences=0.0,
    )


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
        adjustments=_make_zero_adjustments(),
        ca_nol_deductions_9b=0.0,
        amti_exclusion_amount=0.0,
        amt_nol_deduction_post_90pct_cap=0.0,
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


# ---------------------------------------------------------------------------
# Part I — Itemized-deduction branch
# ---------------------------------------------------------------------------
class PartIItemizedBranchTests(unittest.TestCase):
    def test_line_1_is_zero_when_itemizing(self):
        inp = replace(
            _make_minimal_input(),
            itemized_deduction_used=True,
            standard_deduction_amount=0.0,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_1_std_ded_or_zero"], 0.0)

    def test_itemized_add_backs_flow_to_line_14(self):
        """Lines 2-7 add-backs (property taxes, misc) flow into line 14."""
        adj = PartIAdjustments(
            medical_dental=500.0,
            property_taxes=8_000.0,
            home_mortgage_interest=2_000.0,
            misc_itemized=1_000.0,
            property_tax_refund=-300.0,
            investment_interest=200.0,
            post_1986_depreciation=0.0,
            adjusted_gain_or_loss=0.0,
            iso_cqso=0.0,
            passive_activity=0.0,
            estate_trust_beneficiary=0.0,
            other_adjustments_preferences=0.0,
        )
        inp = replace(
            _make_minimal_input(),
            itemized_deduction_used=True,
            standard_deduction_amount=0.0,
            adjustments=adj,
        )
        out = compute_sch_p_540(inp)
        expected_14 = 500.0 + 8_000.0 + 2_000.0 + 1_000.0 + (-300.0) + 200.0
        self.assertEqual(out["schp_540_line_14_total_adjustments_preferences"],
                         expected_14)

    def test_amti_with_itemized_add_backs(self):
        """AMTI = CA_TI + line 14 (all add-backs) when no NOL/exclusion."""
        adj = PartIAdjustments(
            medical_dental=0.0,
            property_taxes=10_000.0,
            home_mortgage_interest=0.0,
            misc_itemized=0.0,
            property_tax_refund=0.0,
            investment_interest=0.0,
            post_1986_depreciation=0.0,
            adjusted_gain_or_loss=0.0,
            iso_cqso=0.0,
            passive_activity=0.0,
            estate_trust_beneficiary=0.0,
            other_adjustments_preferences=0.0,
        )
        ca_ti = 80_000.0
        inp = replace(
            _make_minimal_input(),
            ca_taxable_income=ca_ti,
            itemized_deduction_used=True,
            standard_deduction_amount=0.0,
            adjustments=adj,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_amti"], ca_ti + 10_000.0)


# ---------------------------------------------------------------------------
# Part I — CA-basis adjustments (lines 8-13) + lines 16-20
# ---------------------------------------------------------------------------
class PartIAdjustmentsAndNOLTests(unittest.TestCase):
    def test_iso_cqso_flows_to_line_10(self):
        adj = replace(_make_zero_adjustments(), iso_cqso=25_000.0)
        inp = replace(_make_minimal_input(), adjustments=adj)
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_10_iso_cqso"], 25_000.0)

    def test_post_1986_depreciation_flows_to_line_8(self):
        adj = replace(_make_zero_adjustments(), post_1986_depreciation=12_000.0)
        inp = replace(_make_minimal_input(), adjustments=adj)
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_8_post_1986_depreciation"], 12_000.0)

    def test_nol_add_back_increases_amti(self):
        """Line 16 (positive) adds back NOL deductions taken on Form 540."""
        inp = replace(
            _make_minimal_input(),
            ca_nol_deductions_9b=15_000.0,
        )
        out = compute_sch_p_540(inp)
        baseline = 5_706.0 + 44_294.0
        self.assertEqual(out["schp_540_amti"], baseline + 15_000.0)

    def test_amti_exclusion_reduces_amti(self):
        """Line 17 (negative) is the §17062.5 small-business exclusion."""
        inp = replace(
            _make_minimal_input(),
            amti_exclusion_amount=-5_000.0,
        )
        out = compute_sch_p_540(inp)
        baseline = 5_706.0 + 44_294.0
        self.assertEqual(out["schp_540_amti"], baseline + (-5_000.0))

    def test_amt_nol_reduces_amti(self):
        """Line 20 subtracts AMT-NOL from line 19 to produce AMTI (line 21)."""
        inp = replace(
            _make_minimal_input(),
            ca_taxable_income=100_000.0,
            amt_nol_deduction_post_90pct_cap=10_000.0,
        )
        out = compute_sch_p_540(inp)
        line_19 = 5_706.0 + 100_000.0
        self.assertEqual(out["schp_540_amti"], line_19 - 10_000.0)

    def test_amt_nol_exceeding_90pct_cap_raises(self):
        """Oracle asserts amt_nol_deduction ≤ 90% of line 19. Violation is
        a caller bug — R&TC §17276.20."""
        inp = replace(
            _make_minimal_input(),
            ca_taxable_income=100_000.0,
            amt_nol_deduction_post_90pct_cap=100_000.0,
        )
        with self.assertRaises(ValueError):
            compute_sch_p_540(inp)


if __name__ == "__main__":
    unittest.main()
