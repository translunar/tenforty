"""K-1 reference oracle for 1120-S, 1065, and 1041 pass-through flows.

Independent reference implementation. Given a ``ScheduleK1`` dataclass, produce
the expected downstream flows so production code can be cross-checked.

This module intentionally reads the 2025 IRS instructions *directly* rather
than reusing any production flattener/translator. Divergence between production
and this oracle is the signal we care about — do not smooth over it.

All citations target tax year 2025 IRS instructions unless noted. Every rule
below carries a ``SOURCE:`` comment pointing at the authoritative paragraph so
annual refreshes can diff against next year's instructions.

### Output contract (from team-lead brief)

``k1_to_expected_outputs(k1)`` returns:

    {
      "sch_e_part_ii_row": {
          "nonpassive_income": float,
          "nonpassive_loss":  float,   # positive magnitude
          "passive_income":   float,
          "passive_loss":     float,   # positive magnitude (pre-8582 raw)
      },
      "sch_b_additions": {"interest": float, "ordinary_dividends": float},
      "sch_d_additions": {"short_term": float, "long_term": float},
      "qbi_amount": float,
      "passive_flag": bool,
    }

### Input contract

The ``ScheduleK1`` production dataclass attaches the following fields
(team-lead brief 2026-04-15). Oracle reads them directly — no re-mapping from
raw box numbers, because production's flattener has already normalized the
three entity variants into this shape.

### Numeric type

``float`` per production contract. Sub-cent precision loss accepted; the
comparison test will round to the nearest cent. If precision issues surface in
practice, revisit.

### Scope

See ``README.md`` for in/out scope, ambiguities, and citation lineage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


# ---------------------------------------------------------------------------
# Input protocol — mirrors the production ScheduleK1 dataclass.
# (Structural typing so the test harness can import either a real dataclass
# instance or a mock with the same attributes.)
# ---------------------------------------------------------------------------
class ScheduleK1Like(Protocol):
    entity_name: str
    entity_ein: str
    entity_type: Literal["s_corp", "partnership", "estate_trust"]
    material_participation: bool

    ordinary_business_income: float
    net_rental_real_estate: float
    other_net_rental: float
    interest_income: float
    ordinary_dividends: float
    qualified_dividends: float
    royalties: float
    net_short_term_capital_gain: float
    net_long_term_capital_gain: float
    other_income: float

    qbi_amount: float

    prior_year_passive_loss_carryforward: float


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# 2025 Form 8995 simple-path taxable-income threshold. Above this, production
# must use Form 8995-A (SSTB phase-in, W-2 wage limit, UBIA limit).
#
# VERIFY: IRS draft i8995 (2025) shows $197,300 (single/others) / $394,600
# (MFJ). Those numbers match the 2023 published thresholds, which is
# implausible under normal inflation adjustment. Team-lead's brief stated
# $241,950 single which was the 2024 value. CPA confirmation required
# before any downstream code consumes these constants.
#
# SOURCE (draft): https://www.irs.gov/pub/irs-dft/i8995--dft.pdf
QBI_SIMPLE_THRESHOLD_2025 = {
    "single": 197_300.0,   # VERIFY
    "mfj":    394_600.0,   # VERIFY
    "hoh":    197_300.0,   # VERIFY
    "mfs":    197_300.0,   # VERIFY
    "qss":    394_600.0,   # VERIFY
}

# Form 8582 $25k special allowance for active-participation rental real
# estate loss, per IRC §469(i). Phased out over $100k–$150k MAGI (50%
# reduction per $1 over $100k). MFS living apart: $12.5k cap, $50k–$75k.
# MFS living together at any point: not eligible.
#
# SOURCE: 2025 Instructions for Form 8582, Part II.
SPECIAL_ALLOWANCE_CAP = 25_000.0
SPECIAL_ALLOWANCE_PHASEOUT_START = 100_000.0
SPECIAL_ALLOWANCE_PHASEOUT_END = 150_000.0
SPECIAL_ALLOWANCE_MFS_CAP = 12_500.0
SPECIAL_ALLOWANCE_MFS_PHASEOUT_START = 50_000.0
SPECIAL_ALLOWANCE_MFS_PHASEOUT_END = 75_000.0


# ---------------------------------------------------------------------------
# Scope gates — match tenforty's production flattener pattern (raise loudly
# for items we don't model).
# ---------------------------------------------------------------------------
def _gate_scope(k1: ScheduleK1Like) -> None:
    """Raise NotImplementedError if the K-1 carries amounts this oracle
    does not model. The production ScheduleK1 schema does not expose
    section_1231 / section_179 / SE earnings / credits as separate fields,
    so the only surface where they can hide is ``other_income``. If that's
    nonzero, the caller has packed something unmodeled into it.

    Aligns with the production flattener's "reject unknown forms" approach.
    See README.md → "Out of scope" for the full list of items that may be
    lurking in other_income.
    """
    if k1.other_income != 0.0:
        raise NotImplementedError(
            f"K-1 oracle does not model other_income ({k1.other_income}). "
            f"May include §1231 gain (Form 4797), §179 deduction "
            f"(Form 4562), box 14 self-employment earnings (Schedule SE), "
            f"or K-1 credits (Form 3800 / specific credit forms). "
            f"See tests/oracles/README.md scope section."
        )


# ---------------------------------------------------------------------------
# Passive classification (Form 8582 determination)
# ---------------------------------------------------------------------------
def _classify_components(k1: ScheduleK1Like) -> tuple[float, float]:
    """Return (nonpassive_total, passive_total) across the K-1 components
    that land on Schedule E Part II line 28.

    Rules:
      - Ordinary business income (1120-S box 1 / 1065 box 1 / 1041 box 6):
        nonpassive iff material_participation = True, else passive.
        SOURCE: 2025 Instructions for Schedule K-1 (Form 1120-S), box 1:
          "Schedule E (Form 1040), line 28, column (i) or (k) if you
          materially participated ... column (h) if passive activity
          income ... Follow Form 8582 instructions if passive activity
          loss".
      - Net rental real estate (box 2 / box 2 / box 7): PASSIVE for all
        owners by default, per §469(c)(2). Real estate professional
        exemption (§469(c)(7)) is explicitly OUT OF SCOPE — see README.
      - Other rentals (box 3 / box 3 / box 8): PASSIVE for all owners per
        §469(c)(2).

    Royalties do NOT land on Part II line 28; they flow to Schedule E
    Part I line 4. Interest, dividends, and cap gains flow to Sch B / Sch
    D, not Sch E Part II. They are excluded from this classification.
    """
    obi = k1.ordinary_business_income
    rental_total = k1.net_rental_real_estate + k1.other_net_rental

    if k1.material_participation:
        nonpassive = obi
        passive = rental_total
    else:
        nonpassive = 0.0
        passive = obi + rental_total

    return nonpassive, passive


def passive_flag(k1: ScheduleK1Like) -> bool:
    """True if this K-1 has any passive component (income or loss), OR if
    the filer carries a prior-year passive loss from this activity.

    Interpretation note: the team-lead brief describes this flag as
    "True if losses go to 8582". Read narrowly, that would be True only
    when there's a current-year passive loss. Read broadly, it's True
    whenever 8582 is in play for this activity at all — including when
    positive passive income releases previously-suspended losses.

    This implementation takes the broader reading because 8582 can be
    triggered by positive passive income (to release suspended losses)
    just as well as by a current-year loss. Production can narrow this
    if it turns out to match its intent.
    """
    nonpassive, passive = _classify_components(k1)
    if passive != 0.0:
        return True
    if k1.prior_year_passive_loss_carryforward != 0.0:
        return True
    return False


# ---------------------------------------------------------------------------
# Main entry point — contract per team-lead brief
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Outputs:
    """Internal helper — serialized to plain dict by k1_to_expected_outputs."""
    sch_e_part_ii_row: dict[str, float]
    sch_b_additions: dict[str, float]
    sch_d_additions: dict[str, float]
    qbi_amount: float
    passive_flag: bool


def k1_to_expected_outputs(k1: ScheduleK1Like) -> dict:
    """Compute the full set of expected downstream flows for one K-1.

    Returns a dict matching the contract in the module docstring.

    Raises NotImplementedError if the K-1 carries amounts this oracle
    does not model (see ``_gate_scope``).
    """
    _gate_scope(k1)

    nonpassive, passive = _classify_components(k1)

    sch_e_row = {
        # split into income vs loss buckets; loss reported as positive magnitude
        "nonpassive_income": max(nonpassive, 0.0),
        "nonpassive_loss":   -min(nonpassive, 0.0),
        "passive_income":    max(passive, 0.0),
        "passive_loss":      -min(passive, 0.0),
    }

    # Schedule B Part I / Part II (or directly to 1040 lines 2b / 3b if
    # under the Sch B filing threshold — production decides). Oracle
    # reports the ADDITIONS; caller sums across all interest/dividend
    # sources.
    #
    # IMPORTANT: qualified_dividends is a SUBSET of ordinary_dividends,
    # not an additional amount. It affects the tax computation (via the
    # Qualified Dividends and Capital Gain Tax Worksheet) but does NOT
    # add to Schedule B. Do not double-count.
    #
    # SOURCE:
    #   1120-S box 4 → Form 1040 line 2b; 5a → line 3b; 5b → line 3a
    #   1065 box 5 → Sch B Part I / 1040 line 2b; 6a → line 3b; 6b → line 3a
    #   1041 box 1 → line 2b; 2a → line 3b; 2b → line 3a
    sch_b = {
        "interest": k1.interest_income,
        "ordinary_dividends": k1.ordinary_dividends,
    }

    # Schedule D line 5 (short-term) and line 12 (long-term).
    # 28% collectibles gain, unrecaptured §1250, §1231 — out of scope.
    #
    # SOURCE:
    #   1120-S box 7 → Sch D line 5; box 8a → line 12
    #   1065 box 8 → Sch D line 5; box 9a → line 12
    #   1041 box 3 → Sch D line 5; box 4a → line 12
    sch_d = {
        "short_term": k1.net_short_term_capital_gain,
        "long_term": k1.net_long_term_capital_gain,
    }

    # QBI contribution — box 17V (1120-S) / 20Z (1065) / 14I (1041).
    # Simple Form 8995 aggregation path; no SSTB limitation, no wage/UBIA
    # phase-in. Caller applies the taxable-income threshold.
    #
    # SOURCE: 2025 Form 8995 instructions — "Determining Your Qualified
    # Business Income" subsection.
    qbi = k1.qbi_amount

    return {
        "sch_e_part_ii_row": sch_e_row,
        "sch_b_additions": sch_b,
        "sch_d_additions": sch_d,
        "qbi_amount": qbi,
        "passive_flag": passive_flag(k1),
    }


# ---------------------------------------------------------------------------
# Form 8582 special allowance (not part of k1_to_expected_outputs but
# exposed for test use; 8582 aggregates across ALL passive activities, so
# computing the allowance is a portfolio-level concern, not a per-K-1 one)
# ---------------------------------------------------------------------------
def special_allowance(
    magi: float,
    filing_status: Literal["single", "mfj", "hoh", "mfs", "qss"],
    mfs_lived_with_spouse_any_time: bool = False,
) -> float:
    """Compute the $25,000 special allowance for active-participation
    rental real estate losses.

    SOURCE: 2025 Instructions for Form 8582, Part II; IRC §469(i).

    Phaseout: allowance reduced by 50% of (MAGI − threshold), floored at 0.
    MFS living apart all year: $12,500 cap, $50k–$75k phaseout.
    MFS living together at any point during year: $0.

    This function does NOT apply the "active participation" test itself;
    the caller is responsible for determining eligibility. Real estate
    professional exemption (§469(c)(7)) is a DIFFERENT mechanism and is
    out of scope.
    """
    if filing_status == "mfs":
        if mfs_lived_with_spouse_any_time:
            return 0.0
        cap = SPECIAL_ALLOWANCE_MFS_CAP
        start = SPECIAL_ALLOWANCE_MFS_PHASEOUT_START
        end = SPECIAL_ALLOWANCE_MFS_PHASEOUT_END
    else:
        cap = SPECIAL_ALLOWANCE_CAP
        start = SPECIAL_ALLOWANCE_PHASEOUT_START
        end = SPECIAL_ALLOWANCE_PHASEOUT_END

    if magi <= start:
        return cap
    if magi >= end:
        return 0.0
    # Phaseout: 50 cents per dollar over threshold.
    return max(0.0, cap - 0.5 * (magi - start))


__all__ = [
    "ScheduleK1Like",
    "QBI_SIMPLE_THRESHOLD_2025",
    "SPECIAL_ALLOWANCE_CAP",
    "SPECIAL_ALLOWANCE_PHASEOUT_START",
    "SPECIAL_ALLOWANCE_PHASEOUT_END",
    "SPECIAL_ALLOWANCE_MFS_CAP",
    "SPECIAL_ALLOWANCE_MFS_PHASEOUT_START",
    "SPECIAL_ALLOWANCE_MFS_PHASEOUT_END",
    "k1_to_expected_outputs",
    "passive_flag",
    "special_allowance",
]
