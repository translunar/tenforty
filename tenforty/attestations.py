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
`tests/helpers.scope_out_attestation_defaults()` so that changing what a simple
in-memory test scenario implies (e.g., whether the user is assumed to have
unlimited at-risk amounts when constructing a bare Scenario) is a helper
change, reviewable independently from this registry.

Compute-time ordering note: entries with triggered_when predicates that fire
at sch_e_part_ii compute time appear in the same logical order as the old
per-field checks they replace, so existing tests that assert on which error
fires first for a given scenario remain green."""

from dataclasses import dataclass
from typing import Callable, Sequence

from tenforty.models import (
    PERSONAL_PROPERTY_CLASSES, REAL_PROPERTY_CLASSES,
    SUPPORTED_RECOVERY_CLASSES, EntityType, Scenario,
)
from tenforty.rounding import irs_round


@dataclass(frozen=True)
class Attestation:
    field: str
    triggered_when: Callable[[Scenario], bool]
    load_error: str
    compute_error: str  # required — preserve existing signature
    applies_in_years: frozenset[int] | None = None  # None = all years; trailing optional


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


def k1_part_ii_row_total(k1) -> int:
    """The single Schedule E Part II amount a K-1 prints: its business boxes
    NETTED into one row, IRS-rounded per component (the two rental boxes are
    combined before rounding, matching the form's single rental line).
    Lives here, not in forms/sch_e_part_ii.py (which imports it), so the
    attestation trigger below and the printed row share one definition."""
    return (
        irs_round(k1.ordinary_business_income)
        + irs_round(k1.net_rental_real_estate + k1.other_net_rental)
        + irs_round(k1.royalties)
        + irs_round(k1.other_income)
    )


def scorp_k1_row_is_net_loss(k1) -> bool:
    """True for an S corporation K-1 whose printed Part II row is a NET
    LOSS -- the row Schedule E line 28 column (e) must flag as needing a
    basis computation. Keyed on the printed row, not on box 1 alone: a row
    can report a loss with box 1 at zero or positive, and a box 1 loss
    inside a net-income row prints no loss at all. Public:
    forms/sch_e_part_ii.py uses the SAME predicate to check the box, so the
    gate and the printed box cannot disagree."""
    return (k1.entity_type == EntityType.S_CORP
            and k1_part_ii_row_total(k1) < 0)


def _has_any_scorp_k1_net_loss_row(s: Scenario) -> bool:
    return any(scorp_k1_row_is_net_loss(k1) for k1 in s.schedule_k1s)


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


def _always(s: Scenario) -> bool:
    """Sentinel `triggered_when` predicate: fires for EVERY scenario.

    The mirror image of `_never`. Use this for a scope-out whose subject
    leaves no trace in scenario data, so the attestation itself is the only
    signal available — there is no field to inspect and therefore no
    data-derived trigger to write. With `_always`, `enforce_compute_time`
    raises `NotImplementedError(compute_error)` for any scenario whose
    attestation is False, and proceeds when it is True.

    An `_always` entry MUST carry a non-empty `compute_error`: it is the
    only text the user ever sees for the refusal."""
    return True


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


_FEDERAL_ATTESTATIONS: tuple[Attestation, ...] = (
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
    Attestation(
        field="acknowledges_form_7203_attached_separately",
        triggered_when=_has_any_scorp_k1_net_loss_row,
        load_error=(
            "Scenario config field `acknowledges_form_7203_attached_separately` "
            "is required and must be either true or false. A loss from an S "
            "corporation (a K-1 whose Schedule E Part II row nets to a loss) "
            "requires line 28 column (e) to be checked and the shareholder's basis "
            "computation (Form 7203) to be attached. tenforty checks the box "
            "but does NOT produce Form 7203. Set true to affirm Form 7203 is "
            "prepared by hand and attached to the return; set false "
            "otherwise -- compute will then refuse any S corporation K-1 "
            "net-loss row with NotImplementedError."
        ),
        compute_error=(
            "An S corporation K-1 reports a net loss on Schedule E Part II but "
            "`acknowledges_form_7203_attached_separately` is false. The loss "
            "requires Schedule E line 28 column (e) and an attached basis "
            "computation (Form 7203), which tenforty does not produce. Set "
            "`acknowledges_form_7203_attached_separately: true` to affirm "
            "Form 7203 is prepared by hand and attached to the return."
        ),
    ),
    Attestation(
        field="acknowledges_sch_c_all_investment_at_risk",
        triggered_when=_never,  # enforced in forms.sch_c (line 31 < 0)
        load_error=(
            "Scenario config field `acknowledges_sch_c_all_investment_at_risk` "
            "is required and must be either true or false. A Schedule C "
            "business with a net loss must check line 32a (all investment "
            "is at risk) or 32b (some investment is not at risk, Form 6198). "
            "Form 6198 is not implemented in tenforty v1. Set true to affirm "
            "that ALL investment in every loss-making Schedule C business is "
            "at risk (box 32a is then checked); set false otherwise -- "
            "compute will then refuse any Schedule C net loss with "
            "NotImplementedError."
        ),
        compute_error="",
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


# CA-specific scope-out attestations (year-aware).
# Membership is meaningful, not just ordering: tests/helpers.py derives
# CA_SCOPE_OUT_FIELDS from this tuple, so every member is enumerated as
# Californian by the test suite. Federal gates do NOT belong here even when
# a desired enforcement order would put them at this point in the registry —
# use _ALWAYS_TAIL below.
_CA_ATTESTATIONS = (
    Attestation(
        field="acknowledges_no_540nr_filing",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_540nr_filing` is required "
            "and must be either true or false. Form 540NR (nonresident or "
            "part-year-resident return) is not implemented in tenforty v1; "
            "v1 supports full-year-resident filing only. Set true to affirm "
            "that you were a full-year California resident for the tax year."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_ca_amt_preferences",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ca_amt_preferences` is "
            "required and must be either true or false. California Schedule "
            "P (Alternative Minimum Tax) is not computed by tenforty v1. "
            "Set true to affirm you have NONE of the following preferences: "
            "bonus depreciation under IRC §168(k); §179 expense election; "
            "ISO exercises; private-activity municipal bond interest; "
            "real-estate operating losses outside passive limits; %-depletion. "
            "Compute will raise NotImplementedError if any of these signals "
            "appear and this attestation is False."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_ca_nol_carryover",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ca_nol_carryover` is "
            "required. CA Net Operating Loss carryovers (FTB 3805V) are not "
            "tracked across multiple years by tenforty v1; the CA NOL "
            "suspension rules (TY2024-2026 for AGI ≥ $1M) and CA-specific "
            "recomputation are out of scope. Supply any prior-year NOL "
            "deduction directly via worksheet entries on Sch CA Part I §B 9b."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_ca_depreciation_divergence",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ca_depreciation_divergence` "
            "is required. CA depreciation diverges from federal in many forms "
            "(§168(k) bonus disallowed, §179 limit $25k vs federal $1.16M+, "
            "MACRS recovery period differences for residential rental and "
            "commercial property, §280F luxury-auto cap differences). Compute "
            "the federal-vs-CA reconciliation externally (FTB 3885A) and supply "
            "the addback directly via worksheet entries; tenforty v1 does not "
            "re-derive the difference."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_ca_ira_basis_divergence",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ca_ira_basis_divergence` "
            "is required. CA IRA / Roth IRA basis can diverge from federal "
            "due to multi-year residency changes and SE-income deduction "
            "differences (FTB Pub 1005). Multi-year basis tracking is out of "
            "tenforty v1's scope; supply any divergence directly via worksheet "
            "entries on Sch CA Part I §A 4a/4b."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_ca_rdp_status",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ca_rdp_status` is required "
            "and must be either true or false. Registered Domestic Partner (RDP) "
            "filing status is a CA-specific filing status with no federal analog "
            "and is not implemented in tenforty v1. Set true to affirm you are "
            "NOT filing as RDP."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_excess_business_loss_carryover",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_excess_business_loss_carryover` "
            "is required. IRC §461(l) Excess Business Loss carryover (FTB 3461) "
            "involves multi-year carryforward tracking and CA-specific non-"
            "conformity to TCJA/CARES/ARPA/IRA modifications. Multi-year "
            "carryover state is out of tenforty v1's scope; supply current-year "
            "EBL adjustment directly via worksheet entries."
        ),
        compute_error="",
        applies_in_years=frozenset({2021, 2022, 2023, 2024, 2025}),
    ),
    Attestation(
        field="acknowledges_no_1031_personal_property_divergence",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_1031_personal_property_divergence` "
            "is required. Federal §1031 like-kind exchange was limited to real "
            "property by TCJA (post-2017); CA conformed to that limitation only "
            "for taxpayers with AGI ≥ $250,000 (single) / $500,000 (HoH/MFJ). "
            "Below the threshold, CA still allows broader §1031 nonrecognition "
            "(including personal property). tenforty v1 does not model this "
            "below-threshold divergence; supply any §1031 personal-property "
            "adjustment directly via worksheet entries."
        ),
        compute_error="",
        applies_in_years=frozenset({2021, 2022, 2023, 2024, 2025}),
    ),
    Attestation(
        field="acknowledges_no_ic_worker_reclassification",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_ic_worker_reclassification` "
            "is required and must be either true or false. CA may reclassify "
            "federally-classified independent contractors as employees under "
            "Prop 22 / AB5; this affects multiple Sch CA lines (wages, Sch C "
            "income/deduction, SE tax). tenforty v1 does not model the "
            "reclassification; if any of your federal Sch C income would be "
            "reclassified as wages by CA law, this is out of scope."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_other_state_tax_credit",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_other_state_tax_credit` is "
            "required. CA Schedule S (Other State Tax Credit) is for filers "
            "with income taxed by both California and another state, not "
            "implemented in tenforty v1 (single-state focus). Set true to "
            "affirm you have no out-of-state tax credit to claim."
        ),
        compute_error="",
    ),
    Attestation(
        field="acknowledges_no_railroad_retirement_benefits",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_railroad_retirement_benefits` is "
            "required and must be either true or false. California excludes Railroad "
            "Retirement Board (Tier 1 and Tier 2) benefits from taxation under "
            "R&TC 17087. tenforty v1 does NOT auto-derive an RRB subtraction from "
            "federal data alone because federal compute lumps RRB into "
            "`pensions_taxable` (1040 line 5b) without separating Tier 1/2 from other "
            "pension income. If you received RRB benefits, set "
            "`CA540Return.rrb_tier_1_2_amount` to the RRB portion of your line 5b "
            "amount; the kernel will route it as a §A 5b Col B subtraction. Set true "
            "to affirm you have no RRB benefits."
        ),
        compute_error="",
        applies_in_years=frozenset({2021, 2022, 2023, 2024, 2025}),
    ),
    Attestation(
        field="acknowledges_no_paid_family_leave_benefits",
        triggered_when=_never,
        load_error=(
            "Scenario config field `acknowledges_no_paid_family_leave_benefits` is "
            "required and must be either true or false. California excludes Paid "
            "Family Leave benefits paid by the EDD from CA taxation (FTB Pub 1001 "
            "p.17); PFL is reported on Form 1099-G alongside unemployment but is "
            "not separately surfaced by tenforty v1's federal compute layer (no PFL "
            "field on `Form1099G`; `sch_1.compute` aggregates only UI into line 7). "
            "If you received CA PFL benefits, set `CA540Return.pfl_amount` to the "
            "PFL portion; the kernel will route it as a §B 7 Col B subtraction. Set "
            "true to affirm you have no PFL benefits."
        ),
        compute_error="",
        applies_in_years=frozenset({2021, 2022, 2023, 2024, 2025}),
    ),
)


# Unconditionally-triggered attestations, concatenated LAST (see
# _ATTESTATIONS below). This group exists to make an ordering invariant
# structural instead of positional-by-accident.
#
# `enforce_compute_time` walks _ATTESTATIONS in order and raises on the
# FIRST violated gate, so tuple position IS error precedence. An
# `_always`-triggered gate fires for EVERY scenario, so wherever it sits it
# preempts every data-conditional gate after it — silently changing which
# error a multi-violation scenario reports, and with it the identity of the
# message that error-text assertions match on. That makes "`_always` entries
# sort last" load-bearing behavior, not stylistic tidiness.
#
# Previously the sole `_always` entry got this property by accident: it was
# parked at the physical end of _CA_ATTESTATIONS, with a comment claiming it
# was "LAST in the federal tuple" — which was false, and which also made a
# FEDERAL gate a member of the tuple tests/helpers.py enumerates as the CA
# scope-out set. A separate trailing group gives the invariant a home that
# does not depend on which jurisdiction's tuple happens to be concatenated
# last, and keeps the CA set honest. Add `_always` entries HERE, never to a
# jurisdiction tuple. tests/test_attestations.py::TestAlwaysEntriesSortLast
# enforces this.
_ALWAYS_TAIL: tuple[Attestation, ...] = (
    # --- Schedule D prior-year capital-loss carryover (IRC §1212(b)) ---
    # Federal, not Californian, despite formerly sitting inside
    # _CA_ATTESTATIONS: it applies to every return regardless of state.
    Attestation(
        field="acknowledges_no_capital_loss_carryforward",
        triggered_when=_always,  # no data-derived trigger exists; see _always
        load_error=(
            "Scenario config field `acknowledges_no_capital_loss_carryforward` "
            "is required and must be either true or false. A prior-year "
            "capital-loss carryover enters Schedule D at line 6 (short-term "
            "carryover) and line 14 (long-term carryover), retaining its "
            "character; tenforty v1 models NEITHER line and has no scenario "
            "field to carry either amount. Set true to affirm the filer has "
            "no prior-year capital-loss carryforward. Set false if one "
            "exists — compute will then refuse with NotImplementedError "
            "rather than produce a return that ignores it."
        ),
        compute_error=(
            "`acknowledges_no_capital_loss_carryforward` is false: the filer "
            "has a prior-year capital-loss carryover. Carryovers enter "
            "Schedule D line 6 (short-term) and line 14 (long-term), "
            "retaining their character. tenforty v1 models NEITHER line, so "
            "the carryover would be silently treated as zero and the return "
            "would be WRONG: the carryover's deduction is dropped, so the "
            "computed tax is OVERSTATED, and the §1212(b) carryforward to "
            "next year is UNDERSTATED. No attestation value makes v1 able to "
            "produce this return; supporting it requires modeling the "
            "short-term/long-term carryover split as a feature."
        ),
        # applies_in_years=None (ALL years) is deliberate, not an oversight.
        # Unlike the CA entries above — whose windows track FTB conformity
        # dates that genuinely move year to year — the carryover rules here
        # are statutory constants: IRC §1211(b) (the flat capital-loss
        # deduction cap) and §1212(b) (the character-preserving carryforward
        # to succeeding years) have not been amended since the Tax Reform Act
        # of 1986 (Pub. L. 99-514). There is no year in tenforty's supported
        # range in which a filer with a prior-year carryover is computable,
        # so there is no window to bound and none should be added.
        applies_in_years=None,
    ),
    # --- Federal alternative minimum tax (IRC §55, Form 6251) ---
    # Placed AFTER the carryforward entry on purpose: tuple position is error
    # precedence (see the block comment above), and appending rather than
    # inserting leaves every existing error-text assertion matching the same
    # message it matched before.
    #
    # WHY THE SHAPE IS `_always` — THIS WAS A USER DECISION, NOT A DERIVATION.
    # The alternative considered was a DATA-TRIGGERED attestation: a predicate
    # over scenario inputs that fires only on returns that could plausibly owe
    # AMT. It was rejected for one reason only — writing that predicate means
    # deriving an AMT-exposure trigger from IRS Form 6251 "Who Must File"
    # material, which is not in this repo, and the user declined to have it
    # fetched. Rather than invent a tax-law trigger from memory, the gate asks
    # every filer.
    #
    # READ THAT SCOPE EXACTLY. This entry is NOT a finding that no combination
    # of modeled scenario inputs can produce an AMT-positive return. That
    # question is OPEN and tracked as ticket (q). Because the shape is
    # decision-driven rather than claim-driven, no neutral derivation is owed
    # here: `_always` is the conservative SUPERSET of whatever data trigger (q)
    # eventually justifies, so it cannot be wrong in the dangerous direction —
    # only noisier than necessary. Narrowing it needs (q)'s answer first.
    #
    # THE REAL FIX for (q) is to compute AMT: either port Form 6251 to the
    # native path or harvest the vendor workbook's own 6251 figures. Until one
    # of those lands, this attestation converts a SILENT understatement into an
    # explicit acknowledgment. That is all it does; it computes nothing.
    Attestation(
        field="acknowledges_no_federal_amt",
        triggered_when=_always,  # user decision, not a derived trigger; see above
        load_error=(
            "Scenario config field `acknowledges_no_federal_amt` is required "
            "and must be either true or false. Federal alternative minimum "
            "tax (IRC §55) is reported on Form 6251 and enters the return at "
            "Schedule 2 line 1, which flows to Form 1040 line 17, then line "
            "18, then line 24. tenforty's native compute path implements no "
            "Form 6251 at all, so it treats AMT as zero. Set true to affirm "
            "the filer owes no federal AMT. Set false if AMT may apply — "
            "compute will then refuse rather than emit a return whose tax is "
            "understated by the whole of the AMT."
        ),
        compute_error=(
            "`acknowledges_no_federal_amt` is false: federal alternative "
            "minimum tax may apply to this filer. AMT is computed on Form "
            "6251 and enters the return as Schedule 2 line 1, reaching Form "
            "1040 line 17 (`schedule2_tax`), line 18 (`tax_plus_schedule2`) "
            "and line 24 (total tax). tenforty's NATIVE compute path has no "
            "Form 6251 and no other federal AMT computation, so AMT would be "
            "silently treated as zero. AMT is an ADDITION to tax, so dropping "
            "it makes the computed tax LOWER than the true tax: the return "
            "would be UNDERSTATED — the penalty-and-interest direction, not "
            "the safe one. Note the direction is the OPPOSITE of the "
            "capital-loss-carryforward gate above, which drops a DEDUCTION "
            "and therefore OVERSTATES. THE ALTERNATIVE AVAILABLE TODAY: the "
            "vendor-workbook path does compute Form 6251, and the figures "
            "tenforty harvests from it (Schedule 2 line 3 via `Schedule2_Tax`, "
            "1040 line 18 via `Tax`, line 24 via `Tot_Tax`) carry that AMT "
            "inside them, so the workbook path can produce a return the native "
            "path cannot. Scoped, not absolute: that path's AMT figure is "
            "distrusted on MFJ/MFS returns (see `forms/f1040.py`), and those "
            "returns are refused at harvest today anyway."
        ),
        # applies_in_years=None (ALL years): IRC §55 imposes AMT on individuals
        # in every year tenforty supports. The exemption amounts and phaseout
        # thresholds move year to year, but there is no supported year in which
        # an AMT-bearing filer is computable on the native path, so there is no
        # window to bound.
        applies_in_years=None,
    ),
)

_ATTESTATIONS: tuple[Attestation, ...] = (
    _FEDERAL_ATTESTATIONS + _CA_ATTESTATIONS + _ALWAYS_TAIL
)


def validate_load_time(cfg) -> None:
    """Raise ValueError for any attestation field that's None when its
    applies_in_years range covers cfg.year."""
    for a in _ATTESTATIONS:
        if a.applies_in_years is not None and cfg.year not in a.applies_in_years:
            continue  # skip year-bounded attestations outside their range
        value = getattr(cfg, a.field, None)
        if value is None:
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


# ---------------------------------------------------------------------------
# The refusal ledger: field-less, scenario-triggered refusals.
#
# A sibling species to `Attestation` above, which is untouched. An
# `Attestation` is keyed on a `TaxReturnConfig` field that EVERY scenario must
# answer at load. A `ScopedRefusal` has no config field: it taxes no filer, and
# fires only when its own predicate finds offending items. Acknowledgments that
# lift a scoped refusal live on the activity or asset they concern, and the
# predicate reads them there.
#
# U-1 owns these mechanically: tests/test_scoped_refusals.py requires every
# registered name to appear in its FIRING_PROOFS map, naming the test that
# makes the refusal fire. An entry with no proof fails the suite.
# ---------------------------------------------------------------------------

# "parse": the predicate sees the RAW YAML mapping, before any model is built
#          (for shapes the models can no longer represent).
# "load":  the predicate sees the constructed Scenario. Re-checked at compute
#          entry, because a Scenario built in code never passed the loader.
# "compute": the predicate sees the (effective) Scenario at compute entry.
SCOPED_REFUSAL_STAGES: tuple[str, ...] = ("parse", "load", "compute")


@dataclass(frozen=True)
class ScopedRefusal:
    name: str
    stage: str
    # Returns the offending items; empty means the refusal does not fire.
    offenders: Callable[[object], Sequence]
    # Builds the refusal text from the offending items.
    message: Callable[[Sequence], str]
    exception: type[Exception] = ValueError
    # True for a question that only the WHOLE return can answer (a
    # taxpayer-wide aggregate). Such an entry is skipped when the ledger is
    # run over a single activity, where asking it would give a wrong answer.
    whole_return: bool = False

    def __post_init__(self) -> None:
        if self.stage not in SCOPED_REFUSAL_STAGES:
            raise ValueError(
                f"ScopedRefusal {self.name!r} has unknown stage "
                f"{self.stage!r}; expected one of {SCOPED_REFUSAL_STAGES}.")


# --- Depreciation: the asset model's shape rules ---------------------------

_DEPRECIATION_ACTIVITY_SECTIONS: tuple[tuple[str, str], ...] = (
    ("rental_properties", "rental property"),
    ("schedule_c_businesses", "Schedule C business"),
)


def depreciation_activities(scenario: Scenario):
    """Every activity that can carry depreciation, as
    ``(section, index, label, activity)``. ``label`` is how refusal text names
    the activity."""
    # The resolver runs the ledger over a single activity it was handed
    # directly; that view has no positions to report, so the label omits one.
    unindexed = getattr(scenario, "unindexed_activities", False)
    for i, rp in enumerate(scenario.rental_properties):
        position = "" if unindexed else f" #{i}"
        yield ("rental_properties", i,
               f"rental property{position} ({rp.address!r})", rp)
    for i, biz in enumerate(scenario.schedule_c_businesses):
        position = "" if unindexed else f" #{i}"
        yield ("schedule_c_businesses", i,
               f"Schedule C business{position} ({biz.description!r})", biz)


def _assets(scenario: Scenario):
    """Every nested asset as ``(asset label, asset)``."""
    for _section, _i, label, activity in depreciation_activities(scenario):
        for asset in activity.depreciable_assets:
            yield f"asset {asset.description!r} on {label}", asset


def _raw_top_level_asset_list(raw) -> list:
    return ["depreciable_assets"] if "depreciable_assets" in raw else []


def _raw_assets_with_convention(raw) -> list[str]:
    found = []
    for section, _label in _DEPRECIATION_ACTIVITY_SECTIONS:
        for i, activity in enumerate(raw.get(section) or []):
            if not isinstance(activity, dict):
                continue
            for j, asset in enumerate(activity.get("depreciable_assets") or []):
                if isinstance(asset, dict) and "convention" in asset:
                    found.append(f"{section}[{i}].depreciable_assets[{j}]")
    return found


def _unknown_class_assets(s: Scenario) -> list[str]:
    return [f"{label} has recovery_class {a.recovery_class!r}"
            for label, a in _assets(s)
            if a.recovery_class not in SUPPORTED_RECOVERY_CLASSES]


def _disposed_assets(s: Scenario) -> list[str]:
    return [label for label, a in _assets(s) if a.disposed is not None]


def _negative_asset_amounts(s: Scenario) -> list[str]:
    found = []
    for label, a in _assets(s):
        if a.basis < 0:
            found.append(f"{label} has a negative `basis`")
        if a.prior_depreciation is not None and a.prior_depreciation < 0:
            found.append(f"{label} has a negative `prior_depreciation`")
    for _section, _i, label, activity in depreciation_activities(s):
        ov = activity.depreciation_override
        if ov is None:
            continue
        if ov.amount < 0:
            found.append(
                f"{label} has a negative `depreciation_override.amount`")
        if ov.restates_engine_amount < 0:
            found.append(
                f"{label} has a negative "
                f"`depreciation_override.restates_engine_amount`")
    return found


def has_unattested_bonus_history(asset) -> bool:
    """Personal property whose bonus / section 179 history is not attested
    clean (the field is false or absent)."""
    return (asset.recovery_class in PERSONAL_PROPERTY_CLASSES
            and asset.no_bonus_or_section_179_history is not True)


def has_valid_override(activity) -> bool:
    """An acknowledged value-pinned override on the activity."""
    override = activity.depreciation_override
    return override is not None and override.acknowledgment is True


def _negative_stated_depreciation(s: Scenario) -> list[str]:
    return [label for _sec, _i, label, act in depreciation_activities(s)
            if act.depreciation < 0]


def _bonus_history_assets(s: Scenario) -> list[str]:
    # The refusal is per asset but the out is per activity: a valid override
    # pins the figure the return uses, which keeps the activity's other
    # assets in asset mode. The engine's figure for such an asset is kept
    # off every printed form by two other rules, not by this one: Form 4562
    # is emitted only in a year the return places property in service
    # (forms/f4562.is_required), and `merged_4562_with_override` refuses any
    # such year when an override exists anywhere on the return. (The recon
    # carries a note; see forms/depreciation/resolver.recon_keys.)
    return [
        f"asset {a.description!r} on {label} is {a.recovery_class} personal "
        f"property without `no_bonus_or_section_179_history: true`"
        for _sec, _i, label, act in depreciation_activities(s)
        if not has_valid_override(act)
        for a in act.depreciable_assets
        if has_unattested_bonus_history(a)]


def _real_property_with_history_field(s: Scenario) -> list[str]:
    return [
        f"{label} is {a.recovery_class} real property and must not carry "
        f"`no_bonus_or_section_179_history`"
        for label, a in _assets(s)
        if a.recovery_class in REAL_PROPERTY_CLASSES
        and a.no_bonus_or_section_179_history is not None]


def _assets_missing_prior_depreciation(s: Scenario) -> list[str]:
    year = s.config.year
    return [
        f"{label} was placed in service in "
        f"{a.date_placed_in_service.year}, before the {year} return year, "
        f"but states no `prior_depreciation`"
        for label, a in _assets(s)
        if a.date_placed_in_service.year < year
        and a.prior_depreciation is None]


def _dual_source_activities(s: Scenario) -> list[str]:
    return [label for _sec, _i, label, act in depreciation_activities(s)
            if act.depreciable_assets and act.depreciation]


def _unacknowledged_stated_figures(s: Scenario) -> list[str]:
    return [label for _sec, _i, label, act in depreciation_activities(s)
            if act.depreciation and not act.depreciable_assets
            and act.acknowledges_depreciation_stated_outside_macrs is not True]


def _overrides_outside_asset_mode(s: Scenario) -> list[str]:
    return [label for _sec, _i, label, act in depreciation_activities(s)
            if act.depreciation_override is not None
            and not act.depreciable_assets]


def _unacknowledged_overrides(s: Scenario) -> list[str]:
    return [label for _sec, _i, label, act in depreciation_activities(s)
            if act.depreciation_override is not None
            and act.depreciation_override.acknowledgment is not True]


def _asset_mode_on_unprinted_rentals(s: Scenario) -> list[str]:
    return [f"rental property #{i} ({rp.address!r})"
            for i, rp in enumerate(s.rental_properties)
            if i >= 1 and rp.depreciable_assets]


# The four predicates below need the engine, which lives in
# forms/depreciation/ and itself imports this module -- hence the imports
# inside the functions. Each skips an asset the engine has no figure for
# (unknown class, disposed): those are other entries' refusals.

def _assets_placed_after_return_year(s: Scenario) -> list[str]:
    year = s.config.year
    return [
        f"{label} was placed in service in "
        f"{a.date_placed_in_service.year}, after the {year} return year"
        for label, a in _assets(s) if a.date_placed_in_service.year > year]


def _prior_depreciation_mismatches(s: Scenario) -> list[str]:
    from tenforty.forms.depreciation import resolver
    year = s.config.year
    found = []
    for label, a in _assets(s):
        if not resolver.is_computable(a):
            continue
        mismatch = resolver.prior_depreciation_mismatch(a, year)
        if mismatch is not None:
            stated, reconstructed = mismatch
            found.append(
                f"{label} states `prior_depreciation` of {stated:,} but the "
                f"MACRS tables reconstruct {reconstructed:,} for the years "
                f"before {year}")
    return found


def _computable_overridden_activities(s: Scenario):
    from tenforty.forms.depreciation import resolver
    for _sec, _i, label, act in depreciation_activities(s):
        if act.depreciation_override is None or not act.depreciable_assets:
            continue
        if all(resolver.is_computable(a) for a in act.depreciable_assets):
            yield label, act


def _stale_overrides(s: Scenario) -> list[str]:
    from tenforty.forms.depreciation import resolver
    found = []
    for label, act in _computable_overridden_activities(s):
        engine = resolver.engine_amount(act, s.config.year)
        restated = irs_round(act.depreciation_override.restates_engine_amount)
        if restated != engine:
            found.append(
                f"{label} carries a `depreciation_override` restating the "
                f"engine's figure as {restated:,}, but the engine now "
                f"computes {engine:,}")
    return found


def _overrides_with_current_year_placement(s: Scenario) -> list[str]:
    from tenforty.forms.depreciation import resolver
    year = s.config.year
    found = []
    for label, act in _computable_overridden_activities(s):
        placed = resolver.placed_this_year(act, year)
        if placed:
            names = ", ".join(repr(a.description) for a in placed)
            found.append(
                f"{label} carries a `depreciation_override` and placed "
                f"{names} in service in {year}")
    return found


def _merged_4562_with_override(s: Scenario) -> list[str]:
    """Activities carrying an override, when the return also places
    property in service this year (on any activity). A bonus-history lift
    needs an override, so this covers that case too."""
    year = s.config.year
    activities = list(depreciation_activities(s))
    placed = any(
        a.date_placed_in_service.year == year
        for _sec, _i, _label, act in activities
        for a in act.depreciable_assets)
    if not placed:
        return []
    return [label for _sec, _i, label, act in activities
            if act.depreciation_override is not None]


def _mid_quarter_convention(s: Scenario) -> list[str]:
    from tenforty.forms.depreciation import resolver
    if not resolver.mid_quarter_applies(s):
        return []
    last_quarter, year_total = resolver.mid_quarter_bases(s)
    return [f"{irs_round(last_quarter):,} of {irs_round(year_total):,}"]


def _unverifiable_mid_quarter_test(s: Scenario) -> list[str]:
    from tenforty.forms.depreciation import resolver
    if s.acknowledges_no_personal_property_behind_stated_depreciation is True:
        return []
    if not resolver.personal_property_placed_this_year(s):
        return []
    return resolver.stated_mode_activity_labels(s)


def _join(items: Sequence) -> str:
    return "; ".join(str(i) for i in items)


_DEPRECIATION_SHAPE_REFUSALS: tuple[ScopedRefusal, ...] = (
    ScopedRefusal(
        name="top_level_asset_list",
        stage="parse",
        offenders=_raw_top_level_asset_list,
        message=lambda o: (
            "A top-level `depreciable_assets:` list is no longer accepted: "
            "nothing tied those assets to the activity whose depreciation "
            "they are. Move each asset under its activity -- "
            "`rental_properties[n].depreciable_assets` or "
            "`schedule_c_businesses[n].depreciable_assets` -- and drop any "
            "`convention:` key (it is computed)."),
    ),
    ScopedRefusal(
        name="stated_convention",
        stage="parse",
        offenders=_raw_assets_with_convention,
        message=lambda o: (
            f"{_join(o)} carries `convention:` -- convention is computed, "
            "not stated. Real property is mid-month by statute; personal "
            "property is half-year unless the mid-quarter test applies. "
            "Remove the key."),
    ),
    # Class first: the property-type predicates below classify by it.
    ScopedRefusal(
        name="unknown_recovery_class",
        stage="load",
        offenders=_unknown_class_assets,
        message=lambda o: (
            f"{_join(o)}; tenforty has MACRS tables only for "
            f"{list(SUPPORTED_RECOVERY_CLASSES)}. An asset in any other "
            "class cannot be depreciated here and is never approximated."),
        exception=NotImplementedError,
    ),
    ScopedRefusal(
        name="negative_asset_amount",
        stage="load",
        offenders=_negative_asset_amounts,
        message=lambda o: (
            f"{_join(o)}. Asset amounts are carried through verbatim (never "
            "clamped), so a negative value cannot be silently corrected to "
            "0 -- it is refused instead."),
    ),
    ScopedRefusal(
        name="negative_stated_depreciation",
        stage="load",
        offenders=_negative_stated_depreciation,
        message=lambda o: (
            f"{_join(o)} states a negative `depreciation`. The stated amount "
            "is carried onto the return verbatim (never clamped), so a "
            "negative value cannot be silently corrected to 0 -- it is "
            "refused instead."),
    ),
    ScopedRefusal(
        name="asset_disposed",
        stage="load",
        offenders=_disposed_assets,
        message=lambda o: (
            f"{_join(o)} is marked `disposed`. Dispositions and retirements "
            "-- including partial dispositions, where a component is "
            "superseded by a later replacement -- are not modeled: the "
            "disposal-year proration, gain or loss and any recapture are "
            "all out of scope. This is a named follow-on; until it lands "
            "the return cannot be produced with this asset in the list."),
        exception=NotImplementedError,
    ),
    ScopedRefusal(
        name="history_field_on_real_property",
        stage="load",
        offenders=_real_property_with_history_field,
        message=lambda o: (
            f"{_join(o)}. The field is an attestation about personal "
            "property only; remove it from real property."),
    ),
    ScopedRefusal(
        name="bonus_or_section_179_history",
        stage="load",
        offenders=_bonus_history_assets,
        message=lambda o: (
            f"{_join(o)}. An asset that took a special (bonus) depreciation "
            "allowance or a section 179 deduction computes wrong under the "
            "plain MACRS tables, and tenforty models neither. Set the field "
            "true only if the asset has no such history. Otherwise either "
            "add a `depreciation_override` to the activity (the return then "
            "uses the override amount; the other assets stay tracked), or "
            "remove the activity's asset list and state the activity's "
            "figure instead: its `depreciation` amount with "
            "`acknowledges_depreciation_stated_outside_macrs: true`."),
        exception=NotImplementedError,
    ),
    ScopedRefusal(
        name="missing_prior_depreciation",
        stage="load",
        offenders=_assets_missing_prior_depreciation,
        message=lambda o: (
            f"{_join(o)}. An asset already in service needs the "
            "depreciation taken in earlier years (state 0 if none was)."),
    ),
    ScopedRefusal(
        name="dual_source_depreciation",
        stage="load",
        offenders=_dual_source_activities,
        message=lambda o: (
            f"{_join(o)} carries both `depreciable_assets` and a stated "
            "`depreciation` amount. One activity has one depreciation "
            "source: keep the asset list (and set `depreciation` to 0) or "
            "keep the stated amount (and remove the list). They are never "
            "added together."),
    ),
    ScopedRefusal(
        name="unacknowledged_stated_depreciation",
        stage="load",
        offenders=_unacknowledged_stated_figures,
        message=lambda o: (
            f"{_join(o)} states `depreciation` without an asset list. That "
            "figure comes from outside tenforty's MACRS model and is "
            "carried onto the return unverified. Set "
            "`acknowledges_depreciation_stated_outside_macrs: true` on "
            "that activity to accept it, or replace the amount with "
            "`depreciable_assets`."),
    ),
    ScopedRefusal(
        name="override_outside_asset_mode",
        stage="load",
        offenders=_overrides_outside_asset_mode,
        message=lambda o: (
            f"{_join(o)} carries a `depreciation_override` but no "
            "`depreciable_assets`. The override pins the figure for an "
            "asset-mode activity against the engine's own computation; "
            "with no assets there is nothing to override. State the "
            "activity's `depreciation` amount instead."),
    ),
    ScopedRefusal(
        name="unacknowledged_depreciation_override",
        stage="load",
        offenders=_unacknowledged_overrides,
        message=lambda o: (
            f"{_join(o)} carries a `depreciation_override` without "
            "`acknowledgment: true`. The override replaces the engine's "
            "computed depreciation on the return; it must be acknowledged "
            "explicitly."),
    ),
    ScopedRefusal(
        name="asset_mode_on_unprinted_rental",
        stage="load",
        offenders=_asset_mode_on_unprinted_rentals,
        message=lambda o: (
            f"{_join(o)} carries `depreciable_assets`, but Schedule E prints "
            "only the first rental property (property A). Asset-mode "
            "depreciation on a property the schedule does not print would "
            "compute a deduction no form shows. This refusal lifts when "
            "Schedule E prints beyond property A."),
        exception=NotImplementedError,
    ),
)

# --- Depreciation: what the resolver refuses -------------------------------

_DEPRECIATION_RESOLVER_REFUSALS: tuple[ScopedRefusal, ...] = (
    ScopedRefusal(
        name="asset_placed_after_return_year",
        stage="load",
        offenders=_assets_placed_after_return_year,
        message=lambda o: (
            f"{_join(o)}. An asset not yet in service has no depreciation "
            "for this return; remove it from this year's scenario."),
    ),
    ScopedRefusal(
        name="prior_depreciation_mismatch",
        stage="load",
        offenders=_prior_depreciation_mismatches,
        message=lambda o: (
            f"{_join(o)}. A history that does not match the tables usually "
            "means an earlier year used a different class, method or "
            "convention. Correcting that is a change in accounting method "
            "(Form 3115, with a section 481(a) adjustment) -- CPA "
            "territory, which tenforty does not prepare. To proceed with "
            "the history as it stands, set "
            "`acknowledges_prior_depreciation_as_stated: true` on the "
            "asset; this year's deduction is still computed from the "
            "tables."),
    ),
    ScopedRefusal(
        name="stale_depreciation_override",
        stage="load",
        offenders=_stale_overrides,
        message=lambda o: (
            f"{_join(o)}. The override was acknowledged against a figure "
            "the engine no longer produces (the books changed). Review the "
            "override and re-acknowledge it by setting "
            "`restates_engine_amount` to the engine's current figure."),
    ),
    ScopedRefusal(
        name="override_with_current_year_placement",
        stage="load",
        offenders=_overrides_with_current_year_placement,
        message=lambda o: (
            f"{_join(o)}. Property placed in service this year requires "
            "Form 4562, which would print the engine's figures while the "
            "return claims the override amount -- an internally "
            "inconsistent filing. Overriding an activity in a year it "
            "places property in service is a named follow-on; until then "
            "remove the override, or state the activity's figure instead "
            "of listing assets."),
        exception=NotImplementedError,
    ),
)

# --- Depreciation: the taxpayer-wide convention test -----------------------

_DEPRECIATION_CONVENTION_REFUSALS: tuple[ScopedRefusal, ...] = (
    ScopedRefusal(
        name="merged_4562_with_override",
        stage="load",
        whole_return=True,
        offenders=_merged_4562_with_override,
        message=lambda o: (
            "Form 4562 is required this year (property was placed in "
            f"service), and {_join(o)} carries a `depreciation_override`. "
            "tenforty still prints one merged form for the whole return, "
            "listing every asset with the engine's figures, so its total "
            "would disagree with the override amount that activity claims. "
            "The real resolution is per-activity forms (one Form 4562 per "
            "activity that needs one), which is a later change. Until then "
            "this combination cannot be produced."),
        exception=NotImplementedError,
    ),
    ScopedRefusal(
        name="mid_quarter_convention",
        stage="load",
        whole_return=True,
        offenders=_mid_quarter_convention,
        message=lambda o: (
            f"The mid-quarter convention applies to this return: personal "
            f"property placed in service in the last three months of the "
            f"year has aggregate basis {_join(o)} placed in service during "
            "the year, which is more than 40% (26 U.S.C. 168(d)(3)). "
            "tenforty has no mid-quarter tables, and the half-year tables "
            "would compute every asset placed this year wrong. The totals "
            "run across every activity on the return; real property is in "
            "neither. This return cannot be produced with these assets "
            "listed."),
        exception=NotImplementedError,
    ),
    ScopedRefusal(
        name="unverifiable_mid_quarter_test",
        stage="load",
        whole_return=True,
        offenders=_unverifiable_mid_quarter_test,
        message=lambda o: (
            "The mid-quarter 40% test cannot be verified: an asset list "
            "places personal property in service this year, but "
            f"{_join(o)} states its depreciation as a single figure, and "
            "that figure does not show what it placed in service or when. "
            "The test's totals cover every activity on the return. If no "
            "personal property was placed in service this year behind any "
            "stated depreciation figure, set the top-level scenario key "
            "`acknowledges_no_personal_property_behind_stated_depreciation: "
            "true`. Otherwise the convention cannot be determined here."),
        exception=NotImplementedError,
    ),
)

_SCOPED_REFUSALS: tuple[ScopedRefusal, ...] = (
    _DEPRECIATION_SHAPE_REFUSALS + _DEPRECIATION_RESOLVER_REFUSALS
    + _DEPRECIATION_CONVENTION_REFUSALS
)


def enforce_scoped_refusals(
        subject, stage: str, *, single_activity: bool = False) -> None:
    """Raise the first registered refusal of ``stage`` whose predicate finds
    offending items in ``subject`` (the raw YAML mapping for "parse", the
    Scenario otherwise). Tuple position is error precedence.

    ``single_activity`` is for the depreciation resolver, which runs the
    ledger over the one activity it was handed: `whole_return` entries are
    skipped there."""
    if stage not in SCOPED_REFUSAL_STAGES:
        raise ValueError(
            f"Unknown scoped-refusal stage {stage!r}; expected one of "
            f"{SCOPED_REFUSAL_STAGES}.")
    for refusal in _SCOPED_REFUSALS:
        if refusal.stage != stage:
            continue
        if single_activity and refusal.whole_return:
            continue
        offenders = refusal.offenders(subject)
        if offenders:
            raise refusal.exception(refusal.message(offenders))


def raise_scoped_refusal(name: str, offenders: Sequence) -> None:
    """Raise the registered refusal ``name`` for ``offenders`` directly.

    For code that must stay fail-closed when reached without the ledger
    having run (a direct call that bypassed the loader and the orchestrator):
    it raises the ledger's own exception and text, so the registry remains
    the single owner of the refusal."""
    for refusal in _SCOPED_REFUSALS:
        if refusal.name == name:
            raise refusal.exception(refusal.message(offenders))
    raise KeyError(f"No scoped refusal named {name!r} is registered.")
