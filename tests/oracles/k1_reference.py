"""K-1 reference oracle for 1120-S, 1065, and 1041 pass-through flows.

Independent reference implementation. Given a ``ScheduleK1`` dataclass, produce
the expected downstream flows so production code can be cross-checked.

This module intentionally reads the IRS instructions *directly* rather than
reusing any production flattener/translator. Divergence between production and
this oracle is the signal we care about.

All citations target tax year 2025 IRS instructions unless noted. Every rule
below carries a ``SOURCE:`` comment pointing at the authoritative paragraph so
annual refreshes can diff against next year's instructions.

----

### Schema (pending)

The ``ScheduleK1`` dataclass schema is owned by production (team-lead will
attach). Until it lands, the function signatures below accept ``K1Like`` — a
structural protocol capturing the minimum fields we read. When the real
dataclass lands, swap ``K1Like`` for ``tenforty.models.ScheduleK1`` and delete
the protocol.

### Output contract

Every function returns a ``Decimal`` (or a small frozen dataclass of Decimals).
No floats. No rounding inside the oracle — rounding is production's job; the
oracle reports exact arithmetic so the comparison test can see sub-dollar
divergences before IRS-style rounding hides them.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Protocol


# ---------------------------------------------------------------------------
# Placeholder structural protocol — replace with tenforty.models.ScheduleK1
# once team-lead attaches the production schema.
# ---------------------------------------------------------------------------
class K1Like(Protocol):
    """Minimum fields this oracle reads off a K-1.

    Field names align with IRS Schedule K-1 box labels. The production
    ``ScheduleK1`` dataclass is expected to expose at least these fields
    (possibly more). If it uses different names, this protocol becomes the
    adapter layer.
    """

    entity_kind: str  # one of "s_corp", "partnership", "estate_trust"
    # Ordinary business income/loss
    #   1120-S box 1; 1065 box 1; 1041 box 6
    ordinary_business_income: Decimal
    # Net rental real estate income/loss
    #   1120-S box 2; 1065 box 2; 1041 box 7
    net_rental_real_estate: Decimal
    # Other net rental income/loss
    #   1120-S box 3; 1065 box 3; 1041 box 8
    other_net_rental: Decimal
    # Interest income
    #   1120-S box 4; 1065 box 5; 1041 box 1
    interest_income: Decimal
    # Ordinary dividends
    #   1120-S box 5a; 1065 box 6a; 1041 box 2a
    ordinary_dividends: Decimal
    # Qualified dividends (subset of ordinary)
    #   1120-S box 5b; 1065 box 6b; 1041 box 2b
    qualified_dividends: Decimal
    # Short-term capital gain/loss
    #   1120-S box 7; 1065 box 8; 1041 box 3
    short_term_capital_gain: Decimal
    # Long-term capital gain/loss
    #   1120-S box 8a; 1065 box 9a; 1041 box 4a
    long_term_capital_gain: Decimal
    # Royalties
    #   1120-S box 6; 1065 box 7; 1041 box 5 (partial)
    royalties: Decimal
    # QBI (section 199A qualified business income)
    #   1120-S box 17 code V; 1065 box 20 code Z; 1041 box 14 code I
    qbi_amount: Decimal
    # Passive/nonpassive classification marker. See passive_flag() below.
    # Per regs, ordinary business income from an entity in which the owner
    # materially participates is NONPASSIVE; rental is generally passive.
    material_participation: bool


# ---------------------------------------------------------------------------
# Enums — stable across all three K-1 variants
# ---------------------------------------------------------------------------
class PassiveFlag(str, Enum):
    PASSIVE = "passive"
    NONPASSIVE = "nonpassive"


class ScheduleEColumn(str, Enum):
    """Schedule E Part II, line 28 column letters.

    SOURCE: 2025 Schedule E Instructions, Part II line 28 column headers.
      (g) passive loss allowed (attach Form 8582)
      (h) passive income from Schedule K-1
      (i) nonpassive loss allowed
      (j) section 179 expense deduction (Form 4562)
      (k) nonpassive income from Schedule K-1
    """

    G_PASSIVE_LOSS = "g"
    H_PASSIVE_INCOME = "h"
    I_NONPASSIVE_LOSS = "i"
    J_SECTION_179 = "j"
    K_NONPASSIVE_INCOME = "k"


# ---------------------------------------------------------------------------
# Sch E Part II row fan-out
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduleERow:
    """One line of Schedule E Part II (line 28)."""

    entity_name: str
    column: ScheduleEColumn
    amount: Decimal


def schedule_e_part_ii_row(k1: K1Like, entity_name: str) -> ScheduleERow:
    """Compute the Schedule E Part II line 28 placement for this K-1.

    Box 1 (ordinary business income) is the primary driver:
      - Nonpassive (material participation): column (i) if loss, (k) if income.
          SOURCE: 2025 Instructions for Schedule K-1 (Form 1120-S), box 1
          reporting: "Schedule E (Form 1040), line 28, column (i) or (k) if
          you materially participated".
      - Passive: column (h) if income, column (g) if loss.
          SOURCE: same instructions: "Schedule E (Form 1040), line 28, column
          (h) if passive activity income" / "Follow Form 8582 instructions if
          passive activity loss".

    The 1065 / 1041 rules are parallel; see SOURCE comments in implementation.
    """
    raise NotImplementedError("Pending ScheduleK1 schema from team-lead.")


# ---------------------------------------------------------------------------
# Schedule B additions (interest + ordinary dividends)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduleBAdditions:
    interest: Decimal
    ordinary_dividends: Decimal


def schedule_b_additions(k1: K1Like) -> ScheduleBAdditions:
    """Interest (box 4 / 5 / 1) and ordinary dividends (box 5a / 6a / 2a)
    flow to Schedule B Parts I and II respectively, or directly to 1040
    lines 2b / 3b if Schedule B is not otherwise required.

    SOURCE: 2025 Instructions for Schedule K-1:
      - 1120-S: box 4 → Form 1040 line 2b; box 5a → line 3b; box 5b → line 3a.
      - 1065: box 5 → Schedule B Part I or 1040 line 2b; box 6a → Schedule B
        Part II or 1040 line 3b.
      - 1041: box 1 → line 2b; box 2a → line 3b; box 2b → line 3a.
    """
    raise NotImplementedError("Pending ScheduleK1 schema from team-lead.")


# ---------------------------------------------------------------------------
# Schedule D additions (cap gains)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduleDAdditions:
    short_term: Decimal  # Schedule D line 5
    long_term: Decimal   # Schedule D line 12


def schedule_d_additions(k1: K1Like) -> ScheduleDAdditions:
    """Cap gains flow to Schedule D.

    SOURCE:
      - 1120-S box 7 → Schedule D line 5; box 8a → Schedule D line 12.
      - 1065 box 8 → Schedule D line 5; box 9a → Schedule D line 12.
      - 1041 box 3 → Schedule D line 5; box 4a → Schedule D line 12.

    Out-of-scope for v1 (flagged in README):
      - 28% collectibles gain (box 8b / 9b / 4b) → feeds 28% Rate Gain
        Worksheet, not a simple Schedule D line.
      - Unrecaptured §1250 gain (box 8c / 9c / 4c) → feeds Unrecaptured
        Section 1250 Gain Worksheet.
    """
    raise NotImplementedError("Pending ScheduleK1 schema from team-lead.")


# ---------------------------------------------------------------------------
# QBI (simple — Form 8995 path)
# ---------------------------------------------------------------------------
# 2025 Form 8995 taxable-income threshold for eligibility to use the simple
# form (vs. 8995-A). VERIFY: IRS draft i8995--dft.pdf says $197,300 single /
# $394,600 MFJ; secondary sources conflict. Team-lead stated $241,950 single
# which was the 2024 value. Confirm before merging.
#
# SOURCE (draft): https://www.irs.gov/pub/irs-dft/i8995--dft.pdf
QBI_SIMPLE_THRESHOLD_2025 = {
    "single": Decimal("197300"),       # VERIFY
    "mfj": Decimal("394600"),          # VERIFY
    "hoh": Decimal("197300"),          # VERIFY
    "mfs": Decimal("197300"),          # VERIFY (usually half MFJ; check IRS)
    "qss": Decimal("394600"),          # VERIFY
}


def qbi_contribution(k1: K1Like) -> Decimal:
    """The QBI amount this K-1 contributes to Form 8995 aggregation.

    Box mapping:
      - 1120-S box 17 code V (section 199A information).
      - 1065 box 20 code Z (section 199A information).
      - 1041 box 14 code I (section 199A information).

    SOURCE: 2025 Instructions for Form 8995 — "Determining Your Qualified
    Business Income" subsection under Pass-Through Entity reporting.

    Scope caveats (see README):
      - SSTB limitation not applied here (requires taxable income test
        against QBI_SIMPLE_THRESHOLD_2025 — out of oracle scope; caller
        handles).
      - REIT dividends (Form 8995 line 6) and PTP income are separate
        inputs, not K-1 box amounts; not produced here.
    """
    raise NotImplementedError("Pending ScheduleK1 schema from team-lead.")


# ---------------------------------------------------------------------------
# Passive flag (Form 8582 determination)
# ---------------------------------------------------------------------------
def passive_flag(k1: K1Like) -> PassiveFlag:
    """Classify this K-1 activity as passive or nonpassive.

    Rules (simplified — real determination involves 7 material-participation
    tests under Reg. §1.469-5T; production should defer to taxpayer assertion
    captured on ``ScheduleK1.material_participation``):

      - Ordinary business income (box 1): NONPASSIVE if
        ``material_participation`` is True, else PASSIVE.
      - Rental real estate (box 2): PASSIVE by default for all shareholders
        / partners / beneficiaries, EXCEPT if the owner is a real estate
        professional who materially participates in the specific rental.
      - Other rentals (box 3): PASSIVE for all (§469(c)(2)).

    SOURCE: 2025 Instructions for Form 8582 — "Activities That Are Not Passive
    Activities" and "Material Participation" subsections. Also 2025
    Instructions for Schedule K-1 (1120-S) box 2 commentary.

    Out of scope for v1 (flagged in README):
      - Real estate professional exemption (§469(c)(7)): 750-hour + >50%
        personal services test. Oracle accepts a separate caller-supplied
        flag rather than re-deriving.
      - Grouping elections (Rev. Proc. 2010-13).
    """
    raise NotImplementedError("Pending ScheduleK1 schema from team-lead.")


# ---------------------------------------------------------------------------
# Form 8582 — $25k special allowance (rental real estate active participation)
# ---------------------------------------------------------------------------
SPECIAL_ALLOWANCE_CAP = Decimal("25000")      # §469(i)(2)
SPECIAL_ALLOWANCE_PHASEOUT_START = Decimal("100000")  # §469(i)(3)
SPECIAL_ALLOWANCE_PHASEOUT_END = Decimal("150000")
SPECIAL_ALLOWANCE_MFS_CAP = Decimal("12500")  # MFS living apart all year
SPECIAL_ALLOWANCE_MFS_PHASEOUT_START = Decimal("50000")
SPECIAL_ALLOWANCE_MFS_PHASEOUT_END = Decimal("75000")


def special_allowance(magi: Decimal, filing_status: str) -> Decimal:
    """Compute the $25,000 special allowance for active-participation
    rental real estate losses, phased out between $100,000–$150,000 MAGI.

    SOURCE: 2025 Instructions for Form 8582, Part II "Special Allowance for
    Rental Real Estate Activities With Active Participation", and IRC
    §469(i).

    Phaseout: allowance reduced by 50% of (MAGI − $100,000), floored at 0.
    i.e. allowance = max(0, 25000 − 0.5 * max(0, MAGI − 100000))
    For MFS living apart: cap $12,500, phaseout $50k–$75k.
    For MFS living together at any point: not eligible (returns 0).
    """
    raise NotImplementedError("Pending inputs from team-lead schema attach.")


# ---------------------------------------------------------------------------
# 1099-G (state refund taxability) — a small extra the team-lead listed
# ---------------------------------------------------------------------------
# 1099-G box 2 (state income tax refunds) is taxable to the extent the prior
# year's state tax produced a federal tax benefit via Schedule A itemized
# deduction. See "Tax Benefit Rule" worksheet in 2025 Schedule 1 instructions
# for line 1.
#
# SOURCE: 2025 Instructions for Schedule 1 (Form 1040), line 1 "Taxable
# refunds, credits, or offsets of state and local income taxes" — references
# Pub. 525 "State tax refund" worksheet.
#
# Stub only — implementation pending schema + prior-year context.


__all__ = [
    "K1Like",
    "PassiveFlag",
    "ScheduleEColumn",
    "ScheduleERow",
    "ScheduleBAdditions",
    "ScheduleDAdditions",
    "QBI_SIMPLE_THRESHOLD_2025",
    "SPECIAL_ALLOWANCE_CAP",
    "SPECIAL_ALLOWANCE_PHASEOUT_START",
    "SPECIAL_ALLOWANCE_PHASEOUT_END",
    "SPECIAL_ALLOWANCE_MFS_CAP",
    "SPECIAL_ALLOWANCE_MFS_PHASEOUT_START",
    "SPECIAL_ALLOWANCE_MFS_PHASEOUT_END",
    "schedule_e_part_ii_row",
    "schedule_b_additions",
    "schedule_d_additions",
    "qbi_contribution",
    "passive_flag",
    "special_allowance",
]
