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
from typing import Callable

from tenforty.models import EntityType, Scenario


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


# CA-specific scope-out attestations (12 entries; year-aware).
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
