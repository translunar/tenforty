"""Schedule E Part II — Pass-through income from partnership / S-corp K-1s.

Handles up to 4 K-1 rows (A/B/C/D) across S-corp and partnership entity
types. Fans out separately-stated items to Sch B, Sch D, Form 8995 (QBI),
and Form 8582 (passive activity loss).

**Scope:** Partnership (1065) and S-corp (1120-S) K-1s only. 1041
(estate/trust) K-1s belong on Schedule E Part III, which is NOT
implemented in Plan D — encountering any K-1 with
``entity_type == "estate_trust"`` raises NotImplementedError regardless
of the ``acknowledges_no_estate_trust_k1`` attestation (the attestation
is a user-awareness checkbox, not a "proceed naively" flag).

Scope-outs are gated as active attestations on TaxReturnConfig. Any
triggered gate with attestation False raises NotImplementedError here
— never silent skip.

Note on prior-year passive-loss carryforward: when
``material_participation=True`` (nonpassive column), any nonzero
``prior_year_passive_loss_carryforward`` on that K-1 is dropped — an
activity cannot shift between passive and nonpassive in a single year,
and any prior suspended loss should remain suspended until disposition
(out of scope for Plan D). We log a WARN in that case; the compute-time
behavior is to ignore, not raise.
"""

import logging

from tenforty.models import Scenario, ScheduleK1
from tenforty.rounding import irs_round


log = logging.getLogger(__name__)

_ROW_LETTERS = ("a", "b", "c", "d")


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    _enforce_scope_gates(scenario)

    result: dict = {
        "taxpayer_name": _format_taxpayer_name(scenario),
        "taxpayer_ssn": scenario.config.ssn,
    }

    fanout = {
        "interest_from_k1s": [],
        "ordinary_dividends_from_k1s": [],
        "qualified_dividends_total": 0.0,
        "short_term_cap_gain_from_k1s": 0.0,
        "long_term_cap_gain_from_k1s": 0.0,
        "qbi_total": 0.0,
        "passive_activities": [],
    }

    line_29a_passive_income = 0
    line_29a_passive_loss = 0
    line_29a_nonpassive_income = 0
    line_29a_nonpassive_loss = 0

    for i, k1 in enumerate(scenario.schedule_k1s):
        letter = _ROW_LETTERS[i]
        row = _row_fields(k1, letter)
        result.update(row)

        ord_biz = irs_round(k1.ordinary_business_income)
        rental = irs_round(k1.net_rental_real_estate + k1.other_net_rental)
        roy = irs_round(k1.royalties)
        other = irs_round(k1.other_income)
        total_row = ord_biz + rental + roy + other

        if k1.material_participation:
            if total_row >= 0:
                line_29a_nonpassive_income += total_row
            else:
                line_29a_nonpassive_loss += -total_row
            if k1.prior_year_passive_loss_carryforward:
                log.warning(
                    "K-1 %r has material_participation=True but also a "
                    "prior_year_passive_loss_carryforward of %s; "
                    "dropping the carryforward (cannot mix active and "
                    "suspended-passive in the same year). Track the "
                    "carryforward externally until disposition.",
                    k1.entity_name, k1.prior_year_passive_loss_carryforward,
                )
        else:
            if total_row >= 0:
                line_29a_passive_income += total_row
            else:
                line_29a_passive_loss += -total_row
            fanout["passive_activities"].append({
                "entity_name": k1.entity_name,
                "income": max(0, total_row),
                "loss": max(0, -total_row),
                "prior_carryforward": irs_round(
                    k1.prior_year_passive_loss_carryforward,
                ),
            })

        if k1.interest_income:
            fanout["interest_from_k1s"].append(
                {"payer": k1.entity_name, "amount": float(k1.interest_income)},
            )
        if k1.ordinary_dividends:
            fanout["ordinary_dividends_from_k1s"].append(
                {"payer": k1.entity_name,
                 "amount": float(k1.ordinary_dividends)},
            )
        fanout["qualified_dividends_total"] += k1.qualified_dividends
        fanout["short_term_cap_gain_from_k1s"] += k1.net_short_term_capital_gain
        fanout["long_term_cap_gain_from_k1s"] += k1.net_long_term_capital_gain
        fanout["qbi_total"] += k1.qbi_amount

    result["sch_e_line_29a_total_passive_income"] = line_29a_passive_income
    result["sch_e_line_29b_total_passive_loss"] = line_29a_passive_loss
    result["sch_e_line_29a_total_nonpassive_income"] = line_29a_nonpassive_income
    result["sch_e_line_29b_total_nonpassive_loss"] = line_29a_nonpassive_loss
    # Line 32 = partnership + s-corp subtotal. Line 37 (estate/trust) is
    # unconditionally 0 in Plan D — estate/trust K-1s are rejected at the
    # scope gate above, so nothing ever reaches Part III.
    result["sch_e_line_32_total_partnership_scorp"] = (
        line_29a_passive_income + line_29a_nonpassive_income
        - line_29a_passive_loss - line_29a_nonpassive_loss
    )
    result["sch_e_line_37_total_estate_trust"] = 0
    result["sch_e_line_41_total_pte"] = result["sch_e_line_32_total_partnership_scorp"]

    result["_k1_fanout"] = fanout
    return result


def _enforce_scope_gates(scenario: Scenario) -> None:
    k1s = scenario.schedule_k1s
    if not k1s:
        return
    cfg = scenario.config
    # Estate/trust K-1 — unconditional NotImplementedError (attestation
    # is for user awareness, not "proceed naively").
    for k1 in k1s:
        if k1.entity_type == "estate_trust":
            raise NotImplementedError(
                f"K-1 {k1.entity_name!r} has entity_type='estate_trust'. "
                "1041 K-1 income belongs on Sch E Part III (lines 33-37), "
                "which is NOT implemented in Plan D. Scope out: remove "
                "the K-1 or wait for Part III support. "
                "(`acknowledges_no_estate_trust_k1` is a load-time "
                "user-awareness gate only; it does not enable compute.)"
            )
    if len(k1s) > 4 and not cfg.acknowledges_no_more_than_four_k1s:
        raise NotImplementedError(
            f"Scenario has {len(k1s)} K-1s; Schedule E Part II "
            "continuation (beyond 4 rows) is not implemented in tenforty "
            "v1. Set `acknowledges_no_more_than_four_k1s: true` to accept "
            "that rows beyond D will be dropped, or reduce to 4 K-1s."
        )
    if not cfg.acknowledges_unlimited_at_risk:
        raise NotImplementedError(
            "K-1 present but `acknowledges_unlimited_at_risk` is false. "
            "Form 6198 (at-risk limitation) is not implemented in "
            "tenforty v1; set the attestation to true to affirm all K-1 "
            "activities have unlimited at-risk amounts."
        )
    if not cfg.basis_tracked_externally:
        raise NotImplementedError(
            "K-1 present but `basis_tracked_externally` is false. "
            "tenforty v1 does not compute stock/debt basis worksheets; "
            "set the attestation to true to affirm basis is tracked "
            "outside this system."
        )
    for k1 in k1s:
        if k1.section_1231_gain and not cfg.acknowledges_no_section_1231_gain:
            raise NotImplementedError(
                f"K-1 {k1.entity_name!r} reports section 1231 gain "
                f"{k1.section_1231_gain}. Form 4797 is not implemented "
                "in tenforty v1; set `acknowledges_no_section_1231_gain: "
                "true` only if zero gain is correct."
            )
        if k1.section_179_deduction and not cfg.acknowledges_no_section_179:
            raise NotImplementedError(
                f"K-1 {k1.entity_name!r} reports section 179 deduction "
                f"{k1.section_179_deduction}. Section 179 at the 1040 "
                "level is not implemented in tenforty v1; set "
                "`acknowledges_no_section_179: true` if zero is correct."
            )
        if (k1.entity_type == "partnership"
                and k1.partnership_self_employment_earnings
                and not cfg.acknowledges_no_partnership_se_earnings):
            raise NotImplementedError(
                f"Partnership K-1 {k1.entity_name!r} reports SE "
                f"earnings {k1.partnership_self_employment_earnings}. "
                "Schedule SE is not implemented in tenforty v1; set "
                "`acknowledges_no_partnership_se_earnings: true` only if "
                "zero is correct."
            )
    if not cfg.acknowledges_no_k1_credits:
        raise NotImplementedError(
            "K-1 present but `acknowledges_no_k1_credits` is false. K-1 "
            "box 13 / 15 credits are not implemented in tenforty v1; set "
            "the attestation to true to affirm no K-1 credits apply."
        )


def _row_fields(k1: ScheduleK1, letter: str) -> dict:
    ord_biz = irs_round(k1.ordinary_business_income)
    rental = irs_round(k1.net_rental_real_estate + k1.other_net_rental)
    roy = irs_round(k1.royalties)
    other = irs_round(k1.other_income)
    total = ord_biz + rental + roy + other
    passive_income = passive_loss = nonpassive_income = nonpassive_loss = 0
    if k1.material_participation:
        if total >= 0:
            nonpassive_income = total
        else:
            nonpassive_loss = -total
    else:
        if total >= 0:
            passive_income = total
        else:
            passive_loss = -total
    return {
        f"sch_e_part_ii_row_{letter}_name": k1.entity_name,
        f"sch_e_part_ii_row_{letter}_ein": k1.entity_ein,
        f"sch_e_part_ii_row_{letter}_entity_type_{k1.entity_type}": "X",
        f"sch_e_part_ii_row_{letter}_passive_income": passive_income,
        f"sch_e_part_ii_row_{letter}_passive_loss": passive_loss,
        f"sch_e_part_ii_row_{letter}_nonpassive_income": nonpassive_income,
        f"sch_e_part_ii_row_{letter}_nonpassive_loss": nonpassive_loss,
    }


def _format_taxpayer_name(scenario: Scenario) -> str:
    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return f"{first} {last}".strip()
