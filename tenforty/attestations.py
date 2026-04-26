"""Data-driven attestation registry.

Each Attestation describes a scope-out gate on TaxReturnConfig with a 3-way
contract:
- `None` at load → raise ValueError with `load_error` at load time.
- `False` + `triggered_when(scenario)` truthy → raise NotImplementedError with
  `compute_error` at compute time.
- `True` → proceed (the scope-out path is accepted by the user).

Single source of truth for all 13 attestations. Both
scenario._validate_scenario_config and sch_e_part_ii._enforce_scope_gates
iterate this tuple rather than hand-coded `if ... is None: raise` blocks.

Fixture/helper defaults are deliberately NOT on this dataclass. They live in
`tests/helpers.plan_d_attestation_defaults()` so that changing what a simple
in-memory test scenario implies (e.g., whether the user is assumed to have
unlimited at-risk amounts when constructing a bare Scenario) is a helper
change, reviewable independently from this registry.

Compute-time ordering note: entries with triggered_when predicates that fire
at sch_e_part_ii compute time appear in the same logical order as the old
per-field checks they replace, so existing tests that assert on which error
fires first for a given scenario remain green."""

from dataclasses import dataclass
from typing import Callable

from tenforty.models import EntityType, Scenario


@dataclass(frozen=True)
class Attestation:
    field: str
    triggered_when: Callable[[Scenario], bool]
    load_error: str
    compute_error: str


def _has_any_k1(s: Scenario) -> bool:
    return bool(s.schedule_k1s)


def _has_qbi(s: Scenario) -> bool:
    return any(k1.qbi_amount for k1 in s.schedule_k1s)


def _has_section_1231(s: Scenario) -> bool:
    return any(k1.section_1231_gain for k1 in s.schedule_k1s)


def _has_section_179(s: Scenario) -> bool:
    return any(k1.section_179_deduction for k1 in s.schedule_k1s)


def _has_partnership_se_earnings(s: Scenario) -> bool:
    return any(
        k1.entity_type == EntityType.PARTNERSHIP
        and k1.partnership_self_employment_earnings
        for k1 in s.schedule_k1s
    )


def _more_than_four_k1s(s: Scenario) -> bool:
    return len(s.schedule_k1s) > 4


def _never(s: Scenario) -> bool:
    """Sentinel `triggered_when` predicate: never fires at compute time.

    An attestation whose `triggered_when` is `_never` is enforced **only at
    load time** — the `None → ValueError` gate in `validate_load_time` runs,
    and `enforce_compute_time` skips the entry entirely.

    Use this for attestations that:
    - Raise eagerly in a different place (e.g. `has_foreign_accounts=True`
      raises `NotImplementedError` immediately in `_validate_scenario_config`
      because no scenario context makes a foreign account safe).
    - Are user-awareness knobs with no runtime trigger (e.g.
      `prior_year_itemized` configures the Sch 1 state-refund rule; an
      unset value is rejected at load but the value itself does not cause
      compute-time failure).

    The inline comment on each `triggered_when=_never,` row is for quick
    scanning; this docstring is the canonical reference."""
    return False


def _has_scorp_large_balance_sheet(s: Scenario) -> bool:
    if s.s_corp_return is None:
        return False
    r = s.s_corp_return
    return (
        r.total_assets >= 250_000.0
        or r.income.gross_receipts >= 250_000.0
    )


def _has_scorp_section_1375_tax(s: Scenario) -> bool:
    return (
        s.s_corp_return is not None
        and s.s_corp_return.scope_outs.net_passive_income_tax != 0.0
    )


def _has_scorp_section_1374_tax(s: Scenario) -> bool:
    return (
        s.s_corp_return is not None
        and s.s_corp_return.scope_outs.built_in_gains_tax != 0.0
    )


_ATTESTATIONS: tuple[Attestation, ...] = (
    # --- Load-time-only attestations ---
    Attestation(
        field="has_foreign_accounts",
        triggered_when=_never,  # True-branch raises at load; see scenario._validate_scenario_config.
        load_error=(
            "Scenario config field `has_foreign_accounts` is required and "
            "must be either true or false. Schedule B Part III (Foreign "
            "Accounts and Trusts) is not implemented in tenforty v1; if any "
            "foreign financial account exists, this return will be "
            "INCORRECT and you may be legally required to file FinCEN Form "
            "114 (FBAR). You must answer this question explicitly in every "
            "scenario."
        ),
        compute_error="",  # unused; True-at-load raises NotImplementedError eagerly
    ),
    Attestation(
        field="acknowledges_sch_a_sales_tax_unsupported",
        triggered_when=_never,  # enforced in forms.sch_a
        load_error=(
            "Scenario config field `acknowledges_sch_a_sales_tax_unsupported` "
            "is required and must be either true or false. Schedule A line "
            "5a offers a state-and-local INCOME TAX or GENERAL SALES TAX "
            "election; tenforty v1 implements only the income-tax path. For "
            "filers in no-state-income-tax states (TX, FL, WA, NV, SD, WY, "
            "AK, TN, NH) the sales-tax election is usually the correct "
            "choice and v1 cannot produce it. Set `false` if your state "
            "levies an income tax (the income-tax path is correct for you). "
            "Set `true` ONLY if you are in a no-income-tax state AND you "
            "have reviewed the consequences — v1 will then raise "
            "NotImplementedError from Sch A compute rather than silently "
            "overstating your deduction."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_qbi_below_threshold",
        triggered_when=_never,  # enforced in forms.f8995 (threshold + QBI > 0)
        load_error=(
            "Scenario config field `acknowledges_qbi_below_threshold` is "
            "required and must be either true or false. Form 8995-A (full "
            "QBI) is not implemented in tenforty v1; if a K-1 carries QBI "
            "and taxable income exceeds the Rev. Proc. 2024-40 threshold, "
            "compute will raise NotImplementedError."
        ),
        compute_error="",
    ),
    # --- Compute-time K-1 scope gates, in enforcement order ---
    # Order matches _enforce_scope_gates so that tests asserting on which
    # error fires first for a given scenario stay green.
    Attestation(
        field="acknowledges_no_more_than_four_k1s",
        triggered_when=_more_than_four_k1s,
        load_error=(
            "Scenario config field `acknowledges_no_more_than_four_k1s` is "
            "required and must be either true or false. Schedule E Part II "
            "continuation sheets (for more than 4 K-1s) are not implemented "
            "in tenforty v1; compute will raise NotImplementedError if more "
            "than 4 K-1s are present and this attestation is False."
        ),
        compute_error=(
            "Scenario has more than 4 K-1s; Schedule E Part II continuation "
            "is not implemented in tenforty v1. Set "
            "`acknowledges_no_more_than_four_k1s: true` to accept that rows "
            "beyond D will be dropped, or reduce to 4 K-1s."
        ),
    ),
    Attestation(
        field="acknowledges_unlimited_at_risk",
        triggered_when=_has_any_k1,
        load_error=(
            "Scenario config field `acknowledges_unlimited_at_risk` is "
            "required and must be either true or false. Form 6198 (at-risk "
            "limitations) is not implemented in tenforty v1; compute will "
            "raise NotImplementedError at Sch E Part II time if any K-1 is "
            "present and this attestation is False."
        ),
        compute_error=(
            "K-1 present but `acknowledges_unlimited_at_risk` (at_risk gate) "
            "is false. Form 6198 (at-risk limitation) is not implemented in "
            "tenforty v1; set the attestation to true to affirm all K-1 "
            "activities have unlimited at-risk amounts."
        ),
    ),
    Attestation(
        field="basis_tracked_externally",
        triggered_when=_has_any_k1,
        load_error=(
            "Scenario config field `basis_tracked_externally` is required "
            "and must be either true or false. Shareholder/partner basis "
            "worksheets (Form 7203 for S-corps, partner basis worksheet for "
            "partnerships) are not implemented in tenforty v1; compute will "
            "raise NotImplementedError at Sch E Part II time if any K-1 is "
            "present and this attestation is False."
        ),
        compute_error=(
            "K-1 present but `basis_tracked_externally` is false. tenforty "
            "v1 does not compute stock/debt basis worksheets; set the "
            "attestation to true to affirm basis is tracked outside this "
            "system."
        ),
    ),
    Attestation(
        field="acknowledges_no_section_1231_gain",
        triggered_when=_has_section_1231,
        load_error=(
            "Scenario config field `acknowledges_no_section_1231_gain` is "
            "required and must be either true or false. Form 4797 (sales of "
            "business property) is not implemented in tenforty v1; compute "
            "will raise NotImplementedError if any K-1 carries nonzero "
            "section_1231_gain and this attestation is False."
        ),
        compute_error=(
            "K-1 reports section 1231 gain. Form 4797 is not implemented in "
            "tenforty v1; set `acknowledges_no_section_1231_gain: true` "
            "only if zero gain is correct."
        ),
    ),
    Attestation(
        field="acknowledges_no_section_179",
        triggered_when=_has_section_179,
        load_error=(
            "Scenario config field `acknowledges_no_section_179` is "
            "required and must be either true or false. The Section 179 "
            "deduction (Form 4562 Part I) flowing through from K-1s is not "
            "implemented in tenforty v1; compute will raise "
            "NotImplementedError if any K-1 carries nonzero "
            "section_179_deduction and this attestation is False."
        ),
        compute_error=(
            "K-1 reports section 179 deduction. Section 179 at the 1040 "
            "level is not implemented in tenforty v1; set "
            "`acknowledges_no_section_179: true` if zero is correct."
        ),
    ),
    Attestation(
        field="acknowledges_no_partnership_se_earnings",
        triggered_when=_has_partnership_se_earnings,
        load_error=(
            "Scenario config field `acknowledges_no_partnership_se_earnings` "
            "is required and must be either true or false. Schedule SE is "
            "not implemented in tenforty v1; compute will raise "
            "NotImplementedError if a partnership K-1 carries nonzero "
            "partnership_self_employment_earnings and this attestation is "
            "False."
        ),
        compute_error=(
            "Partnership K-1 reports SE earnings. Schedule SE is not "
            "implemented in tenforty v1; set "
            "`acknowledges_no_partnership_se_earnings: true` only if zero "
            "is correct."
        ),
    ),
    Attestation(
        field="acknowledges_no_k1_credits",
        triggered_when=_has_any_k1,
        load_error=(
            "Scenario config field `acknowledges_no_k1_credits` is required "
            "and must be either true or false. K-1 box 13 (partnership) and "
            "box 15 (S-corp) credits are not implemented in tenforty v1; "
            "compute will raise NotImplementedError if this attestation is "
            "False and any K-1 is present."
        ),
        compute_error=(
            "K-1 present but `acknowledges_no_k1_credits` is false. K-1 box "
            "13 / 15 credits are not implemented in tenforty v1; set the "
            "attestation to true to affirm no K-1 credits apply."
        ),
    ),
    # --- Load-time-only: user-awareness, not a compute trigger ---
    Attestation(
        field="acknowledges_no_estate_trust_k1",
        triggered_when=_never,  # enforced unconditionally in sch_e_part_ii._enforce_scope_gates
        load_error=(
            "Scenario config field `acknowledges_no_estate_trust_k1` is "
            "required and must be either true or false. Schedule E Part III "
            "(estate and trust K-1 income) is not implemented in tenforty "
            "v1; compute will raise NotImplementedError if any K-1 has "
            "entity_type == 'estate_trust'. Declare this attestation even "
            "when no estate/trust K-1 is present."
        ),
        compute_error="",
    ),
    Attestation(
        field="prior_year_itemized",
        triggered_when=_never,
        load_error=(
            "Scenario config field `prior_year_itemized` is required and "
            "must be either true or false. It drives the 1099-G state-tax-"
            "refund tax-benefit-rule on Schedule 1 line 1: if the prior "
            "year used the standard deduction, the refund is not taxable; "
            "if itemized, it is taxable up to the recovery limit."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_wash_sale_adjustments",
        triggered_when=lambda s: any(
            lot.wash_sale_loss_disallowed for lot in s.form1099_b
        ),
        load_error=(
            "`acknowledges_no_wash_sale_adjustments` required: confirm "
            "whether any 1099-B lot has wash-sale-disallowed loss (set "
            "true if none, false if awareness is needed)."
        ),
        compute_error=(
            "A 1099-B lot reports wash_sale_loss_disallowed > 0 but "
            "`acknowledges_no_wash_sale_adjustments` is false. Set the "
            "attestation to true to affirm awareness of IRC §1091 "
            "wash-sale treatment on the affected lot(s)."
        ),
    ),
    Attestation(
        field="acknowledges_no_other_basis_adjustments",
        triggered_when=lambda s: any(
            lot.other_basis_adjustment for lot in s.form1099_b
        ),
        load_error=(
            "`acknowledges_no_other_basis_adjustments` required: confirm "
            "whether any 1099-B lot has a basis adjustment other than "
            "wash sale."
        ),
        compute_error=(
            "A 1099-B lot reports a nonzero other_basis_adjustment but "
            "`acknowledges_no_other_basis_adjustments` is false. Other "
            "basis adjustments (IRS codes B/T/L/N/H/D/O/S/X) are supported "
            "in Form 8949 column (g) only when this attestation is set true."
        ),
    ),
    Attestation(
        field="acknowledges_no_28_rate_gain",
        triggered_when=lambda s: any(
            lot.is_28_rate_collectible for lot in s.form1099_b
        ),
        load_error=(
            "`acknowledges_no_28_rate_gain` required: confirm whether any "
            "1099-B lot is a collectible or §1202 gain subject to the "
            "28%-rate worksheet."
        ),
        compute_error=(
            "A 1099-B lot is flagged is_28_rate_collectible=True but "
            "`acknowledges_no_28_rate_gain` is false. The 28%-rate gain "
            "worksheet feeds Sch D's preferential-rate tax computation; "
            "set the attestation to true to affirm awareness."
        ),
    ),
    Attestation(
        field="acknowledges_no_unrecaptured_section_1250",
        triggered_when=lambda s: any(
            lot.is_section_1250 for lot in s.form1099_b
        ),
        load_error=(
            "`acknowledges_no_unrecaptured_section_1250` required: confirm "
            "whether any 1099-B lot is unrecaptured §1250 gain "
            "(real-property depreciation recapture)."
        ),
        compute_error=(
            "A 1099-B lot is flagged is_section_1250=True but "
            "`acknowledges_no_unrecaptured_section_1250` is false. The "
            "Unrecaptured §1250 Gain Worksheet feeds Sch D line 19; set "
            "the attestation to true to affirm awareness."
        ),
    ),
    # --- 1120-S scope-out attestations (Sub-plan 2) ---
    Attestation(
        field="acknowledges_no_1120s_schedule_l_needed",
        triggered_when=_has_scorp_large_balance_sheet,
        load_error=(
            "Scenario config field `acknowledges_no_1120s_schedule_l_needed` "
            "is required and must be either true or false. Schedule L "
            "(balance sheet) is not implemented in tenforty v1; per Form "
            "1120-S Schedule B Q10 it is optional only when both total "
            "receipts and total assets are under $250,000. Compute will "
            "raise NotImplementedError if either "
            "`s_corp_return.income.gross_receipts >= 250_000` or "
            "`s_corp_return.total_assets >= 250_000` and this attestation "
            "is False."
        ),
        compute_error=(
            "`s_corp_return.income.gross_receipts` or "
            "`s_corp_return.total_assets` reached $250,000, triggering the "
            "Schedule L (balance sheet) requirement. Schedule L is required "
            "per Form 1120-S Schedule B Q10 when total receipts and total "
            "assets meet this threshold. Schedule L is not implemented in "
            "tenforty v1; this return cannot be completed automatically. "
            "Reduce the scenario below the threshold."
        ),
    ),
    Attestation(
        field="acknowledges_no_1120s_schedule_m_needed",
        triggered_when=_has_scorp_large_balance_sheet,
        load_error=(
            "Scenario config field `acknowledges_no_1120s_schedule_m_needed` "
            "is required and must be either true or false. Schedule M-1 "
            "(book/tax reconciliation) and Schedule M-2 (AAA) are not "
            "implemented in tenforty v1; per Form 1120-S Schedule B Q10 "
            "they are optional only when both total receipts and total "
            "assets are under $250,000. Compute will raise "
            "NotImplementedError if either "
            "`s_corp_return.income.gross_receipts >= 250_000` or "
            "`s_corp_return.total_assets >= 250_000` and this attestation "
            "is False."
        ),
        compute_error=(
            "`s_corp_return.income.gross_receipts` or "
            "`s_corp_return.total_assets` reached $250,000, triggering the "
            "Schedule M-1 and M-2 requirement. Schedule M-1 (book/tax "
            "reconciliation) and Schedule M-2 (AAA) are required per Form "
            "1120-S Schedule B Q10 when total receipts and total assets "
            "meet this threshold. Neither is implemented in tenforty v1; "
            "this return cannot be completed automatically. Reduce the "
            "scenario below the threshold."
        ),
    ),
    Attestation(
        field="acknowledges_constant_shareholder_ownership",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_constant_shareholder_ownership` "
            "is required and must be either true or false. tenforty v1 "
            "allocates S-corp pass-through items pro rata using shareholder "
            "ownership percentages that are assumed constant for the full "
            "tax year; mid-year ownership changes (per-day allocation under "
            "IRC §1377) are not implemented."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_section_1375_tax",
        triggered_when=_has_scorp_section_1375_tax,
        load_error=(
            "Scenario config field `acknowledges_no_section_1375_tax` is "
            "required and must be either true or false. The Excess Net "
            "Passive Income Tax (IRC §1375) is not computed by tenforty "
            "v1; if applicable, supply the amount on "
            "`s_corp_return.scope_outs.net_passive_income_tax`. Compute "
            "will raise NotImplementedError if that scope-out value is "
            "nonzero and this attestation is False."
        ),
        compute_error=(
            "`s_corp_return.scope_outs.net_passive_income_tax` is nonzero "
            "but `acknowledges_no_section_1375_tax` is false. tenforty v1 "
            "does not compute the §1375 Excess Net Passive Income Tax; "
            "set the attestation to true to affirm the scope-out value is "
            "provided externally, or set the scope-out value to zero."
        ),
    ),
    Attestation(
        field="acknowledges_no_section_1374_tax",
        triggered_when=_has_scorp_section_1374_tax,
        load_error=(
            "Scenario config field `acknowledges_no_section_1374_tax` is "
            "required and must be either true or false. The Built-in "
            "Gains Tax (IRC §1374) is not computed by tenforty v1; if "
            "applicable, supply the amount on "
            "`s_corp_return.scope_outs.built_in_gains_tax`. Compute will "
            "raise NotImplementedError if that scope-out value is nonzero "
            "and this attestation is False."
        ),
        compute_error=(
            "`s_corp_return.scope_outs.built_in_gains_tax` is nonzero but "
            "`acknowledges_no_section_1374_tax` is false. tenforty v1 "
            "does not compute the §1374 Built-in Gains Tax; set the "
            "attestation to true to affirm the scope-out value is "
            "provided externally, or set the scope-out value to zero."
        ),
    ),
    Attestation(
        field="acknowledges_cogs_aggregate_only",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_cogs_aggregate_only` is "
            "required and must be either true or false. Form 1125-A (Cost "
            "of Goods Sold line-item detail) is not implemented in "
            "tenforty v1; supply the aggregate on "
            "`s_corp_return.income.cogs_aggregate`. Set true to affirm "
            "awareness that line-item COGS detail is not produced."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_officer_comp_aggregate_only",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_officer_comp_aggregate_only` "
            "is required and must be either true or false. Form 1125-E "
            "(Compensation of Officers line-item detail) is not "
            "implemented in tenforty v1; supply the aggregate on "
            "`s_corp_return.deductions.compensation_of_officers`. Set "
            "true to affirm awareness that line-item officer-compensation "
            "detail is not produced."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_elective_payment_election",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_elective_payment_election` "
            "is required and must be either true or false. Form 3800 "
            "elective payment elections (IRC §6417) are not computed by "
            "tenforty v1. The 2025 Form 1120-S routes any elective payment "
            "amount to line 24d via `s_corp_return.scope_outs.refundable_credits`; "
            "set true to affirm awareness that v1 does not compute the "
            "election and any value supplied externally must come from a "
            "completed Form 3800 prepared off-platform."
        ),
        compute_error="",
    ),
)


def validate_load_time(cfg) -> None:
    """Iterate _ATTESTATIONS and raise ValueError for any None field.

    Separate from compute-time enforcement because load runs before a
    Scenario object exists (only TaxReturnConfig is constructed at this
    point). Therefore `triggered_when` is not consulted here — any None
    field raises regardless of whether the trigger would fire."""
    for a in _ATTESTATIONS:
        if getattr(cfg, a.field) is None:
            raise ValueError(a.load_error)


def enforce_compute_time(scenario: Scenario) -> None:
    """Iterate _ATTESTATIONS and raise NotImplementedError for any field
    whose trigger fires while the attestation is False."""
    cfg = scenario.config
    for a in _ATTESTATIONS:
        if not a.triggered_when(scenario):
            continue
        if getattr(cfg, a.field) is False:
            raise NotImplementedError(a.compute_error)
