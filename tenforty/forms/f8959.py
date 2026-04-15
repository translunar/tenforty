"""Form 8959 — Additional Medicare Tax.

v1 scope: W-2 Medicare wages only. Self-employment income (Part II),
RRTA compensation (Part III), and wages from Form 8919 are not
supported — those lines are emitted as zero. The oracle workbook only
exposes the two summary totals (``F8959_Tax`` = line 18,
``F8959_WH`` = line 24) as named ranges, so every intermediate line is
computed natively here and the two totals are cross-checked against the
oracle with a divergence WARNING on mismatch.

Threshold table (2025, Form 8959 instructions):

    Single / HoH / Qualifying widow(er)   $200,000
    Married filing jointly                $250,000
    Married filing separately             $125,000

Rates: 0.9% additional Medicare tax above the threshold; 1.45% regular
Medicare tax on all Medicare wages (used in the line 21 reconciliation).
"""

import logging

from tenforty.models import FilingStatus, Scenario
from tenforty.rounding import irs_round

log = logging.getLogger(__name__)

_ADDITIONAL_MEDICARE_RATE = 0.009
_REGULAR_MEDICARE_RATE = 0.0145

_THRESHOLDS: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 200_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 200_000,
    FilingStatus.QUALIFYING_WIDOW: 200_000,
    FilingStatus.MARRIED_JOINTLY: 250_000,
    FilingStatus.MARRIED_SEPARATELY: 125_000,
}


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream.get("f1040", {})
    threshold = _THRESHOLDS[scenario.config.filing_status]
    medicare_wages = sum(w.medicare_wages for w in scenario.w2s)
    medicare_withheld = sum(w.medicare_tax_withheld for w in scenario.w2s)

    # Part I — wages
    line_1 = medicare_wages
    line_2 = 0.0  # unreported tips (v1: not supported)
    line_3 = 0.0  # 8919 wages (v1: not supported)
    line_4 = line_1 + line_2 + line_3
    line_5 = threshold
    line_6 = max(0.0, line_4 - line_5)
    line_7 = line_6 * _ADDITIONAL_MEDICARE_RATE

    # Part II — self-employment (v1: zero)
    line_8 = 0.0
    line_9 = threshold
    line_10 = line_4
    line_11 = max(0.0, line_9 - line_10)
    line_12 = max(0.0, line_8 - line_11)
    line_13 = line_12 * _ADDITIONAL_MEDICARE_RATE

    # Part III — RRTA (v1: zero)
    line_14 = 0.0
    line_15 = threshold
    line_16 = max(0.0, line_14 - line_15)
    line_17 = line_16 * _ADDITIONAL_MEDICARE_RATE

    # Part IV — total
    line_18 = line_7 + line_13 + line_17

    # Part V — withholding reconciliation
    line_19 = medicare_withheld
    line_20 = line_1
    line_21 = line_20 * _REGULAR_MEDICARE_RATE
    line_22 = max(0.0, line_19 - line_21)
    line_23 = 0.0  # RRTA additional withholding (v1: zero)
    line_24 = line_22 + line_23

    result: dict = {
        "taxpayer_name": _format_taxpayer_name(scenario),
        "taxpayer_ssn": scenario.config.ssn,
        "f8959_line_1": irs_round(line_1),
        "f8959_line_2": irs_round(line_2),
        "f8959_line_3": irs_round(line_3),
        "f8959_line_4": irs_round(line_4),
        "f8959_line_5": irs_round(line_5),
        "f8959_line_6": irs_round(line_6),
        "f8959_line_7": irs_round(line_7),
        "f8959_line_8": irs_round(line_8),
        "f8959_line_9": irs_round(line_9),
        "f8959_line_10": irs_round(line_10),
        "f8959_line_11": irs_round(line_11),
        "f8959_line_12": irs_round(line_12),
        "f8959_line_13": irs_round(line_13),
        "f8959_line_14": irs_round(line_14),
        "f8959_line_15": irs_round(line_15),
        "f8959_line_16": irs_round(line_16),
        "f8959_line_17": irs_round(line_17),
        "f8959_line_18": irs_round(line_18),
        "f8959_line_19": irs_round(line_19),
        "f8959_line_20": irs_round(line_20),
        "f8959_line_21": irs_round(line_21),
        "f8959_line_22": irs_round(line_22),
        "f8959_line_23": irs_round(line_23),
        "f8959_line_24": irs_round(line_24),
    }

    _cross_check(result, "f8959_line_18", f1040.get("f8959_tax_total"), "F8959_Tax")
    _cross_check(
        result, "f8959_line_24",
        f1040.get("additional_medicare_withheld"), "F8959_WH",
    )
    return result


def _cross_check(result: dict, key: str, oracle_value, oracle_name: str) -> None:
    if oracle_value is None:
        return
    oracle_rounded = irs_round(oracle_value)
    if result[key] != oracle_rounded:
        log.warning(
            "Form 8959 %s native compute %s diverges from oracle %s=%s; "
            "keeping native value.",
            key, result[key], oracle_name, oracle_rounded,
        )


def _format_taxpayer_name(scenario: Scenario) -> str:
    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return f"{first} {last}".strip()
