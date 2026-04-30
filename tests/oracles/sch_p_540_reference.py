"""CA FTB Schedule P (540) reference oracle (TY2025).

Computes California AMT (Part I + Part II) and the Part III credit-
limitation pipeline for CA residents. Consumes CA-basis adjustments
per-line; does NOT use federal Form 6251 as a starting point.

### Output contract

``compute_sch_p_540(inp: SchP540Input) -> dict`` returns a flat dict.
See ``README.md`` for the full output contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FilingStatus = Literal["single", "mfj", "mfs", "hoh", "qss"]


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PartIAdjustments:
    """Per-line CA-basis adjustment amounts for Sch P (540) Part I lines 2-13.

    Caller supplies each per-line amount directly. The oracle does NOT
    recompute adjustments from raw asset basis or depreciation schedules —
    it aggregates the caller-determined amounts per the form face. Every
    value uses CA basis, not federal.
    """
    medical_dental: float              # line 2 — smaller of fed Sch A line 4 or 2.5% × fed AGI
    property_taxes: float              # line 3
    home_mortgage_interest: float      # line 4
    misc_itemized: float               # line 5
    property_tax_refund: float         # line 6 (negative — state income-tax refund excluded)
    investment_interest: float         # line 7
    post_1986_depreciation: float      # line 8 (CA basis)
    adjusted_gain_or_loss: float       # line 9 (CA basis)
    iso_cqso: float                    # line 10 — ISO / CQSO bargain-element
    passive_activity: float            # line 11 (CA basis)
    estate_trust_beneficiary: float    # line 12 — from Sch K-1 (541) line 12a
    other_adjustments_preferences: float  # line 13 — sub-items a-l pre-summed


@dataclass(frozen=True)
class CreditEntry:
    """A single nonrefundable credit for Part III processing.

    ``code`` identifies the credit and determines its section placement:
    - Section A (capped at excess tax): "162", "232", "188", and unlabeled
    - Section B (below-TMT): "170", "173", "163", "renter", "187", "242",
      and unlabeled
    - Section C (reduce AMT): "180", "181"
    """
    code: str
    amount: float


# Section routing by credit code.
_SECTION_A_CODES = {"162", "232", "188"}
_SECTION_B_CODES = {"170", "173", "163", "renter", "187", "242"}
_SECTION_C_CODES = {"180", "181"}


@dataclass(frozen=True)
class SchP540Input:
    """Top-level input for the Sch P (540) oracle.

    Mirrors the field-name conventions of ``ca_540_reference`` where
    applicable so the two oracles chain cleanly.
    """
    filing_status: FilingStatus
    federal_agi: float
    ca_taxable_income: float                 # Form 540 line 19 → Sch P line 15
    ca_regular_tax_before_credits: float     # Form 540 line 31 → Sch P line 25
    itemized_deduction_used: bool            # structural branch at Sch P line 1
    standard_deduction_amount: float         # Form 540 line 18 (if std-ded path)
    adjustments: PartIAdjustments            # lines 2-13
    ca_nol_deductions_9b: float              # line 16 (positive NOL add-back)
    amti_exclusion_amount: float             # line 17 (negative; §17062.5)
    amt_nol_deduction_post_90pct_cap: float  # line 20 (attested; oracle guards 90% cap)
    total_tax_before_credits: float          # Form 540 line 35 → Part III line 1
    credits: tuple[CreditEntry, ...]         # Part III credit entries


# ---------------------------------------------------------------------------
# Line 18 thresholds — high-AGI itemized-deduction haircut (R&TC §17077)
# DIFFERENT grouping from Part II exemption phaseout thresholds (§17062).
# Line 18: single+MFS share a threshold; line 22: single+HoH share one.
# ---------------------------------------------------------------------------
_LINE_18_HAIRCUT_THRESHOLD: dict[str, float] = {
    "single": 252_203.0,
    "mfs":    252_203.0,
    "hoh":    378_310.0,
    "mfj":    504_411.0,
    "qss":    504_411.0,
}
_HAIRCUT_RATE = 0.06


# ---------------------------------------------------------------------------
# Part I — AMTI build-up (lines 1-21)
# ---------------------------------------------------------------------------
def _compute_part_i(inp: SchP540Input) -> dict:
    """Lines 1-21: Adjustments, Preferences, and AMTI."""
    # SOURCE: 2025 Sch P (540) form face, Part I.
    a = inp.adjustments

    # Line 1: structural branch. If std-ded, line 1 = std_ded (skip to 6).
    # If itemized, line 1 = 0 (populate lines 2-7 add-backs).
    if inp.itemized_deduction_used:
        line_1 = 0.0
    else:
        line_1 = inp.standard_deduction_amount

    # Lines 2-7: itemized add-backs (zero when std-ded branch, per form).
    line_2 = a.medical_dental
    line_3 = a.property_taxes
    line_4 = a.home_mortgage_interest
    line_5 = a.misc_itemized
    line_6 = a.property_tax_refund
    line_7 = a.investment_interest

    # Lines 8-12: CA-basis adjustments.
    line_8 = a.post_1986_depreciation
    line_9 = a.adjusted_gain_or_loss
    line_10 = a.iso_cqso
    line_11 = a.passive_activity
    line_12 = a.estate_trust_beneficiary

    # Line 13: other adjustments/preferences sub-items a-l pre-summed.
    line_13 = a.other_adjustments_preferences

    # Line 14: Total Adjustments and Preferences.
    line_14 = (
        line_1 + line_2 + line_3 + line_4 + line_5 + line_6 + line_7
        + line_8 + line_9 + line_10 + line_11 + line_12 + line_13
    )

    # Line 15: CA taxable income (Form 540 line 19).
    line_15 = inp.ca_taxable_income

    # Line 16: NOL add-back (positive; from Sch CA Part I §B lines 9b).
    line_16 = inp.ca_nol_deductions_9b

    # Line 17: AMTI exclusion (negative; §17062.5 small-business carve-out).
    line_17 = inp.amti_exclusion_amount

    # Line 18: high-AGI itemized-deduction haircut (§17077). Only applies
    # when itemizing AND fed AGI exceeds the filing-status-keyed threshold.
    # SOURCE: 2025 Sch P (540) form face line 18 + R&TC §17077.
    if inp.itemized_deduction_used:
        threshold_18 = _LINE_18_HAIRCUT_THRESHOLD[inp.filing_status]
        excess = max(0.0, inp.federal_agi - threshold_18)
        line_18 = _HAIRCUT_RATE * excess
    else:
        line_18 = 0.0

    # Line 19: combine 14-18.
    line_19 = line_14 + line_15 + line_16 + line_17 + line_18

    # Line 20: AMT-NOL deduction (attested). Capped at 90% of line 19
    # per R&TC §17276.20; violation is a caller bug.
    line_20 = inp.amt_nol_deduction_post_90pct_cap
    if line_20 > 0.0 and line_19 > 0.0 and line_20 > 0.90 * line_19:
        raise ValueError(
            f"AMT-NOL deduction ({line_20}) exceeds 90% of pre-NOL AMTI "
            f"({line_19}). R&TC §17276.20 caps at 90%. Caller must apply "
            f"the cap before passing to the oracle."
        )

    # Line 21: AMTI = line 19 − line 20.
    line_21 = line_19 - line_20

    return {
        "schp_540_line_1_std_ded_or_zero": line_1,
        "schp_540_line_2_medical_dental": line_2,
        "schp_540_line_3_property_taxes": line_3,
        "schp_540_line_4_home_mortgage_interest": line_4,
        "schp_540_line_5_misc_itemized": line_5,
        "schp_540_line_6_property_tax_refund": line_6,
        "schp_540_line_7_investment_interest": line_7,
        "schp_540_line_8_post_1986_depreciation": line_8,
        "schp_540_line_9_adjusted_gain_or_loss": line_9,
        "schp_540_line_10_iso_cqso": line_10,
        "schp_540_line_11_passive_activity": line_11,
        "schp_540_line_12_estate_trust_beneficiary": line_12,
        "schp_540_line_13_other_adjustments_preferences": line_13,
        "schp_540_line_14_total_adjustments_preferences": line_14,
        "schp_540_line_15_ca_taxable_income": line_15,
        "schp_540_line_16_nol_add_back": line_16,
        "schp_540_line_17_amti_exclusion": line_17,
        "schp_540_line_18_itemized_haircut": line_18,
        "schp_540_line_19_combined": line_19,
        "schp_540_line_20_amt_nol_deduction": line_20,
        "schp_540_line_21_amti": line_21,
        "schp_540_amti": line_21,
    }


# ---------------------------------------------------------------------------
# Part II — Exemption, TMT, AMT (lines 22-26)
# ---------------------------------------------------------------------------
# SOURCE: 2025 Sch P (540) form face, Part II. Exemption amounts and
# phaseout thresholds are CA-indexed under R&TC §17062, not pegged to
# IRC §55(d). Separate from the §17077 itemized-haircut thresholds.
_AMT_EXEMPTION: dict[str, float] = {
    "single": 92_749.0,
    "hoh":    92_749.0,
    "mfj":   123_667.0,
    "qss":   123_667.0,
    "mfs":    61_830.0,
}

_AMT_PHASEOUT_THRESHOLD: dict[str, float] = {
    "single": 347_808.0,
    "hoh":    347_808.0,
    "mfj":   463_745.0,
    "qss":   463_745.0,
    "mfs":   231_868.0,
}

_AMT_PHASEOUT_RATE = 0.25

# SOURCE: R&TC §17062(a) — single flat rate, no bracket split.
_CA_AMT_RATE = 0.07


def _compute_part_ii(amti: float, filing_status: str,
                     regular_tax: float) -> dict:
    """Lines 22-26: Exemption with phaseout, TMT at 7%, and AMT."""
    base_exemption = _AMT_EXEMPTION[filing_status]
    threshold = _AMT_PHASEOUT_THRESHOLD[filing_status]

    # Phaseout: reduce exemption by 25% of (AMTI − threshold), floor 0.
    if amti > threshold:
        reduction = _AMT_PHASEOUT_RATE * (amti - threshold)
        line_22 = max(0.0, base_exemption - reduction)
    else:
        line_22 = base_exemption

    # Line 23: AMTI − exemption (floor 0).
    line_23 = max(0.0, amti - line_22)

    # Line 24: Tentative Minimum Tax.
    line_24 = line_23 * _CA_AMT_RATE

    # Line 25: regular tax before credits (Form 540 line 31).
    line_25 = regular_tax

    # Line 26: AMT = max(0, TMT − regular tax).
    line_26 = max(0.0, line_24 - line_25)

    return {
        "schp_540_line_22_exemption": line_22,
        "schp_540_line_23_amti_minus_exemption": line_23,
        "schp_540_line_24_tmt": line_24,
        "schp_540_tentative_minimum_tax": line_24,
        "schp_540_line_25_regular_tax": line_25,
        "schp_540_line_26_amt": line_26,
        "schp_540_amt_due": line_26,
    }


# ---------------------------------------------------------------------------
# Part III — Credit Limitations
# ---------------------------------------------------------------------------
def _credit_section(code: str) -> str:
    """Route a credit code to its Part III section."""
    if code in _SECTION_A_CODES:
        return "A"
    if code in _SECTION_B_CODES:
        return "B"
    if code in _SECTION_C_CODES:
        return "C"
    raise ValueError(f"Unknown credit code '{code}' — cannot route to Part III section.")


def _compute_part_iii(
    total_tax_before_credits: float,
    tmt: float,
    amt_from_part_ii: float,
    credits: tuple[CreditEntry, ...],
) -> dict:
    """Part III: sequential credit-limitation pipeline.

    Section A: credits limited to excess_tax = total_tax − TMT (floor 0).
    Section B: credits that can reduce below TMT (to zero).
    Section C: credits that reduce AMT itself.
    """
    # SOURCE: 2025 Sch P (540) form face, Part III.
    excess_tax = max(0.0, total_tax_before_credits - tmt)

    # Partition credits by section, preserving input order within each.
    section_a = [c for c in credits if _credit_section(c.code) == "A"]
    section_b = [c for c in credits if _credit_section(c.code) == "B"]
    section_c = [c for c in credits if _credit_section(c.code) == "C"]

    credit_caps: dict[str, dict[str, float]] = {}

    # Section A: consume from excess_tax balance.
    remaining_a = excess_tax
    for c in section_a:
        capped = min(c.amount, remaining_a)
        remaining_a -= capped
        credit_caps[c.code] = {"uncapped": c.amount, "capped": capped}

    # Section B: consume from remaining tax (total_tax − section_a_used).
    # Section B credits can reduce below TMT → remaining balance is
    # total_tax − (excess_tax − remaining_a) = total_tax − section_a_used.
    section_a_used = excess_tax - remaining_a
    remaining_b = total_tax_before_credits - section_a_used
    for c in section_b:
        capped = min(c.amount, max(0.0, remaining_b))
        remaining_b -= capped
        credit_caps[c.code] = {"uncapped": c.amount, "capped": capped}

    # Section C: consume from AMT itself.
    remaining_amt = amt_from_part_ii
    for c in section_c:
        capped = min(c.amount, max(0.0, remaining_amt))
        remaining_amt -= capped
        credit_caps[c.code] = {"uncapped": c.amount, "capped": capped}

    adjusted_amt = max(0.0, remaining_amt)

    return {
        "schp_540_credit_caps": credit_caps,
        "schp_540_amt_due": adjusted_amt,
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def compute_sch_p_540(inp: SchP540Input) -> dict:
    """Compute Sch P (540) Part I (AMTI) + Part II (TMT/AMT) + Part III."""
    out: dict = {}
    part_i = _compute_part_i(inp)
    out.update(part_i)
    part_ii = _compute_part_ii(
        part_i["schp_540_line_21_amti"],
        inp.filing_status,
        inp.ca_regular_tax_before_credits,
    )
    out.update(part_ii)

    part_iii = _compute_part_iii(
        inp.total_tax_before_credits,
        part_ii["schp_540_line_24_tmt"],
        part_ii["schp_540_line_26_amt"],
        inp.credits,
    )
    out.update(part_iii)
    return out
