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
from tenforty.models import Scenario, SCorpReturn
from tenforty.rounding import irs_round


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
        "f1120s_line_1a_gross_receipts": irs_round(line_1a),
        "f1120s_line_1b_returns_and_allowances": irs_round(line_1b),
        "f1120s_line_1c_net_receipts": irs_round(line_1c),
        "f1120s_line_2_cost_of_goods_sold": irs_round(line_2),
        "f1120s_line_3_gross_profit": irs_round(line_3),
        "f1120s_line_4_net_gain_loss_4797": irs_round(line_4),
        "f1120s_line_5_other_income": irs_round(line_5),
        "f1120s_line_6_total_income": irs_round(line_6),
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
    line_21 = income["f1120s_line_6_total_income"] - line_20
    return {
        "f1120s_line_7_compensation_of_officers": irs_round(line_7),
        "f1120s_line_8_salaries_wages": irs_round(line_8),
        "f1120s_line_9_repairs_maintenance": irs_round(line_9),
        "f1120s_line_10_bad_debts": irs_round(line_10),
        "f1120s_line_11_rents": irs_round(line_11),
        "f1120s_line_12_taxes_licenses": irs_round(line_12),
        "f1120s_line_13_interest": irs_round(line_13),
        "f1120s_line_14_depreciation": irs_round(line_14),
        "f1120s_line_15_depletion": irs_round(line_15),
        "f1120s_line_16_advertising": irs_round(line_16),
        "f1120s_line_17_pension_profit_sharing": irs_round(line_17),
        "f1120s_line_18_employee_benefits": irs_round(line_18),
        "f1120s_line_19_other_deductions": irs_round(line_19),
        "f1120s_line_20_total_deductions": irs_round(line_20),
        "f1120s_line_21_ordinary_business_income": irs_round(line_21),
    }


def _compute_total_tax(r: SCorpReturn) -> dict:
    """Form 1120-S Total Tax (line 22). §1375 / §1374 / §453 interest
    are scope-outs (caller-supplied)."""
    line_22a = r.scope_outs.net_passive_income_tax
    line_22b = r.scope_outs.built_in_gains_tax
    line_22c = r.scope_outs.interest_on_453_deferred
    return {
        "f1120s_line_22a_net_passive_income_tax": irs_round(line_22a),
        "f1120s_line_22b_built_in_gains_tax": irs_round(line_22b),
        "f1120s_line_22c_interest_on_453_deferred": irs_round(line_22c),
        "f1120s_line_22_total_tax": irs_round(line_22a + line_22b + line_22c),
    }


def _compute_payments_and_balance(r: SCorpReturn, total_tax: dict) -> dict:
    """Form 1120-S Payments (line 23a-23e) + balance (line 24 / 26)
    + line 25 / line 27 placeholders.

    Lines 24 (amount owed) and 26 (overpayment) are mutually exclusive.
    Reads `total_tax["f1120s_line_22_total_tax"]` to compute the balance.

    Line 25 (estimated tax penalty / Form 2220) and line 27 (overpayment
    credited to next year) emit 0.0 in v1 — Form 2220 is not implemented
    and the full overpayment is treated as refunded. Both are emitted so
    Task 15's PDF mapping has compute keys for the corresponding fields.
    """
    p = r.payments
    line_23a = p.estimated_tax_payments
    line_23b = p.prior_year_overpayment_credited
    line_23c = p.tax_deposited_with_7004
    line_23d = p.credit_for_federal_excise_tax
    line_23e = p.refundable_credits
    line_23 = line_23a + line_23b + line_23c + line_23d + line_23e
    line_22 = total_tax["f1120s_line_22_total_tax"]
    delta = line_22 - line_23
    return {
        "f1120s_line_23a_estimated_tax_payments": irs_round(line_23a),
        "f1120s_line_23b_prior_year_overpayment_credited": irs_round(line_23b),
        "f1120s_line_23c_tax_deposited_with_7004": irs_round(line_23c),
        "f1120s_line_23d_credit_for_federal_excise_tax": irs_round(line_23d),
        "f1120s_line_23e_refundable_credits": irs_round(line_23e),
        "f1120s_line_23_total_payments": irs_round(line_23),
        "f1120s_line_24_amount_owed": irs_round(max(delta, 0.0)),
        "f1120s_line_25_estimated_tax_penalty": irs_round(0.0),
        "f1120s_line_26_overpayment": irs_round(max(-delta, 0.0)),
        "f1120s_line_27_credited_to_next_year": irs_round(0.0),
    }


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    if scenario.s_corp_return is None:
        return {}
    # Run BOTH gates here, not just compute-time. Direct importers (callers
    # who construct Scenario in code rather than via load_scenario) would
    # otherwise bypass the load-time None-attestation check.
    validate_load_time(scenario.config)
    enforce_compute_time(scenario)

    r = scenario.s_corp_return

    # Per-section helpers contribute to the return dict additively. Each
    # later task in this sub-plan adds one helper and one update line.
    out: dict[str, float] = {}
    income = _compute_income(r)
    out.update(income)
    out.update(_compute_deductions(r, income))
    total_tax = _compute_total_tax(r)
    out.update(total_tax)
    out.update(_compute_payments_and_balance(r, total_tax))
    return out
