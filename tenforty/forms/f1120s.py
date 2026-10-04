"""Federal Form 1120-S — S-corporation return.

Computes main form lines 1-28, Schedule B pass-through, Schedule K totals,
and per-shareholder Schedule K-1 allocations from a Scenario whose
`s_corp_return` is set.

Scope follows Sub-plan 2: §1375 and §1374 are scope-outs (caller supplies
amounts); §453 interest is a fail-closed scope-out (shareholder-level, K-1
box 17 codes M/N; nonzero raises NotImplementedError); Sch L, M-1, M-2, M-3 are out of scope (gated
by attestations); Sch D (corporate) and 1125-A/E detail are out of scope.

Caller contract: `compute(scenario, upstream)` runs both the load-time
and compute-time attestation gates. Direct importers DO NOT bypass the
load-time gate by skipping `tenforty.scenario.load_scenario` — calling
`compute` on a Scenario whose config has any required attestation field
left as None will raise from inside `validate_load_time(...)` here, not
silently produce wrong output. This makes `compute` safe to call as a
library function in addition to its primary use through the orchestrator.
"""

from tenforty.attestations import (
    _has_scorp_large_balance_sheet, enforce_compute_time, validate_load_time,
)
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
}


def _compute_income(r: SCorpReturn) -> dict:
    """Form 1120-S Income section (lines 1a-6).

    Rounding election: tenforty prints whole dollars, so every arithmetic
    line is computed from its PRINTED (irs_round-ed) operands and the form's
    visible math foots. Same convention as the Schedule SE R10 ruling.
    """
    line_1a = irs_round(r.income.gross_receipts)
    line_1b = irs_round(r.income.returns_and_allowances)
    line_1c = line_1a - line_1b
    line_2 = irs_round(r.income.cogs_aggregate)
    line_3 = line_1c - line_2
    line_4 = irs_round(r.income.net_gain_loss_4797)
    line_5 = irs_round(r.income.other_income)
    line_6 = line_3 + line_4 + line_5
    return {
        "f1120s_gross_receipts": line_1a,
        "f1120s_returns_and_allowances": line_1b,
        "f1120s_net_receipts": line_1c,
        "f1120s_cost_of_goods_sold": line_2,
        "f1120s_gross_profit": line_3,
        "f1120s_net_gain_loss_4797": line_4,
        "f1120s_other_income": line_5,
        "f1120s_total_income": line_6,
    }


def _compute_deductions(r: SCorpReturn, income: dict) -> dict:
    """Form 1120-S Deductions section (lines 7-21).

    Rounding election (see `_compute_income`): each deduction line prints
    rounded, line 20 is the sum of the PRINTED lines 7-19, and line 21 is
    printed line 6 minus printed line 20 in integer arithmetic with no
    outer re-round. Same convention as the Schedule SE R10 ruling.
    """
    d = r.deductions
    lines = (
        ("f1120s_compensation_of_officers", d.compensation_of_officers),
        ("f1120s_salaries_wages", d.salaries_wages),
        ("f1120s_repairs_maintenance", d.repairs_maintenance),
        ("f1120s_bad_debts", d.bad_debts),
        ("f1120s_rents", d.rents),
        ("f1120s_taxes_licenses", d.taxes_licenses),
        ("f1120s_interest", d.interest),
        ("f1120s_depreciation", d.depreciation),
        ("f1120s_depletion", d.depletion),
        ("f1120s_advertising", d.advertising),
        ("f1120s_pension_profit_sharing", d.pension_profit_sharing_plans),
        ("f1120s_employee_benefits", d.employee_benefits),
        ("f1120s_other_deductions", d.other_deductions),
    )
    printed = {key: irs_round(amount) for key, amount in lines}
    line_20 = sum(printed.values())
    line_21 = income["f1120s_total_income"] - line_20
    return {
        **printed,
        "f1120s_total_deductions": line_20,
        "f1120s_ordinary_business_income": line_21,
    }


def _compute_total_tax(r: SCorpReturn) -> dict:
    """Form 1120-S Total Tax (line 22c / 23c from 2023).

    §1375 / §1374 amounts are scope-outs (caller-supplied) and are summed.

    §453(l)(3) / §453A(c) interest is ALSO a scope-out, but a fail-closed
    one: the IRS instructions make it a SHAREHOLDER liability reported on
    Schedule K-1 box 17 codes M/N, and it never appears in the entity's
    additional-taxes list. tenforty does not model K-1 box 17 M/N, so a
    nonzero amount raises rather than silently misstating entity tax.
    The output key is kept and always reports 0.
    """
    if r.scope_outs.interest_on_453_deferred != 0:
        raise NotImplementedError(
            "interest_on_453_deferred is nonzero, but §453(l)(3)/§453A(c) "
            "interest is a shareholder-level liability (Schedule K-1 box 17 "
            "codes M/N), not entity tax on Form 1120-S line 22c/23c. "
            "tenforty does not model it, so this return cannot be produced."
        )
    line_22a = irs_round(r.scope_outs.net_passive_income_tax)
    line_22b = irs_round(r.scope_outs.built_in_gains_tax)
    return {
        "f1120s_net_passive_income_tax": line_22a,
        "f1120s_built_in_gains_tax": line_22b,
        "f1120s_interest_on_453_deferred": irs_round(0.0),
        "f1120s_total_tax": line_22a + line_22b,
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
    line_23a = irs_round(p.estimated_tax_payments)
    line_23b = irs_round(p.prior_year_overpayment_credited)
    line_23c = irs_round(p.tax_deposited_with_7004)
    line_23d = irs_round(p.credit_for_federal_excise_tax)
    line_23e = irs_round(p.refundable_credits)
    line_23 = line_23a + line_23b + line_23c + line_23d + line_23e
    line_22 = total_tax["f1120s_total_tax"]
    delta = line_22 - line_23
    return {
        "f1120s_estimated_tax_payments": line_23a,
        "f1120s_prior_year_overpayment_credited": line_23b,
        "f1120s_tax_deposited_with_7004": line_23c,
        "f1120s_credit_for_federal_excise_tax": line_23d,
        "f1120s_refundable_credits": line_23e,
        "f1120s_total_payments": line_23,
        "f1120s_amount_owed": max(delta, 0),
        "f1120s_estimated_tax_penalty": irs_round(0.0),
        "f1120s_overpayment": max(-delta, 0),
        "f1120s_credited_to_next_year": irs_round(0.0),
    }


# Schedule B Yes/No questions, in form order: (answer field, form line, what a
# True answer would require that tenforty does not model — "" when True prints).
# Each field yields TWO compute keys, ``f1120s_sch_b_<field>`` (the Yes box) and
# ``f1120s_sch_b_<field>_no`` (the No box); line 7 is a single box, so it has the
# Yes key only. A pair is marked only when the answer is stated: unstated (None)
# leaves both boxes clear.
_SCH_B_YES_NO: tuple[tuple[str, str, str], ...] = (
    ("shareholder_disregarded_entity_trust_estate_or_nominee", "3",
     "Schedule B-1 (Information on Certain Shareholders of an S Corporation)"),
    ("owns_20pct_stock_of_any_corporation", "4a",
     "the line 4a (i)-(v) detail table (corporation name, EIN, country, "
     "percentage, QSub election date)"),
    ("owns_20pct_interest_in_partnership_or_trust", "4b",
     "the line 4b (i)-(v) detail table (entity name, EIN, type, country, "
     "maximum percentage)"),
    ("restricted_stock_outstanding", "5a",
     "the line 5a (i)-(ii) share-count amounts"),
    ("stock_options_or_warrants_outstanding", "5b",
     "the line 5b (i)-(ii) share-count amounts"),
    ("filed_form_8918", "6", ""),
    ("section_163j_election", "9", ""),
    ("form_8990_conditions_met", "10",
     "Form 8990 (Limitation on Business Interest Expense)"),
    ("receipts_and_assets_under_250k", "11", ""),
    ("nonshareholder_debt_canceled", "12",
     "the line 12 principal-reduction amount"),
    ("qsub_election_terminated", "13", ""),
    ("payments_requiring_1099s", "14a", ""),
    ("filed_required_1099s", "14b", ""),
    ("qualified_opportunity_fund", "15",
     "Form 8996 (Qualified Opportunity Fund) and its line 15 amount"),
    ("digital_asset_transactions", "16", ""),
)

# Line 11's False answer means Schedules L and M-1 are REQUIRED; neither is
# modeled, so False refuses (True is the only printable answer).
_SCH_L_M1_REFUSAL = (
    "Schedule B line 11 is stated false: the corporation does not satisfy both "
    "the under-$250,000 total-receipts and total-assets conditions, so Schedule "
    "L (balance sheet) and Schedule M-1 are required. tenforty does not model "
    "Schedule L or M-1; this return cannot be completed automatically. File by "
    "hand."
)


def _compute_schedule_b(r: SCorpReturn) -> dict:
    """Form 1120-S Schedule B Yes/No + text answers (pass-through).

    `accounting_method` (AccountingMethod enum) explodes into three
    boolean keys here so the downstream PDF mapping layer can target the
    form's three checkboxes (Cash / Accrual / Other) directly. The IRS
    form's Question 1 has three exclusive checkboxes — a single enum
    field would require a converter at the PDF-fill boundary; emitting
    three booleans here keeps the boundary trivial.

    Each other question yields a Yes key and a No key (see ``_SCH_B_YES_NO``).
    A ``True`` answer that stands for an unmodeled attachment, or a ``False``
    line 11 (Schedules L / M-1 required), raises ``NotImplementedError`` —
    the compute path refuses what the form would then require us to attach. An
    unstated (None) answer never raises here; emit refuses it separately.
    """
    sb = r.schedule_b_answers
    out: dict = {
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
    }
    for field, line, attachment in _SCH_B_YES_NO:
        answer = getattr(sb, field)
        if answer is True and attachment:
            raise NotImplementedError(
                f"Schedule B line {line} (`{field}`) is stated true, which "
                f"requires {attachment}; tenforty does not model it, so this "
                "return cannot be completed automatically. File by hand, or "
                "set the answer to false if it is in fact No.")
        if answer is False and field == "receipts_and_assets_under_250k":
            raise NotImplementedError(_SCH_L_M1_REFUSAL)
        out[f"f1120s_sch_b_{field}"] = answer is True
        out[f"f1120s_sch_b_{field}_no"] = answer is False
    # Line 7: a single "check this box" cell (no No box); stated False = clear.
    out["f1120s_sch_b_issued_oid_debt_instruments"] = (
        sb.issued_oid_debt_instruments is True)
    # Line 8: dollar amount; omitted (blank) unless stated.
    if sb.net_unrealized_built_in_gain is not None:
        out["f1120s_sch_b_net_unrealized_built_in_gain"] = irs_round(
            sb.net_unrealized_built_in_gain)
    return out


def check_schedule_b_for_emit(scenario: Scenario) -> None:
    """Refuse to print Schedule B with an unstated or unanswerable question.

    Called at PDF EMIT (the compute path never needs the answers). Gathers every
    problem and raises ONE ``ValueError`` listing all of them, so a scenario is
    fixed in one pass:

    * every Yes/No answer and line 7 must be stated (None is refused), except
      line 14b, which is required only when line 14a is Yes, and line 16, which
      is required for tax year 2023 and later;
    * line 14b stated while 14a is No is refused (the form does not ask it);
    * line 16 stated for 2021 / 2022 is refused (that question is not on those
      forms);
    * line 11 stated true while the numbers say receipts or total assets reach
      $250,000 is refused as inconsistent. The test is the SAME function the
      Schedule L / M-1 attestation gate uses (``_has_scorp_large_balance_sheet``)
      so the two can never disagree about which side of the threshold a return
      is on.
    """
    r = scenario.s_corp_return
    if r is None:
        return
    year = scenario.config.year
    sb = r.schedule_b_answers
    missing: list[str] = []
    problems: list[str] = []

    def stated(field):
        return getattr(sb, field) is not None

    for field, line, _attachment in _SCH_B_YES_NO:
        if field == "filed_required_1099s":
            if sb.payments_requiring_1099s is True and not stated(field):
                missing.append(f"{field} (line 14b: required because line 14a "
                               "is Yes)")
            elif sb.payments_requiring_1099s is not True and stated(field):
                problems.append(
                    f"`{field}` (line 14b) is stated but line 14a is not Yes; "
                    "the form asks 14b only when 14a is Yes, so leave it null")
            continue
        if field == "digital_asset_transactions":
            if year >= 2023 and not stated(field):
                missing.append(f"{field} (line 16)")
            elif year < 2023 and stated(field):
                problems.append(
                    f"`{field}` (line 16) is stated, but the {year} Form "
                    "1120-S has no line 16 (digital assets) — leave it null")
            continue
        if not stated(field):
            missing.append(f"{field} (line {line})")
    if sb.issued_oid_debt_instruments is None:
        missing.append("issued_oid_debt_instruments (line 7)")
    if (sb.receipts_and_assets_under_250k is True
            and _has_scorp_large_balance_sheet(scenario)):
        problems.append(
            "`receipts_and_assets_under_250k` (line 11) is stated true, but "
            "s_corp_return.income.gross_receipts or total_assets is $250,000 "
            "or more — the answer cannot be Yes; fix the answer or the "
            "figures")
    if missing or problems:
        parts = []
        if missing:
            parts.append(
                "Form 1120-S PDF emission needs every Schedule B question "
                f"answered for tax year {year}; unstated: "
                + "; ".join(missing)
                + ". Set each to true or false in "
                "s_corp_return.schedule_b_answers (it is null in this "
                "scenario).")
        parts.extend(problems)
        raise ValueError(" ".join(parts))


# Schedule K lines 1-10 (income, far-right column) and lines 11-12d (+16f)
# (deductions) that feed line 18. Only line 1 has inputs in v1; the rest are
# zero placeholders, but line 18 is computed as the real combine so it stays
# correct when separately stated items gain inputs.
_SCH_K_LINE_18_INCOME_KEYS = (
    "f1120s_sch_k_ordinary_business_income",
    "f1120s_sch_k_net_rental_real_estate",
    "f1120s_sch_k_other_net_rental_income",
    "f1120s_sch_k_interest_income",
    "f1120s_sch_k_ordinary_dividends",
    "f1120s_sch_k_royalties",
    "f1120s_sch_k_net_short_term_capital_gain",
    "f1120s_sch_k_net_long_term_capital_gain",
    "f1120s_sch_k_net_section_1231_gain",
    "f1120s_sch_k_other_income",
)
_SCH_K_LINE_18_DEDUCTION_KEYS = (
    "f1120s_sch_k_section_179_deduction",
    "f1120s_sch_k_charitable_contributions",
)


def _schedule_k_line_18(sch_k: dict) -> int:
    """Schedule K line 18 (income/loss reconciliation): combine lines 1-10,
    subtract lines 11-12d (and 16f, which has no key). Computed from the
    printed Schedule K amounts."""
    return (
        sum(sch_k[k] for k in _SCH_K_LINE_18_INCOME_KEYS)
        - sum(sch_k[k] for k in _SCH_K_LINE_18_DEDUCTION_KEYS)
    )


def _compute_schedule_k(deductions: dict) -> dict:
    """Form 1120-S Schedule K entity-level totals.

    In v1 only line 1 (OBI) has compute logic; the remaining lines emit
    zero so the Sch K section is complete on the fill output (the keys
    are required by the PDF mapping but their values await later sub-plans).
    Line 18 is the real combine of the lines above (`_schedule_k_line_18`).
    """
    sch_k = {
        "f1120s_sch_k_ordinary_business_income":
            deductions["f1120s_ordinary_business_income"],
        **_SCH_K_V1_ZERO_PLACEHOLDERS,
    }
    sch_k["f1120s_sch_k_income_loss_reconciliation"] = \
        _schedule_k_line_18(sch_k)
    return sch_k


def _compute_schedule_k1_allocations(
    r: SCorpReturn, schedule_k: dict,
) -> list[K1Allocation]:
    """Per-shareholder K-1 allocation (pro-rata by ownership %).

    v1 supports Sch K line 1 (OBI) on Sch K-1 box 1, plus box 17 code V
    (§199A QBI, W-2 wages, UBIA) sourced from `SCorpReturn.section_199a`;
    other separately-stated items have no v1 compute logic.
    """
    sch_k_line_1 = schedule_k["f1120s_sch_k_ordinary_business_income"]
    info = r.section_199a
    entity_qbi = (
        sch_k_line_1 if (info is None or info.qbi_override is None)
        else irs_round(info.qbi_override)
    )
    # Default Statement A when `section_199a` is None: QBI = Sch K line 1,
    # W-2 wages 0, UBIA 0. The zero W-2 wages is CONSERVATIVE, not derived:
    # an S corporation that pays wages (nonzero salaries_wages /
    # compensation_of_officers) generally reports entity-paid W-2 wages on
    # Statement A for the shareholders' §199A wage limitation, and
    # understating them can only shrink (never overstate) the shareholder's
    # deduction. §199A's W-2-wage definition is not simply the deduction
    # lines, so we do not auto-populate from them; callers who want the
    # wage limitation credited supply `SCorp199AInfo.w2_wages`.
    entity_w2 = 0.0 if info is None else info.w2_wages
    entity_ubia = 0.0 if info is None else info.ubia
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
            box_17v_qbi=irs_round(entity_qbi * share),
            box_17v_w2_wages=irs_round(entity_w2 * share),
            box_17v_ubia=irs_round(entity_ubia * share),
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
