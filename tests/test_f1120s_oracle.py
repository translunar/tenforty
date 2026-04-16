"""Unit tests for tests/oracles/f1120s_reference.py.

Follows project convention: ``unittest.TestCase`` subclasses, imports at top,
no silent fallthrough. See tests/oracles/README.md for oracle scope.
"""

import unittest
from dataclasses import replace

from tests.oracles.f1120s_reference import (
    Deductions,
    EntityIdentity,
    F1120SInput,
    GrossReceipts,
    ScheduleBAnswers,
    ScheduleKItems,
    Shareholder,
    TaxAndPayments,
    compute_f1120s,
)


# ---------------------------------------------------------------------------
# Test fixture helpers
# ---------------------------------------------------------------------------
def _make_entity() -> EntityIdentity:
    return EntityIdentity(
        name="Acme S Corp",
        ein="XX-XXXXXXX",
        accounting_method="accrual",
    )


def _make_zero_gross() -> GrossReceipts:
    return GrossReceipts(
        gross_receipts_or_sales=0.0,
        returns_and_allowances=0.0,
        cost_of_goods_sold=0.0,
        net_gain_from_4797=0.0,
        other_income=0.0,
    )


def _make_zero_deductions() -> Deductions:
    return Deductions(
        compensation_of_officers=0.0,
        salaries_and_wages=0.0,
        repairs_and_maintenance=0.0,
        bad_debts=0.0,
        rents=0.0,
        taxes_and_licenses=0.0,
        interest_expense=0.0,
        depreciation_not_on_1125a=0.0,
        depletion=0.0,
        advertising=0.0,
        pension_and_profit_sharing=0.0,
        employee_benefit_programs=0.0,
        energy_efficient_commercial_buildings_179d=0.0,
        other_deductions=0.0,
    )


def _make_zero_tax() -> TaxAndPayments:
    return TaxAndPayments(
        excess_net_passive_income_or_lifo_tax=0.0,
        tax_from_schedule_d=0.0,
        prior_year_overpayment_and_estimates=0.0,
        tax_deposited_with_7004=0.0,
        credit_for_federal_tax_paid_on_fuels=0.0,
        elective_payment_election_from_form_3800=0.0,
        estimated_tax_penalty=0.0,
        amount_credited_to_next_year_estimates=0.0,
    )


def _make_zero_sch_b() -> ScheduleBAnswers:
    return ScheduleBAnswers(
        business_activity="Consulting",
        product_or_service="Advisory services",
        owns_stock_in_other_entity=False,
        owns_partnership_or_llc_interest_ge_20pct=False,
        total_receipts_and_assets_under_250k=True,
        subject_to_163j_limitation=False,
        three_year_average_gross_receipts=0.0,
    )


def _make_zero_sch_k() -> ScheduleKItems:
    return ScheduleKItems(
        net_rental_real_estate_income=0.0,
        other_net_rental_income=0.0,
        interest_income=0.0,
        ordinary_dividends=0.0,
        qualified_dividends=0.0,
        royalties=0.0,
        net_short_term_capital_gain=0.0,
        net_long_term_capital_gain=0.0,
        qbi_amount=0.0,
    )


def _make_single_shareholder() -> tuple[Shareholder, ...]:
    return (
        Shareholder(
            shareholder_id="shareholder_1",
            name="Jane Smith",
            tin="000-00-0001",
            ownership_percentage=1.0,
            is_us_resident=True,
            material_participation=True,
        ),
    )


def _make_minimal_input() -> F1120SInput:
    return F1120SInput(
        entity=_make_entity(),
        gross=_make_zero_gross(),
        deductions=_make_zero_deductions(),
        tax=_make_zero_tax(),
        sch_b=_make_zero_sch_b(),
        sch_k=_make_zero_sch_k(),
        shareholders=_make_single_shareholder(),
    )


# ---------------------------------------------------------------------------
# Main form income lines
# ---------------------------------------------------------------------------
class MainFormIncomeTests(unittest.TestCase):
    def test_line_1c_nets_returns(self):
        inp = _make_minimal_input()
        gross = GrossReceipts(
            gross_receipts_or_sales=1_000_000.0,
            returns_and_allowances=50_000.0,
            cost_of_goods_sold=0.0,
            net_gain_from_4797=0.0,
            other_income=0.0,
        )
        out = compute_f1120s(replace(inp, gross=gross))
        self.assertEqual(out["f1120s_line_1c_net_receipts"], 950_000.0)

    def test_line_3_subtracts_cogs_from_1c(self):
        inp = _make_minimal_input()
        gross = GrossReceipts(
            gross_receipts_or_sales=1_000_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=400_000.0,
            net_gain_from_4797=0.0,
            other_income=0.0,
        )
        out = compute_f1120s(replace(inp, gross=gross))
        self.assertEqual(out["f1120s_line_3_gross_profit"], 600_000.0)

    def test_line_6_sums_income_components(self):
        inp = _make_minimal_input()
        gross = GrossReceipts(
            gross_receipts_or_sales=500_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=200_000.0,
            net_gain_from_4797=10_000.0,
            other_income=5_000.0,
        )
        out = compute_f1120s(replace(inp, gross=gross))
        # 500k - 200k = 300k; +10k +5k = 315k
        self.assertEqual(out["f1120s_line_6_total_income"], 315_000.0)


# ---------------------------------------------------------------------------
# Main form deduction lines
# ---------------------------------------------------------------------------
class MainFormDeductionTests(unittest.TestCase):
    def test_line_21_sums_all_deduction_lines(self):
        inp = _make_minimal_input()
        d = Deductions(
            compensation_of_officers=100_000.0,
            salaries_and_wages=200_000.0,
            repairs_and_maintenance=5_000.0,
            bad_debts=1_000.0,
            rents=24_000.0,
            taxes_and_licenses=10_000.0,
            interest_expense=3_000.0,
            depreciation_not_on_1125a=15_000.0,
            depletion=0.0,
            advertising=7_000.0,
            pension_and_profit_sharing=25_000.0,
            employee_benefit_programs=12_000.0,
            energy_efficient_commercial_buildings_179d=4_000.0,
            other_deductions=8_000.0,
        )
        expected = (
            100_000.0 + 200_000.0 + 5_000.0 + 1_000.0 + 24_000.0
            + 10_000.0 + 3_000.0 + 15_000.0 + 0.0 + 7_000.0
            + 25_000.0 + 12_000.0 + 4_000.0 + 8_000.0
        )
        out = compute_f1120s(replace(inp, deductions=d))
        self.assertEqual(out["f1120s_line_21_total_deductions"], expected)

    def test_line_19_179d_emitted_as_separate_line(self):
        inp = _make_minimal_input()
        d = Deductions(
            compensation_of_officers=0.0,
            salaries_and_wages=0.0,
            repairs_and_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes_and_licenses=0.0,
            interest_expense=0.0,
            depreciation_not_on_1125a=0.0,
            depletion=0.0,
            advertising=0.0,
            pension_and_profit_sharing=0.0,
            employee_benefit_programs=0.0,
            energy_efficient_commercial_buildings_179d=12_500.0,
            other_deductions=0.0,
        )
        out = compute_f1120s(replace(inp, deductions=d))
        self.assertEqual(
            out["f1120s_line_19_energy_efficient_commercial_buildings_179d"],
            12_500.0,
        )
        self.assertEqual(out["f1120s_line_20_other_deductions"], 0.0)


# ---------------------------------------------------------------------------
# OBI (line 22)
# ---------------------------------------------------------------------------
class OrdinaryBusinessIncomeTests(unittest.TestCase):
    def test_line_22_is_income_minus_deductions(self):
        inp = _make_minimal_input()
        gross = GrossReceipts(
            gross_receipts_or_sales=1_000_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=400_000.0,
            net_gain_from_4797=0.0,
            other_income=0.0,
        )
        d = Deductions(
            compensation_of_officers=200_000.0,
            salaries_and_wages=100_000.0,
            repairs_and_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes_and_licenses=0.0,
            interest_expense=0.0,
            depreciation_not_on_1125a=0.0,
            depletion=0.0,
            advertising=0.0,
            pension_and_profit_sharing=0.0,
            employee_benefit_programs=0.0,
            energy_efficient_commercial_buildings_179d=0.0,
            other_deductions=0.0,
        )
        out = compute_f1120s(replace(inp, gross=gross, deductions=d))
        # line 6 = 600k; line 21 = 300k; line 22 = 300k
        self.assertEqual(out["f1120s_line_22_ordinary_business_income"], 300_000.0)

    def test_line_22_can_be_negative(self):
        inp = _make_minimal_input()
        d = Deductions(
            compensation_of_officers=50_000.0,
            salaries_and_wages=0.0,
            repairs_and_maintenance=0.0,
            bad_debts=0.0,
            rents=0.0,
            taxes_and_licenses=0.0,
            interest_expense=0.0,
            depreciation_not_on_1125a=0.0,
            depletion=0.0,
            advertising=0.0,
            pension_and_profit_sharing=0.0,
            employee_benefit_programs=0.0,
            energy_efficient_commercial_buildings_179d=0.0,
            other_deductions=0.0,
        )
        out = compute_f1120s(replace(inp, deductions=d))
        self.assertEqual(
            out["f1120s_line_22_ordinary_business_income"], -50_000.0
        )


# ---------------------------------------------------------------------------
# Tax and payments (lines 23-28)
# ---------------------------------------------------------------------------
class TaxAndPaymentsTests(unittest.TestCase):
    def test_line_23c_sums_23a_and_23b(self):
        inp = _make_minimal_input()
        t = TaxAndPayments(
            excess_net_passive_income_or_lifo_tax=1_000.0,
            tax_from_schedule_d=5_000.0,
            prior_year_overpayment_and_estimates=0.0,
            tax_deposited_with_7004=0.0,
            credit_for_federal_tax_paid_on_fuels=0.0,
            elective_payment_election_from_form_3800=0.0,
            estimated_tax_penalty=0.0,
            amount_credited_to_next_year_estimates=0.0,
        )
        out = compute_f1120s(replace(inp, tax=t))
        self.assertEqual(out["f1120s_line_23c_total_tax"], 6_000.0)

    def test_balance_due_when_payments_below_tax(self):
        inp = _make_minimal_input()
        t = TaxAndPayments(
            excess_net_passive_income_or_lifo_tax=0.0,
            tax_from_schedule_d=10_000.0,
            prior_year_overpayment_and_estimates=3_000.0,
            tax_deposited_with_7004=2_000.0,
            credit_for_federal_tax_paid_on_fuels=0.0,
            elective_payment_election_from_form_3800=0.0,
            estimated_tax_penalty=100.0,
            amount_credited_to_next_year_estimates=0.0,
        )
        out = compute_f1120s(replace(inp, tax=t))
        # 23c = 10k; 24z = 5k; total_owed = 10.1k; balance = 5.1k
        self.assertEqual(out["f1120s_line_26_amount_owed"], 5_100.0)
        self.assertEqual(out["f1120s_line_27_overpayment"], 0.0)

    def test_overpayment_when_payments_exceed_tax(self):
        inp = _make_minimal_input()
        t = TaxAndPayments(
            excess_net_passive_income_or_lifo_tax=0.0,
            tax_from_schedule_d=2_000.0,
            prior_year_overpayment_and_estimates=5_000.0,
            tax_deposited_with_7004=0.0,
            credit_for_federal_tax_paid_on_fuels=0.0,
            elective_payment_election_from_form_3800=0.0,
            estimated_tax_penalty=0.0,
            amount_credited_to_next_year_estimates=1_000.0,
        )
        out = compute_f1120s(replace(inp, tax=t))
        # 23c = 2k; 24z = 5k; overpayment = 3k; 1k credited, 2k refunded
        self.assertEqual(out["f1120s_line_26_amount_owed"], 0.0)
        self.assertEqual(out["f1120s_line_27_overpayment"], 3_000.0)
        self.assertEqual(out["f1120s_line_28a_credited_to_next_year"], 1_000.0)
        self.assertEqual(out["f1120s_line_28b_refunded"], 2_000.0)

    def test_credit_capped_at_overpayment(self):
        """If shareholder asks more credited forward than the overpayment
        available, cap at overpayment (no phantom credit)."""
        inp = _make_minimal_input()
        t = TaxAndPayments(
            excess_net_passive_income_or_lifo_tax=0.0,
            tax_from_schedule_d=1_000.0,
            prior_year_overpayment_and_estimates=1_500.0,
            tax_deposited_with_7004=0.0,
            credit_for_federal_tax_paid_on_fuels=0.0,
            elective_payment_election_from_form_3800=0.0,
            estimated_tax_penalty=0.0,
            amount_credited_to_next_year_estimates=5_000.0,
        )
        out = compute_f1120s(replace(inp, tax=t))
        # overpayment is 500; credit capped at 500; refund 0
        self.assertEqual(out["f1120s_line_27_overpayment"], 500.0)
        self.assertEqual(out["f1120s_line_28a_credited_to_next_year"], 500.0)
        self.assertEqual(out["f1120s_line_28b_refunded"], 0.0)

    def test_line_24d_elective_payment_flows_into_total_payments(self):
        """§6417 elective payment election from Form 3800 (new line 24d on
        the 2024/2025 form face) counts as a payment on line 24z total."""
        inp = _make_minimal_input()
        t = TaxAndPayments(
            excess_net_passive_income_or_lifo_tax=0.0,
            tax_from_schedule_d=10_000.0,
            prior_year_overpayment_and_estimates=1_000.0,
            tax_deposited_with_7004=0.0,
            credit_for_federal_tax_paid_on_fuels=0.0,
            elective_payment_election_from_form_3800=4_000.0,
            estimated_tax_penalty=0.0,
            amount_credited_to_next_year_estimates=0.0,
        )
        out = compute_f1120s(replace(inp, tax=t))
        # 23c = 10k tax; 24a+24d = 1k+4k = 5k payments; 26 = 5k owed
        self.assertEqual(out["f1120s_line_24d_elective_payment_election"], 4_000.0)
        self.assertEqual(out["f1120s_line_24z_total_payments"], 5_000.0)
        self.assertEqual(out["f1120s_line_26_amount_owed"], 5_000.0)


# ---------------------------------------------------------------------------
# Schedule B pass-through
# ---------------------------------------------------------------------------
class ScheduleBTests(unittest.TestCase):
    def test_accounting_method_passes_through(self):
        inp = _make_minimal_input()
        out = compute_f1120s(inp)
        self.assertEqual(out["sch_b_line_1_accounting_method"], "accrual")

    def test_250k_gate_preserved(self):
        inp = _make_minimal_input()
        out = compute_f1120s(inp)
        self.assertTrue(out["sch_b_line_9_total_receipts_and_assets_under_250k"])


# ---------------------------------------------------------------------------
# Schedule K totals
# ---------------------------------------------------------------------------
class ScheduleKTests(unittest.TestCase):
    def test_sch_k_line_1_equals_main_form_line_22(self):
        inp = _make_minimal_input()
        gross = GrossReceipts(
            gross_receipts_or_sales=200_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=50_000.0,
            net_gain_from_4797=0.0,
            other_income=0.0,
        )
        out = compute_f1120s(replace(inp, gross=gross))
        self.assertEqual(
            out["sch_k_line_1_ordinary_business_income"],
            out["f1120s_line_22_ordinary_business_income"],
        )

    def test_sch_k_separately_stated_items_flow_unchanged(self):
        inp = _make_minimal_input()
        k = ScheduleKItems(
            net_rental_real_estate_income=1_000.0,
            other_net_rental_income=2_000.0,
            interest_income=3_000.0,
            ordinary_dividends=4_000.0,
            qualified_dividends=2_500.0,
            royalties=500.0,
            net_short_term_capital_gain=1_500.0,
            net_long_term_capital_gain=8_000.0,
            qbi_amount=50_000.0,
        )
        out = compute_f1120s(replace(inp, sch_k=k))
        self.assertEqual(out["sch_k_line_4_interest_income"], 3_000.0)
        self.assertEqual(out["sch_k_line_5a_ordinary_dividends"], 4_000.0)
        self.assertEqual(out["sch_k_line_5b_qualified_dividends"], 2_500.0)
        self.assertEqual(out["sch_k_line_17v_qbi_amount"], 50_000.0)


# ---------------------------------------------------------------------------
# Schedule K-1 per-shareholder allocation
# ---------------------------------------------------------------------------
class ScheduleK1AllocationTests(unittest.TestCase):
    def _two_shareholder_60_40(self) -> F1120SInput:
        inp = _make_minimal_input()
        return replace(
            inp,
            shareholders=(
                Shareholder(
                    shareholder_id="a",
                    name="Alice",
                    tin="900-00-0001",
                    ownership_percentage=0.6,
                    is_us_resident=True,
                    material_participation=True,
                ),
                Shareholder(
                    shareholder_id="b",
                    name="Bob",
                    tin="900-00-0002",
                    ownership_percentage=0.4,
                    is_us_resident=True,
                    material_participation=False,
                ),
            ),
        )

    def test_obi_split_pro_rata(self):
        inp = self._two_shareholder_60_40()
        gross = GrossReceipts(
            gross_receipts_or_sales=1_000_000.0,
            returns_and_allowances=0.0,
            cost_of_goods_sold=0.0,
            net_gain_from_4797=0.0,
            other_income=0.0,
        )
        out = compute_f1120s(replace(inp, gross=gross))
        self.assertEqual(
            out["sch_k1_a_box_1_ordinary_business_income"], 600_000.0
        )
        self.assertEqual(
            out["sch_k1_b_box_1_ordinary_business_income"], 400_000.0
        )

    def test_separately_stated_items_split_pro_rata(self):
        inp = self._two_shareholder_60_40()
        k = ScheduleKItems(
            net_rental_real_estate_income=0.0,
            other_net_rental_income=0.0,
            interest_income=1_000.0,
            ordinary_dividends=500.0,
            qualified_dividends=300.0,
            royalties=0.0,
            net_short_term_capital_gain=0.0,
            net_long_term_capital_gain=10_000.0,
            qbi_amount=0.0,
        )
        out = compute_f1120s(replace(inp, sch_k=k))
        self.assertEqual(out["sch_k1_a_box_4_interest_income"], 600.0)
        self.assertEqual(out["sch_k1_b_box_4_interest_income"], 400.0)
        self.assertEqual(out["sch_k1_a_box_8a_net_long_term_capital_gain"], 6_000.0)
        self.assertEqual(out["sch_k1_b_box_8a_net_long_term_capital_gain"], 4_000.0)

    def test_qualified_dividends_is_subset_of_ordinary(self):
        """5b is a subset of 5a — both carry independently on the K-1; the
        downstream consumer handles the 'subset' relationship. Oracle just
        allocates each pro rata."""
        inp = self._two_shareholder_60_40()
        k = ScheduleKItems(
            net_rental_real_estate_income=0.0,
            other_net_rental_income=0.0,
            interest_income=0.0,
            ordinary_dividends=1_000.0,
            qualified_dividends=700.0,
            royalties=0.0,
            net_short_term_capital_gain=0.0,
            net_long_term_capital_gain=0.0,
            qbi_amount=0.0,
        )
        out = compute_f1120s(replace(inp, sch_k=k))
        self.assertEqual(out["sch_k1_a_box_5a_ordinary_dividends"], 600.0)
        self.assertEqual(out["sch_k1_a_box_5b_qualified_dividends"], 420.0)

    def test_material_participation_flag_flows_to_k1_like_shape(self):
        inp = self._two_shareholder_60_40()
        out = compute_f1120s(inp)
        self.assertTrue(
            out["sch_k1_a_schedule_k1_like"]["material_participation"]
        )
        self.assertFalse(
            out["sch_k1_b_schedule_k1_like"]["material_participation"]
        )

    def test_k1_like_shape_pins_entity_type_as_s_corp(self):
        inp = self._two_shareholder_60_40()
        out = compute_f1120s(inp)
        self.assertEqual(
            out["sch_k1_a_schedule_k1_like"]["entity_type"], "s_corp"
        )

    def test_k1_like_shape_zeros_other_income(self):
        """The 1120-S oracle's scope excludes K-1 items that land in
        other_income (§1231, §179, SE, credits). It must emit zero there so
        the downstream K-1 oracle's scope gate passes."""
        inp = self._two_shareholder_60_40()
        out = compute_f1120s(inp)
        self.assertEqual(
            out["sch_k1_a_schedule_k1_like"]["other_income"], 0.0
        )


# ---------------------------------------------------------------------------
# Scope gates
# ---------------------------------------------------------------------------
class ScopeGateTests(unittest.TestCase):
    def test_no_shareholders_rejected(self):
        inp = _make_minimal_input()
        with self.assertRaises(ValueError):
            compute_f1120s(replace(inp, shareholders=()))

    def test_ownership_not_summing_to_one_rejected(self):
        inp = _make_minimal_input()
        bad = (
            Shareholder(
                shareholder_id="a",
                name="Alice",
                tin="900-00-0001",
                ownership_percentage=0.6,
                is_us_resident=True,
                material_participation=True,
            ),
            Shareholder(
                shareholder_id="b",
                name="Bob",
                tin="900-00-0002",
                ownership_percentage=0.3,  # total only 0.9
                is_us_resident=True,
                material_participation=True,
            ),
        )
        with self.assertRaises(ValueError):
            compute_f1120s(replace(inp, shareholders=bad))

    def test_duplicate_shareholder_ids_rejected(self):
        inp = _make_minimal_input()
        bad = (
            Shareholder(
                shareholder_id="same",
                name="Alice",
                tin="900-00-0001",
                ownership_percentage=0.5,
                is_us_resident=True,
                material_participation=True,
            ),
            Shareholder(
                shareholder_id="same",
                name="Bob",
                tin="900-00-0002",
                ownership_percentage=0.5,
                is_us_resident=True,
                material_participation=True,
            ),
        )
        with self.assertRaises(ValueError):
            compute_f1120s(replace(inp, shareholders=bad))


if __name__ == "__main__":
    unittest.main()
