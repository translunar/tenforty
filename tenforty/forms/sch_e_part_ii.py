"""Schedule E Part II — Pass-through income from partnership / S-corp K-1s.

Handles up to 4 K-1 rows (A/B/C/D) across S-corp and partnership entity
types. Fans out separately-stated items to Sch B, Sch D, Form 8995 (QBI),
and Form 8582 (passive activity loss).

**Scope:** Partnership (1065) and S-corp (1120-S) K-1s only. 1041
(estate/trust) K-1s belong on Schedule E Part III, which is NOT
implemented in tenforty v1 — encountering any K-1 with
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
(out of scope for tenforty v1). We log a WARN in that case; the compute-time
behavior is to ignore, not raise.
"""

import logging

from tenforty.attestations import enforce_compute_time
from tenforty.models import (
    EntityType, K1FanoutActivity, K1FanoutData, PayerAmount,
    Scenario, ScheduleK1,
)
from tenforty.rounding import irs_round


log = logging.getLogger(__name__)

_ROW_LETTERS = ("a", "b", "c", "d")


def _k1_row_total(k1: ScheduleK1) -> float:
    """Sum of the Sch E Part II row components per K-1, IRS-rounded
    per component (rentals are combined before rounding, matching the
    form's single 'Rental real estate' line)."""
    return (
        irs_round(k1.ordinary_business_income)
        + irs_round(k1.net_rental_real_estate + k1.other_net_rental)
        + irs_round(k1.royalties)
        + irs_round(k1.other_income)
    )


def compute(
    scenario: Scenario, upstream: dict,
) -> tuple[dict, K1FanoutData]:
    _enforce_scope_gates(scenario)

    result: dict = {
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }

    interest_additions: list[PayerAmount] = []
    dividend_additions: list[PayerAmount] = []
    short_term_additions: list[float] = []
    long_term_additions: list[float] = []
    passive_activities: list[K1FanoutActivity] = []
    qbi_aggregate = 0.0
    qualified_dividends_aggregate = 0.0

    line_29a_passive_income = 0
    line_29a_passive_loss = 0
    line_29a_nonpassive_income = 0
    line_29a_nonpassive_loss = 0

    for i, k1 in enumerate(scenario.schedule_k1s):
        letter = _ROW_LETTERS[i]
        row = _row_fields(k1, letter)
        result.update(row)

        total_row = _k1_row_total(k1)

        if k1.material_participation:
            if total_row >= 0:
                line_29a_nonpassive_income += total_row
            else:
                line_29a_nonpassive_loss += -total_row
            if k1.prior_year_passive_loss_carryforward:
                log.warning(
                    "K-1 %r has material_participation=True but also a "
                    "prior_year_passive_loss_carryforward of %s; "
                    "dropping (cannot mix active and suspended-passive "
                    "in the same year). Track the carryforward externally "
                    "until disposition.",
                    k1.entity_name, k1.prior_year_passive_loss_carryforward,
                )
        else:
            if total_row >= 0:
                line_29a_passive_income += total_row
            else:
                line_29a_passive_loss += -total_row
            passive_activities.append(K1FanoutActivity(
                entity_name=k1.entity_name,
                entity_ein=k1.entity_ein,
                entity_type=k1.entity_type,
                income=float(max(0, total_row)),
                loss=float(max(0, -total_row)),
                prior_carryforward=float(
                    irs_round(k1.prior_year_passive_loss_carryforward),
                ),
            ))

        if k1.interest_income:
            interest_additions.append(
                PayerAmount(payer=k1.entity_name, amount=float(k1.interest_income)),
            )
        if k1.ordinary_dividends:
            dividend_additions.append(
                PayerAmount(
                    payer=k1.entity_name, amount=float(k1.ordinary_dividends),
                ),
            )
        qualified_dividends_aggregate += k1.qualified_dividends
        short_term_additions.append(float(k1.net_short_term_capital_gain))
        long_term_additions.append(float(k1.net_long_term_capital_gain))
        qbi_aggregate += k1.qbi_amount

    result["sch_e_line_29a_total_passive_income"] = line_29a_passive_income
    result["sch_e_line_29b_total_passive_loss"] = line_29a_passive_loss
    result["sch_e_line_29a_total_nonpassive_income"] = line_29a_nonpassive_income
    result["sch_e_line_29b_total_nonpassive_loss"] = line_29a_nonpassive_loss
    # Line 37 (estate/trust) is always 0: estate_trust K-1s are rejected by
    # _enforce_scope_gates, so nothing reaches Part III.
    result["sch_e_line_32_total_partnership_scorp"] = (
        line_29a_passive_income + line_29a_nonpassive_income
        - line_29a_passive_loss - line_29a_nonpassive_loss
    )
    result["sch_e_line_37_total_estate_trust"] = 0
    result["sch_e_line_41_total_pte"] = result["sch_e_line_32_total_partnership_scorp"]

    fanout = K1FanoutData(
        sch_b_interest_additions=tuple(interest_additions),
        sch_b_dividend_additions=tuple(dividend_additions),
        sch_d_short_term_additions=tuple(short_term_additions),
        sch_d_long_term_additions=tuple(long_term_additions),
        qbi_aggregate=qbi_aggregate,
        qualified_dividends_aggregate=qualified_dividends_aggregate,
        passive_activities=tuple(passive_activities),
    )
    return result, fanout


def _enforce_scope_gates(scenario: Scenario) -> None:
    """Compute-time scope-out enforcement.

    Two parts:
    1. estate_trust K-1 — unconditional NotImplementedError regardless of
       attestation (Schedule E Part III is not implemented; the attestation
       is user-awareness only).
    2. All other gates driven by _ATTESTATIONS.enforce_compute_time.
    """
    for k1 in scenario.schedule_k1s:
        if k1.entity_type == EntityType.ESTATE_TRUST:
            raise NotImplementedError(
                f"K-1 {k1.entity_name!r} has entity_type='estate_trust'. "
                "1041 K-1 income belongs on Sch E Part III (lines 33-37), "
                "which is NOT implemented in tenforty v1. Scope out: remove "
                "the K-1 or wait for Part III support. "
                "(`acknowledges_no_estate_trust_k1` is a load-time "
                "user-awareness gate only; it does not enable compute.)"
            )
    enforce_compute_time(scenario)


def _row_fields(k1: ScheduleK1, letter: str) -> dict:
    total = _k1_row_total(k1)
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
        f"sch_e_part_ii_row_{letter}_entity_type_{k1.entity_type.value}": "X",
        f"sch_e_part_ii_row_{letter}_passive_income": passive_income,
        f"sch_e_part_ii_row_{letter}_passive_loss": passive_loss,
        f"sch_e_part_ii_row_{letter}_nonpassive_income": nonpassive_income,
        f"sch_e_part_ii_row_{letter}_nonpassive_loss": nonpassive_loss,
    }
