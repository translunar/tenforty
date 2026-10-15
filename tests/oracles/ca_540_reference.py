"""California FTB Form 540 + Schedule CA (540) reference oracle, tax year 2025.

Independent reference implementation. Given a ``CA540Input`` dataclass, compute
every numbered line on Form 540 and Schedule CA (540) that the oracle models,
so production code has something to cross-check against. The oracle reads the
2025 FTB instructions directly; divergence between this module and production
is the signal the harness watches for.

This module intentionally does not import from the production ``tenforty/``
package. The only shared surface is the input dataclass schema (mirroring
whatever production will expose) — no behavior is shared.

### Numeric type

``float`` per the federal oracle contract. Sub-cent precision loss is accepted;
the comparison harness rounds to the nearest cent (or dollar, FTB-style) before
comparing. No rounding happens inside the oracle; rounding is production's job
and will vary by line (FTB uses "whole-dollar with rounding" on most lines).

### Output contract

``compute_ca_540(ca_input)`` returns a flat ``dict[str, float | bool]`` keyed by
``f540_line_<N>_<semantic>`` and ``schca_part_<N>_line_<M>_<col>_<semantic>``
entries. A test harness can diff the dict against production output directly.

### Scope

See ``README.md`` for in-scope / out-of-scope lines, ambiguities, and citation
lineage. Anything out of scope either:
  - raises ``NotImplementedError`` from ``_gate_scope`` (hard fail), or
  - is documented inline as "caller supplies X", where the oracle accepts a
    precomputed value and does not attempt to derive it.

### Citation convention

Every rule below carries a ``SOURCE:`` comment pointing at an FTB paragraph so
annual refresh (rediffing against TY2026 instructions) is mechanical.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Literal

FilingStatus = Literal["single", "mfj", "mfs", "hoh", "qss"]


# ---------------------------------------------------------------------------
# Constants — TY2025
#
# VERIFY note: direct FTB.ca.gov access was blocked (HTTP 403) during oracle
# research; figures below were extracted from the FTB 540 booklet PDF via a
# tax-form mirror and cross-referenced against the 3% annual indexing pattern
# applied to TY2024 published values. CPA confirmation required on any figure
# tagged VERIFY before a downstream consumer trusts it.
#
# Re-verified 2026-10-14 against the FTB-direct booklet recorded in
# CA_540_BOOKLET_2025_PROVENANCE (below): standard deduction chart (p. 13),
# exemption credit preprints (Form 540 side 1), AGI Limitation Worksheet
# thresholds (p. 14), Schedules X/Y/Z (p. 75) — all match. Renter's credit
# AGI limits did NOT match and were corrected (see that block).
# ---------------------------------------------------------------------------

# SOURCE: FTB 2025 Form 540 instructions, "Standard Deduction" worksheet.
# Dependent-floor $1,350 per FTB 540 Booklet instruction (inherits federal
# "earned income + $450" base with CA's own $1,350 minimum).
STANDARD_DEDUCTION_2025: dict[str, float] = {
    "single": 5_706.0,
    "mfs":    5_706.0,
    "mfj":    11_412.0,
    "hoh":    11_412.0,
    "qss":    11_412.0,
}
DEPENDENT_STANDARD_DEDUCTION_MIN_2025 = 1_350.0
DEPENDENT_STANDARD_DEDUCTION_EARNED_BUMP_2025 = 450.0  # federal-tied; unindexed

# SOURCE: FTB 2025 Form 540 instructions, line 7/8/9/10 ("Exemption credits").
# Per-person credits: $153 personal/blind/senior, $475 per dependent. MFJ/QSS
# line 7 is exactly 2 × $153 = $306 — the Form 540 face preprint reads
# "[count] × $153" and the filer multiplies the per-person amount by the
# count themselves; there is no filing-status-specific dollar preprint and
# no rounding quirk.
EXEMPTION_CREDIT_PERSONAL_2025 = 153.0
EXEMPTION_CREDIT_BLIND_2025 = 153.0
EXEMPTION_CREDIT_SENIOR_2025 = 153.0
EXEMPTION_CREDIT_DEPENDENT_2025 = 475.0

# SOURCE: FTB 2025 Form 540 instructions, "AGI Limitation Worksheet" (line 32
# exemption credit phaseout) and Schedule CA (540) Part II "Itemized
# Deductions Worksheet" (line 29 phaseout). Same thresholds apply to both.
AGI_PHASEOUT_THRESHOLD_2025: dict[str, float] = {
    "single": 252_203.0,
    "mfs":    252_203.0,
    "hoh":    378_310.0,
    "mfj":    504_411.0,
    "qss":    504_411.0,
}
# Per-block reduction: $6 per $2,500 over threshold per exemption-credit count.
# MFS divisor is $1,250 (half the block size).
EXEMPTION_PHASEOUT_BLOCK_2025 = 2_500.0
EXEMPTION_PHASEOUT_BLOCK_MFS_2025 = 1_250.0
EXEMPTION_PHASEOUT_REDUCTION_PER_BLOCK_2025 = 6.0

# Itemized-deduction phaseout: lesser of (6% × excess over threshold) or
# (80% × non-protected itemized). Same threshold as above.
ITEMIZED_PHASEOUT_EXCESS_RATE = 0.06
ITEMIZED_PHASEOUT_CAP_RATE = 0.80

# SOURCE: FTB 2025 Form 540 instructions, line 31 tax-method decision.
# Tax table applies when line 19 ≤ $100,000; tax rate schedules otherwise.
TAX_TABLE_CUTOFF_2025 = 100_000.0

# SOURCE: FTB 2025 Tax Rate Schedules (Schedule X single/MFS; Schedule Y
# MFJ/QSS; Schedule Z HOH). Each entry is (over, base_tax, rate_on_excess).
# The first bracket's "over" is 0. Brackets are evaluated until the filer's
# line 19 is less than the next bracket's threshold.
_RateBracket = tuple[float, float, float]

TAX_RATE_SCHEDULE_X_2025: list[_RateBracket] = [  # Single / MFS
    (0.0,         0.00,       0.01),
    (11_079.0,    110.79,     0.02),
    (26_264.0,    414.49,     0.04),
    (41_452.0,    1_022.01,   0.06),
    (57_542.0,    1_987.41,   0.08),
    (72_724.0,    3_201.97,   0.093),
    (371_479.0,   30_986.19,  0.103),
    (445_771.0,   38_638.27,  0.113),
    (742_953.0,   72_219.84,  0.123),
]
TAX_RATE_SCHEDULE_Y_2025: list[_RateBracket] = [  # MFJ / QSS
    (0.0,           0.00,         0.01),
    (22_158.0,      221.58,       0.02),
    (52_528.0,      828.98,       0.04),
    (82_904.0,      2_044.02,     0.06),
    (115_084.0,     3_974.82,     0.08),
    (145_448.0,     6_403.94,     0.093),
    (742_958.0,     61_972.37,    0.103),
    (891_542.0,     77_276.52,    0.113),
    (1_485_906.0,   144_439.65,   0.123),
]
TAX_RATE_SCHEDULE_Z_2025: list[_RateBracket] = [  # HOH
    (0.0,           0.00,        0.01),
    (22_173.0,      221.73,      0.02),
    (52_530.0,      828.87,      0.04),
    (67_716.0,      1_436.31,    0.06),
    (83_805.0,      2_401.65,    0.08),
    (98_990.0,      3_616.45,    0.093),
    (505_208.0,     41_394.72,   0.103),
    (606_251.0,     51_802.15,   0.113),
    (1_010_417.0,   97_472.91,   0.123),
]

# SOURCE: FTB 2025 Form 540 instructions, line 62.
# Behavioral Health Services Tax (renamed from Mental Health Services Tax for
# TY2025 under SB 711). 1% of taxable income over $1,000,000. Threshold is set
# by statute (R&TC §17043) and is NOT inflation-indexed.
BHST_THRESHOLD_2025 = 1_000_000.0
BHST_RATE_2025 = 0.01

# SOURCE: FTB 2025 Form 540 instructions, line 46 (Nonrefundable Renter's
# Credit). Hard AGI cliff, no phaseout. AGI limits re-verified against the
# FTB-direct booklet (see CA_540_BOOKLET_2025_PROVENANCE), page 25,
# Nonrefundable Renter's Credit Qualification Record question 2; the earlier
# mirror-derived limits did not match the booklet and were corrected.
RENTERS_CREDIT_SINGLE_MFS_2025 = 60.0
RENTERS_CREDIT_HOUSEHOLD_2025 = 120.0
RENTERS_CREDIT_AGI_LIMIT_SINGLE_MFS_2025 = 53_994.0
RENTERS_CREDIT_AGI_LIMIT_HOUSEHOLD_2025 = 107_988.0

# SOURCE: FTB 2025 Schedule CA (540) instructions, Part II line 5e.
# California does NOT apply the federal SALT cap. The federal cap for TY2025
# (OBBBA) is $40,000 ($20,000 MFS) with a $500k MAGI phaseout. The oracle
# needs the pre-cap federal SALT total and the post-cap (federally deducted)
# SALT total to compute the col C add-back correctly; see the
# ``fed_sch_a_state_and_local_tax_pre_cap`` and ``fed_sch_a_salt_capped_total``
# fields on CA540Input.
#
# SOURCE: FTB 2025 Schedule CA (540) instructions, Part II line 8.
# California mortgage-interest acquisition-debt limit is the pre-TCJA
# $1,000,000 ($500,000 MFS). Federal TY2025 limit is $750,000 (OBBBA made the
# TCJA cap permanent). The caller supplies ``mortgage_interest_over_ca_cap``
# already computed on a CA basis (i.e., the CA-permitted excess over the
# federal $750k cap).
CA_MORTGAGE_ACQUISITION_DEBT_CAP = 1_000_000.0
CA_MORTGAGE_ACQUISITION_DEBT_CAP_MFS = 500_000.0


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------
# Grouped by topic to keep the field surface navigable. Every field is
# required (no defaults) so a scenario cannot silently omit data. The test
# harness must construct a full input explicitly — matches tenforty's
# "no silent fallthrough" design principle (iron law 2).
#
# Amount fields are ``float``; boolean fields are ``bool``; integer counts
# are ``int``. Monetary conventions:
#   - Income/deduction amounts are always positive unless explicitly a loss.
#   - "Losses" on the input side are NOT magnitudes; a $5,000 loss is -5_000.0.
#   - Column B / Column C adjustments on Schedule CA are POSITIVE magnitudes
#     (FTB convention — the form has separate add/subtract columns).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Demographics:
    """Filing status and personal-exemption inputs.

    ``can_be_claimed_as_dependent`` is the primary taxpayer's checkbox on
    Form 540 line 6. ``spouse_can_be_claimed_as_dependent`` is the
    analogous flag for the spouse/RDP on a joint return (FTB worksheet
    line 7, "Married/RDP filing jointly and only one spouse/RDP can be
    claimed as a dependent" sub-case). For non-MFJ filing statuses
    (single / MFS / HOH / QSS) the spouse flag is not meaningful and
    producers should pass False; the oracle ignores it in those cases.
    """
    filing_status: FilingStatus
    can_be_claimed_as_dependent: bool
    spouse_can_be_claimed_as_dependent: bool
    taxpayer_age_65_or_older: bool
    spouse_age_65_or_older: bool
    taxpayer_blind: bool
    spouse_blind: bool
    dependent_count: int
    # Taxpayer's own earned income, per the federal dependent Standard
    # Deduction Worksheet line 5 definition (IRS Pub 501: wages, salaries,
    # tips, professional fees, net self-employment compensation; excludes
    # interest, dividends, capital gains, pensions, non-taxable
    # scholarships). Only read when ``can_be_claimed_as_dependent`` is
    # True. Producers can pass 0.0 when the filer is not claimable as a
    # dependent; the standard-deduction computation ignores it in that
    # branch. SOURCE: FTB 2025 Form 540 Instructions, line 18
    # "Standard Deduction Worksheet for Dependents".
    dependent_earned_income: float


@dataclass(frozen=True)
class FederalCarryIn:
    """Federal amounts flowing into CA computation."""
    federal_agi: float  # Form 1040 line 11 → Form 540 line 13
    state_wages_from_w2_box16: float  # Form 540 line 12


@dataclass(frozen=True)
class SchCAPartIAdjustments:
    """Schedule CA (540) Part I column B (subtractions) and C (additions).

    Caller passes **per-line delta magnitudes** because the oracle doesn't
    attempt to re-derive CA adjustments from raw income documents — that
    logic lives in the production flattener + this oracle cross-checks the
    totals. Every field is the amount to apply to the named line/column.

    Where FTB has multiple potential drivers for a line (e.g., W-2 wage
    adjustments for treaty-excluded income, tribal income, IHSS, Sinai
    combat pay, HSA employer contribution), the caller sums those drivers
    into the single line/column delta.
    """
    # Section A lines (from federal 1040)
    # Line 1 — wages (CA col B subtractions and col C additions)
    line_1_col_b_wage_subtractions: float
    line_1_col_c_wage_additions: float
    # Line 2 — taxable interest
    line_2_col_b_us_obligation_interest: float
    line_2_col_c_non_ca_muni_interest: float
    # Line 3 — ordinary dividends (rarely adjusted)
    line_3_col_b_dividend_subtractions: float
    line_3_col_c_dividend_additions: float
    # Line 4 — IRA distributions
    line_4_col_b_ira_subtractions: float
    line_4_col_c_ira_additions: float
    # Line 5 — pensions and annuities (includes military retirement excl.)
    line_5_col_b_pension_subtractions: float
    line_5_col_c_pension_additions: float
    # Line 6 — Social Security benefits. CA never taxes SS → col B only.
    line_6_col_b_social_security_subtraction: float
    # Line 7 — capital gains (rarely adjusted in v1 scope)
    line_7_col_b_capital_gain_subtractions: float
    line_7_col_c_capital_gain_additions: float

    # Section B lines (from federal Schedule 1)
    # Line 1 — taxable state refund (CA never taxes → col B = full amount)
    line_sb_1_col_b_state_refund: float
    # Line 3 — business income adjustments (depreciation, §179, etc.)
    line_sb_3_col_b_business_subtractions: float
    line_sb_3_col_c_business_additions: float
    # Line 5 — rental/partnership/S-corp (depreciation, passive differences)
    line_sb_5_col_b_rental_subtractions: float
    line_sb_5_col_c_rental_additions: float
    # Line 7 — unemployment (CA never taxes → col B = full amount)
    line_sb_7_col_b_unemployment: float
    # Line 8 — other income (CA lottery excluded, mortgage forgiveness, etc.)
    line_sb_8_col_b_other_subtractions: float
    line_sb_8_col_c_other_additions: float

    # Section C — adjustments to income (from federal Schedule 1 Part II)
    # Line 13 — HSA deduction (CA always adds back the federal deduction)
    line_sc_13_col_b_hsa_deduction_addback: float
    # Line 14 — moving expenses (CA allows non-military)
    line_sc_14_col_c_moving_expenses: float
    # Line 21 — student loan interest (rarely adjusted but supported)
    line_sc_21_col_b_student_loan_subtractions: float
    line_sc_21_col_c_student_loan_additions: float
    # Line 24z — other adjustments
    line_sc_24z_col_b_other_adj_subtractions: float
    line_sc_24z_col_c_other_adj_additions: float


@dataclass(frozen=True)
class SchCAPartIIAdjustments:
    """Schedule CA (540) Part II — CA itemized deduction recomputation.

    Caller passes the federal Schedule A line items and the CA-specific
    adjustments. The oracle computes lines 4, 7, 10, 14, 18, 22, 25, 26, 28,
    29, and 30 from these inputs.
    """
    # Federal Schedule A pre-SALT-cap values
    fed_sch_a_medical_expenses: float  # Sch A line 1
    fed_sch_a_state_and_local_tax_pre_cap: float  # Sch A line 5d (before federal cap)
    fed_sch_a_state_income_tax: float  # subset of line 5d → CA col B subtraction
    fed_sch_a_foreign_income_tax: float  # Sch A line 6 portion attributable to foreign
    fed_sch_a_foreign_real_property_tax: float  # Sch A line 6 allowed for CA, not fed
    fed_sch_a_generation_skipping_tax: float  # Sch A line 6 portion (CA disallows)
    fed_sch_a_salt_capped_total: float  # Sch A line 7 (after federal $40k cap)
    fed_sch_a_mortgage_interest_on_1098: float  # Sch A line 8a
    fed_sch_a_mortgage_interest_not_on_1098: float  # Sch A line 8b
    fed_sch_a_points_not_on_1098: float  # Sch A line 8c
    fed_sch_a_mortgage_interest_federally_limited_excess: float  # addback for CA's higher cap
    fed_sch_a_home_equity_interest_federally_disallowed: float  # addback for CA
    fed_sch_a_mortgage_interest_credit_reduction: float  # federal Form 8396 reduction
    fed_sch_a_investment_interest: float  # Sch A line 9
    fed_sch_a_gifts_cash: float  # Sch A line 11
    fed_sch_a_gifts_noncash: float  # Sch A line 12
    fed_sch_a_gifts_carryover: float  # Sch A line 13
    fed_sch_a_casualty_federally_declared: float  # Sch A line 15
    fed_sch_a_gambling_losses: float  # subset of Sch A line 16 (ordinary gambling)
    fed_sch_a_other_itemized_excl_gambling: float  # Sch A line 16 minus gambling

    # CA-specific deltas (col B subtractions / col C additions)
    medical_col_c_sehi_itemized: float  # self-employed health insurance reclassified
    medical_col_c_hsa_qualified_dist_over_floor: float  # HSA med distributions
    charitable_col_b_conservation_contribution_over_30pct: float  # CA caps at 30%
    charitable_col_b_ca_access_tax_credit_donation: float  # used for CA credit
    charitable_col_c_college_seating: float  # federal disallows; CA allows
    charitable_col_b_noncash_over_50pct: float
    charitable_col_c_charitable_carryover_difference: float
    charitable_col_b_charitable_carryover_difference: float
    casualty_ca_nonfederal_declared: float  # CA allows, federal suspended
    gambling_col_b_ca_lottery_losses: float  # CA lottery losses not deductible
    other_itemized_col_b_estate_tax_on_ird: float  # CA disallows

    # CA-only line 22 (misc 2%-floor subject deductions — federally suspended)
    ca_unreimbursed_employee_expenses: float
    ca_tax_preparation_fees: float
    ca_other_investment_and_misc_expenses: float

    # Line 27 — other adjustments (rare)
    line_27_other_adjustments: float  # signed: positive adds, negative subtracts

    itemize: bool  # True if caller chose to itemize for CA


@dataclass(frozen=True)
class Form540Payments:
    """Form 540 lines 71–77 (withholding, estimated payments, state credits)."""
    line_71_ca_withholding: float  # W-2 box 17, 1099 CA withholding
    line_72_estimated_payments_and_carryover: float
    line_73_592b_593_withholding: float
    line_74_motion_picture_credit: float  # FTB 3541 refundable portion
    line_75_eitc: float  # caller computes via FTB 3514; out of scope to derive
    line_76_yctc: float
    line_77_fytc: float


@dataclass(frozen=True)
class Form540Credits:
    """Nonrefundable credits the oracle models (v1 = dep-care + renter's)."""
    # Line 40 — Nonrefundable Child & Dependent Care Expenses Credit.
    # Eligibility: federal AGI ≤ $100,000; caller computes amount via FTB 3506.
    dep_care_federal_agi_for_eligibility: float
    dep_care_credit_amount: float  # caller supplies; oracle enforces AGI gate

    # Line 46 — Nonrefundable Renter's Credit.
    eligible_for_renters_credit: bool

    # Line 43/44/45 — other special credits the caller precomputed.
    other_nonrefundable_credits: float


@dataclass(frozen=True)
class Form540OtherTaxes:
    """Line 63 other taxes (caller precomputes; oracle doesn't derive)."""
    # Includes early-withdrawal add-ons (FTB 3805P), §409A NQDC, §453A
    # installment interest, and recapture (FTB 3531/3540/3554/3835).
    line_63_other_taxes: float


@dataclass(frozen=True)
class Form540Misc:
    """Remaining Form 540 inputs — use tax, contributions, amount applied."""
    line_91_use_tax: float
    line_98_overpayment_applied_to_2026: float  # of line 97
    line_110_voluntary_contributions: float


@dataclass(frozen=True)
class ScopeOut:
    """Inputs that cause the oracle to raise loudly when nonzero/True.

    Matches tenforty's production "reject unknown forms" gate pattern. The
    oracle does NOT silently handle these; it errors so the harness knows
    it's looking at an unsupported scenario.
    """
    amt_preferences_present: bool  # Schedule P (540) — out of scope v1
    lump_sum_distribution_tax: float  # Schedule G-1
    accumulation_distribution_tax: float  # FTB 5870A
    kiddie_tax_child_filer: bool  # FTB 3800 / FTB 3803
    nol_deduction: float  # FTB 3805V / 3805Z / 3807 / 3809
    excess_business_loss_adjustment: float  # FTB 3461
    isr_penalty: float  # FTB 3853 (individual shared-responsibility)
    underpayment_penalty: float  # FTB 5805 / 5805F


@dataclass(frozen=True)
class CA540Input:
    """Top-level oracle input. Every CA 540 computation starts here."""
    demographics: Demographics
    federal: FederalCarryIn
    sch_ca_part_i: SchCAPartIAdjustments
    sch_ca_part_ii: SchCAPartIIAdjustments
    payments: Form540Payments
    credits: Form540Credits
    other_taxes: Form540OtherTaxes
    misc: Form540Misc
    scope_out: ScopeOut


# ---------------------------------------------------------------------------
# Scope gates
# ---------------------------------------------------------------------------
def _gate_scope(ca: CA540Input) -> None:
    """Raise NotImplementedError if the scenario triggers an unmodeled feature.

    Aligns with tenforty's production flattener "reject unknown forms" pattern
    and iron law 2 (no silent fallthrough). The caller MUST resolve every
    out-of-scope item explicitly rather than letting the oracle produce an
    incomplete answer.
    """
    s = ca.scope_out
    if s.amt_preferences_present:
        raise NotImplementedError(
            "CA 540 oracle does not compute AMT (Schedule P (540))."
        )
    if s.lump_sum_distribution_tax != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute Schedule G-1 alternative tax."
        )
    if s.accumulation_distribution_tax != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute FTB 5870A accumulation distribution tax."
        )
    if s.kiddie_tax_child_filer:
        raise NotImplementedError(
            "CA 540 oracle does not compute FTB 3800 / FTB 3803 (kiddie tax)."
        )
    if s.nol_deduction != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute NOL deductions (FTB 3805V/3805Z/3807/3809)."
        )
    if s.excess_business_loss_adjustment != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute FTB 3461 excess business loss adjustment."
        )
    if s.isr_penalty != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute FTB 3853 ISR penalty."
        )
    if s.underpayment_penalty != 0.0:
        raise NotImplementedError(
            "CA 540 oracle does not compute FTB 5805/5805F underpayment penalty."
        )


# ---------------------------------------------------------------------------
# Schedule CA (540) Part I — income adjustments
# ---------------------------------------------------------------------------
def _schedule_ca_part_i(ca: CA540Input) -> dict[str, float]:
    """Compute Schedule CA (540) Part I line 27 column B and column C totals.

    SOURCE: FTB 2025 Schedule CA (540) instructions, Part I Sections A/B/C.
    The oracle sums every per-line delta the caller supplied into line 27.
    Individual line-level outputs are included so the harness can diff at the
    line level rather than only on the aggregate.
    """
    p1 = ca.sch_ca_part_i

    # Section A per-line totals
    sa_line_1_col_b = p1.line_1_col_b_wage_subtractions
    sa_line_1_col_c = p1.line_1_col_c_wage_additions
    sa_line_2_col_b = p1.line_2_col_b_us_obligation_interest
    sa_line_2_col_c = p1.line_2_col_c_non_ca_muni_interest
    sa_line_3_col_b = p1.line_3_col_b_dividend_subtractions
    sa_line_3_col_c = p1.line_3_col_c_dividend_additions
    sa_line_4_col_b = p1.line_4_col_b_ira_subtractions
    sa_line_4_col_c = p1.line_4_col_c_ira_additions
    sa_line_5_col_b = p1.line_5_col_b_pension_subtractions
    sa_line_5_col_c = p1.line_5_col_c_pension_additions
    sa_line_6_col_b = p1.line_6_col_b_social_security_subtraction
    sa_line_7_col_b = p1.line_7_col_b_capital_gain_subtractions
    sa_line_7_col_c = p1.line_7_col_c_capital_gain_additions

    # Section B per-line totals
    sb_line_1_col_b = p1.line_sb_1_col_b_state_refund
    sb_line_3_col_b = p1.line_sb_3_col_b_business_subtractions
    sb_line_3_col_c = p1.line_sb_3_col_c_business_additions
    sb_line_5_col_b = p1.line_sb_5_col_b_rental_subtractions
    sb_line_5_col_c = p1.line_sb_5_col_c_rental_additions
    sb_line_7_col_b = p1.line_sb_7_col_b_unemployment
    sb_line_8_col_b = p1.line_sb_8_col_b_other_subtractions
    sb_line_8_col_c = p1.line_sb_8_col_c_other_additions

    # Section C per-line totals (adjustments to income; these reduce AGI
    # when applied — col B = DISALLOW the federal deduction for CA purposes,
    # i.e. adds it back to income; col C = ALLOW a deduction CA permits but
    # federal doesn't, reducing CA AGI).
    #
    # FTB Schedule CA Part I mechanics:
    #   line 10 (total income) col B/C → summed
    #   line 25 (total adjustments to income) col B/C → summed
    #   line 27 = line 10 − line 25  per column
    # The total flows to Form 540 line 14 (col B → subtractions from federal
    # AGI) and line 16 (col C → additions to federal AGI). Despite the name,
    # a col B "subtraction" on an adjustment-to-income line adds to CA taxable
    # income (because federal got a deduction CA doesn't allow); the FTB form
    # arithmetic reconciles it via the line 27 subtraction of line 25.
    sc_line_13_col_b = p1.line_sc_13_col_b_hsa_deduction_addback
    sc_line_14_col_c = p1.line_sc_14_col_c_moving_expenses
    sc_line_21_col_b = p1.line_sc_21_col_b_student_loan_subtractions
    sc_line_21_col_c = p1.line_sc_21_col_c_student_loan_additions
    sc_line_24z_col_b = p1.line_sc_24z_col_b_other_adj_subtractions
    sc_line_24z_col_c = p1.line_sc_24z_col_c_other_adj_additions

    # Line 10: total income adjustments (sum of Sections A and B lines).
    line_10_col_b = (
        sa_line_1_col_b + sa_line_2_col_b + sa_line_3_col_b + sa_line_4_col_b
        + sa_line_5_col_b + sa_line_6_col_b + sa_line_7_col_b
        + sb_line_1_col_b + sb_line_3_col_b + sb_line_5_col_b + sb_line_7_col_b
        + sb_line_8_col_b
    )
    line_10_col_c = (
        sa_line_1_col_c + sa_line_2_col_c + sa_line_3_col_c + sa_line_4_col_c
        + sa_line_5_col_c + sa_line_7_col_c
        + sb_line_3_col_c + sb_line_5_col_c + sb_line_8_col_c
    )

    # Line 25/26: total adjustments to income (Section C).
    line_25_col_b = sc_line_13_col_b + sc_line_21_col_b + sc_line_24z_col_b
    line_25_col_c = sc_line_14_col_c + sc_line_21_col_c + sc_line_24z_col_c
    # Line 26 = line 25 (simple sum); FTB form has separate "total
    # adjustments" and "total other adjustments" lines. Combined here.
    line_26_col_b = line_25_col_b
    line_26_col_c = line_25_col_c

    # Line 27 per column = line 10 − line 26.
    # SOURCE: FTB 2025 Schedule CA (540) Part I, "Total" line.
    line_27_col_b = line_10_col_b - line_26_col_b
    line_27_col_c = line_10_col_c - line_26_col_c

    return {
        "schca_part_1_line_10_col_b": line_10_col_b,
        "schca_part_1_line_10_col_c": line_10_col_c,
        "schca_part_1_line_25_col_b": line_25_col_b,
        "schca_part_1_line_25_col_c": line_25_col_c,
        "schca_part_1_line_26_col_b": line_26_col_b,
        "schca_part_1_line_26_col_c": line_26_col_c,
        "schca_part_1_line_27_col_b": line_27_col_b,
        "schca_part_1_line_27_col_c": line_27_col_c,
    }


# ---------------------------------------------------------------------------
# Schedule CA (540) Part II — itemized-deduction adjustments
# ---------------------------------------------------------------------------
def _schedule_ca_part_ii(ca: CA540Input) -> dict[str, float]:
    """Compute Schedule CA (540) Part II itemized-deduction figures.

    SOURCE: FTB 2025 Schedule CA (540) instructions, Part II lines 1–30.

    Returns line 30 (CA itemized deduction, or standard deduction if larger)
    which flows to Form 540 line 18. Also returns the intermediate line
    values for harness-level diffing.
    """
    p2 = ca.sch_ca_part_ii
    fs = ca.demographics.filing_status

    # Medical (line 1–4)
    line_1_col_a = p2.fed_sch_a_medical_expenses
    line_1_col_c = (
        p2.medical_col_c_sehi_itemized
        + p2.medical_col_c_hsa_qualified_dist_over_floor
    )
    # Line 2 = federal AGI; line 3 = line 2 × 7.5%; line 4 = line 1 − line 3
    # applied per-column on the CA-adjusted total.
    line_2 = ca.federal.federal_agi
    line_3 = line_2 * 0.075
    line_1_ca_total = line_1_col_a + line_1_col_c  # col B is 0 for medical in v1
    line_4_ca_medical = max(line_1_ca_total - line_3, 0.0)

    # Taxes (line 5a–5e, 6, 7)
    # CA adjusts line 5d (federal SALT total before cap) down by state income
    # tax (col B) and up by anything above the federal cap (col C).
    line_5a_col_a = (
        p2.fed_sch_a_state_and_local_tax_pre_cap  # rough — refined below
    )
    # col B subtraction for line 5a = state income tax (always disallowed)
    line_5a_col_b = p2.fed_sch_a_state_income_tax
    # Line 5d = federal sum before cap; line 7 = sum of 5e and 6.
    # For CA, we don't apply the federal $40k cap; so the CA-side line 5e =
    # full state-and-local tax total MINUS state income tax (col B).
    #
    # SOURCE: Schedule CA (540) TY2025 instructions, Part II line 5e:
    # "If your federal deduction was limited, enter in column C the amount
    # over the federal limit."
    ca_salt_pre_limit = p2.fed_sch_a_state_and_local_tax_pre_cap - line_5a_col_b
    # Col C addition to restore amount above federal cap.
    line_5e_col_c = max(
        p2.fed_sch_a_state_and_local_tax_pre_cap - p2.fed_sch_a_salt_capped_total,
        0.0,
    )
    # CA-basis line 5e value = the uncapped total of non-state-income-tax
    # SALT components.
    line_5e_ca = ca_salt_pre_limit

    # Line 6: other taxes. CA disallows foreign income tax (col B) and
    # generation-skipping transfer tax (col B); CA allows foreign real
    # property tax (col C) where federal post-TCJA does not.
    line_6_col_b = (
        p2.fed_sch_a_foreign_income_tax + p2.fed_sch_a_generation_skipping_tax
    )
    line_6_col_c = p2.fed_sch_a_foreign_real_property_tax
    line_6_ca = line_6_col_c - line_6_col_b  # signed adjustment from federal

    # Line 7 = 5e + 6 (CA basis).
    line_7_ca_taxes = line_5e_ca + line_6_ca

    # Interest (line 8, 9, 10)
    line_8a_col_a = p2.fed_sch_a_mortgage_interest_on_1098
    line_8b_col_a = p2.fed_sch_a_mortgage_interest_not_on_1098
    line_8c_col_a = p2.fed_sch_a_points_not_on_1098
    line_8e_col_a = line_8a_col_a + line_8b_col_a + line_8c_col_a
    # Col C additions: excess over federal $750k cap (CA allows up to $1M);
    # home-equity interest federally disallowed (CA allows); Form 8396
    # mortgage interest credit reduction (add back for CA).
    line_8e_col_c = (
        p2.fed_sch_a_mortgage_interest_federally_limited_excess
        + p2.fed_sch_a_home_equity_interest_federally_disallowed
        + p2.fed_sch_a_mortgage_interest_credit_reduction
    )
    line_8e_ca = line_8e_col_a + line_8e_col_c
    line_9_ca_investment_interest = p2.fed_sch_a_investment_interest
    line_10_ca_interest = line_8e_ca + line_9_ca_investment_interest

    # Charitable (line 11, 12, 13, 14)
    line_11_col_a = p2.fed_sch_a_gifts_cash
    line_11_col_b = p2.charitable_col_b_ca_access_tax_credit_donation
    line_11_col_c = p2.charitable_col_c_college_seating
    line_12_col_a = p2.fed_sch_a_gifts_noncash
    line_12_col_b = (
        p2.charitable_col_b_conservation_contribution_over_30pct
        + p2.charitable_col_b_noncash_over_50pct
    )
    line_13_col_a = p2.fed_sch_a_gifts_carryover
    line_13_col_b = p2.charitable_col_b_charitable_carryover_difference
    line_13_col_c = p2.charitable_col_c_charitable_carryover_difference
    line_14_ca = (
        (line_11_col_a + line_11_col_c - line_11_col_b)
        + (line_12_col_a - line_12_col_b)
        + (line_13_col_a + line_13_col_c - line_13_col_b)
    )

    # Casualty (line 15)
    # CA allows nonfederally-declared losses; federal only allows
    # federally-declared.
    line_15_ca = (
        p2.fed_sch_a_casualty_federally_declared + p2.casualty_ca_nonfederal_declared
    )

    # Other itemized (line 16)
    # Includes gambling losses (up to winnings); CA lottery losses NOT
    # deductible for CA → col B; federal estate tax on IRD NOT deductible for
    # CA → col B.
    line_16_col_a = (
        p2.fed_sch_a_gambling_losses + p2.fed_sch_a_other_itemized_excl_gambling
    )
    line_16_col_b = (
        p2.gambling_col_b_ca_lottery_losses
        + p2.other_itemized_col_b_estate_tax_on_ird
    )
    line_16_ca = line_16_col_a - line_16_col_b

    # Line 17 = 4 + 7 + 10 + 14 + 15 + 16 (CA basis).
    line_17_ca = (
        line_4_ca_medical
        + line_7_ca_taxes
        + line_10_ca_interest
        + line_14_ca
        + line_15_ca
        + line_16_ca
    )

    # Line 18 = line 17 after col-level netting. Already computed CA-basis.
    line_18_ca = line_17_ca

    # Line 22: CA-only misc 2%-floor subject deductions (fed suspended).
    line_19 = p2.ca_unreimbursed_employee_expenses
    line_20 = p2.ca_tax_preparation_fees
    line_21 = p2.ca_other_investment_and_misc_expenses
    line_22_ca_misc_total = line_19 + line_20 + line_21
    # Line 23 = federal AGI; line 24 = line 23 × 2%; line 25 = max(22 − 24, 0).
    line_23 = ca.federal.federal_agi
    line_24 = line_23 * 0.02
    line_25_ca = max(line_22_ca_misc_total - line_24, 0.0)

    # Line 26 = 18 + 25.
    line_26_ca = line_18_ca + line_25_ca

    # Line 27: other adjustments (signed).
    line_27_other = p2.line_27_other_adjustments

    # Line 28 = 26 + 27.
    line_28_ca = line_26_ca + line_27_other

    # Line 29: AGI-based phaseout per worksheet.
    # SOURCE: FTB 2025 Schedule CA (540) instructions, "Itemized Deductions
    # Worksheet" (California Itemized Deduction Phaseout).
    threshold = AGI_PHASEOUT_THRESHOLD_2025[fs]
    protected = (
        line_4_ca_medical
        + line_9_ca_investment_interest
        + line_15_ca
        + p2.fed_sch_a_gambling_losses
    )
    unprotected = max(line_28_ca - protected, 0.0)
    excess_agi = max(ca.federal.federal_agi - threshold, 0.0)
    reduction = min(
        unprotected * ITEMIZED_PHASEOUT_CAP_RATE,
        excess_agi * ITEMIZED_PHASEOUT_EXCESS_RATE,
    )
    # If unprotected == 0 OR excess_agi == 0, no reduction.
    if unprotected == 0.0 or excess_agi == 0.0:
        reduction = 0.0
    line_29_ca_itemized = line_28_ca - reduction

    # Line 30: larger of line 29 or CA standard deduction (with MFS exception
    # — if MFS and spouse itemizes, filer must use line 29 regardless).
    standard = _ca_standard_deduction(ca)
    if p2.itemize:
        line_30_ca_deduction = line_29_ca_itemized
    else:
        line_30_ca_deduction = max(line_29_ca_itemized, standard)

    return {
        "schca_part_2_line_4_ca_medical": line_4_ca_medical,
        "schca_part_2_line_5e_ca_salt": line_5e_ca,
        "schca_part_2_line_7_ca_taxes": line_7_ca_taxes,
        "schca_part_2_line_10_ca_interest": line_10_ca_interest,
        "schca_part_2_line_14_ca_charitable": line_14_ca,
        "schca_part_2_line_15_ca_casualty": line_15_ca,
        "schca_part_2_line_16_ca_other": line_16_ca,
        "schca_part_2_line_17_ca_subtotal": line_17_ca,
        "schca_part_2_line_18_ca_net_itemized": line_18_ca,
        "schca_part_2_line_22_ca_misc_total": line_22_ca_misc_total,
        "schca_part_2_line_25_ca_misc_deductible": line_25_ca,
        "schca_part_2_line_26_ca_itemized_pre_phaseout": line_26_ca,
        "schca_part_2_line_27_other_adjustments": line_27_other,
        "schca_part_2_line_28_ca_itemized_pre_phaseout_adjusted": line_28_ca,
        "schca_part_2_line_29_ca_itemized_post_phaseout": line_29_ca_itemized,
        "schca_part_2_line_30_ca_deduction": line_30_ca_deduction,
    }


def _ca_standard_deduction(ca: CA540Input) -> float:
    """Compute the CA standard deduction for line 18.

    SOURCE: FTB 2025 Form 540 instructions, line 18
    "Standard Deduction Worksheet for Dependents" (used when the filer
    themselves can be claimed as a dependent on another return).

    Worksheet mechanics:
      line 1: federal earned income + $450
      line 2: CA floor $1,350
      line 3: greater of line 1 and line 2
      line 4: filing-status cap ($5,706 single/MFS; $11,412 MFJ/HOH/QSS)
      line 5: lesser of line 3 and line 4
    """
    fs = ca.demographics.filing_status
    base = STANDARD_DEDUCTION_2025[fs]
    if not ca.demographics.can_be_claimed_as_dependent:
        return base
    earned_base = (
        ca.demographics.dependent_earned_income
        + DEPENDENT_STANDARD_DEDUCTION_EARNED_BUMP_2025
    )
    greater = max(earned_base, DEPENDENT_STANDARD_DEDUCTION_MIN_2025)
    return min(greater, base)


# ---------------------------------------------------------------------------
# Form 540 lines 12–19 (income / CA AGI / deduction / taxable income)
# ---------------------------------------------------------------------------
def _form_540_income_and_taxable(
    ca: CA540Input,
    sch_ca_p1: dict[str, float],
    sch_ca_p2: dict[str, float],
) -> dict[str, float]:
    """Compute Form 540 lines 12–19.

    SOURCE: FTB 2025 Form 540 instructions, "Taxable Income" section.
    """
    line_12 = ca.federal.state_wages_from_w2_box16
    line_13 = ca.federal.federal_agi
    line_14 = sch_ca_p1["schca_part_1_line_27_col_b"]
    line_15 = line_13 - line_14
    line_16 = sch_ca_p1["schca_part_1_line_27_col_c"]
    line_17_ca_agi = line_15 + line_16
    line_18 = sch_ca_p2["schca_part_2_line_30_ca_deduction"]
    line_19 = max(line_17_ca_agi - line_18, 0.0)
    return {
        "f540_line_12_state_wages": line_12,
        "f540_line_13_federal_agi": line_13,
        "f540_line_14_ca_subtractions": line_14,
        "f540_line_15": line_15,
        "f540_line_16_ca_additions": line_16,
        "f540_line_17_ca_agi": line_17_ca_agi,
        "f540_line_18_deduction": line_18,
        "f540_line_19_taxable_income": line_19,
    }


# ---------------------------------------------------------------------------
# Tax (line 31) — tax table surrogate + tax rate schedules
# ---------------------------------------------------------------------------
def _tax_rate_schedule_for(fs: FilingStatus) -> list[_RateBracket]:
    """SOURCE: FTB 2025 Tax Rate Schedules. Schedule X for Single/MFS,
    Schedule Y for MFJ/QSS, Schedule Z for HOH."""
    if fs in ("single", "mfs"):
        return TAX_RATE_SCHEDULE_X_2025
    if fs in ("mfj", "qss"):
        return TAX_RATE_SCHEDULE_Y_2025
    if fs == "hoh":
        return TAX_RATE_SCHEDULE_Z_2025
    raise ValueError(f"unknown filing status: {fs}")


def _tax_from_rate_schedule(taxable: float, schedule: list[_RateBracket]) -> float:
    """Evaluate a tax-rate schedule on a taxable-income amount.

    The oracle does NOT reproduce the FTB tax table (midpoint-based lookup
    over $50 brackets) line-for-line; it applies the rate schedule directly.
    This means the oracle and FTB tax table will disagree by up to a few
    dollars for income ≤ $100,000 — the midpoint-vs-exact discrepancy. The
    harness should account for this ≈ $3 tolerance window for line 31 when
    line 19 ≤ $100,000.
    """
    if taxable <= 0.0:
        return 0.0
    applicable: _RateBracket = schedule[0]
    for bracket in schedule:
        if taxable > bracket[0]:
            applicable = bracket
        else:
            break
    over, base, rate = applicable
    return base + (taxable - over) * rate


def _form_540_tax(
    ca: CA540Input,
    income: dict[str, float],
) -> dict[str, float]:
    """Compute Form 540 lines 31–35 (tax before special credits)."""
    line_19 = income["f540_line_19_taxable_income"]
    fs = ca.demographics.filing_status

    # SOURCE: FTB 2025 Form 540 instructions, line 31. Below the tax-table
    # cutoff, FTB requires use of the tax table; above, rate schedules. The
    # oracle uses the rate schedule in both cases (see
    # ``_tax_from_rate_schedule`` docstring for the ≈$3 tolerance note).
    line_31_tax = _tax_from_rate_schedule(line_19, _tax_rate_schedule_for(fs))

    # Line 32 exemption credits — pre-phaseout sum then AGI-limitation.
    line_32_exemption_credits = _exemption_credits_after_phaseout(ca)

    # Line 33 = line 31 − line 32 (zero floor).
    line_33 = max(line_31_tax - line_32_exemption_credits, 0.0)

    # Line 34 — Schedule G-1 / FTB 5870A — gated out of scope by _gate_scope.
    line_34 = 0.0

    # Line 35 = line 33 + line 34.
    line_35 = line_33 + line_34

    return {
        "f540_line_31_tax": line_31_tax,
        "f540_line_32_exemption_credits": line_32_exemption_credits,
        "f540_line_33_tax_after_exemption_credits": line_33,
        "f540_line_34_lump_sum_tax": line_34,
        "f540_line_35_total_tax_before_special_credits": line_35,
    }


# ---------------------------------------------------------------------------
# Form 540 lines 7–11, 32 — exemption credits + AGI phaseout
# ---------------------------------------------------------------------------
def _count_exemptions(ca: CA540Input) -> tuple[int, int, int, int]:
    """Return (personal_count, senior_count, blind_count, dep_count).

    SOURCE: FTB 2025 Form 540 instructions, line 7 worksheet:
      "No" on line 6 → follow Form 540 line 7 instructions.
      "Yes" on line 6 (primary claimable) → enter:
        0 for single / MFS / HOH / QSS;
        0 for MFJ if both spouses claimable;
        1 for MFJ if only one spouse claimable.
    Lines 8 (blind) and 9 (senior) each carry the warning "Do not claim
    this credit if someone else can claim you as a dependent" — applied
    per-spouse on MFJ so a non-claimable spouse retains their own
    senior/blind credit.
    Line 10 (dependent) carries the same warning — dropped when the
    entire filing unit is claimable.
    """
    d = ca.demographics
    fs = d.filing_status
    prim = d.can_be_claimed_as_dependent
    spouse = d.spouse_can_be_claimed_as_dependent

    if fs == "mfj":
        personal = 2 - int(prim) - int(spouse)
    elif fs == "qss":
        personal = 0 if prim else 2
    else:
        personal = 0 if prim else 1

    senior = 0
    if d.taxpayer_age_65_or_older and not prim:
        senior += 1
    if fs == "mfj" and d.spouse_age_65_or_older and not spouse:
        senior += 1

    blind = 0
    if d.taxpayer_blind and not prim:
        blind += 1
    if fs == "mfj" and d.spouse_blind and not spouse:
        blind += 1

    unit_is_dependent = prim and (fs != "mfj" or spouse)
    dep = 0 if unit_is_dependent else max(d.dependent_count, 0)
    return personal, senior, blind, dep


def _exemption_credits_pre_phaseout(ca: CA540Input) -> tuple[float, float]:
    """Return (credits_from_lines_7_8_9, credits_from_line_10).

    Split because the AGI phaseout applies a separate $6/block reduction to
    each group.

    SOURCE: FTB 2025 Form 540 instructions, lines 7–10 and the AGI
    Limitation Worksheet.
    """
    personal, senior, blind, dep = _count_exemptions(ca)
    credits_789 = (
        personal * EXEMPTION_CREDIT_PERSONAL_2025
        + senior * EXEMPTION_CREDIT_SENIOR_2025
        + blind * EXEMPTION_CREDIT_BLIND_2025
    )
    credits_10 = dep * EXEMPTION_CREDIT_DEPENDENT_2025
    return credits_789, credits_10


def _exemption_credits_after_phaseout(ca: CA540Input) -> float:
    """Apply the AGI Limitation Worksheet to the exemption credits.

    SOURCE: FTB 2025 Form 540 instructions, "AGI Limitation Worksheet"
    accompanying line 32.

    Key mechanics:
      - threshold depends on filing status
      - block size is $2,500 ($1,250 if MFS)
      - "divide by block; round UP to whole number" (ceiling)
      - reduction = ceil_blocks × $6 × (credit_count for that group)
      - group A = personal + senior + blind credit counts (lines 7/8/9)
      - group B = dependent credit count (line 10)
      - apply reduction separately to the two groups' dollar amounts
    """
    d = ca.demographics
    fs = d.filing_status
    threshold = AGI_PHASEOUT_THRESHOLD_2025[fs]
    block = (
        EXEMPTION_PHASEOUT_BLOCK_MFS_2025 if fs == "mfs"
        else EXEMPTION_PHASEOUT_BLOCK_2025
    )
    excess = ca.federal.federal_agi - threshold

    credits_789, credits_10 = _exemption_credits_pre_phaseout(ca)

    if excess <= 0.0:
        return credits_789 + credits_10

    # Ceiling division by block.
    blocks = math.ceil(excess / block)
    per_count_reduction = blocks * EXEMPTION_PHASEOUT_REDUCTION_PER_BLOCK_2025

    personal, senior, blind, dep = _count_exemptions(ca)
    count_789 = personal + senior + blind
    count_10 = dep

    reduced_789 = max(credits_789 - per_count_reduction * count_789, 0.0)
    reduced_10 = max(credits_10 - per_count_reduction * count_10, 0.0)
    return reduced_789 + reduced_10


# ---------------------------------------------------------------------------
# Form 540 lines 40–48 (special credits)
# ---------------------------------------------------------------------------
def _form_540_credits(
    ca: CA540Input,
    income: dict[str, float],
    tax: dict[str, float],
) -> dict[str, float]:
    """Compute Form 540 lines 40, 43–46, 47, 48.

    Modeled credits:
      - Line 40 Nonrefundable Child & Dependent Care Expenses (caller supplies
        the FTB 3506 amount; oracle enforces the federal-AGI ≤ $100,000 gate).
      - Line 46 Nonrefundable Renter's Credit (oracle applies the CA-AGI
        cliff against Form 540 line 17).
      - Lines 43–45 Other special credits (caller precomputes; oracle only
        sums them).

    SOURCE: FTB 2025 Form 540 instructions, lines 40/43–46/47.
    """
    c = ca.credits

    # Line 40: dep care credit, gated by federal AGI ≤ $100,000.
    if c.dep_care_federal_agi_for_eligibility <= 100_000.0:
        line_40 = c.dep_care_credit_amount
    else:
        line_40 = 0.0

    # Lines 43–45: other special credits (pre-computed).
    line_other_credits = c.other_nonrefundable_credits

    # Line 46: renter's credit — hard CA-AGI cliff, no phaseout.
    # SOURCE: FTB Form 540 Booklet, Nonrefundable Renter's Credit
    # Qualification Record, Question 2 — "Is your California adjusted gross
    # income the amount on line 17 [≤ cliff]?" CA AGI (line 17) is already
    # computed above and available in ``income``; using it avoids the
    # false-deny that federal AGI would produce when large Sch CA col B
    # subtractions (Social Security, unemployment, CA lottery, railroad
    # retirement) push CA AGI materially below federal AGI near the cliff.
    fs = ca.demographics.filing_status
    ca_agi = income["f540_line_17_ca_agi"]
    if c.eligible_for_renters_credit:
        if fs in ("single", "mfs"):
            limit = RENTERS_CREDIT_AGI_LIMIT_SINGLE_MFS_2025
            amount = RENTERS_CREDIT_SINGLE_MFS_2025
        else:
            limit = RENTERS_CREDIT_AGI_LIMIT_HOUSEHOLD_2025
            amount = RENTERS_CREDIT_HOUSEHOLD_2025
        line_46 = amount if ca_agi <= limit else 0.0
    else:
        line_46 = 0.0

    # Line 47: total nonrefundable credits = sum of 40, 43–45, 46.
    line_47 = line_40 + line_other_credits + line_46

    # Line 48: line 35 − line 47 (zero floor).
    line_48 = max(
        tax["f540_line_35_total_tax_before_special_credits"] - line_47, 0.0
    )

    return {
        "f540_line_40_dep_care_credit": line_40,
        "f540_line_43_45_other_special_credits": line_other_credits,
        "f540_line_46_renters_credit": line_46,
        "f540_line_47_total_nonrefundable_credits": line_47,
        "f540_line_48_tax_after_special_credits": line_48,
    }


# ---------------------------------------------------------------------------
# Form 540 lines 61–64 (other taxes: AMT, BHST, recapture)
# ---------------------------------------------------------------------------
def _form_540_other_taxes(
    ca: CA540Input,
    income: dict[str, float],
    credits: dict[str, float],
) -> dict[str, float]:
    """Compute Form 540 lines 61–64.

    Line 61 (AMT) is gated to zero by _gate_scope; see scope-out.

    SOURCE: FTB 2025 Form 540 instructions, lines 61–64.
    """
    line_61_amt = 0.0  # out of scope; _gate_scope raises if preferences set

    # Line 62: Behavioral Health Services Tax = 1% of (line 19 − $1M), floored.
    # SOURCE: FTB 2025 Form 540 instructions, line 62.
    line_19 = income["f540_line_19_taxable_income"]
    line_62_bhst = max(line_19 - BHST_THRESHOLD_2025, 0.0) * BHST_RATE_2025

    # Line 63: other taxes (caller precomputes).
    line_63 = ca.other_taxes.line_63_other_taxes

    # Line 64 = line 48 + line 61 + line 62 + line 63.
    line_64 = (
        credits["f540_line_48_tax_after_special_credits"]
        + line_61_amt
        + line_62_bhst
        + line_63
    )

    return {
        "f540_line_61_amt": line_61_amt,
        "f540_line_62_bhst": line_62_bhst,
        "f540_line_63_other_taxes": line_63,
        "f540_line_64_total_tax": line_64,
    }


# ---------------------------------------------------------------------------
# Form 540 lines 71–78 (payments)
# ---------------------------------------------------------------------------
def _form_540_payments(ca: CA540Input) -> dict[str, float]:
    """Sum Form 540 lines 71–77 into line 78.

    SOURCE: FTB 2025 Form 540 instructions, lines 71–78.
    """
    p = ca.payments
    line_78 = (
        p.line_71_ca_withholding
        + p.line_72_estimated_payments_and_carryover
        + p.line_73_592b_593_withholding
        + p.line_74_motion_picture_credit
        + p.line_75_eitc
        + p.line_76_yctc
        + p.line_77_fytc
    )
    return {
        "f540_line_71_withholding": p.line_71_ca_withholding,
        "f540_line_72_estimated_payments": p.line_72_estimated_payments_and_carryover,
        "f540_line_73_592b_593": p.line_73_592b_593_withholding,
        "f540_line_74_motion_picture_credit": p.line_74_motion_picture_credit,
        "f540_line_75_eitc": p.line_75_eitc,
        "f540_line_76_yctc": p.line_76_yctc,
        "f540_line_77_fytc": p.line_77_fytc,
        "f540_line_78_total_payments": line_78,
    }


# ---------------------------------------------------------------------------
# Form 540 lines 91–115 (use tax, overpaid/owed, contributions, refund/due)
# ---------------------------------------------------------------------------
def _form_540_balance(
    ca: CA540Input,
    other_taxes: dict[str, float],
    payments: dict[str, float],
) -> dict[str, float]:
    """Compute Form 540 lines 91–115 (use tax, overpaid, refund/due).

    SOURCE: FTB 2025 Form 540 instructions, lines 91–115.
    """
    line_91 = ca.misc.line_91_use_tax
    line_92 = 0.0  # ISR penalty — out of scope

    line_78 = payments["f540_line_78_total_payments"]
    line_64 = other_taxes["f540_line_64_total_tax"]

    # Line 93: if line 78 > line 91, line 78 − line 91.
    # Line 94: if line 91 > line 78, line 91 − line 78.
    if line_78 > line_91:
        line_93 = line_78 - line_91
        line_94 = 0.0
    else:
        line_93 = 0.0
        line_94 = line_91 - line_78

    # Line 95: if line 93 > line 92, line 93 − line 92.
    # Line 96: if line 92 > line 93, line 92 − line 93.
    if line_93 > line_92:
        line_95 = line_93 - line_92
        line_96 = 0.0
    else:
        line_95 = 0.0
        line_96 = line_92 - line_93

    # Line 97 (overpaid): if line 95 > line 64, line 95 − line 64.
    # Line 100 (tax due): if line 95 < line 64, line 64 − line 95.
    if line_95 > line_64:
        line_97 = line_95 - line_64
        line_100 = 0.0
    else:
        line_97 = 0.0
        line_100 = line_64 - line_95

    # Line 98 (amount applied to 2026 estimated tax) — caller supplies; cannot
    # exceed line 97.
    line_98 = min(ca.misc.line_98_overpayment_applied_to_2026, line_97)

    # Line 99: line 97 − line 98.
    line_99 = line_97 - line_98

    # Line 110: voluntary contributions (caller precomputes).
    line_110 = ca.misc.line_110_voluntary_contributions

    # Line 111: if no amount on line 99, line 94 + line 96 + line 100 + 110;
    # else if line 110 > line 99, line 110 − line 99.
    if line_99 == 0.0:
        line_111 = line_94 + line_96 + line_100 + line_110
    elif line_110 > line_99:
        line_111 = line_110 - line_99
    else:
        line_111 = 0.0

    line_112 = 0.0  # penalties/interest — out of scope
    line_113 = 0.0  # underpayment — out of scope

    # Line 114 = 111 + 112 + 113 (amount you owe).
    line_114 = line_111 + line_112 + line_113

    # Line 115 = 99 − (110 + 112 + 113), floored at 0 (refund).
    line_115 = max(line_99 - (line_110 + line_112 + line_113), 0.0)

    return {
        "f540_line_91_use_tax": line_91,
        "f540_line_92_isr_penalty": line_92,
        "f540_line_93": line_93,
        "f540_line_94": line_94,
        "f540_line_95": line_95,
        "f540_line_96": line_96,
        "f540_line_97_overpaid": line_97,
        "f540_line_98_applied_to_2026": line_98,
        "f540_line_99_overpaid_net": line_99,
        "f540_line_100_tax_due_pre_contributions": line_100,
        "f540_line_110_contributions": line_110,
        "f540_line_111_owe_before_penalties": line_111,
        "f540_line_112_penalties": line_112,
        "f540_line_113_underpayment": line_113,
        "f540_line_114_total_amount_due": line_114,
        "f540_line_115_refund": line_115,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def compute_ca_540(ca: CA540Input) -> dict[str, float | bool]:
    """Compute every CA 540 line the oracle models for a single scenario.

    Returns a flat dict keyed by ``f540_line_<N>_<semantic>`` and
    ``schca_part_<N>_line_<M>_<col>_<semantic>`` entries. The harness diffs
    this dict against production output.

    Raises NotImplementedError if the scenario triggers an unmodeled feature
    (see ``_gate_scope``).
    """
    _gate_scope(ca)

    sch_ca_p1 = _schedule_ca_part_i(ca)
    sch_ca_p2 = _schedule_ca_part_ii(ca)
    income = _form_540_income_and_taxable(ca, sch_ca_p1, sch_ca_p2)
    tax = _form_540_tax(ca, income)
    credits = _form_540_credits(ca, income, tax)
    other_taxes = _form_540_other_taxes(ca, income, credits)
    payments = _form_540_payments(ca)
    balance = _form_540_balance(ca, other_taxes, payments)

    out: dict[str, float | bool] = {}
    out.update(sch_ca_p1)
    out.update(sch_ca_p2)
    out.update(income)
    out.update(tax)
    out.update(credits)
    out.update(other_taxes)
    out.update(payments)
    out.update(balance)

    # Audit fields — exemption-credit counts and pre-phaseout amounts, so the
    # harness can diff granular pieces of line 32.
    personal, senior, blind, dep = _count_exemptions(ca)
    pre_789, pre_10 = _exemption_credits_pre_phaseout(ca)
    out["f540_line_7_personal_exemption_count"] = float(personal)
    out["f540_line_8_blind_exemption_count"] = float(blind)
    out["f540_line_9_senior_exemption_count"] = float(senior)
    out["f540_line_10_dependent_exemption_count"] = float(dep)
    out["f540_line_11_exemption_amount_pre_phaseout"] = pre_789 + pre_10
    out["f540_line_18_ca_standard_deduction"] = _ca_standard_deduction(ca)

    return out


# ---------------------------------------------------------------------------
# Hand-worked filing-status cases — TY2025, MFJ and HOH
#
# Each case below is worked BY HAND from the published FTB booklet, not by
# running ``compute_ca_540``. The expected values are whole dollars as they
# would be entered on the printed Form 540. ``compute_ca_540`` is checked
# against them (oracle self-consistency) and production is checked against
# them (cross-check), in tests/test_ca_540_oracle.py.
#
# All people and amounts are synthetic.
# ---------------------------------------------------------------------------
CA_540_BOOKLET_2025_PROVENANCE: dict[str, str] = {
    "url": "https://www.ftb.ca.gov/forms/2025/2025-540-booklet.pdf",
    "edition": (
        "2025 Personal Income Tax Booklet (540 Forms & Instructions); "
        "PDF Keywords 'Revised 02/2026 ... Revised 04/2026' (Schedule CA "
        "instruction pages only, stamped REV 02-26 / REV 04-26); Form 540 "
        "instructions, tax table and rate schedules carry no REV stamp; "
        "Form 540 side 1 form code 3101253; PDF ModDate 2026-05-04"
    ),
    "sha256": "b48ee24bd2f9b9e74fe9a5bbc548d15bae0bd1ce53306bef1ff33fc76f8078c1",
    "retrieved": "2026-10-14",
}


@dataclass(frozen=True)
class HandWorkedCase540:
    """One hand-worked TY2025 Form 540 scenario.

    Inputs are the raw facts a filer would bring; ``expected`` maps oracle
    output keys (see ``compute_ca_540``) to the whole-dollar hand result.
    ``line_31_method`` records which booklet method set line 31: the tax
    table (line 19 ≤ $100,000, $100-row midpoint lookup) or the tax rate
    schedules. ``compute_ca_540`` evaluates the rate schedule exactly, so
    on a tax-table case its line 31 (and every line downstream of it) may
    differ from the hand value by the table's midpoint rounding.
    """
    name: str
    filing_status: FilingStatus
    w2_wages: tuple[float, ...]
    w2_ca_withholding: tuple[float, ...]
    taxable_interest: float
    renter_six_months_in_ca: bool
    line_31_method: Literal["tax_table", "tax_rate_schedule"]
    expected: dict[str, float]
    # Birthdates drive the line 9 senior count (``senior_count_2025``).
    # None = no birthdate modeled; that person is not 65 or older.
    taxpayer_birth_date: date | None
    spouse_birth_date: date | None


# SOURCE: booklet p.12, "Line 9 – Senior Exemptions": "65 years of age or
# older by December 31, 2025*" … "* If your 65th birthday is on January 1,
# 2026, you are considered to be age 65 on December 31, 2025." 65th
# birthday on or before 2026-01-01 ⇔ born on or before 1961-01-01.
SENIOR_BIRTH_DATE_CUTOFF_2025 = date(1961, 1, 1)


def senior_count_2025(case: HandWorkedCase540) -> int:
    """Form 540 line 9 box count: one per spouse/RDP born on or before the
    cutoff (side 1: "If you (or your spouse/RDP) are 65 or older, enter 1;
    if both are 65 or older, enter 2"). No case is a dependent of another
    person, so the line 9 dependent bar never applies."""
    if case.filing_status != "mfj" and case.spouse_birth_date is not None:
        raise ValueError(f"{case.name}: spouse birthdate on a non-joint case")
    return sum(
        is_senior_2025(born)
        for born in (case.taxpayer_birth_date, case.spouse_birth_date)
    )


def is_senior_2025(born: date | None) -> bool:
    """65 or older by 12/31/2025 per the line 9 rule above."""
    return born is not None and born <= SENIOR_BIRTH_DATE_CUTOFF_2025


def _zero_balance_tail(*, line_64: float, line_71: float) -> dict[str, float]:
    """Lines 61–115 for a case with no AMT/BHST/other tax, no estimates,
    no use tax, no contributions, and payments exceeding tax (refund).

    Booklet p. 16–19: line 64 = 48 + 61 + 62 + 63; line 78 = 71 + … + 77;
    line 93 = 78 − 91; line 95 = 93 − 92; line 97 = 95 − 64 (overpaid);
    line 99 = 97 − 98; line 115 = 99 − (110 + 112 + 113).
    """
    overpaid = line_71 - line_64
    assert overpaid > 0, "helper models the refund branch only"
    return {
        "f540_line_61_amt": 0.0,
        "f540_line_62_bhst": 0.0,
        "f540_line_63_other_taxes": 0.0,
        "f540_line_64_total_tax": line_64,
        "f540_line_71_withholding": line_71,
        "f540_line_72_estimated_payments": 0.0,
        "f540_line_78_total_payments": line_71,
        "f540_line_91_use_tax": 0.0,
        "f540_line_93": line_71,
        "f540_line_94": 0.0,
        "f540_line_95": line_71,
        "f540_line_96": 0.0,
        "f540_line_97_overpaid": overpaid,
        "f540_line_98_applied_to_2026": 0.0,
        "f540_line_99_overpaid_net": overpaid,
        "f540_line_100_tax_due_pre_contributions": 0.0,
        "f540_line_110_contributions": 0.0,
        "f540_line_111_owe_before_penalties": 0.0,
        "f540_line_114_total_amount_due": 0.0,
        "f540_line_115_refund": overpaid,
    }


# Case: MFJ, two W-2s, standard deduction, not renters, both under 65.
#   L12 state wages = 98,400 + 51,300 = 149,700
#   L13 federal AGI = 149,700 (wages only); L14 = 0; L15 = 149,700; L16 = 0
#   L17 CA AGI = 149,700
#   L18 std ded, chart p.13, status 2 = 11,412
#   L19 = 149,700 − 11,412 = 138,288  (> 100,000 → rate schedule)
#   L31 Schedule Y, over 115,084: 138,288 − 115,084 = 23,204;
#       23,204 × 8% = 1,856.32; 3,974.82 + 1,856.32 = 5,831.14 → 5,831
#   L7 status 2 → 2 × 153 = 306; L8/L9/L10 = 0; L11 = 306
#   L32: L13 149,700 ≤ 504,411 (p.14) → no AGI limitation; L32 = 306
#   L33 = 5,831 − 306 = 5,525; L34 = 0; L35 = 5,525
#   L40/43–45/46 = 0; L47 = 0; L48 = 5,525; L61–63 = 0; L64 = 5,525
#   L71 = 4,100 + 1,750 = 5,850 = L78 = L93 = L95
#   L97 = 5,850 − 5,525 = 325 = L99 = L115 refund
CASE_MFJ_TWO_W2_2025 = HandWorkedCase540(
    name="mfj_two_w2_wages_only",
    filing_status="mfj",
    w2_wages=(98_400.0, 51_300.0),
    w2_ca_withholding=(4_100.0, 1_750.0),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_11_exemption_amount_pre_phaseout": 306.0,
        "f540_line_12_state_wages": 149_700.0,
        "f540_line_13_federal_agi": 149_700.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 149_700.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 149_700.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 138_288.0,
        "f540_line_31_tax": 5_831.0,
        "f540_line_32_exemption_credits": 306.0,
        "f540_line_33_tax_after_exemption_credits": 5_525.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 5_525.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 5_525.0,
        **_zero_balance_tail(line_64=5_525.0, line_71=5_850.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: MFJ, one W-2 + taxable interest, standard deduction, not renters.
#   L12 state wages = 143,250 (interest is not W-2 box 16)
#   L13 federal AGI = 143,250 + 2,610 = 145,860
#   Sch CA: ordinary taxable interest, no US-obligation or non-CA muni
#   component → no col B/C entry; L14 = 0, L16 = 0; L15 = L17 = 145,860
#   L18 = 11,412; L19 = 145,860 − 11,412 = 134,448 (> 100,000 → schedule)
#   L31 Schedule Y, over 115,084: 134,448 − 115,084 = 19,364;
#       19,364 × 8% = 1,549.12; 3,974.82 + 1,549.12 = 5,523.94 → 5,524
#   L7 = 2 × 153 = 306 = L11; L13 ≤ 504,411 → L32 = 306
#   L33 = 5,524 − 306 = 5,218 = L35 = L48 = L64
#   L71 = 7,900; L97 = 7,900 − 5,218 = 2,682 = L115 refund
CASE_MFJ_W2_PLUS_INTEREST_2025 = HandWorkedCase540(
    name="mfj_one_w2_plus_interest",
    filing_status="mfj",
    w2_wages=(143_250.0,),
    w2_ca_withholding=(7_900.0,),
    taxable_interest=2_610.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_11_exemption_amount_pre_phaseout": 306.0,
        "f540_line_12_state_wages": 143_250.0,
        "f540_line_13_federal_agi": 145_860.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 145_860.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 145_860.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 134_448.0,
        "f540_line_31_tax": 5_524.0,
        "f540_line_32_exemption_credits": 306.0,
        "f540_line_33_tax_after_exemption_credits": 5_218.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 5_218.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 5_218.0,
        **_zero_balance_tail(line_64=5_218.0, line_71=7_900.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: HOH, one W-2, renter all year in CA, no dependents listed.
#   L12 = L13 = L15 = L17 = 67,800; L14 = L16 = 0
#   L18 = 11,412 (status 4); L19 = 67,800 − 11,412 = 56,388 (≤ 100,000 →
#   tax table, p.69ff): row "56,351 – 56,450", column "4 Is" = 984
#     (cross-check: table is Schedule Z at the row midpoint 56,400:
#      828.87 + (56,400 − 52,530) × 4% = 828.87 + 154.80 = 983.67 → 984)
#   L7 status 4 → 1 × 153 = 153 = L11; L13 ≤ 378,310 → L32 = 153
#   L33 = 984 − 153 = 831 = L35
#   L46 renter's credit (p.25–26): Q1 resident yes; Q2 CA AGI L17 67,800 ≤
#   107,988 (MFJ/HOH/QSS limit) yes; Q3 rented ≥ half year yes; Q4 not a
#   dependent; Q6 not exempt property; Q7 no homeowner's exemption; Q8
#   single (unmarried) → Q11: head of household → 120
#   L47 = 120; L48 = 831 − 120 = 711 = L64
#   L71 = 2,480; L97 = 2,480 − 711 = 1,769 = L115 refund
CASE_HOH_RENTER_2025 = HandWorkedCase540(
    name="hoh_wages_only_renter",
    filing_status="hoh",
    w2_wages=(67_800.0,),
    w2_ca_withholding=(2_480.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=True,
    line_31_method="tax_table",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 153.0,
        "f540_line_12_state_wages": 67_800.0,
        "f540_line_13_federal_agi": 67_800.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 67_800.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 67_800.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 56_388.0,
        "f540_line_31_tax": 984.0,
        "f540_line_32_exemption_credits": 153.0,
        "f540_line_33_tax_after_exemption_credits": 831.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 831.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 120.0,
        "f540_line_47_total_nonrefundable_credits": 120.0,
        "f540_line_48_tax_after_special_credits": 711.0,
        **_zero_balance_tail(line_64=711.0, line_71=2_480.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: HOH, one W-2, higher wages, not a renter, no dependents listed.
#   L12 = L13 = L15 = L17 = 112,000; L14 = L16 = 0
#   L18 = 11,412; L19 = 112,000 − 11,412 = 100,588 (> 100,000 → schedule)
#   L31 Schedule Z, over 98,990: 100,588 − 98,990 = 1,598;
#       1,598 × 9.3% = 148.614 → 148.61 (p.75 step 4: round to two
#       decimals); 3,616.45 + 148.61 = 3,765.06 → 3,765
#   L7 = 1 × 153 = 153 = L11; exemption AGI limitation: L13 112,000 ≤
#   378,310 (HOH, p.14) → phaseout NOT reached; L32 = 153
#   L33 = 3,765 − 153 = 3,612 = L35 = L48 = L64 (no renter's credit)
#   L71 = 5,900; L97 = 5,900 − 3,612 = 2,288 = L115 refund
CASE_HOH_HIGHER_WAGES_2025 = HandWorkedCase540(
    name="hoh_higher_wages",
    filing_status="hoh",
    w2_wages=(112_000.0,),
    w2_ca_withholding=(5_900.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 153.0,
        "f540_line_12_state_wages": 112_000.0,
        "f540_line_13_federal_agi": 112_000.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 112_000.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 112_000.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 100_588.0,
        "f540_line_31_tax": 3_765.0,
        "f540_line_32_exemption_credits": 153.0,
        "f540_line_33_tax_after_exemption_credits": 3_612.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 3_612.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 3_612.0,
        **_zero_balance_tail(line_64=3_612.0, line_71=5_900.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

HAND_WORKED_STATUS_CASES_2025: tuple[HandWorkedCase540, ...] = (
    CASE_MFJ_TWO_W2_2025,
    CASE_MFJ_W2_PLUS_INTEREST_2025,
    CASE_HOH_RENTER_2025,
    CASE_HOH_HIGHER_WAGES_2025,
)


# ---------------------------------------------------------------------------
# Hand-worked aged cases — TY2025, line 9 senior exemption credit
#
# Booklet facts used (all from CA_540_BOOKLET_2025_PROVENANCE):
#   - Line 9 senior condition: see SENIOR_BIRTH_DATE_CUTOFF_2025 (p.12).
#   - Line 9 amount: Form 540 side 1 preprint "9 Senior … X $153" — $153
#     per senior, one per qualifying spouse/RDP.
#   - Line 18: Standard Deduction Chart for Most People (p.13) is keyed by
#     filing status only; it has no age-65 addition, so aged filers take
#     the same 5,706 / 11,412 as everyone else.
#   - Line 32: AGI limitation applies only if line 13 exceeds 252,203
#     (single) / 504,411 (MFJ) (p.14); none of these cases do.
#   - Line 31: line 19 > 100,000 in every case → tax rate schedules (p.75),
#     step 4 rounds step 3 to two decimals, then whole dollars.
# ---------------------------------------------------------------------------

# Case: single, aged, one W-2, not a renter.
#   Taxpayer born 1955-03-14 ≤ 1961-01-01 cutoff → 70 on 12/31/2025 → senior
#   L12 = L13 = L15 = L17 = 120,000; L14 = L16 = 0
#   L18 chart status 1 = 5,706 (no age addition)
#   L19 = 120,000 − 5,706 = 114,294 (> 100,000 → schedule)
#   L31 Schedule X, over 72,724: 114,294 − 72,724 = 41,570;
#       41,570 × 9.3% = 3,866.01; 3,201.97 + 3,866.01 = 7,067.98 → 7,068
#   L7 status 1 → 1 × 153 = 153; L8 = 0; L9 1 × 153 = 153; L10 = 0
#   L11 = 153 + 153 = 306
#   L32: L13 120,000 ≤ 252,203 → no AGI limitation; L32 = 306
#   L33 = 7,068 − 306 = 6,762 = L35 = L48 = L64 (no special credits)
#   L71 = 7,200; L97 = 7,200 − 6,762 = 438 = L115 refund
CASE_SINGLE_AGED_2025 = HandWorkedCase540(
    name="single_aged",
    filing_status="single",
    w2_wages=(120_000.0,),
    w2_ca_withholding=(7_200.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_9_senior_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 306.0,
        "f540_line_12_state_wages": 120_000.0,
        "f540_line_13_federal_agi": 120_000.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 120_000.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 120_000.0,
        "f540_line_18_deduction": 5_706.0,
        "f540_line_19_taxable_income": 114_294.0,
        "f540_line_31_tax": 7_068.0,
        "f540_line_32_exemption_credits": 306.0,
        "f540_line_33_tax_after_exemption_credits": 6_762.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 6_762.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 6_762.0,
        **_zero_balance_tail(line_64=6_762.0, line_71=7_200.0),
    },
    taxpayer_birth_date=date(1955, 3, 14),
    spouse_birth_date=None,
)

# Case: MFJ, both spouses aged, two W-2s, not renters.
#   Taxpayer born 1957-08-20, spouse born 1959-11-02; both ≤ 1961-01-01
#   → 68 and 66 on 12/31/2025 → two seniors
#   L12 = 95,000 + 70,000 = 165,000 = L13 = L15 = L17; L14 = L16 = 0
#   L18 chart status 2 = 11,412 (no age addition)
#   L19 = 165,000 − 11,412 = 153,588 (> 100,000 → schedule)
#   L31 Schedule Y, over 145,448: 153,588 − 145,448 = 8,140;
#       8,140 × 9.3% = 757.02; 6,403.94 + 757.02 = 7,160.96 → 7,161
#   L7 status 2 → 2 × 153 = 306; L8 = 0; L9 2 × 153 = 306; L10 = 0
#   L11 = 306 + 306 = 612
#   L32: L13 165,000 ≤ 504,411 → no AGI limitation; L32 = 612
#   L33 = 7,161 − 612 = 6,549 = L35 = L48 = L64
#   L71 = 5,200 + 3,600 = 8,800; L97 = 8,800 − 6,549 = 2,251 = L115 refund
CASE_MFJ_BOTH_AGED_2025 = HandWorkedCase540(
    name="mfj_both_aged",
    filing_status="mfj",
    w2_wages=(95_000.0, 70_000.0),
    w2_ca_withholding=(5_200.0, 3_600.0),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_9_senior_exemption_count": 2.0,
        "f540_line_11_exemption_amount_pre_phaseout": 612.0,
        "f540_line_12_state_wages": 165_000.0,
        "f540_line_13_federal_agi": 165_000.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 165_000.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 165_000.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 153_588.0,
        "f540_line_31_tax": 7_161.0,
        "f540_line_32_exemption_credits": 612.0,
        "f540_line_33_tax_after_exemption_credits": 6_549.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 6_549.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 6_549.0,
        **_zero_balance_tail(line_64=6_549.0, line_71=8_800.0),
    },
    taxpayer_birth_date=date(1957, 8, 20),
    spouse_birth_date=date(1959, 11, 2),
)

# Case: MFJ, spouse-only aged, two W-2s, not renters.
#   Taxpayer born 1968-05-10 > 1961-01-01 → 57 on 12/31/2025 → not senior
#   Spouse born 1958-02-14 ≤ 1961-01-01 → 67 on 12/31/2025 → senior
#   → one senior
#   L12 = 110,000 + 18,500 = 128,500 = L13 = L15 = L17; L14 = L16 = 0
#   L18 chart status 2 = 11,412
#   L19 = 128,500 − 11,412 = 117,088 (> 100,000 → schedule)
#   L31 Schedule Y, over 115,084: 117,088 − 115,084 = 2,004;
#       2,004 × 8% = 160.32; 3,974.82 + 160.32 = 4,135.14 → 4,135
#   L7 status 2 → 2 × 153 = 306; L8 = 0; L9 1 × 153 = 153; L10 = 0
#   L11 = 306 + 153 = 459
#   L32: L13 128,500 ≤ 504,411 → no AGI limitation; L32 = 459
#   L33 = 4,135 − 459 = 3,676 = L35 = L48 = L64
#   L71 = 6,100 + 900 = 7,000; L97 = 7,000 − 3,676 = 3,324 = L115 refund
CASE_MFJ_SPOUSE_ONLY_AGED_2025 = HandWorkedCase540(
    name="mfj_spouse_only_aged",
    filing_status="mfj",
    w2_wages=(110_000.0, 18_500.0),
    w2_ca_withholding=(6_100.0, 900.0),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_9_senior_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 459.0,
        "f540_line_12_state_wages": 128_500.0,
        "f540_line_13_federal_agi": 128_500.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 128_500.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 128_500.0,
        "f540_line_18_deduction": 11_412.0,
        "f540_line_19_taxable_income": 117_088.0,
        "f540_line_31_tax": 4_135.0,
        "f540_line_32_exemption_credits": 459.0,
        "f540_line_33_tax_after_exemption_credits": 3_676.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 3_676.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 3_676.0,
        **_zero_balance_tail(line_64=3_676.0, line_71=7_000.0),
    },
    taxpayer_birth_date=date(1968, 5, 10),
    spouse_birth_date=date(1958, 2, 14),
)

HAND_WORKED_AGED_CASES_2025: tuple[HandWorkedCase540, ...] = (
    CASE_SINGLE_AGED_2025,
    CASE_MFJ_BOTH_AGED_2025,
    CASE_MFJ_SPOUSE_ONLY_AGED_2025,
)


# ---------------------------------------------------------------------------
# Hand-worked cases — TY2024 (MFJ, HOH, aged single)
#
# Worked by hand from the 2024 booklet in CA_540_BOOKLET_2024_PROVENANCE.
# ``compute_ca_540`` carries TY2025 constants only, so these cases are NOT
# run through it; they are checked against the production chain alone.
#
# Booklet facts used (2024 booklet page numbers):
#   - Line 7/8/9 amount: Form 540 side 1 preprint "X $149" on each of
#     lines 7, 8 and 9 (booklet PDF page 39).
#   - Line 9 senior condition: see SENIOR_BIRTH_DATE_CUTOFF_2024 (p.12).
#   - Line 18: Standard Deduction Chart for Most People (p.13): status 1/3
#     = 5,540; status 2/4/5 = 11,080. Keyed by filing status only; no
#     age-65 addition.
#   - Line 31: line 19 > 100,000 → tax rate schedules (p.13); Schedules
#     X / Y / Z (p.75). Step 4 rounds step 3 to two decimals, adds the
#     base tax, then the result is rounded to whole dollars.
#   - Line 32: AGI limitation applies only if line 13 exceeds 244,857
#     (single/MFS), 489,719 (MFJ/QSS), 367,291 (HOH) (p.14); none of
#     these cases do.
#   - Lines 33–115 flow as in ``_zero_balance_tail`` (Form 540 side 2–4:
#     L33 = L31 − L32; L35 = L33 + L34; L48 = L35 − L47; L64 = L48 + L61
#     + L62 + L63; L97 = L95 − L64; L99 = L97 − L98). TY2024 line 62 is
#     the Mental Health Services Tax (zero here); the ``*_bhst`` and
#     ``*_applied_to_2026`` key names are the harness's year-neutral keys.
#
# All people and amounts are synthetic.
# ---------------------------------------------------------------------------
CA_540_BOOKLET_2024_PROVENANCE: dict[str, str] = {
    "url": "https://www.ftb.ca.gov/forms/2024/2024-540-booklet.pdf",
    "edition": (
        "2024 California 540 Forms & Instructions Personal Income Tax "
        "Booklet; 80 PDF pages; Form 540 side 1 form code 3101243; PDF "
        "CreationDate 2024-12-03, ModDate 2025-03-10"
    ),
    "sha256": "446372719f6e1ce90132d550c268d7804fc44cefcf13514e09bf9ac9907ee374",
    "retrieved": "2026-10-15",
}

# SOURCE: 2024 booklet p.12, "Line 9 – Senior Exemptions": "If you were 65
# years of age or older by December 31, 2024*" … "* If your 65th birthday
# is on January 1, 2025, you are considered to be age 65 on December 31,
# 2024." 65th birthday on or before 2025-01-01 ⇔ born on or before
# 1960-01-01.
SENIOR_BIRTH_DATE_CUTOFF_2024 = date(1960, 1, 1)


def is_senior_2024(born: date | None) -> bool:
    """65 or older by 12/31/2024 per the TY2024 line 9 rule above."""
    return born is not None and born <= SENIOR_BIRTH_DATE_CUTOFF_2024


def senior_count_2024(case: HandWorkedCase540) -> int:
    """TY2024 Form 540 line 9 box count (same side-1 wording as TY2025:
    one per spouse/RDP 65 or older). No case is anyone's dependent."""
    if case.filing_status != "mfj" and case.spouse_birth_date is not None:
        raise ValueError(f"{case.name}: spouse birthdate on a non-joint case")
    return sum(
        is_senior_2024(born)
        for born in (case.taxpayer_birth_date, case.spouse_birth_date)
    )


# Case: MFJ, two W-2s, standard deduction, not renters, both under 65.
#   L12 state wages = 104,600 + 47,850 = 152,450
#   L13 federal AGI = 152,450 (wages only); L14 = 0; L15 = 152,450; L16 = 0
#   L17 CA AGI = 152,450
#   L18 std ded, chart p.13, status 2 = 11,080
#   L19 = 152,450 − 11,080 = 141,370  (> 100,000 → rate schedule)
#   L31 Schedule Y, over 141,212: 141,370 − 141,212 = 158;
#       158 × 9.3% = 14.694 → 14.69; 6,217.44 + 14.69 = 6,232.13 → 6,232
#   L7 status 2 → 2 × 149 = 298; L8/L9/L10 = 0; L11 = 298
#   L32: L13 152,450 ≤ 489,719 (p.14) → no AGI limitation; L32 = 298
#   L33 = 6,232 − 298 = 5,934; L34 = 0; L35 = 5,934
#   L40/43–45/46 = 0; L47 = 0; L48 = 5,934; L61–63 = 0; L64 = 5,934
#   L71 = 4,300 + 2,150 = 6,450 = L78 = L93 = L95
#   L97 = 6,450 − 5,934 = 516 = L99 = L115 refund
CASE_MFJ_TWO_W2_2024 = HandWorkedCase540(
    name="mfj_two_w2_wages_only_2024",
    filing_status="mfj",
    w2_wages=(104_600.0, 47_850.0),
    w2_ca_withholding=(4_300.0, 2_150.0),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_9_senior_exemption_count": 0.0,
        "f540_line_11_exemption_amount_pre_phaseout": 298.0,
        "f540_line_12_state_wages": 152_450.0,
        "f540_line_13_federal_agi": 152_450.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 152_450.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 152_450.0,
        "f540_line_18_deduction": 11_080.0,
        "f540_line_19_taxable_income": 141_370.0,
        "f540_line_31_tax": 6_232.0,
        "f540_line_32_exemption_credits": 298.0,
        "f540_line_33_tax_after_exemption_credits": 5_934.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 5_934.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 5_934.0,
        **_zero_balance_tail(line_64=5_934.0, line_71=6_450.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: HOH, one W-2, not a renter, no dependents listed, not aged.
#   L12 = L13 = L15 = L17 = 118,500; L14 = L16 = 0
#   L18 chart status 4 = 11,080
#   L19 = 118,500 − 11,080 = 107,420 (> 100,000 → schedule)
#   L31 Schedule Z, over 96,107: 107,420 − 96,107 = 11,313;
#       11,313 × 9.3% = 1,052.109 → 1,052.11; 3,511.13 + 1,052.11
#       = 4,563.24 → 4,563
#   L7 status 4 → 1 × 149 = 149; L8/L9/L10 = 0; L11 = 149
#   L32: L13 118,500 ≤ 367,291 (HOH, p.14) → no AGI limitation; L32 = 149
#   L33 = 4,563 − 149 = 4,414 = L35 = L48 = L64 (no special credits)
#   L71 = 5,250; L97 = 5,250 − 4,414 = 836 = L115 refund
CASE_HOH_2024 = HandWorkedCase540(
    name="hoh_wages_only_2024",
    filing_status="hoh",
    w2_wages=(118_500.0,),
    w2_ca_withholding=(5_250.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_9_senior_exemption_count": 0.0,
        "f540_line_11_exemption_amount_pre_phaseout": 149.0,
        "f540_line_12_state_wages": 118_500.0,
        "f540_line_13_federal_agi": 118_500.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 118_500.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 118_500.0,
        "f540_line_18_deduction": 11_080.0,
        "f540_line_19_taxable_income": 107_420.0,
        "f540_line_31_tax": 4_563.0,
        "f540_line_32_exemption_credits": 149.0,
        "f540_line_33_tax_after_exemption_credits": 4_414.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 4_414.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 4_414.0,
        **_zero_balance_tail(line_64=4_414.0, line_71=5_250.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: single, aged, one W-2, not a renter.
#   Taxpayer born 1957-06-22 ≤ 1960-01-01 cutoff → 67 on 12/31/2024 → senior
#   L12 = L13 = L15 = L17 = 108,750; L14 = L16 = 0
#   L18 chart status 1 = 5,540 (no age addition)
#   L19 = 108,750 − 5,540 = 103,210 (> 100,000 → schedule)
#   L31 Schedule X, over 70,606: 103,210 − 70,606 = 32,604;
#       32,604 × 9.3% = 3,032.172 → 3,032.17; 3,108.72 + 3,032.17
#       = 6,140.89 → 6,141
#   L7 status 1 → 1 × 149 = 149; L8 = 0; L9 1 × 149 = 149; L10 = 0
#   L11 = 149 + 149 = 298
#   L32: L13 108,750 ≤ 244,857 → no AGI limitation; L32 = 298
#   L33 = 6,141 − 298 = 5,843 = L35 = L48 = L64 (no special credits)
#   L71 = 6,000; L97 = 6,000 − 5,843 = 157 = L115 refund
CASE_SINGLE_AGED_2024 = HandWorkedCase540(
    name="single_aged_2024",
    filing_status="single",
    w2_wages=(108_750.0,),
    w2_ca_withholding=(6_000.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_9_senior_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 298.0,
        "f540_line_12_state_wages": 108_750.0,
        "f540_line_13_federal_agi": 108_750.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 108_750.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 108_750.0,
        "f540_line_18_deduction": 5_540.0,
        "f540_line_19_taxable_income": 103_210.0,
        "f540_line_31_tax": 6_141.0,
        "f540_line_32_exemption_credits": 298.0,
        "f540_line_33_tax_after_exemption_credits": 5_843.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 5_843.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 5_843.0,
        **_zero_balance_tail(line_64=5_843.0, line_71=6_000.0),
    },
    taxpayer_birth_date=date(1957, 6, 22),
    spouse_birth_date=None,
)

HAND_WORKED_CASES_2024: tuple[HandWorkedCase540, ...] = (
    CASE_MFJ_TWO_W2_2024,
    CASE_HOH_2024,
    CASE_SINGLE_AGED_2024,
)


# ---------------------------------------------------------------------------
# Hand-worked cases — TY2023 (MFJ, HOH, aged single)
#
# Worked by hand from the 2023 booklet in CA_540_BOOKLET_2023_PROVENANCE.
# ``compute_ca_540`` carries TY2025 constants only, so these cases are NOT
# run through it; they are checked against the production chain alone.
#
# Booklet facts used (2023 booklet page numbers):
#   - Line 7/8/9 amount: Form 540 side 1 preprint "X $144" on each of
#     lines 7, 8 and 9 (booklet PDF page 39).
#   - Line 9 senior condition: see SENIOR_BIRTH_DATE_CUTOFF_2023 (p.12).
#   - Line 18: Standard Deduction Chart for Most People (p.13): status 1/3
#     = 5,363; status 2/4/5 = 10,726. Keyed by filing status only; no
#     age-65 addition.
#   - Line 31: line 19 > 100,000 → tax rate schedules (p.13); Schedules
#     X / Y / Z (p.75). Step 4 rounds step 3 to two decimals, adds the
#     base tax, then the result is rounded to whole dollars.
#   - Line 32: AGI limitation applies only if line 13 exceeds 237,035
#     (single/MFS), 474,075 (MFJ/QSS), 355,558 (HOH) (p.14); none of
#     these cases do.
#   - Lines 33–115 flow as in ``_zero_balance_tail`` (Form 540 side 2–4:
#     L33 = L31 − L32; L35 = L33 + L34; L47 = L40 + … + L46; L48 = L35 −
#     L47; L64 = L48 + L61 + L62 + L63; L97 = L95 − L64). TY2023 line 62
#     is the Mental Health Services Tax (zero here); the ``*_bhst`` and
#     ``*_applied_to_2026`` key names are the harness's year-neutral keys.
#
# All people and amounts are synthetic.
# ---------------------------------------------------------------------------
CA_540_BOOKLET_2023_PROVENANCE: dict[str, str] = {
    "url": "https://www.ftb.ca.gov/forms/2023/2023-540-booklet.pdf",
    "edition": (
        "2023 California 540 Forms & Instructions Personal Income Tax "
        "Booklet; 80 PDF pages; Form 540 side 1 form code 3101233; PDF "
        "CreationDate 2023-10-26, ModDate 2024-03-28"
    ),
    "sha256": "e2d8ef0ba279abf65eec7941a77de6604af9186226e1e79cc80a8ecd2a14d4b9",
    "retrieved": "2026-10-15",
}

# SOURCE: 2023 booklet p.12, "Line 9 – Senior Exemptions": "If you were 65
# years of age or older by December 31, 2023*" … "*If your 65th birthday
# is on January 1, 2024, you are considered to be age 65 on December 31,
# 2023." 65th birthday on or before 2024-01-01 ⇔ born on or before
# 1959-01-01.
SENIOR_BIRTH_DATE_CUTOFF_2023 = date(1959, 1, 1)


def is_senior_2023(born: date | None) -> bool:
    """65 or older by 12/31/2023 per the TY2023 line 9 rule above."""
    return born is not None and born <= SENIOR_BIRTH_DATE_CUTOFF_2023


def senior_count_2023(case: HandWorkedCase540) -> int:
    """TY2023 Form 540 line 9 box count (side 1: "If you (or your
    spouse/RDP) are 65 or older, enter 1; if both are 65 or older, enter
    2"). No case is anyone's dependent."""
    if case.filing_status != "mfj" and case.spouse_birth_date is not None:
        raise ValueError(f"{case.name}: spouse birthdate on a non-joint case")
    return sum(
        is_senior_2023(born)
        for born in (case.taxpayer_birth_date, case.spouse_birth_date)
    )


# Case: MFJ, two W-2s, standard deduction, not renters, both under 65.
#   L12 state wages = 96,300 + 58,250 = 154,550
#   L13 federal AGI = 154,550 (wages only); L14 = 0; L15 = 154,550; L16 = 0
#   L17 CA AGI = 154,550
#   L18 std ded, chart p.13, status 2 = 10,726
#   L19 = 154,550 − 10,726 = 143,824  (> 100,000 → rate schedule)
#   L31 Schedule Y, over 136,700: 143,824 − 136,700 = 7,124;
#       7,124 × 9.3% = 662.532 → 662.53; 6,018.80 + 662.53 = 6,681.33
#       → 6,681
#   L7 status 2 → 2 × 144 = 288; L8/L9/L10 = 0; L11 = 288
#   L32: L13 154,550 ≤ 474,075 (p.14) → no AGI limitation; L32 = 288
#   L33 = 6,681 − 288 = 6,393; L34 = 0; L35 = 6,393
#   L40/43–45/46 = 0; L47 = 0; L48 = 6,393; L61–63 = 0; L64 = 6,393
#   L71 = 4,650 + 2,300 = 6,950 = L78 = L93 = L95
#   L97 = 6,950 − 6,393 = 557 = L99 = L115 refund
CASE_MFJ_TWO_W2_2023 = HandWorkedCase540(
    name="mfj_two_w2_wages_only_2023",
    filing_status="mfj",
    w2_wages=(96_300.0, 58_250.0),
    w2_ca_withholding=(4_650.0, 2_300.0),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 2.0,
        "f540_line_9_senior_exemption_count": 0.0,
        "f540_line_11_exemption_amount_pre_phaseout": 288.0,
        "f540_line_12_state_wages": 154_550.0,
        "f540_line_13_federal_agi": 154_550.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 154_550.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 154_550.0,
        "f540_line_18_deduction": 10_726.0,
        "f540_line_19_taxable_income": 143_824.0,
        "f540_line_31_tax": 6_681.0,
        "f540_line_32_exemption_credits": 288.0,
        "f540_line_33_tax_after_exemption_credits": 6_393.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 6_393.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 6_393.0,
        **_zero_balance_tail(line_64=6_393.0, line_71=6_950.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: HOH, one W-2, not a renter, no dependents listed, not aged.
#   L12 = L13 = L15 = L17 = 113,900; L14 = L16 = 0
#   L18 chart status 4 = 10,726
#   L19 = 113,900 − 10,726 = 103,174 (> 100,000 → schedule)
#   L31 Schedule Z, over 93,037: 103,174 − 93,037 = 10,137;
#       10,137 × 9.3% = 942.741 → 942.74; 3,398.97 + 942.74 = 4,341.71
#       → 4,342
#   L7 status 4 → 1 × 144 = 144; L8/L9/L10 = 0; L11 = 144
#   L32: L13 113,900 ≤ 355,558 (HOH, p.14) → no AGI limitation; L32 = 144
#   L33 = 4,342 − 144 = 4,198 = L35 = L48 = L64 (no special credits)
#   L71 = 4,750; L97 = 4,750 − 4,198 = 552 = L115 refund
CASE_HOH_2023 = HandWorkedCase540(
    name="hoh_wages_only_2023",
    filing_status="hoh",
    w2_wages=(113_900.0,),
    w2_ca_withholding=(4_750.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_9_senior_exemption_count": 0.0,
        "f540_line_11_exemption_amount_pre_phaseout": 144.0,
        "f540_line_12_state_wages": 113_900.0,
        "f540_line_13_federal_agi": 113_900.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 113_900.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 113_900.0,
        "f540_line_18_deduction": 10_726.0,
        "f540_line_19_taxable_income": 103_174.0,
        "f540_line_31_tax": 4_342.0,
        "f540_line_32_exemption_credits": 144.0,
        "f540_line_33_tax_after_exemption_credits": 4_198.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 4_198.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 4_198.0,
        **_zero_balance_tail(line_64=4_198.0, line_71=4_750.0),
    },
    taxpayer_birth_date=None,
    spouse_birth_date=None,
)

# Case: single, aged, one W-2, not a renter.
#   Taxpayer born 1956-09-03 ≤ 1959-01-01 cutoff → 67 on 12/31/2023 → senior
#   L12 = L13 = L15 = L17 = 112,400; L14 = L16 = 0
#   L18 chart status 1 = 5,363 (no age addition)
#   L19 = 112,400 − 5,363 = 107,037 (> 100,000 → schedule)
#   L31 Schedule X, over 68,350: 107,037 − 68,350 = 38,687;
#       38,687 × 9.3% = 3,597.891 → 3,597.89; 3,009.40 + 3,597.89
#       = 6,607.29 → 6,607
#   L7 status 1 → 1 × 144 = 144; L8 = 0; L9 1 × 144 = 144; L10 = 0
#   L11 = 144 + 144 = 288
#   L32: L13 112,400 ≤ 237,035 → no AGI limitation; L32 = 288
#   L33 = 6,607 − 288 = 6,319 = L35 = L48 = L64 (no special credits)
#   L71 = 6,600; L97 = 6,600 − 6,319 = 281 = L115 refund
CASE_SINGLE_AGED_2023 = HandWorkedCase540(
    name="single_aged_2023",
    filing_status="single",
    w2_wages=(112_400.0,),
    w2_ca_withholding=(6_600.0,),
    taxable_interest=0.0,
    renter_six_months_in_ca=False,
    line_31_method="tax_rate_schedule",
    expected={
        "f540_line_7_personal_exemption_count": 1.0,
        "f540_line_9_senior_exemption_count": 1.0,
        "f540_line_11_exemption_amount_pre_phaseout": 288.0,
        "f540_line_12_state_wages": 112_400.0,
        "f540_line_13_federal_agi": 112_400.0,
        "f540_line_14_ca_subtractions": 0.0,
        "f540_line_15": 112_400.0,
        "f540_line_16_ca_additions": 0.0,
        "f540_line_17_ca_agi": 112_400.0,
        "f540_line_18_deduction": 5_363.0,
        "f540_line_19_taxable_income": 107_037.0,
        "f540_line_31_tax": 6_607.0,
        "f540_line_32_exemption_credits": 288.0,
        "f540_line_33_tax_after_exemption_credits": 6_319.0,
        "f540_line_34_lump_sum_tax": 0.0,
        "f540_line_35_total_tax_before_special_credits": 6_319.0,
        "f540_line_40_dep_care_credit": 0.0,
        "f540_line_43_45_other_special_credits": 0.0,
        "f540_line_46_renters_credit": 0.0,
        "f540_line_47_total_nonrefundable_credits": 0.0,
        "f540_line_48_tax_after_special_credits": 6_319.0,
        **_zero_balance_tail(line_64=6_319.0, line_71=6_600.0),
    },
    taxpayer_birth_date=date(1956, 9, 3),
    spouse_birth_date=None,
)

HAND_WORKED_CASES_2023: tuple[HandWorkedCase540, ...] = (
    CASE_MFJ_TWO_W2_2023,
    CASE_HOH_2023,
    CASE_SINGLE_AGED_2023,
)


__all__ = [
    # Hand-worked cases
    "CA_540_BOOKLET_2025_PROVENANCE",
    "HandWorkedCase540",
    "HAND_WORKED_STATUS_CASES_2025",
    "CASE_MFJ_TWO_W2_2025",
    "CASE_MFJ_W2_PLUS_INTEREST_2025",
    "CASE_HOH_RENTER_2025",
    "CASE_HOH_HIGHER_WAGES_2025",
    "HAND_WORKED_AGED_CASES_2025",
    "CASE_SINGLE_AGED_2025",
    "CASE_MFJ_BOTH_AGED_2025",
    "CASE_MFJ_SPOUSE_ONLY_AGED_2025",
    "SENIOR_BIRTH_DATE_CUTOFF_2025",
    "senior_count_2025",
    "is_senior_2025",
    "CA_540_BOOKLET_2024_PROVENANCE",
    "HAND_WORKED_CASES_2024",
    "CASE_MFJ_TWO_W2_2024",
    "CASE_HOH_2024",
    "CASE_SINGLE_AGED_2024",
    "SENIOR_BIRTH_DATE_CUTOFF_2024",
    "senior_count_2024",
    "is_senior_2024",
    "CA_540_BOOKLET_2023_PROVENANCE",
    "HAND_WORKED_CASES_2023",
    "CASE_MFJ_TWO_W2_2023",
    "CASE_HOH_2023",
    "CASE_SINGLE_AGED_2023",
    "SENIOR_BIRTH_DATE_CUTOFF_2023",
    "senior_count_2023",
    "is_senior_2023",
    # Enums / constants
    "FilingStatus",
    "STANDARD_DEDUCTION_2025",
    "EXEMPTION_CREDIT_PERSONAL_2025",
    "EXEMPTION_CREDIT_BLIND_2025",
    "EXEMPTION_CREDIT_SENIOR_2025",
    "EXEMPTION_CREDIT_DEPENDENT_2025",
    "AGI_PHASEOUT_THRESHOLD_2025",
    "BHST_THRESHOLD_2025",
    "BHST_RATE_2025",
    "RENTERS_CREDIT_SINGLE_MFS_2025",
    "RENTERS_CREDIT_HOUSEHOLD_2025",
    "TAX_RATE_SCHEDULE_X_2025",
    "TAX_RATE_SCHEDULE_Y_2025",
    "TAX_RATE_SCHEDULE_Z_2025",
    # Dataclasses
    "Demographics",
    "FederalCarryIn",
    "SchCAPartIAdjustments",
    "SchCAPartIIAdjustments",
    "Form540Payments",
    "Form540Credits",
    "Form540OtherTaxes",
    "Form540Misc",
    "ScopeOut",
    "CA540Input",
    # Entry point
    "compute_ca_540",
]
