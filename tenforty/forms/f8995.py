"""Form 8995 — Qualified Business Income Deduction (simplified).

Scope: v1 simple path only. Over-threshold scenarios with nonzero QBI
require Form 8995-A (not implemented) and raise NotImplementedError at
compute time — the gate message carries the full explanation.

net_capital_gain simplification: v1 uses `qualified_dividends + max(0,
net_LTCG)` in place of `qualified_dividends + net_LTCG − net_STCL`.
K-1-only scenarios rarely realize a meaningful STCL worth netting; a
scenario with a meaningful STCL will slightly under-state the deduction.
"""

from tenforty.constants import y2025
from tenforty.models import K1FanoutData, Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()
    f1040 = upstream.get("f1040", {})

    taxable_income = float(f1040.get("taxable_income_before_qbi_deduction", 0))
    net_cap_gain = float(f1040.get("net_capital_gain", 0))
    threshold = y2025.QBI_THRESHOLD[scenario.config.filing_status]

    qbi_total = fanout.qbi_aggregate
    qualified_divs = fanout.qualified_dividends_aggregate

    if (qbi_total > 0
            and taxable_income > threshold
            and not scenario.config.acknowledges_qbi_below_threshold):
        raise NotImplementedError(
            f"Taxable income before QBI ({taxable_income:.0f}) exceeds the "
            f"Form 8995 simple-path threshold ({threshold}) for filing "
            f"status {scenario.config.filing_status.value}, and the "
            f"scenario has {qbi_total:.0f} of QBI. Form 8995-A "
            "is not implemented in tenforty v1. Set "
            "`acknowledges_qbi_below_threshold: true` ONLY if you have "
            "confirmed that the simple-path formula is correct for your "
            "return; otherwise this return cannot be produced by v1."
        )

    line_1 = irs_round(qbi_total)
    line_2 = line_1
    line_3 = irs_round(0.20 * line_2)
    line_4 = 0
    line_5 = 0
    line_6 = line_3 + line_5

    line_11 = irs_round(taxable_income)
    line_12 = irs_round(max(0, net_cap_gain) + qualified_divs)
    line_13 = max(0, line_11 - line_12)
    line_14 = irs_round(0.20 * line_13)

    line_15 = min(line_6, line_14)

    return {
        "f8995_line_1_qbi": line_1,
        "f8995_line_2_total_qbi": line_2,
        "f8995_line_3_component": line_3,
        "f8995_line_4_reit_ptp": line_4,
        "f8995_line_5_reit_ptp_component": line_5,
        "f8995_line_6_total_before_limit": line_6,
        "f8995_line_11_taxable_income": line_11,
        "f8995_line_12_net_capital_gain": line_12,
        "f8995_line_13_subtract": line_13,
        "f8995_line_14_income_limit": line_14,
        "f8995_line_15_qbi_deduction": line_15,
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }
