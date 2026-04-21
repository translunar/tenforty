"""Form 8582 — Passive Activity Loss Limitations.

Computes the current-year allowed passive loss and the per-activity
suspended amount that carries forward to next year's scenario.

v1 scope:
- Special allowance per IRC §469(i)(5) — varies by filing status:
    * single/mfj/hoh/qss: $25,000 base, phaseout $100k-$150k MAGI.
    * mfs, lived APART from spouse ALL year: $12,500 base,
      phaseout $50k-$75k MAGI.
    * mfs, lived WITH spouse any time: $0.
- Sch E Part I rentals are treated as actively participated rental
  real estate (v1 has no opt-out flag).
- K-1 passive activities with net_rental_real_estate nonzero are also
  treated as rental real estate for the §469(i) allowance (active
  participation is a lower standard than material participation; v1
  assumes active participation applies to all passive K-1 rental RE).
- K-1 passive activities (material_participation=False) contribute
  passive income and loss, plus prior-year carryforward.
- No real-estate-professional rules (all rentals are passive regardless
  of hours — documented scope; IRC §469(c)(7) not implemented).

Consumes upstream["sch_e"] for Sch E Part I results — does NOT
re-invoke forms.sch_e.compute, avoiding circular layering.
"""

from tenforty.models import FilingStatus, K1FanoutData, Scenario
from tenforty.rounding import irs_round


def special_allowance(
    magi: float,
    filing_status: FilingStatus,
    mfs_lived_with_spouse_any_time: bool,
) -> float:
    """Per IRC §469(i)(5). Returns unrounded allowance float.

    filing_status table:
    - single / mfj / hoh / qss: base=$25,000, phaseout $100k-$150k MAGI.
    - mfs, lived apart all year:  base=$12,500, phaseout $50k-$75k MAGI.
    - mfs, lived with spouse any time: $0 (no allowance).
    """
    if filing_status == FilingStatus.MARRIED_SEPARATELY:
        if mfs_lived_with_spouse_any_time:
            return 0.0
        base, phaseout_start, phaseout_end = 12_500.0, 50_000.0, 75_000.0
    else:
        base, phaseout_start, phaseout_end = 25_000.0, 100_000.0, 150_000.0
    if magi >= phaseout_end:
        return 0.0
    if magi <= phaseout_start:
        return base
    return max(0.0, base - 0.5 * (magi - phaseout_start))


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()
    agi = float(upstream.get("f1040", {}).get("magi", 0))
    sch_e_upstream = upstream.get("sch_e", {})

    passive_activities: list[dict] = [
        {
            "entity_name": a.entity_name,
            "income": a.income,
            "loss": a.loss,
            "prior_carryforward": a.prior_carryforward,
        }
        for a in fanout.passive_activities
    ]

    # Sch E Part I rental property contributes to passive activities.
    if scenario.rental_properties:
        rental_net = int(sch_e_upstream.get("sch_e_property_a_income_loss", 0))
        passive_activities.append({
            "entity_name": scenario.rental_properties[0].address,
            "income": max(0, rental_net),
            "loss": max(0, -rental_net),
            "prior_carryforward": 0,
        })

    passive_income_total = sum(a["income"] for a in passive_activities)
    passive_loss_total = sum(a["loss"] for a in passive_activities)
    prior_carryforward_total = sum(
        a["prior_carryforward"] for a in passive_activities
    )

    # Form 8582 MAGI (line 6) is AGI modified to exclude passive income/loss
    # per the IRS line-6 instructions. The workbook formula is:
    #   MAGI = Adj_Gross_Inc - PassiveIncomeLoss
    # where PassiveIncomeLoss = line 3 (the net of all passive activities).
    # Net passive activity = income - loss - prior_carryforward (negative
    # when losses dominate). Subtracting a negative adds it back to AGI.
    net_passive = passive_income_total - passive_loss_total - prior_carryforward_total
    magi = max(0.0, agi - net_passive)

    # Active-participation rental RE qualifies for the §469(i)(5) special
    # allowance.  v1 treats all Sch E Part I rentals as actively participated.
    # K-1 passive activities sourced from net_rental_real_estate are also
    # treated as actively participated rental RE (active participation is a
    # lower bar than material participation).
    has_sch_e_rental = bool(scenario.rental_properties)
    has_k1_rental_re = any(
        k1.net_rental_real_estate for k1 in scenario.schedule_k1s
        if not k1.material_participation
    )
    has_active_participation_rental = has_sch_e_rental or has_k1_rental_re

    if has_active_participation_rental:
        mfs_flag: bool = (
            bool(scenario.config.mfs_lived_with_spouse_any_time)
            if scenario.config.mfs_lived_with_spouse_any_time is not None
            else False
        )
        allowance_raw = special_allowance(
            magi=magi,
            filing_status=scenario.config.filing_status,
            mfs_lived_with_spouse_any_time=mfs_flag,
        )
    else:
        allowance_raw = 0.0
    allowance = max(0, irs_round(allowance_raw))

    total_passive_loss = passive_loss_total + prior_carryforward_total
    allowed_loss = min(
        passive_income_total + allowance, total_passive_loss,
    )
    suspended_total = total_passive_loss - allowed_loss

    per_activity_carryforwards = []
    for a in passive_activities:
        activity_total_loss = a["loss"] + a["prior_carryforward"]
        if total_passive_loss > 0:
            suspended = irs_round(
                activity_total_loss * (suspended_total / total_passive_loss),
            )
        else:
            suspended = 0
        if suspended:
            per_activity_carryforwards.append({
                "entity_name": a["entity_name"],
                "suspended_amount": suspended,
            })

    return {
        "f8582_line_1a_activities_with_income": passive_income_total,
        "f8582_line_1b_activities_with_loss": passive_loss_total,
        "f8582_line_1c_prior_year_unallowed_loss": prior_carryforward_total,
        "f8582_line_1d_combine": (
            passive_income_total - passive_loss_total - prior_carryforward_total
        ),
        "f8582_line_11_allowed_loss": allowed_loss,
        "f8582_special_allowance": allowance,
        "per_activity_carryforwards": per_activity_carryforwards,
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }
