"""Form 8995 — Qualified Business Income Deduction Simplified Computation.

v1 scope: simple path only. When taxable income exceeds the Rev. Proc.
2024-40 threshold AND the scenario actually has QBI to deduct, the
scenario must attest with `acknowledges_qbi_below_threshold: true` to
accept that the simple path is being used in place of Form 8995-A
(scoped out of v1). If qbi_total == 0 the threshold gate is
unconditionally skipped — there is no deduction to compute.

net_capital_gain simplification (v1): per Form 8995 Inst, the correct
figure is `qualified_dividends + net_LTCG − net_STCL`. v1 narrows to
`qualified_dividends + max(0, net_LTCG)`, since K-1-only scenarios
rarely realize a net short-term capital loss worth netting. Scenarios
with a meaningful STCL will slightly over-state the income limit and
under-state the deduction — documented limitation.
"""

from tenforty.constants import y2025
from tenforty.models import Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    fanout = upstream.get("_k1_fanout", {})
    f1040 = upstream.get("f1040", {})

    taxable_income = float(f1040.get("taxable_income_before_qbi_deduction", 0))
    net_cap_gain = float(f1040.get("net_capital_gain", 0))
    threshold = y2025.QBI_THRESHOLD[scenario.config.filing_status]

    qbi_total = float(fanout.get("qbi_total", 0.0))
    qualified_divs = float(fanout.get("qualified_dividends_total", 0.0))

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

    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
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
        "taxpayer_name": f"{first} {last}".strip(),
        "taxpayer_ssn": scenario.config.ssn,
    }
