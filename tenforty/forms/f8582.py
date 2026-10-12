"""Form 8582 — Passive Activity Loss Limitations.

Computes the current-year allowed passive loss and the per-activity
suspended amount that carries forward to next year's scenario.

v1 scope:
- Special allowance per IRC §469(i)(5) — varies by filing status:
    * single/mfj/hoh/qss: $25,000 base, phaseout $100k-$150k MAGI.
    * mfs, lived APART from spouse ALL year: $12,500 base,
      phaseout $50k-$75k MAGI.
    * mfs, lived WITH spouse any time: $0.
- Each Sch E Part I rental (one per printed column A/B/C) is its own
  passive activity, treated as actively participated rental real estate
  (v1 has no opt-out flag). Income and loss come from that column's
  printed line 21, so a loss on any column reaches the limitation.
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

from tenforty.forms import sch_e as form_sch_e
from tenforty.models import FilingStatus, K1FanoutData, Scenario
from tenforty.rounding import irs_round


# The K-1 business boxes that are NOT rental real estate (box 2). Every
# business box the Schedule E Part II row nets, less `net_rental_real_estate`.
_NON_RENTAL_REAL_ESTATE_BOXES = (
    "ordinary_business_income", "other_net_rental", "royalties",
    "other_income",
)


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
    f1040_upstream = upstream.get("f1040", {})
    # Modified AGI drives the special allowance, and a missing figure is NOT
    # zero: zero grants the maximum allowance. The arithmetic below still
    # runs on 0 so the form's other lines exist, but the result is flagged,
    # and the passive_loss_allowance_unknown_magi refusal stops any return
    # that has a passive loss to limit.
    magi_known = "magi" in f1040_upstream
    agi = float(f1040_upstream.get("magi", 0))
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

    # Every Sch E Part I rental is one passive activity, from its own
    # column's printed line 21. Activities are kept by position, never
    # merged by name: two rentals may share an address. With no Schedule E
    # result at all there are no figures to read; with one, a column whose
    # line 21 is missing is a wiring fault, not a zero.
    for letter, rp in form_sch_e.printed_columns(scenario):
        key = form_sch_e.line_21_key(letter)
        if sch_e_upstream and key not in sch_e_upstream:
            raise KeyError(
                f"Form 8582: the Schedule E result carries no {key!r} for "
                f"rental property {rp.address!r}; its passive income or "
                f"loss cannot be read.")
        rental_net = int(sch_e_upstream.get(key, 0))
        passive_activities.append({
            "entity_name": rp.address,
            "income": max(0, rental_net),
            "loss": max(0, -rental_net),
            "prior_carryforward": 0,
        })

    passive_income_total = sum(a["income"] for a in passive_activities)
    passive_loss_total = sum(a["loss"] for a in passive_activities)
    prior_carryforward_total = sum(
        a["prior_carryforward"] for a in passive_activities
    )
    # KNOWN LIMIT of this module: the special allowance below is applied to
    # the whole passive-loss pool, though it may only excuse a rental real
    # estate net loss. These two figures let the refusal ledger
    # (passive_loss_limitation_not_applied) stop the returns on which that
    # over-allowance can change the answer. They are taken BOX BY BOX across
    # the passive K-1s, not from the netted Schedule E rows: a K-1 whose
    # rental real estate income hides an ordinary loss in its row net still
    # contributes that loss here.
    non_rental_boxes = [
        irs_round(getattr(k1, box))
        for k1 in scenario.schedule_k1s if not k1.material_participation
        for box in _NON_RENTAL_REAL_ESTATE_BOXES
    ]
    non_rental_loss_total = sum(-v for v in non_rental_boxes if v < 0)
    non_rental_income_total = sum(v for v in non_rental_boxes if v > 0)

    # Form 8582 MAGI (line 6) = AGI minus net passive activity. Subtracting a
    # negative net (losses > income) adds the loss back, which is intentional.
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
        **scenario.config.pdf_header(),
        "f8582_line_1a_activities_with_income": passive_income_total,
        "f8582_line_1b_activities_with_loss": passive_loss_total,
        "f8582_line_1c_prior_year_unallowed_loss": prior_carryforward_total,
        "f8582_line_1d_combine": (
            passive_income_total - passive_loss_total - prior_carryforward_total
        ),
        "f8582_line_11_allowed_loss": allowed_loss,
        "f8582_special_allowance": allowance,
        "f8582_non_rental_passive_loss": non_rental_loss_total,
        "f8582_non_rental_passive_income": non_rental_income_total,
        "per_activity_carryforwards": per_activity_carryforwards,
        # Present only when unknown, so a known-MAGI result is unchanged.
        **({} if magi_known else {"f8582_magi_unknown": True}),
    }
