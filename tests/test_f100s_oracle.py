"""Tests for the CA Form 100S reference oracle (TY2025).

TDD red-green-refactor against tests/oracles/f100s_reference.py.
All tests subclass unittest.TestCase (iron law #3).
"""

import unittest

from tests.oracles.f100s_reference import (
    ScheduleFIncome,
    ScheduleFDeductions,
    StateAdjustmentAdditions,
    StateAdjustmentDeductions,
    NOLDeductions,
    EntityIdentity,
    CreditEntry,
    AdditionalTaxes,
    _compute_schedule_f_income,
    _compute_schedule_f_deductions,
    _compute_schedule_f_obi,
    _compute_state_adjustments,
    _compute_tax,
    Payments,
    _compute_payments,
    ScheduleKItems,
    _compute_schedule_k,
    Shareholder,
    _compute_schedule_k1,
    F100SInput,
    compute_f100s,
)


# ---------------------------------------------------------------------------
# Helpers — zero-value fixtures
# ---------------------------------------------------------------------------
def _make_zero_schf_income() -> ScheduleFIncome:
    return ScheduleFIncome(
        gross_receipts_or_sales=0.0,
        returns_and_allowances=0.0,
        cost_of_goods_sold=0.0,
        net_gain_or_loss=0.0,
        other_income=0.0,
    )


def _make_zero_schf_deductions() -> ScheduleFDeductions:
    return ScheduleFDeductions(
        compensation_of_officers=0.0,
        salaries_and_wages=0.0,
        repairs_and_maintenance=0.0,
        bad_debts=0.0,
        rents=0.0,
        taxes=0.0,
        interest=0.0,
        depreciation_total=0.0,
        depreciation_elsewhere=0.0,
        depletion=0.0,
        advertising=0.0,
        pension_profit_sharing=0.0,
        employee_benefit_programs=0.0,
        travel_total=0.0,
        travel_deductible=0.0,
        other_deductions=0.0,
    )


# ---------------------------------------------------------------------------
# Schedule F — Income (lines 1-6)
# ---------------------------------------------------------------------------
class ScheduleFIncomeTests(unittest.TestCase):
    """Schedule F Side 4, lines 1a-6."""

    def test_zero_income_baseline(self):
        """All-zero income → all lines zero."""
        inc = _make_zero_schf_income()
        out = _compute_schedule_f_income(inc)
        self.assertAlmostEqual(out["f100s_schf_line_1c_net_receipts"], 0.0)
        self.assertAlmostEqual(out["f100s_schf_line_3_gross_profit"], 0.0)
        self.assertAlmostEqual(out["f100s_schf_line_6_total_income"], 0.0)

    def test_gross_receipts_minus_returns(self):
        """Line 1c = 1a − 1b."""
        inc = ScheduleFIncome(
            gross_receipts_or_sales=500_000.0,
            returns_and_allowances=20_000.0,
            cost_of_goods_sold=0.0,
            net_gain_or_loss=0.0,
            other_income=0.0,
        )
        out = _compute_schedule_f_income(inc)
        self.assertAlmostEqual(out["f100s_schf_line_1c_net_receipts"], 480_000.0)

    def test_gross_profit_and_total_income(self):
        """Line 3 = 1c − 2; line 6 = 3 + 4 + 5."""
        inc = ScheduleFIncome(
            gross_receipts_or_sales=500_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=100_000.0,
            net_gain_or_loss=15_000.0,
            other_income=5_000.0,
        )
        out = _compute_schedule_f_income(inc)
        self.assertAlmostEqual(out["f100s_schf_line_3_gross_profit"], 400_000.0)
        self.assertAlmostEqual(out["f100s_schf_line_6_total_income"], 420_000.0)


# ---------------------------------------------------------------------------
# Schedule F — Deductions (lines 7-21)
# ---------------------------------------------------------------------------
class ScheduleFDeductionsTests(unittest.TestCase):
    """Schedule F Side 4, lines 7-22."""

    def test_zero_deductions_baseline(self):
        """All-zero deductions → total deductions = 0."""
        ded =_make_zero_schf_deductions()
        out = _compute_schedule_f_deductions(ded)
        self.assertAlmostEqual(out["f100s_schf_line_21_total_deductions"], 0.0)

    def test_depreciation_net_is_14a_minus_14b(self):
        """Line 14c = 14a − 14b; used in total."""
        ded =ScheduleFDeductions(
            compensation_of_officers=0.0,
            salaries_and_wages=0.0,
            repairs_and_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes=0.0,
            interest=0.0,
            depreciation_total=50_000.0,
            depreciation_elsewhere=10_000.0,
            depletion=0.0,
            advertising=0.0,
            pension_profit_sharing=0.0,
            employee_benefit_programs=0.0,
            travel_total=0.0,
            travel_deductible=0.0,
            other_deductions=0.0,
        )
        out = _compute_schedule_f_deductions(ded)
        self.assertAlmostEqual(out["f100s_schf_line_14c_depreciation"], 40_000.0)
        self.assertAlmostEqual(out["f100s_schf_line_21_total_deductions"], 40_000.0)

    def test_travel_uses_deductible_not_total(self):
        """Line 21 uses travel_deductible (19b), not travel_total (19a)."""
        ded =ScheduleFDeductions(
            compensation_of_officers=0.0,
            salaries_and_wages=0.0,
            repairs_and_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes=0.0,
            interest=0.0,
            depreciation_total=0.0,
            depreciation_elsewhere=0.0,
            depletion=0.0,
            advertising=0.0,
            pension_profit_sharing=0.0,
            employee_benefit_programs=0.0,
            travel_total=10_000.0,
            travel_deductible=7_500.0,
            other_deductions=0.0,
        )
        out = _compute_schedule_f_deductions(ded)
        self.assertAlmostEqual(out["f100s_schf_line_19a_travel_total"], 10_000.0)
        self.assertAlmostEqual(out["f100s_schf_line_19b_travel_deductible"], 7_500.0)
        self.assertAlmostEqual(out["f100s_schf_line_21_total_deductions"], 7_500.0)

    def test_all_deductions_sum(self):
        """Total deductions = sum of lines 7-20 (using 14c and 19b)."""
        ded =ScheduleFDeductions(
            compensation_of_officers=100_000.0,
            salaries_and_wages=50_000.0,
            repairs_and_maintenance=5_000.0,
            bad_debts=1_000.0,
            rents=12_000.0,
            taxes=8_000.0,
            interest=3_000.0,
            depreciation_total=20_000.0,
            depreciation_elsewhere=5_000.0,
            depletion=0.0,
            advertising=2_000.0,
            pension_profit_sharing=10_000.0,
            employee_benefit_programs=4_000.0,
            travel_total=6_000.0,
            travel_deductible=4_000.0,
            other_deductions=3_000.0,
        )
        out = _compute_schedule_f_deductions(ded)
        expected = (100_000 + 50_000 + 5_000 + 1_000 + 12_000 + 8_000
                    + 3_000 + 15_000 + 0 + 2_000 + 10_000 + 4_000
                    + 4_000 + 3_000)
        self.assertAlmostEqual(out["f100s_schf_line_21_total_deductions"], expected)


# ---------------------------------------------------------------------------
# Schedule F — OBI (line 22)
# ---------------------------------------------------------------------------
class ScheduleFOBITests(unittest.TestCase):
    """Schedule F line 22: OBI = line 6 − line 21."""

    def test_obi_positive(self):
        """Positive OBI when income > deductions."""
        out = _compute_schedule_f_obi(420_000.0, 217_000.0)
        self.assertAlmostEqual(out["f100s_schf_line_22_obi"], 203_000.0)

    def test_obi_loss(self):
        """Negative OBI when deductions > income."""
        out = _compute_schedule_f_obi(50_000.0, 120_000.0)
        self.assertAlmostEqual(out["f100s_schf_line_22_obi"], -70_000.0)


# ---------------------------------------------------------------------------
# Helpers — zero-value state adjustment fixtures
# ---------------------------------------------------------------------------
def _make_zero_additions() -> StateAdjustmentAdditions:
    return StateAdjustmentAdditions(
        taxes_deducted=0.0,
        interest_on_government_obligations=0.0,
        net_capital_gain=0.0,
        depreciation_amortization_adjustment=0.0,
        portfolio_income=0.0,
        other_additions=0.0,
    )


def _make_zero_state_deductions() -> StateAdjustmentDeductions:
    return StateAdjustmentDeductions(
        dividends_received_deduction=0.0,
        waters_edge_dividend_deduction=0.0,
        charitable_contributions=0.0,
        other_deductions=0.0,
    )


def _make_zero_nol() -> NOLDeductions:
    return NOLDeductions(
        section_23802e_deduction=0.0,
        nol_deduction=0.0,
        ez_tta_lambra_nol=0.0,
        disaster_loss_deduction=0.0,
    )


# ---------------------------------------------------------------------------
# Main Form — State Adjustments (lines 1-20)
# ---------------------------------------------------------------------------
class StateAdjustmentAdditionsTests(unittest.TestCase):
    """Main form Side 1, lines 1-8 (additions)."""

    def test_zero_additions_baseline(self):
        """OBI flows through, additions are zero → line 8 = OBI."""
        out = _compute_state_adjustments(
            obi=200_000.0,
            additions=_make_zero_additions(),
            deductions=_make_zero_state_deductions(),
            nol=_make_zero_nol(),
        )
        self.assertAlmostEqual(out["f100s_line_1_obi"], 200_000.0)
        self.assertAlmostEqual(out["f100s_line_8_total_additions"], 200_000.0)

    def test_additions_sum_with_obi(self):
        """Line 8 = lines 1 through 7."""
        additions = StateAdjustmentAdditions(
            taxes_deducted=5_000.0,
            interest_on_government_obligations=1_000.0,
            net_capital_gain=10_000.0,
            depreciation_amortization_adjustment=3_000.0,
            portfolio_income=2_000.0,
            other_additions=500.0,
        )
        out = _compute_state_adjustments(
            obi=100_000.0,
            additions=additions,
            deductions=_make_zero_state_deductions(),
            nol=_make_zero_nol(),
        )
        self.assertAlmostEqual(out["f100s_line_8_total_additions"], 121_500.0)


class StateAdjustmentDeductionsTests(unittest.TestCase):
    """Main form Side 1, lines 9-13 (deductions)."""

    def test_deductions_sum(self):
        """Line 13 = lines 9 through 12."""
        deductions = StateAdjustmentDeductions(
            dividends_received_deduction=2_000.0,
            waters_edge_dividend_deduction=500.0,
            charitable_contributions=3_000.0,
            other_deductions=1_000.0,
        )
        out = _compute_state_adjustments(
            obi=100_000.0,
            additions=_make_zero_additions(),
            deductions=deductions,
            nol=_make_zero_nol(),
        )
        self.assertAlmostEqual(out["f100s_line_13_total_deductions"], 6_500.0)


class NetIncomeTests(unittest.TestCase):
    """Main form lines 14-20."""

    def test_line_14_net_income_after_adjustments(self):
        """Line 14 = line 8 − line 13."""
        additions = StateAdjustmentAdditions(
            taxes_deducted=5_000.0,
            interest_on_government_obligations=0.0,
            net_capital_gain=0.0,
            depreciation_amortization_adjustment=0.0,
            portfolio_income=0.0,
            other_additions=0.0,
        )
        deductions = StateAdjustmentDeductions(
            dividends_received_deduction=2_000.0,
            waters_edge_dividend_deduction=0.0,
            charitable_contributions=0.0,
            other_deductions=0.0,
        )
        out = _compute_state_adjustments(
            obi=100_000.0,
            additions=additions,
            deductions=deductions,
            nol=_make_zero_nol(),
        )
        self.assertAlmostEqual(out["f100s_line_14_net_income_after_adjustments"], 103_000.0)

    def test_line_15_equals_line_14_no_apportionment(self):
        """Line 15 = line 14 (no Schedule R apportionment)."""
        out = _compute_state_adjustments(
            obi=100_000.0,
            additions=_make_zero_additions(),
            deductions=_make_zero_state_deductions(),
            nol=_make_zero_nol(),
        )
        self.assertAlmostEqual(out["f100s_line_15_net_income_state"], out["f100s_line_14_net_income_after_adjustments"])

    def test_nol_reduces_net_income(self):
        """Line 20 = line 15 − (16 + 17 + 18 + 19)."""
        nol = NOLDeductions(
            section_23802e_deduction=1_000.0,
            nol_deduction=5_000.0,
            ez_tta_lambra_nol=0.0,
            disaster_loss_deduction=2_000.0,
        )
        out = _compute_state_adjustments(
            obi=100_000.0,
            additions=_make_zero_additions(),
            deductions=_make_zero_state_deductions(),
            nol=nol,
        )
        self.assertAlmostEqual(out["f100s_line_20_net_income_for_tax"], 92_000.0)

    def test_full_pipeline_additions_deductions_nol(self):
        """Full pipeline: OBI + additions − deductions − NOL → line 20."""
        additions = StateAdjustmentAdditions(
            taxes_deducted=10_000.0,
            interest_on_government_obligations=0.0,
            net_capital_gain=5_000.0,
            depreciation_amortization_adjustment=0.0,
            portfolio_income=0.0,
            other_additions=0.0,
        )
        deductions = StateAdjustmentDeductions(
            dividends_received_deduction=3_000.0,
            waters_edge_dividend_deduction=0.0,
            charitable_contributions=2_000.0,
            other_deductions=0.0,
        )
        nol = NOLDeductions(
            section_23802e_deduction=0.0,
            nol_deduction=10_000.0,
            ez_tta_lambra_nol=0.0,
            disaster_loss_deduction=0.0,
        )
        out = _compute_state_adjustments(
            obi=200_000.0,
            additions=additions,
            deductions=deductions,
            nol=nol,
        )
        # line 8 = 200k + 10k + 5k = 215k
        # line 13 = 3k + 2k = 5k
        # line 14 = 215k − 5k = 210k
        # line 15 = 210k (no apportionment)
        # line 20 = 210k − 10k = 200k
        self.assertAlmostEqual(out["f100s_line_8_total_additions"], 215_000.0)
        self.assertAlmostEqual(out["f100s_line_13_total_deductions"], 5_000.0)
        self.assertAlmostEqual(out["f100s_line_14_net_income_after_adjustments"], 210_000.0)
        self.assertAlmostEqual(out["f100s_line_20_net_income_for_tax"], 200_000.0)


# ---------------------------------------------------------------------------
# Tax Computation (lines 21-30)
# ---------------------------------------------------------------------------
def _make_zero_additional_taxes() -> AdditionalTaxes:
    return AdditionalTaxes(
        tax_from_schedule_d=0.0,
        excess_net_passive_income_tax=0.0,
        pte_elective_tax=0.0,
    )


class TaxComputationBasicTests(unittest.TestCase):
    """Main form lines 21-30: entity-level tax."""

    def test_1_5_pct_rate_above_minimum(self):
        """1.5% × net income when result exceeds $800 minimum."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=100_000.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        self.assertAlmostEqual(out["f100s_line_21_tax"], 1_500.0)

    def test_minimum_franchise_tax_floor(self):
        """When 1.5% × net income < $800, tax = $800."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=10_000.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        # 1.5% × 10k = 150 < 800 → tax = 800
        self.assertAlmostEqual(out["f100s_line_21_tax"], 800.0)

    def test_first_year_exemption_no_minimum(self):
        """First-year corps: no $800 floor; tax = 1.5% × net income."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=True, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=10_000.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        self.assertAlmostEqual(out["f100s_line_21_tax"], 150.0)

    def test_first_year_zero_income_zero_tax(self):
        """First-year with zero income → zero tax (no $800 floor)."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=True, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=0.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        self.assertAlmostEqual(out["f100s_line_21_tax"], 0.0)

    def test_financial_s_corp_3_5_pct(self):
        """Financial S-corps use 3.5% rate per R&TC §23186."""
        entity = EntityIdentity(
            name="Financial Corp", ein="XX-XXXTEST",
            accounting_method="accrual",
            is_financial_s_corp=True, is_first_year=False, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=100_000.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        self.assertAlmostEqual(out["f100s_line_21_tax"], 3_500.0)

    def test_negative_income_minimum_tax_applies(self):
        """Negative net income → tax = $800 minimum (not first year)."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_tax(
            net_income_for_tax=-50_000.0,
            entity=entity,
            credits=(),
            additional_taxes=_make_zero_additional_taxes(),
        )
        self.assertAlmostEqual(out["f100s_line_21_tax"], 800.0)


class TaxCreditFloorTests(unittest.TestCase):
    """Line 26 credit floor: min franchise tax + QSub taxes."""

    def test_credits_reduce_tax_but_not_below_floor(self):
        """Credits cannot reduce tax below $800 minimum."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        credits = (CreditEntry(code="some_credit", amount=2_000.0),)
        out = _compute_tax(
            net_income_for_tax=100_000.0,
            entity=entity,
            credits=credits,
            additional_taxes=_make_zero_additional_taxes(),
        )
        # tax = 1500, credits = 2000, but floor = 800
        self.assertAlmostEqual(out["f100s_line_25_total_credits"], 2_000.0)
        self.assertAlmostEqual(out["f100s_line_26_balance"], 800.0)

    def test_credits_reduce_tax_partially(self):
        """Credits reduce tax but remain above floor."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        credits = (CreditEntry(code="c1", amount=200.0),)
        out = _compute_tax(
            net_income_for_tax=100_000.0,
            entity=entity,
            credits=credits,
            additional_taxes=_make_zero_additional_taxes(),
        )
        # tax = 1500, credits = 200 → balance = 1300 (above 800 floor)
        self.assertAlmostEqual(out["f100s_line_26_balance"], 1_300.0)

    def test_qsub_taxes_raise_floor(self):
        """QSub annual taxes ($800 each) raise the credit floor."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=2,
        )
        credits = (CreditEntry(code="big_credit", amount=10_000.0),)
        out = _compute_tax(
            net_income_for_tax=200_000.0,
            entity=entity,
            credits=credits,
            additional_taxes=_make_zero_additional_taxes(),
        )
        # tax = 3000, credits = 10000, floor = 800 + 2×800 = 2400
        self.assertAlmostEqual(out["f100s_line_26_balance"], 2_400.0)


class TaxAdditionalTaxesTests(unittest.TestCase):
    """Lines 27-30: additional entity-level taxes."""

    def test_additional_taxes_added_to_total(self):
        """Line 30 = line 26 + lines 27 + 28 + 29."""
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        add_taxes = AdditionalTaxes(
            tax_from_schedule_d=5_000.0,
            excess_net_passive_income_tax=3_000.0,
            pte_elective_tax=1_000.0,
        )
        out = _compute_tax(
            net_income_for_tax=100_000.0,
            entity=entity,
            credits=(),
            additional_taxes=add_taxes,
        )
        # line 26 = 1500 (no credits), + 5000 + 3000 + 1000 = 10500
        self.assertAlmostEqual(out["f100s_line_30_total_tax"], 10_500.0)


# ---------------------------------------------------------------------------
# Payments + Balance (lines 31-45)
# ---------------------------------------------------------------------------
class PaymentsTests(unittest.TestCase):
    """Main form lines 31-45."""

    def test_total_payments_sum(self):
        """Line 36 = sum of lines 31-35."""
        p = Payments(
            prior_year_overpayment=1_000.0,
            estimated_tax_payments=2_000.0,
            withholding=500.0,
            amount_paid_with_extension=300.0,
            pte_elective_tax_payments=200.0,
            amount_credited_to_next_year=0.0,
        )
        out = _compute_payments(total_tax=800.0, payments=p)
        self.assertAlmostEqual(out["f100s_line_36_total_payments"], 4_000.0)

    def test_overpayment_when_payments_exceed_tax(self):
        """Overpayment = payments − tax when payments > tax."""
        p = Payments(
            prior_year_overpayment=0.0,
            estimated_tax_payments=5_000.0,
            withholding=0.0,
            amount_paid_with_extension=0.0,
            pte_elective_tax_payments=0.0,
            amount_credited_to_next_year=0.0,
        )
        out = _compute_payments(total_tax=800.0, payments=p)
        self.assertAlmostEqual(out["f100s_line_40_tax_due"], 0.0)
        self.assertAlmostEqual(out["f100s_line_41_overpayment"], 4_200.0)

    def test_tax_due_when_tax_exceeds_payments(self):
        """Tax due = tax − payments when tax > payments."""
        p = Payments(
            prior_year_overpayment=0.0,
            estimated_tax_payments=500.0,
            withholding=0.0,
            amount_paid_with_extension=0.0,
            pte_elective_tax_payments=0.0,
            amount_credited_to_next_year=0.0,
        )
        out = _compute_payments(total_tax=2_000.0, payments=p)
        self.assertAlmostEqual(out["f100s_line_40_tax_due"], 1_500.0)
        self.assertAlmostEqual(out["f100s_line_41_overpayment"], 0.0)

    def test_overpayment_split_credit_and_refund(self):
        """Overpayment split between credited forward (line 42) and refund (line 43)."""
        p = Payments(
            prior_year_overpayment=0.0,
            estimated_tax_payments=10_000.0,
            withholding=0.0,
            amount_paid_with_extension=0.0,
            pte_elective_tax_payments=0.0,
            amount_credited_to_next_year=3_000.0,
        )
        out = _compute_payments(total_tax=800.0, payments=p)
        self.assertAlmostEqual(out["f100s_line_41_overpayment"], 9_200.0)
        self.assertAlmostEqual(out["f100s_line_42_credited_to_next_year"], 3_000.0)
        self.assertAlmostEqual(out["f100s_line_43_refund"], 6_200.0)

    def test_credit_forward_capped_at_overpayment(self):
        """Amount credited forward cannot exceed overpayment."""
        p = Payments(
            prior_year_overpayment=0.0,
            estimated_tax_payments=1_000.0,
            withholding=0.0,
            amount_paid_with_extension=0.0,
            pte_elective_tax_payments=0.0,
            amount_credited_to_next_year=5_000.0,
        )
        out = _compute_payments(total_tax=800.0, payments=p)
        # overpayment = 200, credit forward capped at 200
        self.assertAlmostEqual(out["f100s_line_42_credited_to_next_year"], 200.0)
        self.assertAlmostEqual(out["f100s_line_43_refund"], 0.0)


# ---------------------------------------------------------------------------
# Schedule K (100S) — Entity-Level Totals
# ---------------------------------------------------------------------------
def _make_zero_sch_k_items() -> ScheduleKItems:
    return ScheduleKItems(
        net_rental_real_estate_income=0.0,
        other_gross_rental_income=0.0,
        other_gross_rental_expenses=0.0,
        interest_income=0.0,
        dividends=0.0,
        royalties=0.0,
        net_short_term_capital_gain=0.0,
        net_long_term_capital_gain=0.0,
        other_portfolio_income=0.0,
        other_income=0.0,
        section_179_expense=0.0,
        charitable_contributions_cash=0.0,
        charitable_contributions_noncash=0.0,
        investment_interest_expense=0.0,
        other_deductions=0.0,
        tax_exempt_interest=0.0,
        other_tax_exempt_income=0.0,
        nondeductible_expenses=0.0,
        total_property_distributions=0.0,
        investment_income=0.0,
        investment_expenses=0.0,
    )


class ScheduleKTests(unittest.TestCase):
    """Schedule K (100S) entity-level totals."""

    def test_obi_flows_to_line_1(self):
        """Line 1 = OBI from Schedule F."""
        out = _compute_schedule_k(
            sch_k=_make_zero_sch_k_items(),
            obi=200_000.0,
        )
        self.assertAlmostEqual(out["f100s_sch_k_line_1_obi"], 200_000.0)

    def test_other_rental_net_is_3a_minus_3b(self):
        """Line 3c = 3a − 3b."""
        k = ScheduleKItems(
            net_rental_real_estate_income=0.0,
            other_gross_rental_income=10_000.0,
            other_gross_rental_expenses=4_000.0,
            interest_income=0.0,
            dividends=0.0,
            royalties=0.0,
            net_short_term_capital_gain=0.0,
            net_long_term_capital_gain=0.0,
            other_portfolio_income=0.0,
            other_income=0.0,
            section_179_expense=0.0,
            charitable_contributions_cash=0.0,
            charitable_contributions_noncash=0.0,
            investment_interest_expense=0.0,
            other_deductions=0.0,
            tax_exempt_interest=0.0,
            other_tax_exempt_income=0.0,
            nondeductible_expenses=0.0,
            total_property_distributions=0.0,
            investment_income=0.0,
            investment_expenses=0.0,
        )
        out = _compute_schedule_k(sch_k=k, obi=0.0)
        self.assertAlmostEqual(out["f100s_sch_k_line_3c_other_net_rental"], 6_000.0)

    def test_reconciliation_line_19(self):
        """Line 19 = 1+2+3c+4+5+6+7+8+10a+10b − 11 − 12a-f."""
        k = ScheduleKItems(
            net_rental_real_estate_income=5_000.0,
            other_gross_rental_income=2_000.0,
            other_gross_rental_expenses=500.0,
            interest_income=1_000.0,
            dividends=500.0,
            royalties=200.0,
            net_short_term_capital_gain=300.0,
            net_long_term_capital_gain=700.0,
            other_portfolio_income=100.0,
            other_income=50.0,
            section_179_expense=1_000.0,
            charitable_contributions_cash=200.0,
            charitable_contributions_noncash=100.0,
            investment_interest_expense=50.0,
            other_deductions=150.0,
            tax_exempt_interest=0.0,
            other_tax_exempt_income=0.0,
            nondeductible_expenses=0.0,
            total_property_distributions=0.0,
            investment_income=0.0,
            investment_expenses=0.0,
        )
        out = _compute_schedule_k(sch_k=k, obi=100_000.0)
        # income: 100000 + 5000 + 1500 + 1000 + 500 + 200 + 300 + 700 + 100 + 50 = 109350
        # deductions: 1000 + 200 + 100 + 50 + 150 = 1500
        # line 19 = 109350 − 1500 = 107850
        self.assertAlmostEqual(out["f100s_sch_k_line_19_reconciliation"], 107_850.0)

    def test_all_items_emitted(self):
        """All Schedule K lines are present in output."""
        out = _compute_schedule_k(sch_k=_make_zero_sch_k_items(), obi=0.0)
        expected_keys = [
            "f100s_sch_k_line_1_obi",
            "f100s_sch_k_line_2_net_rental_real_estate",
            "f100s_sch_k_line_3a_other_gross_rental_income",
            "f100s_sch_k_line_3b_other_gross_rental_expenses",
            "f100s_sch_k_line_3c_other_net_rental",
            "f100s_sch_k_line_4_interest_income",
            "f100s_sch_k_line_5_dividends",
            "f100s_sch_k_line_6_royalties",
            "f100s_sch_k_line_7_net_short_term_capital_gain",
            "f100s_sch_k_line_8_net_long_term_capital_gain",
            "f100s_sch_k_line_10a_other_portfolio_income",
            "f100s_sch_k_line_10b_other_income",
            "f100s_sch_k_line_11_section_179_expense",
            "f100s_sch_k_line_12a_charitable_cash",
            "f100s_sch_k_line_12b_charitable_noncash",
            "f100s_sch_k_line_12c_investment_interest_expense",
            "f100s_sch_k_line_12f_other_deductions",
            "f100s_sch_k_line_16a_tax_exempt_interest",
            "f100s_sch_k_line_16b_other_tax_exempt_income",
            "f100s_sch_k_line_16c_nondeductible_expenses",
            "f100s_sch_k_line_16d_total_property_distributions",
            "f100s_sch_k_line_17a_investment_income",
            "f100s_sch_k_line_17b_investment_expenses",
            "f100s_sch_k_line_19_reconciliation",
        ]
        for key in expected_keys:
            self.assertIn(key, out, f"Missing key: {key}")


# ---------------------------------------------------------------------------
# Schedule K-1 (100S) — Per-Shareholder Allocation
# ---------------------------------------------------------------------------
class ScheduleK1AllocationTests(unittest.TestCase):
    """Schedule K-1 (100S) pro-rata share allocation."""

    def _make_sch_k_output(self, obi=100_000.0) -> dict:
        """Compute Schedule K output for use in K-1 tests."""
        k = ScheduleKItems(
            net_rental_real_estate_income=10_000.0,
            other_gross_rental_income=0.0,
            other_gross_rental_expenses=0.0,
            interest_income=5_000.0,
            dividends=2_000.0,
            royalties=0.0,
            net_short_term_capital_gain=1_000.0,
            net_long_term_capital_gain=3_000.0,
            other_portfolio_income=0.0,
            other_income=0.0,
            section_179_expense=2_000.0,
            charitable_contributions_cash=500.0,
            charitable_contributions_noncash=0.0,
            investment_interest_expense=0.0,
            other_deductions=0.0,
            tax_exempt_interest=100.0,
            other_tax_exempt_income=0.0,
            nondeductible_expenses=50.0,
            total_property_distributions=0.0,
            investment_income=0.0,
            investment_expenses=0.0,
        )
        return _compute_schedule_k(sch_k=k, obi=obi)

    def test_single_shareholder_100_pct(self):
        """100% owner gets full K amounts."""
        sch_k_out = self._make_sch_k_output()
        shareholders = (
            Shareholder(
                shareholder_id="juno", name="Juno Woods",
                tin="XXX-XX-TEST", ownership_percentage=1.0,
                is_ca_resident=True, material_participation=True,
            ),
        )
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_schedule_k1(entity, sch_k_out, shareholders)
        self.assertAlmostEqual(
            out["f100s_sch_k1_juno_line_1_obi"], 100_000.0)
        self.assertAlmostEqual(
            out["f100s_sch_k1_juno_line_2_net_rental_real_estate"], 10_000.0)
        self.assertAlmostEqual(
            out["f100s_sch_k1_juno_line_4_interest_income"], 5_000.0)

    def test_two_shareholders_pro_rata(self):
        """Two shareholders get pro-rata allocations."""
        sch_k_out = self._make_sch_k_output()
        shareholders = (
            Shareholder(
                shareholder_id="alice", name="Alice",
                tin="XXX-XX-AAA1", ownership_percentage=0.6,
                is_ca_resident=True, material_participation=True,
            ),
            Shareholder(
                shareholder_id="bob", name="Bob",
                tin="XXX-XX-BBB2", ownership_percentage=0.4,
                is_ca_resident=True, material_participation=False,
            ),
        )
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_schedule_k1(entity, sch_k_out, shareholders)
        self.assertAlmostEqual(out["f100s_sch_k1_alice_line_1_obi"], 60_000.0)
        self.assertAlmostEqual(out["f100s_sch_k1_bob_line_1_obi"], 40_000.0)
        self.assertAlmostEqual(out["f100s_sch_k1_alice_line_4_interest_income"], 3_000.0)
        self.assertAlmostEqual(out["f100s_sch_k1_bob_line_4_interest_income"], 2_000.0)


class ScheduleK1CarryInTests(unittest.TestCase):
    """ca_540_carry_in convenience dict per shareholder."""

    def test_carry_in_dict_present(self):
        """Each shareholder has a ca_540_carry_in convenience dict."""
        k = ScheduleKItems(
            net_rental_real_estate_income=10_000.0,
            other_gross_rental_income=0.0,
            other_gross_rental_expenses=0.0,
            interest_income=5_000.0,
            dividends=2_000.0,
            royalties=0.0,
            net_short_term_capital_gain=0.0,
            net_long_term_capital_gain=3_000.0,
            other_portfolio_income=0.0,
            other_income=0.0,
            section_179_expense=0.0,
            charitable_contributions_cash=0.0,
            charitable_contributions_noncash=0.0,
            investment_interest_expense=0.0,
            other_deductions=0.0,
            tax_exempt_interest=0.0,
            other_tax_exempt_income=0.0,
            nondeductible_expenses=0.0,
            total_property_distributions=0.0,
            investment_income=0.0,
            investment_expenses=0.0,
        )
        sch_k_out = _compute_schedule_k(sch_k=k, obi=100_000.0)
        shareholders = (
            Shareholder(
                shareholder_id="juno", name="Juno Woods",
                tin="XXX-XX-TEST", ownership_percentage=1.0,
                is_ca_resident=True, material_participation=True,
            ),
        )
        entity = EntityIdentity(
            name="Translunar LLC", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_schedule_k1(entity, sch_k_out, shareholders)
        carry_in = out["f100s_sch_k1_juno_ca_540_carry_in"]
        self.assertIsInstance(carry_in, dict)
        self.assertEqual(carry_in["entity_name"], "Translunar LLC")
        self.assertEqual(carry_in["entity_type"], "s_corp")
        self.assertAlmostEqual(carry_in["ordinary_business_income"], 100_000.0)
        self.assertAlmostEqual(carry_in["interest_income"], 5_000.0)
        self.assertAlmostEqual(carry_in["net_long_term_capital_gain"], 3_000.0)
        # §199A QBI should NOT be present in CA carry-in
        self.assertNotIn("qbi_amount", carry_in)

    def test_carry_in_material_participation_flag(self):
        """ca_540_carry_in reflects shareholder's material participation."""
        sch_k_out = _compute_schedule_k(sch_k=_make_zero_sch_k_items(), obi=50_000.0)
        shareholders = (
            Shareholder(
                shareholder_id="active", name="Active",
                tin="XXX-XX-AAA1", ownership_percentage=0.5,
                is_ca_resident=True, material_participation=True,
            ),
            Shareholder(
                shareholder_id="passive", name="Passive",
                tin="XXX-XX-BBB2", ownership_percentage=0.5,
                is_ca_resident=True, material_participation=False,
            ),
        )
        entity = EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        )
        out = _compute_schedule_k1(entity, sch_k_out, shareholders)
        self.assertTrue(out["f100s_sch_k1_active_ca_540_carry_in"]["material_participation"])
        self.assertFalse(out["f100s_sch_k1_passive_ca_540_carry_in"]["material_participation"])


# ---------------------------------------------------------------------------
# Top-level compute_f100s + Scope Gates
# ---------------------------------------------------------------------------
def _make_minimal_input(**overrides) -> F100SInput:
    """Build a minimal valid F100SInput with sensible defaults."""
    defaults = dict(
        entity=EntityIdentity(
            name="Test Corp", ein="XX-XXXTEST",
            accounting_method="cash",
            is_financial_s_corp=False, is_first_year=False, num_qsubs=0,
        ),
        schf_income=_make_zero_schf_income(),
        schf_deductions=_make_zero_schf_deductions(),
        additions=_make_zero_additions(),
        deductions=_make_zero_state_deductions(),
        nol=_make_zero_nol(),
        credits=(),
        additional_taxes=_make_zero_additional_taxes(),
        payments=Payments(
            prior_year_overpayment=0.0,
            estimated_tax_payments=0.0,
            withholding=0.0,
            amount_paid_with_extension=0.0,
            pte_elective_tax_payments=0.0,
            amount_credited_to_next_year=0.0,
        ),
        sch_k=_make_zero_sch_k_items(),
        shareholders=(
            Shareholder(
                shareholder_id="owner", name="Owner",
                tin="XXX-XX-TEST", ownership_percentage=1.0,
                is_ca_resident=True, material_participation=True,
            ),
        ),
    )
    defaults.update(overrides)
    return F100SInput(**defaults)


class ScopeGateTests(unittest.TestCase):
    """Scope gates: reject out-of-scope inputs."""

    def test_no_shareholders_raises(self):
        """Must have at least one shareholder."""
        with self.assertRaises(ValueError):
            compute_f100s(_make_minimal_input(shareholders=()))

    def test_ownership_not_100_pct_raises(self):
        """Shareholder ownership must sum to 1.0."""
        bad_shareholders = (
            Shareholder("a", "A", "111", 0.5, True, True),
            Shareholder("b", "B", "222", 0.3, True, True),
        )
        with self.assertRaises(ValueError):
            compute_f100s(_make_minimal_input(shareholders=bad_shareholders))

    def test_duplicate_shareholder_ids_raises(self):
        """Shareholder IDs must be unique."""
        dupes = (
            Shareholder("same", "A", "111", 0.5, True, True),
            Shareholder("same", "B", "222", 0.5, True, True),
        )
        with self.assertRaises(ValueError):
            compute_f100s(_make_minimal_input(shareholders=dupes))


class IntegrationTests(unittest.TestCase):
    """End-to-end integration through compute_f100s."""

    def test_zero_input_produces_minimum_tax(self):
        """All-zero inputs → $800 minimum franchise tax."""
        inp = _make_minimal_input()
        out = compute_f100s(inp)
        self.assertAlmostEqual(out["f100s_line_21_tax"], 800.0)
        self.assertAlmostEqual(out["f100s_line_30_total_tax"], 800.0)
        self.assertAlmostEqual(out["f100s_line_40_tax_due"], 800.0)

    def test_full_pipeline_with_income(self):
        """Income flows through Schedule F → state adjustments → tax → payments."""
        inp = _make_minimal_input(
            schf_income=ScheduleFIncome(
                gross_receipts_or_sales=300_000.0,
                returns_and_allowances=0.0,
                cost_of_goods_sold=50_000.0,
                net_gain_or_loss=0.0,
                other_income=0.0,
            ),
            schf_deductions=ScheduleFDeductions(
                compensation_of_officers=80_000.0,
                salaries_and_wages=40_000.0,
                repairs_and_maintenance=0.0,
                bad_debts=0.0,
                rents=0.0,
                taxes=5_000.0,
                interest=0.0,
                depreciation_total=10_000.0,
                depreciation_elsewhere=0.0,
                depletion=0.0,
                advertising=0.0,
                pension_profit_sharing=0.0,
                employee_benefit_programs=0.0,
                travel_total=0.0,
                travel_deductible=0.0,
                other_deductions=0.0,
            ),
            additions=StateAdjustmentAdditions(
                taxes_deducted=5_000.0,
                interest_on_government_obligations=0.0,
                net_capital_gain=0.0,
                depreciation_amortization_adjustment=0.0,
                portfolio_income=0.0,
                other_additions=0.0,
            ),
            payments=Payments(
                prior_year_overpayment=0.0,
                estimated_tax_payments=2_000.0,
                withholding=0.0,
                amount_paid_with_extension=0.0,
                pte_elective_tax_payments=0.0,
                amount_credited_to_next_year=0.0,
            ),
        )
        out = compute_f100s(inp)
        # Sch F: income = 300k − 50k = 250k gross profit = total income
        # deductions = 80k + 40k + 5k + 10k = 135k
        # OBI = 250k − 135k = 115k
        self.assertAlmostEqual(out["f100s_schf_line_22_obi"], 115_000.0)
        # State adj: line 8 = 115k + 5k (taxes) = 120k; line 13 = 0
        # line 14 = 120k; line 15 = 120k; line 20 = 120k
        self.assertAlmostEqual(out["f100s_line_20_net_income_for_tax"], 120_000.0)
        # Tax: 1.5% × 120k = 1800 (> $800 minimum)
        self.assertAlmostEqual(out["f100s_line_21_tax"], 1_800.0)
        # Payments: 2000; tax due: 0; overpayment: 200
        self.assertAlmostEqual(out["f100s_line_41_overpayment"], 200.0)
        # K-1: 100% owner gets full OBI
        self.assertAlmostEqual(out["f100s_sch_k1_owner_line_1_obi"], 115_000.0)
        # ca_540_carry_in present
        self.assertIn("f100s_sch_k1_owner_ca_540_carry_in", out)

    def test_k1_keys_present_for_each_shareholder(self):
        """K-1 output includes both raw and carry-in per shareholder."""
        shareholders = (
            Shareholder("s1", "S1", "111", 0.6, True, True),
            Shareholder("s2", "S2", "222", 0.4, True, False),
        )
        inp = _make_minimal_input(shareholders=shareholders)
        out = compute_f100s(inp)
        for sid in ["s1", "s2"]:
            self.assertIn(f"f100s_sch_k1_{sid}_line_1_obi", out)
            self.assertIn(f"f100s_sch_k1_{sid}_ca_540_carry_in", out)


if __name__ == "__main__":
    unittest.main()
