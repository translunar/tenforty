"""Unit tests for the CA 540 reference oracle.

The oracle is a hand-coded reference implementation of CA FTB Form 540 +
Schedule CA (540). These tests exercise the oracle's arithmetic with fully
synthetic scenarios — numbers are invented from scratch, divisible by $50
per tenforty's committed-fixture convention, and bear no resemblance to any
real taxpayer's return.

Tests are organized into focused sections matching the oracle's modules:
  - Tax rate schedule evaluation
  - Exemption credit counts and AGI phaseout worksheet
  - Schedule CA (540) Part I aggregation
  - Schedule CA (540) Part II itemized deduction + phaseout
  - Behavioral Health Services Tax
  - Nonrefundable Renter's Credit cliff
  - End-to-end synthetic scenarios
  - Scope-out gate behavior

Every test class subclasses ``unittest.TestCase`` (iron law 3); imports are
at module top (iron law 4).
"""

import dataclasses
import unittest

from tests.oracles.ca_540_reference import (
    AGI_PHASEOUT_THRESHOLD_2025,
    BHST_RATE_2025,
    BHST_THRESHOLD_2025,
    CA540Input,
    Demographics,
    EXEMPTION_CREDIT_DEPENDENT_2025,
    EXEMPTION_CREDIT_PERSONAL_2025,
    FederalCarryIn,
    Form540Credits,
    Form540Misc,
    Form540OtherTaxes,
    Form540Payments,
    RENTERS_CREDIT_AGI_LIMIT_HOUSEHOLD_2025,
    RENTERS_CREDIT_AGI_LIMIT_SINGLE_MFS_2025,
    RENTERS_CREDIT_HOUSEHOLD_2025,
    RENTERS_CREDIT_SINGLE_MFS_2025,
    STANDARD_DEDUCTION_2025,
    SchCAPartIAdjustments,
    SchCAPartIIAdjustments,
    ScopeOut,
    TAX_RATE_SCHEDULE_X_2025,
    TAX_RATE_SCHEDULE_Y_2025,
    TAX_RATE_SCHEDULE_Z_2025,
    _count_exemptions,
    _exemption_credits_after_phaseout,
    _exemption_credits_pre_phaseout,
    _tax_from_rate_schedule,
    compute_ca_540,
)


# ---------------------------------------------------------------------------
# Helpers — build a fully-zeroed input, then replace fields in specific tests.
# Synthetic throughout (iron law 1).
# ---------------------------------------------------------------------------
def _zero_sch_ca_part_i() -> SchCAPartIAdjustments:
    return SchCAPartIAdjustments(
        line_1_col_b_wage_subtractions=0.0,
        line_1_col_c_wage_additions=0.0,
        line_2_col_b_us_obligation_interest=0.0,
        line_2_col_c_non_ca_muni_interest=0.0,
        line_3_col_b_dividend_subtractions=0.0,
        line_3_col_c_dividend_additions=0.0,
        line_4_col_b_ira_subtractions=0.0,
        line_4_col_c_ira_additions=0.0,
        line_5_col_b_pension_subtractions=0.0,
        line_5_col_c_pension_additions=0.0,
        line_6_col_b_social_security_subtraction=0.0,
        line_7_col_b_capital_gain_subtractions=0.0,
        line_7_col_c_capital_gain_additions=0.0,
        line_sb_1_col_b_state_refund=0.0,
        line_sb_3_col_b_business_subtractions=0.0,
        line_sb_3_col_c_business_additions=0.0,
        line_sb_5_col_b_rental_subtractions=0.0,
        line_sb_5_col_c_rental_additions=0.0,
        line_sb_7_col_b_unemployment=0.0,
        line_sb_8_col_b_other_subtractions=0.0,
        line_sb_8_col_c_other_additions=0.0,
        line_sc_13_col_b_hsa_deduction_addback=0.0,
        line_sc_14_col_c_moving_expenses=0.0,
        line_sc_21_col_b_student_loan_subtractions=0.0,
        line_sc_21_col_c_student_loan_additions=0.0,
        line_sc_24z_col_b_other_adj_subtractions=0.0,
        line_sc_24z_col_c_other_adj_additions=0.0,
    )


def _zero_sch_ca_part_ii(*, itemize: bool = False) -> SchCAPartIIAdjustments:
    return SchCAPartIIAdjustments(
        fed_sch_a_medical_expenses=0.0,
        fed_sch_a_state_and_local_tax_pre_cap=0.0,
        fed_sch_a_state_income_tax=0.0,
        fed_sch_a_foreign_income_tax=0.0,
        fed_sch_a_foreign_real_property_tax=0.0,
        fed_sch_a_generation_skipping_tax=0.0,
        fed_sch_a_salt_capped_total=0.0,
        fed_sch_a_mortgage_interest_on_1098=0.0,
        fed_sch_a_mortgage_interest_not_on_1098=0.0,
        fed_sch_a_points_not_on_1098=0.0,
        fed_sch_a_mortgage_interest_federally_limited_excess=0.0,
        fed_sch_a_home_equity_interest_federally_disallowed=0.0,
        fed_sch_a_mortgage_interest_credit_reduction=0.0,
        fed_sch_a_investment_interest=0.0,
        fed_sch_a_gifts_cash=0.0,
        fed_sch_a_gifts_noncash=0.0,
        fed_sch_a_gifts_carryover=0.0,
        fed_sch_a_casualty_federally_declared=0.0,
        fed_sch_a_gambling_losses=0.0,
        fed_sch_a_other_itemized_excl_gambling=0.0,
        medical_col_c_sehi_itemized=0.0,
        medical_col_c_hsa_qualified_dist_over_floor=0.0,
        charitable_col_b_conservation_contribution_over_30pct=0.0,
        charitable_col_b_ca_access_tax_credit_donation=0.0,
        charitable_col_c_college_seating=0.0,
        charitable_col_b_noncash_over_50pct=0.0,
        charitable_col_c_charitable_carryover_difference=0.0,
        charitable_col_b_charitable_carryover_difference=0.0,
        casualty_ca_nonfederal_declared=0.0,
        gambling_col_b_ca_lottery_losses=0.0,
        other_itemized_col_b_estate_tax_on_ird=0.0,
        ca_unreimbursed_employee_expenses=0.0,
        ca_tax_preparation_fees=0.0,
        ca_other_investment_and_misc_expenses=0.0,
        line_27_other_adjustments=0.0,
        itemize=itemize,
    )


def _zero_payments() -> Form540Payments:
    return Form540Payments(
        line_71_ca_withholding=0.0,
        line_72_estimated_payments_and_carryover=0.0,
        line_73_592b_593_withholding=0.0,
        line_74_motion_picture_credit=0.0,
        line_75_eitc=0.0,
        line_76_yctc=0.0,
        line_77_fytc=0.0,
    )


def _zero_credits() -> Form540Credits:
    return Form540Credits(
        dep_care_federal_agi_for_eligibility=0.0,
        dep_care_credit_amount=0.0,
        eligible_for_renters_credit=False,
        other_nonrefundable_credits=0.0,
    )


def _zero_other_taxes() -> Form540OtherTaxes:
    return Form540OtherTaxes(line_63_other_taxes=0.0)


def _zero_misc() -> Form540Misc:
    return Form540Misc(
        line_91_use_tax=0.0,
        line_98_overpayment_applied_to_2026=0.0,
        line_110_voluntary_contributions=0.0,
    )


def _zero_scope_out() -> ScopeOut:
    return ScopeOut(
        amt_preferences_present=False,
        lump_sum_distribution_tax=0.0,
        accumulation_distribution_tax=0.0,
        kiddie_tax_child_filer=False,
        nol_deduction=0.0,
        excess_business_loss_adjustment=0.0,
        isr_penalty=0.0,
        underpayment_penalty=0.0,
    )


def _make_input(
    *,
    filing_status: str = "single",
    federal_agi: float = 0.0,
    state_wages: float = 0.0,
    can_be_claimed: bool = False,
    taxpayer_65: bool = False,
    spouse_65: bool = False,
    taxpayer_blind: bool = False,
    spouse_blind: bool = False,
    dependent_count: int = 0,
    dependent_earned_income: float = 0.0,
) -> CA540Input:
    return CA540Input(
        demographics=Demographics(
            filing_status=filing_status,
            can_be_claimed_as_dependent=can_be_claimed,
            taxpayer_age_65_or_older=taxpayer_65,
            spouse_age_65_or_older=spouse_65,
            taxpayer_blind=taxpayer_blind,
            spouse_blind=spouse_blind,
            dependent_count=dependent_count,
            dependent_earned_income=dependent_earned_income,
        ),
        federal=FederalCarryIn(
            federal_agi=federal_agi,
            state_wages_from_w2_box16=state_wages,
        ),
        sch_ca_part_i=_zero_sch_ca_part_i(),
        sch_ca_part_ii=_zero_sch_ca_part_ii(),
        payments=_zero_payments(),
        credits=_zero_credits(),
        other_taxes=_zero_other_taxes(),
        misc=_zero_misc(),
        scope_out=_zero_scope_out(),
    )


# ---------------------------------------------------------------------------
# Tax rate schedule tests
# ---------------------------------------------------------------------------
class TaxRateScheduleTests(unittest.TestCase):
    def test_zero_taxable_income_yields_zero_tax(self):
        self.assertEqual(
            _tax_from_rate_schedule(0.0, TAX_RATE_SCHEDULE_X_2025), 0.0
        )
        self.assertEqual(
            _tax_from_rate_schedule(-500.0, TAX_RATE_SCHEDULE_Y_2025), 0.0
        )

    def test_single_schedule_bottom_bracket_is_1_percent(self):
        # $10,000 is entirely within the first 1% bracket on Schedule X.
        # Expected tax = 10,000 * 0.01 = 100.0
        self.assertAlmostEqual(
            _tax_from_rate_schedule(10_000.0, TAX_RATE_SCHEDULE_X_2025),
            100.0,
            places=6,
        )

    def test_single_schedule_second_bracket(self):
        # $20,000 taxable (Schedule X): spans first two brackets.
        # First bracket ends at $11,079 (tax $110.79), then 2% on remainder.
        expected = 110.79 + (20_000.0 - 11_079.0) * 0.02
        self.assertAlmostEqual(
            _tax_from_rate_schedule(20_000.0, TAX_RATE_SCHEDULE_X_2025),
            expected,
            places=6,
        )

    def test_mfj_schedule_middle_bracket(self):
        # $100,000 taxable on Schedule Y: lands in the 6% bracket.
        # Base at $82,904 is $2,044.02; rate 6% on excess.
        expected = 2_044.02 + (100_000.0 - 82_904.0) * 0.06
        self.assertAlmostEqual(
            _tax_from_rate_schedule(100_000.0, TAX_RATE_SCHEDULE_Y_2025),
            expected,
            places=6,
        )

    def test_hoh_schedule_middle_bracket(self):
        # $70,000 taxable on Schedule Z: lands in the 6% bracket.
        expected = 1_436.31 + (70_000.0 - 67_716.0) * 0.06
        self.assertAlmostEqual(
            _tax_from_rate_schedule(70_000.0, TAX_RATE_SCHEDULE_Z_2025),
            expected,
            places=6,
        )

    def test_top_bracket_single(self):
        # $1,000,000 taxable on Schedule X lands in the 12.3% top bracket.
        expected = 72_219.84 + (1_000_000.0 - 742_953.0) * 0.123
        self.assertAlmostEqual(
            _tax_from_rate_schedule(1_000_000.0, TAX_RATE_SCHEDULE_X_2025),
            expected,
            places=6,
        )


# ---------------------------------------------------------------------------
# Exemption credit tests
# ---------------------------------------------------------------------------
class ExemptionCountTests(unittest.TestCase):
    def test_single_filer_claims_one_personal(self):
        ca = _make_input(filing_status="single")
        self.assertEqual(_count_exemptions(ca), (1, 0, 0, 0))

    def test_mfj_filer_claims_two_personal(self):
        ca = _make_input(filing_status="mfj")
        self.assertEqual(_count_exemptions(ca), (2, 0, 0, 0))

    def test_senior_and_blind_both_counted(self):
        ca = _make_input(
            filing_status="single",
            taxpayer_65=True,
            taxpayer_blind=True,
        )
        self.assertEqual(_count_exemptions(ca), (1, 1, 1, 0))

    def test_mfj_both_spouses_senior(self):
        ca = _make_input(
            filing_status="mfj", taxpayer_65=True, spouse_65=True
        )
        self.assertEqual(_count_exemptions(ca), (2, 2, 0, 0))

    def test_can_be_claimed_zeroes_personal_for_single(self):
        ca = _make_input(filing_status="single", can_be_claimed=True)
        self.assertEqual(_count_exemptions(ca), (0, 0, 0, 0))

    def test_can_be_claimed_zeroes_senior_and_blind(self):
        # Even if the dependent is 65+ and blind, those credits are zeroed.
        ca = _make_input(
            filing_status="single",
            can_be_claimed=True,
            taxpayer_65=True,
            taxpayer_blind=True,
        )
        self.assertEqual(_count_exemptions(ca), (0, 0, 0, 0))

    def test_dependent_count_passes_through(self):
        ca = _make_input(filing_status="mfj", dependent_count=3)
        self.assertEqual(_count_exemptions(ca), (2, 0, 0, 3))


class DependentStandardDeductionTests(unittest.TestCase):
    """FTB 2025 Standard Deduction Worksheet for Dependents (line 18).

    Worksheet: greater-of(earned_income + $450, $1,350) capped at the
    filing-status base ($5,706 single/MFS, $11,412 MFJ/HOH/QSS).
    """

    def test_not_claimable_returns_full_base(self):
        # Filer not claimable as dependent: worksheet does not apply.
        ca = _make_input(filing_status="single", can_be_claimed=False)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_18_deduction"], STANDARD_DEDUCTION_2025["single"]
        )

    def test_claimable_zero_earned_income_returns_floor(self):
        # earned + $450 = $450; floor = $1,350 > $450 → $1,350.
        ca = _make_input(
            filing_status="single",
            can_be_claimed=True,
            dependent_earned_income=0.0,
        )
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_18_deduction"], 1_350.0)

    def test_claimable_exactly_900_earned_still_returns_floor(self):
        # earned + $450 = $1,350 = floor → $1,350 (tie goes to greater-of).
        ca = _make_input(
            filing_status="single",
            can_be_claimed=True,
            dependent_earned_income=900.0,
        )
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_18_deduction"], 1_350.0)

    def test_claimable_moderate_earned_uses_earned_plus_450(self):
        # earned $3,000 + $450 = $3,450 > floor $1,350 → $3,450 (below cap).
        ca = _make_input(
            filing_status="single",
            can_be_claimed=True,
            dependent_earned_income=3_000.0,
        )
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_18_deduction"], 3_450.0)

    def test_claimable_earned_above_cap_capped_at_filing_status_base(self):
        # earned $10,000 + $450 = $10,450 > single cap $5,706 → $5,706.
        ca = _make_input(
            filing_status="single",
            can_be_claimed=True,
            dependent_earned_income=10_000.0,
        )
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_18_deduction"], STANDARD_DEDUCTION_2025["single"]
        )


class ExemptionCreditPhaseoutTests(unittest.TestCase):
    def test_below_threshold_no_phaseout(self):
        ca = _make_input(filing_status="single", federal_agi=100_000.0)
        pre_789, pre_10 = _exemption_credits_pre_phaseout(ca)
        self.assertAlmostEqual(
            _exemption_credits_after_phaseout(ca), pre_789 + pre_10
        )
        # Single with no seniors/blind/deps: just 1 × personal credit.
        self.assertAlmostEqual(pre_789, EXEMPTION_CREDIT_PERSONAL_2025)
        self.assertAlmostEqual(pre_10, 0.0)

    def test_at_threshold_no_phaseout(self):
        ca = _make_input(
            filing_status="single",
            federal_agi=AGI_PHASEOUT_THRESHOLD_2025["single"],
        )
        pre_789, pre_10 = _exemption_credits_pre_phaseout(ca)
        self.assertAlmostEqual(
            _exemption_credits_after_phaseout(ca), pre_789 + pre_10
        )

    def test_one_block_over_threshold_reduces_by_6(self):
        # $2,500 over threshold → 1 block → $6 reduction per credit.
        # Single filer with 1 personal credit (count_789 = 1).
        agi = AGI_PHASEOUT_THRESHOLD_2025["single"] + 2_500.0
        ca = _make_input(filing_status="single", federal_agi=agi)
        expected = EXEMPTION_CREDIT_PERSONAL_2025 - 6.0
        self.assertAlmostEqual(_exemption_credits_after_phaseout(ca), expected)

    def test_partial_block_rounds_up(self):
        # $1 over threshold still counts as 1 block (ceiling).
        agi = AGI_PHASEOUT_THRESHOLD_2025["single"] + 1.0
        ca = _make_input(filing_status="single", federal_agi=agi)
        expected = EXEMPTION_CREDIT_PERSONAL_2025 - 6.0
        self.assertAlmostEqual(_exemption_credits_after_phaseout(ca), expected)

    def test_mfs_uses_1250_block_size(self):
        # $1,250 over threshold → 1 block for MFS. Personal count = 1 for
        # MFS (filing status 3 → 1 person). Reduction = $6.
        agi = AGI_PHASEOUT_THRESHOLD_2025["mfs"] + 1_250.0
        ca = _make_input(filing_status="mfs", federal_agi=agi)
        expected = EXEMPTION_CREDIT_PERSONAL_2025 - 6.0
        self.assertAlmostEqual(_exemption_credits_after_phaseout(ca), expected)

    def test_dependent_credit_phased_separately(self):
        # MFJ + 2 dependents, AGI $2,500 over the MFJ threshold.
        # count_789 = 2 (personal), count_10 = 2 (deps).
        # Reduction per count per block = $6. Blocks = 1.
        # Line 7-9 credits (pre): 2 × $153 = $306 → after: $306 − $12 = $294.
        # Line 10 credits (pre): 2 × $475 = $950 → after: $950 − $12 = $938.
        # Total = $294 + $938 = $1,232.
        agi = AGI_PHASEOUT_THRESHOLD_2025["mfj"] + 2_500.0
        ca = _make_input(
            filing_status="mfj", federal_agi=agi, dependent_count=2
        )
        expected_789 = 2 * EXEMPTION_CREDIT_PERSONAL_2025 - 2 * 6.0
        expected_10 = 2 * EXEMPTION_CREDIT_DEPENDENT_2025 - 2 * 6.0
        self.assertAlmostEqual(
            _exemption_credits_after_phaseout(ca),
            expected_789 + expected_10,
        )

    def test_phaseout_cannot_reduce_below_zero(self):
        # Massive AGI — reduction exceeds the credit value.
        agi = AGI_PHASEOUT_THRESHOLD_2025["single"] + 100_000_000.0
        ca = _make_input(filing_status="single", federal_agi=agi)
        self.assertEqual(_exemption_credits_after_phaseout(ca), 0.0)


# ---------------------------------------------------------------------------
# Schedule CA Part I aggregation
# ---------------------------------------------------------------------------
class SchCAPart1AggregationTests(unittest.TestCase):
    def test_social_security_always_subtracted(self):
        # CA never taxes SS; col B subtraction = full amount.
        ca = _make_input(filing_status="single", federal_agi=50_000.0)
        new_p1 = dataclasses.replace(
            ca.sch_ca_part_i,
            line_6_col_b_social_security_subtraction=12_000.0,
        )
        ca = dataclasses.replace(ca, sch_ca_part_i=new_p1)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["schca_part_1_line_27_col_b"], 12_000.0)
        self.assertAlmostEqual(out["schca_part_1_line_27_col_c"], 0.0)

    def test_hsa_addback_reduces_adjustments(self):
        # Federal HSA deduction adds back as Section C line 13 col B.
        # Line 27 col B = line 10 col B − line 25 col B = 0 − 3_000 = -3_000.
        # Negative col B means CA AGI is HIGHER than federal AGI by $3,000
        # (Form 540 line 15 = line 13 − line 14 = fed_agi − (-3_000) = +3_000).
        ca = _make_input(filing_status="single", federal_agi=100_000.0)
        new_p1 = dataclasses.replace(
            ca.sch_ca_part_i,
            line_sc_13_col_b_hsa_deduction_addback=3_000.0,
        )
        ca = dataclasses.replace(ca, sch_ca_part_i=new_p1)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["schca_part_1_line_27_col_b"], -3_000.0)
        # Line 15 should therefore be 100_000 - (-3_000) = 103_000.
        self.assertAlmostEqual(out["f540_line_15"], 103_000.0)

    def test_non_ca_muni_interest_addition(self):
        ca = _make_input(filing_status="mfj", federal_agi=150_000.0)
        new_p1 = dataclasses.replace(
            ca.sch_ca_part_i,
            line_2_col_c_non_ca_muni_interest=2_500.0,
        )
        ca = dataclasses.replace(ca, sch_ca_part_i=new_p1)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["schca_part_1_line_27_col_c"], 2_500.0)
        self.assertAlmostEqual(out["f540_line_17_ca_agi"], 152_500.0)


# ---------------------------------------------------------------------------
# Schedule CA Part II itemized tests
# ---------------------------------------------------------------------------
class SchCAPart2ItemizedTests(unittest.TestCase):
    def test_salt_cap_addback_restores_state_property_tax(self):
        # Scenario: $25k state income tax + $20k property tax = $45k SALT.
        # Federal 2025 cap is $40k → federal deducts $40k.
        # CA col B removes state income tax ($25k). CA col C restores the $5k
        # over the federal cap. Net CA taxes line 5e = $45k − $25k = $20k.
        ca = _make_input(filing_status="single", federal_agi=300_000.0)
        new_p2 = dataclasses.replace(
            ca.sch_ca_part_ii,
            fed_sch_a_state_and_local_tax_pre_cap=45_000.0,
            fed_sch_a_state_income_tax=25_000.0,
            fed_sch_a_salt_capped_total=40_000.0,
            itemize=True,
        )
        ca = dataclasses.replace(ca, sch_ca_part_ii=new_p2)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["schca_part_2_line_5e_ca_salt"], 20_000.0
        )

    def test_itemized_phaseout_at_high_agi(self):
        # $100,000 itemized (all charitable — "unprotected"), single filer,
        # federal AGI = threshold + $50,000.
        # Reduction = min(80% × 100k, 6% × 50k) = min(80k, 3k) = 3k.
        # Line 29 = 100k − 3k = 97k.
        ca = _make_input(
            filing_status="single",
            federal_agi=AGI_PHASEOUT_THRESHOLD_2025["single"] + 50_000.0,
        )
        new_p2 = dataclasses.replace(
            ca.sch_ca_part_ii, fed_sch_a_gifts_cash=100_000.0, itemize=True
        )
        ca = dataclasses.replace(ca, sch_ca_part_ii=new_p2)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["schca_part_2_line_29_ca_itemized_post_phaseout"], 97_000.0
        )

    def test_itemized_phaseout_medical_protected(self):
        # Same scenario, but deduction is entirely medical (protected).
        # Reduction floor: unprotected = 0 → no reduction, line 29 = full.
        #
        # Medical is also subject to a 7.5% AGI floor — so at federal AGI
        # $302,203 (threshold + 50k), the 7.5% floor is $22,665.225. For a
        # medical input that exceeds this floor substantially, the resulting
        # CA line 4 (medical deductible) is the input minus the floor.
        federal_agi = AGI_PHASEOUT_THRESHOLD_2025["single"] + 50_000.0
        medical_input = 150_000.0
        expected_medical = medical_input - federal_agi * 0.075
        ca = _make_input(filing_status="single", federal_agi=federal_agi)
        new_p2 = dataclasses.replace(
            ca.sch_ca_part_ii,
            fed_sch_a_medical_expenses=medical_input,
            itemize=True,
        )
        ca = dataclasses.replace(ca, sch_ca_part_ii=new_p2)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["schca_part_2_line_4_ca_medical"], expected_medical
        )
        self.assertAlmostEqual(
            out["schca_part_2_line_29_ca_itemized_post_phaseout"],
            expected_medical,
        )

    def test_standard_deduction_wins_when_itemized_not_chosen(self):
        # If caller sets itemize=False, output uses max(CA itemized, standard).
        # With zero itemized inputs, standard deduction wins.
        ca = _make_input(filing_status="single", federal_agi=50_000.0)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_18_deduction"], STANDARD_DEDUCTION_2025["single"]
        )


# ---------------------------------------------------------------------------
# Behavioral Health Services Tax
# ---------------------------------------------------------------------------
class BehavioralHealthServicesTaxTests(unittest.TestCase):
    def test_below_threshold_no_bhst(self):
        # Line 19 = $800k, below $1M threshold.
        # Use a high-income scenario that clears the 7.5% standard deduction.
        ca = _make_input(
            filing_status="mfj", federal_agi=800_000.0 + STANDARD_DEDUCTION_2025["mfj"]
        )
        out = compute_ca_540(ca)
        self.assertEqual(out["f540_line_62_bhst"], 0.0)

    def test_at_threshold_no_bhst(self):
        fs = "mfj"
        line_19_target = 1_000_000.0
        fed_agi = line_19_target + STANDARD_DEDUCTION_2025[fs]
        ca = _make_input(filing_status=fs, federal_agi=fed_agi)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_19_taxable_income"], 1_000_000.0)
        self.assertEqual(out["f540_line_62_bhst"], 0.0)

    def test_above_threshold_1_percent(self):
        # Taxable income = $1,500,000 → BHST = 0.01 × $500,000 = $5,000.
        fs = "mfj"
        fed_agi = 1_500_000.0 + STANDARD_DEDUCTION_2025[fs]
        ca = _make_input(filing_status=fs, federal_agi=fed_agi)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_19_taxable_income"], 1_500_000.0)
        self.assertAlmostEqual(out["f540_line_62_bhst"], 5_000.0)

    def test_rate_and_threshold_constants_exposed(self):
        self.assertEqual(BHST_THRESHOLD_2025, 1_000_000.0)
        self.assertEqual(BHST_RATE_2025, 0.01)


# ---------------------------------------------------------------------------
# Nonrefundable Renter's Credit
# ---------------------------------------------------------------------------
class RentersCreditTests(unittest.TestCase):
    def test_eligible_single_below_limit_gets_60(self):
        ca = _make_input(
            filing_status="single",
            federal_agi=50_000.0,
        )
        new_credits = dataclasses.replace(
            ca.credits, eligible_for_renters_credit=True
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_46_renters_credit"], RENTERS_CREDIT_SINGLE_MFS_2025
        )

    def test_eligible_mfj_below_limit_gets_120(self):
        ca = _make_input(
            filing_status="mfj",
            federal_agi=100_000.0,
        )
        new_credits = dataclasses.replace(
            ca.credits, eligible_for_renters_credit=True
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_46_renters_credit"], RENTERS_CREDIT_HOUSEHOLD_2025
        )

    def test_over_limit_zero_credit_single(self):
        # Single above the AGI cliff → zero credit.
        ca = _make_input(
            filing_status="single",
            federal_agi=RENTERS_CREDIT_AGI_LIMIT_SINGLE_MFS_2025 + 1_000.0,
        )
        new_credits = dataclasses.replace(
            ca.credits, eligible_for_renters_credit=True
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertEqual(out["f540_line_46_renters_credit"], 0.0)

    def test_ineligible_flag_overrides(self):
        ca = _make_input(filing_status="single", federal_agi=20_000.0)
        # eligible_for_renters_credit defaults to False.
        out = compute_ca_540(ca)
        self.assertEqual(out["f540_line_46_renters_credit"], 0.0)

    def test_at_exact_cliff_still_eligible(self):
        ca = _make_input(
            filing_status="mfj",
            federal_agi=RENTERS_CREDIT_AGI_LIMIT_HOUSEHOLD_2025,
        )
        new_credits = dataclasses.replace(
            ca.credits, eligible_for_renters_credit=True
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(
            out["f540_line_46_renters_credit"], RENTERS_CREDIT_HOUSEHOLD_2025
        )


# ---------------------------------------------------------------------------
# Dependent-care credit AGI gate
# ---------------------------------------------------------------------------
class DependentCareCreditTests(unittest.TestCase):
    def test_dep_care_at_exact_agi_limit_is_allowed(self):
        # FTB 3506 eligibility: federal AGI ≤ $100,000. Cliff at exact limit.
        ca = _make_input(filing_status="mfj", federal_agi=100_000.0)
        new_credits = dataclasses.replace(
            ca.credits,
            dep_care_federal_agi_for_eligibility=100_000.0,
            dep_care_credit_amount=350.0,
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_40_dep_care_credit"], 350.0)

    def test_dep_care_above_agi_limit_zero(self):
        ca = _make_input(filing_status="mfj", federal_agi=100_050.0)
        new_credits = dataclasses.replace(
            ca.credits,
            dep_care_federal_agi_for_eligibility=100_050.0,
            dep_care_credit_amount=350.0,
        )
        ca = dataclasses.replace(ca, credits=new_credits)
        out = compute_ca_540(ca)
        self.assertEqual(out["f540_line_40_dep_care_credit"], 0.0)


# ---------------------------------------------------------------------------
# Refund / amount due balance tests
# ---------------------------------------------------------------------------
class RefundAndAmountDueTests(unittest.TestCase):
    def test_overpayment_refunded_when_payments_exceed_tax(self):
        # Scenario: single filer, $60,000 federal AGI, $5,000 withholding,
        # no itemized. Standard deduction $5,706. Taxable = $54,294.
        # Tax = 110.79 + (54_294 − 11_079) × 0.02 + ... (rate schedule)
        # Credits (line 32) = $153 personal exemption.
        # The oracle reports the final net overpayment in line 115.
        ca = _make_input(
            filing_status="single",
            federal_agi=60_000.0,
            state_wages=60_000.0,
        )
        new_payments = dataclasses.replace(
            ca.payments, line_71_ca_withholding=5_000.0
        )
        ca = dataclasses.replace(ca, payments=new_payments)
        out = compute_ca_540(ca)
        # Payments $5,000 vs. tax around $1,500 → refund around $3,500.
        self.assertGreater(out["f540_line_115_refund"], 3_000.0)
        self.assertLess(out["f540_line_115_refund"], 4_000.0)
        self.assertEqual(out["f540_line_114_total_amount_due"], 0.0)

    def test_balance_due_when_tax_exceeds_payments(self):
        # Scenario: single filer, $200,000 federal AGI, $2,000 withholding.
        # Tax is much larger than withholding → balance due.
        ca = _make_input(
            filing_status="single",
            federal_agi=200_000.0,
            state_wages=200_000.0,
        )
        new_payments = dataclasses.replace(
            ca.payments, line_71_ca_withholding=2_000.0
        )
        ca = dataclasses.replace(ca, payments=new_payments)
        out = compute_ca_540(ca)
        self.assertGreater(out["f540_line_114_total_amount_due"], 10_000.0)
        self.assertEqual(out["f540_line_115_refund"], 0.0)

    def test_use_tax_reduces_refund(self):
        # Withholding $5,000, use tax $200, tax $1,500 → refund = $3,300.
        ca = _make_input(
            filing_status="single",
            federal_agi=60_000.0,
            state_wages=60_000.0,
        )
        new_payments = dataclasses.replace(
            ca.payments, line_71_ca_withholding=5_000.0
        )
        new_misc = dataclasses.replace(ca.misc, line_91_use_tax=200.0)
        ca = dataclasses.replace(ca, payments=new_payments, misc=new_misc)
        out = compute_ca_540(ca)
        # Refund should be $200 less than the no-use-tax version.
        ca_no_use = _make_input(
            filing_status="single",
            federal_agi=60_000.0,
            state_wages=60_000.0,
        )
        ca_no_use = dataclasses.replace(
            ca_no_use,
            payments=dataclasses.replace(
                ca_no_use.payments, line_71_ca_withholding=5_000.0
            ),
        )
        out_no_use = compute_ca_540(ca_no_use)
        self.assertAlmostEqual(
            out_no_use["f540_line_115_refund"] - out["f540_line_115_refund"],
            200.0,
        )


# ---------------------------------------------------------------------------
# Scope-out gates — ensure the oracle raises on unmodeled scenarios
# ---------------------------------------------------------------------------
class ScopeOutTests(unittest.TestCase):
    def test_amt_raises(self):
        ca = _make_input(filing_status="single", federal_agi=50_000.0)
        new_scope = dataclasses.replace(
            ca.scope_out, amt_preferences_present=True
        )
        ca = dataclasses.replace(ca, scope_out=new_scope)
        with self.assertRaisesRegex(NotImplementedError, "AMT"):
            compute_ca_540(ca)

    def test_lump_sum_distribution_raises(self):
        ca = _make_input(filing_status="single", federal_agi=50_000.0)
        new_scope = dataclasses.replace(
            ca.scope_out, lump_sum_distribution_tax=1_000.0
        )
        ca = dataclasses.replace(ca, scope_out=new_scope)
        with self.assertRaisesRegex(NotImplementedError, "Schedule G-1"):
            compute_ca_540(ca)

    def test_kiddie_tax_raises(self):
        ca = _make_input(filing_status="single", federal_agi=10_000.0)
        new_scope = dataclasses.replace(
            ca.scope_out, kiddie_tax_child_filer=True
        )
        ca = dataclasses.replace(ca, scope_out=new_scope)
        with self.assertRaisesRegex(NotImplementedError, "FTB 3800"):
            compute_ca_540(ca)

    def test_nol_raises(self):
        ca = _make_input(filing_status="mfj", federal_agi=-50_000.0)
        new_scope = dataclasses.replace(ca.scope_out, nol_deduction=50_000.0)
        ca = dataclasses.replace(ca, scope_out=new_scope)
        with self.assertRaisesRegex(NotImplementedError, "NOL"):
            compute_ca_540(ca)


# ---------------------------------------------------------------------------
# End-to-end synthetic scenarios
# ---------------------------------------------------------------------------
class EndToEndSyntheticTests(unittest.TestCase):
    def test_simple_w2_single_standard_deduction(self):
        """Single filer, W-2 only, standard deduction, no credits, no adjustments."""
        ca = _make_input(
            filing_status="single",
            federal_agi=55_000.0,
            state_wages=55_000.0,
        )
        new_payments = dataclasses.replace(
            ca.payments, line_71_ca_withholding=2_000.0
        )
        ca = dataclasses.replace(ca, payments=new_payments)
        out = compute_ca_540(ca)

        # Taxable income = 55,000 − 5,706 = 49,294.
        self.assertAlmostEqual(out["f540_line_19_taxable_income"], 49_294.0)
        # Tax via Schedule X: base 1,022.01 at $41,452 bracket, 6% on excess.
        expected_tax = 1_022.01 + (49_294.0 - 41_452.0) * 0.06
        self.assertAlmostEqual(out["f540_line_31_tax"], expected_tax, places=4)
        # Exemption credit = $153 (single, below phaseout).
        self.assertAlmostEqual(
            out["f540_line_32_exemption_credits"],
            EXEMPTION_CREDIT_PERSONAL_2025,
        )

    def test_mfj_high_income_with_bhst(self):
        """MFJ filer with taxable income > $1M triggers BHST."""
        fs = "mfj"
        federal_agi = 1_200_000.0 + STANDARD_DEDUCTION_2025[fs]
        ca = _make_input(filing_status=fs, federal_agi=federal_agi)
        out = compute_ca_540(ca)
        self.assertAlmostEqual(out["f540_line_19_taxable_income"], 1_200_000.0)
        # BHST = (1,200,000 − 1,000,000) × 1% = $2,000.
        self.assertAlmostEqual(out["f540_line_62_bhst"], 2_000.0)
        # Exemption credit phased out — AGI far above threshold, all zero.
        self.assertEqual(out["f540_line_32_exemption_credits"], 0.0)

    def test_hoh_with_dependents_renter_credit_below_limit(self):
        """HOH with 2 dependents, below renter's credit AGI cliff."""
        ca = _make_input(
            filing_status="hoh",
            federal_agi=70_000.0,
            state_wages=70_000.0,
            dependent_count=2,
        )
        new_credits = dataclasses.replace(
            ca.credits, eligible_for_renters_credit=True
        )
        new_payments = dataclasses.replace(
            ca.payments, line_71_ca_withholding=3_000.0
        )
        ca = dataclasses.replace(
            ca, credits=new_credits, payments=new_payments
        )
        out = compute_ca_540(ca)
        # Renter's credit is the household amount ($120) because HOH.
        self.assertAlmostEqual(
            out["f540_line_46_renters_credit"], RENTERS_CREDIT_HOUSEHOLD_2025
        )
        # Exemption credits = 1 personal + 2 dependents, no phaseout.
        expected_exemptions = (
            EXEMPTION_CREDIT_PERSONAL_2025
            + 2 * EXEMPTION_CREDIT_DEPENDENT_2025
        )
        self.assertAlmostEqual(
            out["f540_line_32_exemption_credits"], expected_exemptions
        )

    def test_mfj_itemize_high_income_salt_restoration(self):
        """MFJ high-income filer itemizes; oracle restores SALT above federal cap."""
        ca = _make_input(
            filing_status="mfj",
            federal_agi=400_000.0,
            state_wages=400_000.0,
        )
        new_p2 = dataclasses.replace(
            ca.sch_ca_part_ii,
            fed_sch_a_state_and_local_tax_pre_cap=55_000.0,
            fed_sch_a_state_income_tax=30_000.0,
            fed_sch_a_salt_capped_total=40_000.0,
            fed_sch_a_mortgage_interest_on_1098=15_000.0,
            fed_sch_a_gifts_cash=5_000.0,
            itemize=True,
        )
        ca = dataclasses.replace(ca, sch_ca_part_ii=new_p2)
        out = compute_ca_540(ca)
        # CA SALT post-CA-rules = $55k − $30k state income tax = $25k.
        self.assertAlmostEqual(
            out["schca_part_2_line_5e_ca_salt"], 25_000.0
        )
        # CA itemized deduction covers SALT + mortgage + charitable.
        # Line 18 = 25k + 15k + 5k = 45k (assuming below phaseout threshold).
        self.assertAlmostEqual(
            out["schca_part_2_line_18_ca_net_itemized"], 45_000.0
        )


if __name__ == "__main__":
    unittest.main()
