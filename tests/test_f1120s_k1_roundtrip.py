"""Roundtrip integration test: 1120-S oracle → K-1 oracle.

Validates that the per-shareholder ``schedule_k1_like`` dict produced by
``tests.oracles.f1120s_reference.compute_f1120s`` is a valid input to
``tests.oracles.k1_reference.k1_to_expected_outputs``.

The K-1 oracle lives on a parallel branch (``oracle/k1-reference``). When
this test runs on a branch where both modules are importable, it engages
automatically. On a branch where only one is present, the test class is
skipped.
"""

import unittest
from types import SimpleNamespace

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

try:
    from tests.oracles import k1_reference
except ImportError:
    k1_reference = None


@unittest.skipUnless(
    k1_reference is not None,
    "K-1 oracle not available on this branch — roundtrip test skipped.",
)
class F1120SToK1RoundtripTests(unittest.TestCase):
    """Feed 1120-S per-shareholder output into the K-1 oracle and verify
    the integration is sound."""

    def _build_input(self) -> F1120SInput:
        return F1120SInput(
            entity=EntityIdentity(
                name="Roundtrip S Corp",
                ein="XX-XXXXXXX",
                accounting_method="accrual",
            ),
            gross=GrossReceipts(
                gross_receipts_or_sales=500_000.0,
                returns_and_allowances=0.0,
                cost_of_goods_sold=100_000.0,
                net_gain_from_4797=0.0,
                other_income=0.0,
            ),
            deductions=Deductions(
                compensation_of_officers=80_000.0,
                salaries_and_wages=120_000.0,
                repairs_and_maintenance=0.0,
                bad_debts=0.0,
                rents=24_000.0,
                taxes_and_licenses=6_000.0,
                interest_expense=0.0,
                depreciation_not_on_1125a=10_000.0,
                depletion=0.0,
                advertising=5_000.0,
                pension_and_profit_sharing=0.0,
                employee_benefit_programs=0.0,
                other_deductions=5_000.0,
            ),
            tax=TaxAndPayments(
                excess_net_passive_income_or_lifo_tax=0.0,
                built_in_gains_tax=0.0,
                prior_year_overpayment_and_estimates=0.0,
                tax_deposited_with_7004=0.0,
                credit_for_federal_tax_paid_on_fuels=0.0,
                estimated_tax_penalty=0.0,
                amount_credited_to_next_year_estimates=0.0,
            ),
            sch_b=ScheduleBAnswers(
                business_activity="Consulting",
                product_or_service="Advisory services",
                owns_stock_in_other_entity=False,
                owns_partnership_or_llc_interest_ge_20pct=False,
                total_receipts_and_assets_under_250k=False,
                subject_to_163j_limitation=False,
                three_year_average_gross_receipts=500_000.0,
            ),
            sch_k=ScheduleKItems(
                net_rental_real_estate_income=0.0,
                other_net_rental_income=0.0,
                interest_income=2_000.0,
                ordinary_dividends=1_000.0,
                qualified_dividends=700.0,
                royalties=0.0,
                net_short_term_capital_gain=0.0,
                net_long_term_capital_gain=5_000.0,
                qbi_amount=150_000.0,
            ),
            shareholders=(
                Shareholder(
                    shareholder_id="alice",
                    name="Alice",
                    tin="900-00-0001",
                    ownership_percentage=0.6,
                    is_us_resident=True,
                    material_participation=True,
                ),
                Shareholder(
                    shareholder_id="bob",
                    name="Bob",
                    tin="900-00-0002",
                    ownership_percentage=0.4,
                    is_us_resident=True,
                    material_participation=False,
                ),
            ),
        )

    def test_materially_participating_shareholder_is_nonpassive(self):
        """Alice (material_participation=True) — her pro-rata OBI should
        flow to nonpassive_income in the K-1 oracle's Sch E row."""
        inp = self._build_input()
        f1120s_out = compute_f1120s(inp)

        # Construct a minimal mock matching ScheduleK1Like from Alice's
        # 1120-S output. Use SimpleNamespace so attribute access works.
        alice_k1 = SimpleNamespace(**f1120s_out["sch_k1_alice_schedule_k1_like"])

        k1_out = k1_reference.k1_to_expected_outputs(alice_k1)

        # Alice's OBI share: line 21 = (500k-100k) - (80+120+24+6+10+5+5)k
        # = 400k - 250k = 150k. Alice gets 60%: 90k.
        self.assertEqual(k1_out["sch_e_part_ii_row"]["nonpassive_income"], 90_000.0)
        self.assertEqual(k1_out["sch_e_part_ii_row"]["passive_income"], 0.0)
        self.assertFalse(k1_out["passive_flag"])

    def test_non_materially_participating_shareholder_is_passive(self):
        """Bob (material_participation=False) — his pro-rata OBI flows to
        passive_income, and passive_flag is True."""
        inp = self._build_input()
        f1120s_out = compute_f1120s(inp)

        bob_k1 = SimpleNamespace(**f1120s_out["sch_k1_bob_schedule_k1_like"])

        k1_out = k1_reference.k1_to_expected_outputs(bob_k1)

        # Bob gets 40% of 150k = 60k, passive.
        self.assertEqual(k1_out["sch_e_part_ii_row"]["nonpassive_income"], 0.0)
        self.assertEqual(k1_out["sch_e_part_ii_row"]["passive_income"], 60_000.0)
        self.assertTrue(k1_out["passive_flag"])

    def test_sch_b_additions_match_pro_rata_allocation(self):
        """Interest + ordinary dividends from the K-1 oracle's Sch B
        additions should equal the shareholder's pro-rata share from
        the 1120-S oracle."""
        inp = self._build_input()
        f1120s_out = compute_f1120s(inp)

        alice_k1 = SimpleNamespace(**f1120s_out["sch_k1_alice_schedule_k1_like"])

        k1_out = k1_reference.k1_to_expected_outputs(alice_k1)

        # Alice 60% of $2k interest and $1k ordinary dividends
        self.assertEqual(k1_out["sch_b_additions"]["interest"], 1_200.0)
        self.assertEqual(k1_out["sch_b_additions"]["ordinary_dividends"], 600.0)

    def test_sch_d_long_term_cap_gain_flows_through(self):
        inp = self._build_input()
        f1120s_out = compute_f1120s(inp)

        alice_k1 = SimpleNamespace(**f1120s_out["sch_k1_alice_schedule_k1_like"])

        k1_out = k1_reference.k1_to_expected_outputs(alice_k1)

        # Alice 60% of $5k long-term cap gain
        self.assertEqual(k1_out["sch_d_additions"]["long_term"], 3_000.0)
        self.assertEqual(k1_out["sch_d_additions"]["short_term"], 0.0)

    def test_qbi_amount_flows_through(self):
        inp = self._build_input()
        f1120s_out = compute_f1120s(inp)

        alice_k1 = SimpleNamespace(**f1120s_out["sch_k1_alice_schedule_k1_like"])

        k1_out = k1_reference.k1_to_expected_outputs(alice_k1)

        # Alice 60% of $150k entity QBI
        self.assertEqual(k1_out["qbi_amount"], 90_000.0)


if __name__ == "__main__":
    unittest.main()
