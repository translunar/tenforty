"""Unit tests for tests/oracles/sch_p_540_reference.py.

Follows project convention: ``unittest.TestCase`` subclasses, imports at top,
no silent fallthrough. See tests/oracles/README.md for oracle scope.
"""

import unittest
from dataclasses import replace

from tests.oracles.sch_p_540_reference import (
    CreditEntry,
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
        total_tax_before_credits=1_000.0,
        credits=(),
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


# ---------------------------------------------------------------------------
# Part II — Exemption, TMT, and AMT (lines 22-26)
# ---------------------------------------------------------------------------
class PartIIExemptionNoPhaseoutTests(unittest.TestCase):
    def test_single_exemption_below_phaseout(self):
        """AMTI below $347,808 → full $92,749 exemption for single filer."""
        inp = replace(_make_minimal_input(), ca_taxable_income=200_000.0)
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_22_exemption"], 92_749.0)

    def test_mfj_exemption_below_phaseout(self):
        inp = replace(
            _make_minimal_input(),
            filing_status="mfj",
            ca_taxable_income=300_000.0,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_22_exemption"], 123_667.0)

    def test_mfs_exemption_below_phaseout(self):
        inp = replace(
            _make_minimal_input(),
            filing_status="mfs",
            ca_taxable_income=150_000.0,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_22_exemption"], 61_830.0)


class PartIIExemptionPhaseoutTests(unittest.TestCase):
    def test_single_partial_phaseout(self):
        """AMTI $10,000 over threshold → exemption reduced by 25% × $10,000."""
        adj = _make_zero_adjustments()
        ca_ti = 347_808.0 + 10_000.0 - 5_706.0  # AMTI = ca_ti + std_ded = threshold + 10k
        inp = replace(_make_minimal_input(), ca_taxable_income=ca_ti)
        out = compute_sch_p_540(inp)
        expected = 92_749.0 - 0.25 * 10_000.0
        self.assertEqual(out["schp_540_line_22_exemption"], expected)

    def test_single_complete_phaseout(self):
        """AMTI at or above $718,804 (threshold + 4×exemption) → zero."""
        ca_ti = 718_804.0 - 5_706.0
        inp = replace(_make_minimal_input(), ca_taxable_income=ca_ti)
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_22_exemption"], 0.0)

    def test_mfs_complete_phaseout_matches_line_21_threshold(self):
        """Self-consistency: MFS complete-phaseout = $479,188 = threshold + 4 × exemption."""
        ca_ti = 479_188.0 - 5_706.0
        inp = replace(
            _make_minimal_input(),
            filing_status="mfs",
            ca_taxable_income=ca_ti,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_22_exemption"], 0.0)


class PartIITMTAndAMTTests(unittest.TestCase):
    def test_tmt_is_7pct_of_amti_minus_exemption(self):
        """Line 24 = (line 21 − line 22) × 7.0%, if positive."""
        ca_ti = 200_000.0
        inp = replace(_make_minimal_input(), ca_taxable_income=ca_ti)
        out = compute_sch_p_540(inp)
        amti = ca_ti + 5_706.0
        expected_tmt = (amti - 92_749.0) * 0.07
        self.assertAlmostEqual(out["schp_540_line_24_tmt"], expected_tmt)
        self.assertAlmostEqual(out["schp_540_tentative_minimum_tax"], expected_tmt)

    def test_amt_zero_when_regular_exceeds_tmt(self):
        """AMT = max(0, TMT − regular). If regular tax ≥ TMT, AMT = 0."""
        ca_ti = 44_294.0
        inp = replace(
            _make_minimal_input(),
            ca_taxable_income=ca_ti,
            ca_regular_tax_before_credits=50_000.0,
        )
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_line_26_amt"], 0.0)
        self.assertEqual(out["schp_540_amt_due"], 0.0)

    def test_amt_positive_when_tmt_exceeds_regular(self):
        """High AMTI (ISO bargain-element pushes it up) + low regular tax."""
        adj = replace(_make_zero_adjustments(), iso_cqso=500_000.0)
        inp = replace(
            _make_minimal_input(),
            ca_taxable_income=80_000.0,
            ca_regular_tax_before_credits=3_000.0,
            adjustments=adj,
        )
        out = compute_sch_p_540(inp)
        amti = 80_000.0 + 5_706.0 + 500_000.0
        exemption = max(0.0, 92_749.0 - 0.25 * max(0.0, amti - 347_808.0))
        tmt = max(0.0, (amti - exemption) * 0.07)
        expected_amt = max(0.0, tmt - 3_000.0)
        self.assertAlmostEqual(out["schp_540_line_26_amt"], expected_amt)
        self.assertAlmostEqual(out["schp_540_amt_due"], expected_amt)


# ---------------------------------------------------------------------------
# Part III — Credit limitations
# ---------------------------------------------------------------------------
class PartIIICreditLimitationTests(unittest.TestCase):
    def _make_amt_scenario(self) -> SchP540Input:
        """Scenario with AMT: ISO bargain pushes AMTI high, regular tax low."""
        adj = replace(_make_zero_adjustments(), iso_cqso=500_000.0)
        return replace(
            _make_minimal_input(),
            ca_taxable_income=80_000.0,
            ca_regular_tax_before_credits=3_000.0,
            total_tax_before_credits=3_000.0,
            adjustments=adj,
        )

    def test_no_credits_amt_due_unchanged(self):
        """With no credits supplied, Part III doesn't reduce anything."""
        inp = self._make_amt_scenario()
        out = compute_sch_p_540(inp)
        self.assertEqual(out["schp_540_amt_due"], out["schp_540_line_26_amt"])

    def test_section_a_credit_capped_at_excess_tax(self):
        """Section A credit (Code 232 child/dep care) cannot reduce tax
        below TMT. Cap = total_tax_before_credits − TMT."""
        inp = self._make_amt_scenario()
        tmt_preview = compute_sch_p_540(inp)["schp_540_line_24_tmt"]
        excess_tax = max(0.0, 3_000.0 - tmt_preview)

        inp = replace(
            inp,
            credits=(CreditEntry(code="232", amount=50_000.0),),
        )
        out = compute_sch_p_540(inp)
        capped = out["schp_540_credit_caps"]["232"]["capped"]
        self.assertAlmostEqual(capped, excess_tax)
        self.assertLessEqual(capped, 50_000.0)

    def test_section_b_ostc_can_reduce_below_tmt(self):
        """Section B credit Code 187 (OSTC) can reduce tax below TMT per
        R&TC §18001. If excess_tax is zero but the OSTC is $500, the
        OSTC can still be applied (up to remaining balance)."""
        inp = replace(
            self._make_amt_scenario(),
            credits=(CreditEntry(code="187", amount=500.0),),
        )
        out = compute_sch_p_540(inp)
        capped = out["schp_540_credit_caps"]["187"]["capped"]
        self.assertEqual(capped, 500.0)

    def test_section_c_solar_reduces_amt(self):
        """Section C credits (Code 180/181) reduce AMT itself. Adjusted
        AMT (Part III line 25) should be less than Part II line 26."""
        inp = replace(
            self._make_amt_scenario(),
            credits=(CreditEntry(code="180", amount=200.0),),
        )
        out = compute_sch_p_540(inp)
        self.assertAlmostEqual(
            out["schp_540_amt_due"],
            out["schp_540_line_26_amt"] - 200.0,
        )

    def test_section_c_solar_cannot_reduce_amt_below_zero(self):
        """Solar carryover can't make AMT negative."""
        inp = replace(
            self._make_amt_scenario(),
            credits=(CreditEntry(code="180", amount=999_999.0),),
        )
        out = compute_sch_p_540(inp)
        self.assertGreaterEqual(out["schp_540_amt_due"], 0.0)

    def test_credit_caps_contains_uncapped_and_capped(self):
        """Each credit in the output has both uncapped and capped values."""
        inp = replace(
            self._make_amt_scenario(),
            credits=(CreditEntry(code="232", amount=1_000.0),),
        )
        out = compute_sch_p_540(inp)
        entry = out["schp_540_credit_caps"]["232"]
        self.assertIn("uncapped", entry)
        self.assertIn("capped", entry)
        self.assertEqual(entry["uncapped"], 1_000.0)


if __name__ == "__main__":
    unittest.main()
