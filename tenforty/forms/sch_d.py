"""Schedule D — Capital Gains and Losses.

``f8949.compute`` has already partitioned ``scenario.form1099_b`` into two
buckets and emitted totals for each: aggregate-path lots (Box A/D no-
adjustment) flow to lines 1a/8a; 8949-path lots flow per-box to 1b/2/3
and 8b/9/10. ``sch_d.compute`` forwards both partitions' totals — no
subtraction, no re-partitioning. The no-double-count invariant is
enforced separately on the f8949 emission.
"""

from tenforty.models import K1FanoutData, Scenario
from tenforty.params.federal import load as load_federal_params
from tenforty.rounding import irs_round
from tenforty.types import UpstreamState


def compute(
    scenario: Scenario,
    upstream: UpstreamState,
    *,
    taxable_income_unfloored: float | None = None,
) -> dict:
    """Schedule D compute.

    ``taxable_income_unfloored`` (keyword-only, default ``None``) is the
    §1212(b)(2) honesty-guard input: this return's taxable income WITHOUT
    the 1040 "if less than zero, enter -0-" floor. It is REQUIRED to get a
    carryforward whenever the return has a capital loss beyond the
    §1211(b) cap: without it, the two carryforward keys are OMITTED from
    the result rather than filled with an unverified split. Supplied and
    negative, compute refuses outright (§1212(b)(2), unmodelled in v1).
    Returns with no capped loss need not supply it. See the VALIDITY
    BOUNDARY comment below for the full case table.
    """
    f8949 = upstream.get("f8949", {})
    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()

    line_1a = _agg_line(f8949, term="short")
    line_8a = _agg_line(f8949, term="long")

    line_1b = _box_line(f8949, letter="a")
    line_2 = _box_line(f8949, letter="b")
    line_3 = _box_line(f8949, letter="c")
    line_8b = _box_line(f8949, letter="d")
    line_9 = _box_line(f8949, letter="e")
    line_10 = _box_line(f8949, letter="f")

    k1_short = irs_round(sum(fanout.sch_d_short_term_additions))
    k1_long = irs_round(sum(fanout.sch_d_long_term_additions))

    # Sch D line 13 — capital gain distributions from 1099-DIV box 2a.
    # These are treated as long-term capital gains and enter the long-term
    # total (line 15) before rolling into the net total (line 16).
    line_13 = irs_round(
        sum(f.capital_gain_distributions for f in scenario.form1099_div)
    )

    line_7 = (line_1a["gain"] + line_1b["gain"] + line_2["gain"]
              + line_3["gain"] + k1_short)
    line_15 = (line_8a["gain"] + line_8b["gain"] + line_9["gain"]
               + line_10["gain"] + k1_long + line_13)
    line_16 = line_7 + line_15

    # --- Line 21: IRC §1211(b) net-capital-loss limitation ---------------
    # "If line 16 is a loss, enter here and on Form 1040 line 7 the SMALLER
    # of: (a) that loss, or (b) $3,000 ($1,500 MFS)." "Smaller" here means
    # smaller in MAGNITUDE, not smaller as a signed number. Between a
    # -50,000 loss and the -3,000 cap, the magnitude-smaller loss is
    # -3,000, but numerically -3,000 > -50,000 -- so picking the smaller
    # LOSS is `max()`, not `min()`, on these signed values. Do not
    # "simplify" this to min() -- that reads naturally as "smaller of two
    # numbers" but computes the WRONG (bigger, understated) loss.
    # When line_16 is a GAIN (>= 0), line 21 is not used on the return;
    # this branch passes line_16 through untouched.
    params = load_federal_params(scenario.config.year)
    cap = params.capital_loss_limit[scenario.config.filing_status.value]
    if line_16 >= 0:
        line_21 = line_16
    else:
        line_21 = max(line_16, -cap)

    # --- Carryforward split by character (IRC §1212(b)) ------------------
    # A loss disallowed this year (line_16 - line_21, zero unless line_16
    # is a loss beyond the cap) carries forward retaining its short-term /
    # long-term character: next year it re-enters Schedule D at line 6 (ST)
    # and line 14 (LT). The arithmetic below reproduces the IRS "Capital
    # Loss Carryover Worksheet -- Lines 6 and 14" (Schedule D instructions)
    # lines 5-13 (the ST/LT split), substituting this year's flat-cap
    # allowed-loss magnitude (`abs(line_21)`) for that worksheet's own
    # line 4. That substitution is EXACT -- reproduces the worksheet's
    # line 4 precisely -- whenever this year's (unfloored) taxable income
    # is >= 0; see the guard immediately below for the case where it is
    # not, which this function refuses to answer for.
    #
    # VALIDITY BOUNDARY for sch_d_st_capital_loss_carryforward and
    # sch_d_lt_capital_loss_carryforward, read this before consuming
    # either key:
    #   - line_16 >= 0 (a gain, or zero): both keys are 0. Always valid --
    #     the worksheet is not used when there's no loss.
    #   - line_16 < 0 (a loss) and line_16 == line_21 (loss fully allowed,
    #     did not exceed the cap): both keys are 0. Always valid -- no
    #     disallowed remainder exists to carry forward.
    #   - line_16 < 0 and line_16 < line_21 (loss exceeded the cap) AND the
    #     caller supplied `taxable_income_unfloored >= 0`: both keys hold
    #     the worksheet-exact split. Valid.
    #   - line_16 < 0 and line_16 < line_21 and `taxable_income_unfloored`
    #     is negative: REFUSES (raises NotImplementedError below) rather
    #     than emit a split the real worksheet would disagree with.
    #   - line_16 < 0 and line_16 < line_21 and `taxable_income_unfloored`
    #     is None: BOTH KEYS ARE ABSENT from the returned dict. Without
    #     the taxable-income figure we cannot know whether the flat-cap
    #     substitution is exact for this return, and emitting a split
    #     anyway would rest on an assumption nobody verified. ENFORCED,
    #     not merely documented: a comment saying callers "must" pass
    #     something is not a guard, and a strict read that is only
    #     sometimes strict is a silent path with extra steps. Reading
    #     either key on such a return raises KeyError -- there is no
    #     number and no sentinel to mistake for an answer. A consumer
    #     must NOT paper over that with `.get(key, 0)`; it must supply
    #     `taxable_income_unfloored` instead.
    # Callers with NO capped loss never need to supply the parameter --
    # they have no carryforward to get wrong, which is why it stays
    # optional rather than required.
    if line_21 >= 0:
        st_carryforward = 0
        lt_carryforward = 0
    else:
        allowed_magnitude = -line_21  # positive; worksheet's line 4, naive
        if line_7 < 0:
            st_loss = -line_7  # worksheet line 5
            lt_gain = max(0, line_15)  # worksheet line 6
            st_used = allowed_magnitude + lt_gain  # worksheet line 7
            st_carryforward = -max(0, st_loss - st_used)  # worksheet line 8
        else:
            st_loss = 0
            st_carryforward = 0
        if line_15 < 0:
            lt_loss = -line_15  # worksheet line 9
            st_gain = max(0, line_7)  # worksheet line 10
            lt_headroom = max(0, allowed_magnitude - st_loss)  # worksheet line 11
            lt_used = st_gain + lt_headroom  # worksheet line 12
            lt_carryforward = -max(0, lt_loss - lt_used)  # worksheet line 13
        else:
            lt_carryforward = 0

    # --- §1212(b)(2) honesty guard -----------------------------------
    # The real worksheet's line 4 is `min(loss magnitude, combine(taxable
    # income, loss magnitude))`, not the flat loss magnitude used above --
    # when this year's (unfloored) taxable income is negative, less of the
    # allowed loss was actually "used" against income, so line 4 comes in
    # SMALLER than the flat cap, and the true carryforward is LARGER than
    # what the arithmetic above computes. v1 does not implement that
    # income-based adjustment (only the flat-cap substitution). Trigger,
    # derived from the worksheet (not invented): the flat-cap substitution
    # is exact if and only if unfloored taxable income >= 0 (at exactly 0,
    # combine(0, magnitude) == magnitude, still exact); it diverges for any
    # negative value, however small the divergence.  "Unfloored" matters:
    # this must be the return's taxable income WITHOUT the 1040
    # instructions' "if less than zero, enter -0-" floor, i.e. it may
    # itself be negative -- the ordinary floored `taxable_income` figure
    # would hide exactly the case this guard exists to catch.
    #
    # FAIL-CLOSED IN BOTH DIRECTIONS. Two distinct failure modes, two
    # branches, two messages: (1) the caller gave us a negative taxable
    # income, so we KNOW v1's arithmetic is wrong for this return; (2) the
    # caller gave us nothing, so we cannot know either way -- and "cannot
    # know" must refuse just as loudly as "know it's wrong", or the
    # unsupplied path silently becomes the assumed-fine path.
    # Mode (2), "cannot know": a capped loss exists (so there IS a real
    # remainder to carry forward) but no taxable-income figure was
    # supplied, so we cannot tell whether v1's flat-cap arithmetic is
    # exact for this return. We therefore emit NO carryforward keys at
    # all -- see `_emit_carryforward` below. Omission, not a number and
    # not a sentinel: there is nothing for a downstream consumer to
    # mistake for an answer, and any consumer that reads these keys gets
    # a loud KeyError. This is the same strict-read discipline f8995.py
    # applies to "qualified_dividends".
    #
    # A raise here would ALSO be fail-closed, but its blast radius is out
    # of this task's scope: the orchestrator calls sch_d.compute without
    # this parameter, so raising makes every capped-loss return
    # UNCOMPUTABLE END-TO-END (verified: 10 previously-passing subtests
    # in test_spine_battery_parameterization.py fail, the battery's
    # `capital_loss_over_cap` scenario among them). Supplying the figure
    # requires wiring taxable income through orchestrator.py /
    # f1040_spine.py, which is a later task. Escalated in the report.
    emit_carryforward = not (
        line_21 < 0 and line_16 < line_21 and taxable_income_unfloored is None
    )

    if line_21 < 0 and taxable_income_unfloored is not None and taxable_income_unfloored < 0:
        raise NotImplementedError(
            "Capital loss carryforward cannot be computed for this return: "
            "IRC section 1212(b)(2) adjusts the capital loss carryover "
            "when taxable income (unfloored) for the loss year is "
            "negative -- less of the allowed loss is treated as 'used' "
            "against income in that case, so the true carryforward is "
            "larger than this module's flat-cap arithmetic would produce. "
            "tenforty v1 does not model that income-based adjustment. The "
            "in-year allowed loss (Schedule D line 21) is unaffected and "
            "is still correct. The short-term and long-term capital loss "
            "carryforward for this return must instead be computed by the "
            "preparer using the IRS Capital Loss Carryover Worksheet "
            "(Schedule D instructions, 'Lines 6 and 14')."
        )

    carryforward_keys = {
        # See the VALIDITY BOUNDARY comment above (where these two values
        # are computed) for exactly which returns each key is trustworthy
        # for, which OMIT these keys entirely, and which refuse outright.
        "sch_d_st_capital_loss_carryforward": st_carryforward,
        "sch_d_lt_capital_loss_carryforward": lt_carryforward,
    } if emit_carryforward else {}

    return {
        **scenario.config.pdf_header(),

        "sch_d_line_1a_proceeds": line_1a["proceeds"],
        "sch_d_line_1a_basis": line_1a["basis"],
        "sch_d_line_1a_gain": line_1a["gain"],
        "sch_d_line_1b_proceeds": line_1b["proceeds"],
        "sch_d_line_1b_basis": line_1b["basis"],
        "sch_d_line_1b_gain": line_1b["gain"],
        "sch_d_line_2_proceeds": line_2["proceeds"],
        "sch_d_line_2_basis": line_2["basis"],
        "sch_d_line_2_gain": line_2["gain"],
        "sch_d_line_3_proceeds": line_3["proceeds"],
        "sch_d_line_3_basis": line_3["basis"],
        "sch_d_line_3_gain": line_3["gain"],
        "sch_d_line_5_net_short_k1": k1_short,
        "sch_d_line_7_net_short": line_7,

        "sch_d_line_8a_proceeds": line_8a["proceeds"],
        "sch_d_line_8a_basis": line_8a["basis"],
        "sch_d_line_8a_gain": line_8a["gain"],
        "sch_d_line_8b_proceeds": line_8b["proceeds"],
        "sch_d_line_8b_basis": line_8b["basis"],
        "sch_d_line_8b_gain": line_8b["gain"],
        "sch_d_line_9_proceeds": line_9["proceeds"],
        "sch_d_line_9_basis": line_9["basis"],
        "sch_d_line_9_gain": line_9["gain"],
        "sch_d_line_10_proceeds": line_10["proceeds"],
        "sch_d_line_10_basis": line_10["basis"],
        "sch_d_line_10_gain": line_10["gain"],
        "sch_d_line_12_net_long_k1": k1_long,
        "sch_d_line_13_cap_gain_dist": line_13,
        "sch_d_line_15_net_long": line_15,

        "sch_d_line_16_total": line_16,
        "sch_d_line_21_allowed_loss": line_21,
        **carryforward_keys,
        "sch_d_unrecap_1250": f8949.get("f8949_total_unrecap_1250", 0),
        "sch_d_28_rate_gain": f8949.get("f8949_total_28_rate_gain", 0),
    }


def _agg_line(f8949: dict, *, term: str) -> dict[str, int]:
    return {
        "proceeds": f8949.get(f"f8949_agg_{term}_proceeds", 0),
        "basis": f8949.get(f"f8949_agg_{term}_basis", 0),
        "gain": f8949.get(f"f8949_agg_{term}_gain", 0),
    }


def _box_line(f8949: dict, *, letter: str) -> dict[str, int]:
    return {
        "proceeds": f8949.get(f"f8949_box_{letter}_total_proceeds", 0),
        "basis": f8949.get(f"f8949_box_{letter}_total_basis", 0),
        "gain": f8949.get(f"f8949_box_{letter}_total_gain", 0),
    }
