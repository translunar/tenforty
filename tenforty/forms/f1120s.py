"""Federal Form 1120-S — S-corporation return.

Computes main form lines 1-28, Schedule B pass-through, Schedule K totals,
and per-shareholder Schedule K-1 allocations from a Scenario whose
`s_corp_return` is set.

Scope follows Sub-plan 2: §1375, §1374, §453 interest are scope-outs
(caller supplies amounts); Sch L, M-1, M-2, M-3 are out of scope (gated
by attestations); Sch D (corporate) and 1125-A/E detail are out of scope.

Caller contract: `compute(scenario, upstream)` runs both the load-time
and compute-time attestation gates. Direct importers DO NOT bypass the
load-time gate by skipping `tenforty.scenario.load_scenario` — calling
`compute` on a Scenario whose config has any required attestation field
left as None will raise from inside `validate_load_time(...)` here, not
silently produce wrong output. This makes `compute` safe to call as a
library function in addition to its primary use through the orchestrator.
"""

from tenforty.attestations import enforce_compute_time, validate_load_time
from tenforty.models import (
    AccountingMethod, K1Allocation, K1AllocationEntity,
    K1AllocationShareholder, Scenario, SCorpReturn,
)
from tenforty.rounding import irs_round


# `int` (not `float`) values: each entry is the rounded form of 0.0 per
# the form-wide `irs_round` output convention. Using `int` here removes
# the redundant `irs_round(0.0)` wrap on every line and makes the type
# match the rest of the compute output.
_SCH_K_V1_ZERO_PLACEHOLDERS: dict[str, int] = {
    "f1120s_sch_k_net_rental_real_estate": 0,
    "f1120s_sch_k_other_net_rental_income": 0,
    "f1120s_sch_k_interest_income": 0,
    "f1120s_sch_k_ordinary_dividends": 0,
    "f1120s_sch_k_royalties": 0,
    "f1120s_sch_k_net_short_term_capital_gain": 0,
    "f1120s_sch_k_net_long_term_capital_gain": 0,
    "f1120s_sch_k_net_section_1231_gain": 0,
    "f1120s_sch_k_other_income": 0,
    "f1120s_sch_k_section_179_deduction": 0,
    "f1120s_sch_k_charitable_contributions": 0,
    "f1120s_sch_k_low_income_housing_credit": 0,
    "f1120s_sch_k_foreign_transactions": 0,
    "f1120s_sch_k_amt_items": 0,
    "f1120s_sch_k_tax_exempt_interest": 0,
    "f1120s_sch_k_investment_income": 0,
    "f1120s_sch_k_income_loss_reconciliation": 0,
}


def _compute_income(r: SCorpReturn) -> dict:
    """Form 1120-S Income section (lines 1a-6)."""
    line_1a = r.income.gross_receipts
    line_1b = r.income.returns_and_allowances
    line_1c = line_1a - line_1b
    line_2 = r.income.cogs_aggregate
    line_3 = line_1c - line_2
    line_4 = r.income.net_gain_loss_4797
    line_5 = r.income.other_income
    line_6 = line_3 + line_4 + line_5
    return {
        "f1120s_gross_receipts": irs_round(line_1a),
        "f1120s_returns_and_allowances": irs_round(line_1b),
        "f1120s_net_receipts": irs_round(line_1c),
        "f1120s_cost_of_goods_sold": irs_round(line_2),
        "f1120s_gross_profit": irs_round(line_3),
        "f1120s_net_gain_loss_4797": irs_round(line_4),
        "f1120s_other_income": irs_round(line_5),
        "f1120s_total_income": irs_round(line_6),
    }


def _compute_deductions(r: SCorpReturn, income: dict) -> dict:
    """Form 1120-S Deductions section (lines 7-21).

    Takes the income-section dict (rather than recomputing line 6 from
    raw fields) because IRS line 21 = (rounded) line 6 − (rounded)
    line 20, not raw arithmetic. The IRS instructions consistently
    define each line as a function of *form-displayed* (rounded) values
    on prior lines, so reading line_6 from `income` is the
    instructions-faithful path; recomputing from `r.income.*` would
    produce a different value when gross_receipts has cents.
    """
    d = r.deductions
    line_7 = d.compensation_of_officers
    line_8 = d.salaries_wages
    line_9 = d.repairs_maintenance
    line_10 = d.bad_debts
    line_11 = d.rents
    line_12 = d.taxes_licenses
    line_13 = d.interest
    line_14 = d.depreciation
    line_15 = d.depletion
    line_16 = d.advertising
    line_17 = d.pension_profit_sharing_plans
    line_18 = d.employee_benefits
    line_19 = d.other_deductions
    line_20 = sum((
        line_7, line_8, line_9, line_10, line_11, line_12, line_13,
        line_14, line_15, line_16, line_17, line_18, line_19,
    ))
    line_21 = income["f1120s_total_income"] - line_20
    return {
        "f1120s_compensation_of_officers": irs_round(line_7),
        "f1120s_salaries_wages": irs_round(line_8),
        "f1120s_repairs_maintenance": irs_round(line_9),
        "f1120s_bad_debts": irs_round(line_10),
        "f1120s_rents": irs_round(line_11),
        "f1120s_taxes_licenses": irs_round(line_12),
        "f1120s_interest": irs_round(line_13),
        "f1120s_depreciation": irs_round(line_14),
        "f1120s_depletion": irs_round(line_15),
        "f1120s_advertising": irs_round(line_16),
        "f1120s_pension_profit_sharing": irs_round(line_17),
        "f1120s_employee_benefits": irs_round(line_18),
        "f1120s_other_deductions": irs_round(line_19),
        "f1120s_total_deductions": irs_round(line_20),
        "f1120s_ordinary_business_income": irs_round(line_21),
    }


def _compute_total_tax(r: SCorpReturn) -> dict:
    """Form 1120-S Total Tax (line 22). §1375 / §1374 / §453 interest
    are scope-outs (caller-supplied)."""
    line_22a = r.scope_outs.net_passive_income_tax
    line_22b = r.scope_outs.built_in_gains_tax
    line_22c = r.scope_outs.interest_on_453_deferred
    return {
        "f1120s_net_passive_income_tax": irs_round(line_22a),
        "f1120s_built_in_gains_tax": irs_round(line_22b),
        "f1120s_interest_on_453_deferred": irs_round(line_22c),
        "f1120s_total_tax": irs_round(line_22a + line_22b + line_22c),
    }


def _compute_payments_and_balance(r: SCorpReturn, total_tax: dict) -> dict:
    """Form 1120-S Payments (line 23a-23e) + balance (line 24 / 26)
    + line 25 / line 27 placeholders.

    Lines 24 (amount owed) and 26 (overpayment) are mutually exclusive.
    Reads `total_tax["f1120s_total_tax"]` to compute the balance.

    Lines 25 and 27 emit 0 unconditionally in v1; the keys exist so the
    PDF mapping has a slot to fill (Form 2220 estimated-tax penalty is
    out of scope for v1).
    """
    p = r.payments
    line_23a = p.estimated_tax_payments
    line_23b = p.prior_year_overpayment_credited
    line_23c = p.tax_deposited_with_7004
    line_23d = p.credit_for_federal_excise_tax
    line_23e = p.refundable_credits
    line_23 = line_23a + line_23b + line_23c + line_23d + line_23e
    line_22 = total_tax["f1120s_total_tax"]
    delta = line_22 - line_23
    return {
        "f1120s_estimated_tax_payments": irs_round(line_23a),
        "f1120s_prior_year_overpayment_credited": irs_round(line_23b),
        "f1120s_tax_deposited_with_7004": irs_round(line_23c),
        "f1120s_credit_for_federal_excise_tax": irs_round(line_23d),
        "f1120s_refundable_credits": irs_round(line_23e),
        "f1120s_total_payments": irs_round(line_23),
        "f1120s_amount_owed": irs_round(max(delta, 0.0)),
        "f1120s_estimated_tax_penalty": irs_round(0.0),
        "f1120s_overpayment": irs_round(max(-delta, 0.0)),
        "f1120s_credited_to_next_year": irs_round(0.0),
    }


def _compute_schedule_b(r: SCorpReturn) -> dict:
    """Form 1120-S Schedule B Yes/No + text answers (pass-through).

    `accounting_method` (AccountingMethod enum) explodes into three
    boolean keys here so the downstream PDF mapping layer can target the
    form's three checkboxes (Cash / Accrual / Other) directly. The IRS
    form's Question 1 has three exclusive checkboxes — a single enum
    field would require a converter at the PDF-fill boundary; emitting
    three booleans here keeps the boundary trivial.
    """
    sb = r.schedule_b_answers
    return {
        "f1120s_sch_b_accounting_method_cash":
            sb.accounting_method == AccountingMethod.CASH,
        "f1120s_sch_b_accounting_method_accrual":
            sb.accounting_method == AccountingMethod.ACCRUAL,
        "f1120s_sch_b_accounting_method_other":
            sb.accounting_method == AccountingMethod.OTHER,
        "f1120s_sch_b_business_activity_code": sb.business_activity_code,
        "f1120s_sch_b_business_activity_description":
            sb.business_activity_description,
        "f1120s_sch_b_product_or_service": sb.product_or_service,
        "f1120s_sch_b_any_c_corp_subsidiaries": sb.any_c_corp_subsidiaries,
        "f1120s_sch_b_has_any_foreign_shareholders":
            sb.has_any_foreign_shareholders,
        "f1120s_sch_b_owns_foreign_entity": sb.owns_foreign_entity,
    }


def _compute_schedule_k(deductions: dict) -> dict:
    """Form 1120-S Schedule K entity-level totals.

    In v1 only line 1 (OBI) has compute logic; the remaining lines emit
    zero so the Sch K section is complete on the fill output (the keys
    are required by the PDF mapping but their values await later sub-plans).
    """
    return {
        "f1120s_sch_k_ordinary_business_income": irs_round(
            deductions["f1120s_ordinary_business_income"]
        ),
        **_SCH_K_V1_ZERO_PLACEHOLDERS,
    }


def _compute_schedule_k1_allocations(
    r: SCorpReturn, schedule_k: dict,
) -> list[K1Allocation]:
    """Per-shareholder K-1 allocation (pro-rata by ownership %).

    v1 supports only Sch K line 1 (OBI) on Sch K-1 box 1; other
    separately-stated items have no v1 compute logic.
    """
    sch_k_line_1 = schedule_k["f1120s_sch_k_ordinary_business_income"]
    allocations: list[K1Allocation] = []
    for sh in r.shareholders:
        share = sh.ownership_percentage / 100.0
        allocations.append(K1Allocation(
            entity=K1AllocationEntity(
                name=r.name,
                ein=r.ein,
                address=r.address,
            ),
            shareholder=K1AllocationShareholder(
                name=sh.name,
                ssn_or_ein=sh.ssn_or_ein,
                address=sh.address,
            ),
            ownership_percentage=sh.ownership_percentage,
            box_1_ordinary_business_income=sch_k_line_1 * share,
        ))
    return allocations


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    if scenario.s_corp_return is None:
        return {}
    validate_load_time(scenario.config)
    enforce_compute_time(scenario)

    r = scenario.s_corp_return
    income = _compute_income(r)
    deductions = _compute_deductions(r, income)
    total_tax = _compute_total_tax(r)
    schedule_k = _compute_schedule_k(deductions)
    return {
        **income,
        **deductions,
        **total_tax,
        **_compute_payments_and_balance(r, total_tax),
        **_compute_schedule_b(r),
        **schedule_k,
        "f1120s_sch_k1_allocations":
            _compute_schedule_k1_allocations(r, schedule_k),
    }
