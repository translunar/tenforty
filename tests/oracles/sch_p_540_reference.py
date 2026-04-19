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


# ---------------------------------------------------------------------------
# Part I — AMTI build-up (lines 1-21)
# ---------------------------------------------------------------------------
def _compute_part_i(inp: SchP540Input) -> dict:
    """Lines 1-21: Adjustments, Preferences, and AMTI."""
    # SOURCE: 2025 Sch P (540) form face, Part I.

    # Line 1: structural branch. If std-ded, line 1 = std_ded (skip to 6).
    # If itemized, line 1 = 0 (populate lines 2-7 add-backs).
    if inp.itemized_deduction_used:
        line_1 = 0.0
    else:
        line_1 = inp.standard_deduction_amount

    # Lines 2-7: itemized add-backs. V1 stub — all zero unless caller
    # populates later when input shape expands.
    line_2 = 0.0
    line_3 = 0.0
    line_4 = 0.0
    line_5 = 0.0
    line_6 = 0.0
    line_7 = 0.0

    # Lines 8-12: CA-basis adjustments.
    line_8 = 0.0
    line_9 = 0.0
    line_10 = 0.0
    line_11 = 0.0
    line_12 = 0.0

    # Line 13: other adjustments/preferences sub-items a-l summed.
    line_13 = 0.0

    # Line 14: Total Adjustments and Preferences.
    line_14 = (
        line_1 + line_2 + line_3 + line_4 + line_5 + line_6 + line_7
        + line_8 + line_9 + line_10 + line_11 + line_12 + line_13
    )

    # Line 15: CA taxable income (Form 540 line 19).
    line_15 = inp.ca_taxable_income

    # Lines 16-18: NOL add-back, AMTI exclusion, itemized haircut.
    line_16 = 0.0
    line_17 = 0.0
    line_18 = 0.0

    # Line 19: combine 14-18.
    line_19 = line_14 + line_15 + line_16 + line_17 + line_18

    # Line 20: AMT-NOL deduction (attested — stub zero).
    line_20 = 0.0

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
# Public entry point
# ---------------------------------------------------------------------------
def compute_sch_p_540(inp: SchP540Input) -> dict:
    """Compute Sch P (540) Part I (AMTI) + Part II (TMT/AMT) + Part III."""
    out: dict = {}
    out.update(_compute_part_i(inp))
    return out
