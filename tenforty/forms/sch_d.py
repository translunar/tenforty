"""Schedule D — Capital Gains and Losses.

v1: SUMMARY PATH ONLY. Collapses 1099-B transactions where basis was
reported to the IRS and no adjustments apply into per-term line 1a / 8a
summary totals. Per-lot emission through Form 8949 is not yet wired up;
when it lands, this module will consume that upstream state rather than
summing lots directly.
"""

from tenforty.models import Form1099B, K1FanoutData, Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    short_lots: list[Form1099B] = []
    long_lots: list[Form1099B] = []
    for lot in scenario.form1099_b:
        (short_lots if lot.short_term else long_lots).append(lot)

    short = _summarize(short_lots)
    lng = _summarize(long_lots)

    fanout = upstream.get("k1_fanout") or K1FanoutData.empty()
    k1_short = irs_round(sum(fanout.sch_d_short_term_additions))
    k1_long = irs_round(sum(fanout.sch_d_long_term_additions))

    return {
        "sch_d_line_1a_proceeds": short["proceeds"],
        "sch_d_line_1a_basis": short["basis"],
        "sch_d_line_1a_gain": short["gain"],
        "sch_d_line_5_net_short_k1": k1_short,
        "sch_d_line_7_net_short": short["gain"] + k1_short,
        "sch_d_line_8a_proceeds": lng["proceeds"],
        "sch_d_line_8a_basis": lng["basis"],
        "sch_d_line_8a_gain": lng["gain"],
        "sch_d_line_12_net_long_k1": k1_long,
        "sch_d_line_15_net_long": lng["gain"] + k1_long,
        "sch_d_line_16_total": (short["gain"] + k1_short) + (lng["gain"] + k1_long),
        "taxpayer_name": scenario.config.full_name,
        "taxpayer_ssn": scenario.config.ssn,
    }


def _summarize(lots: list[Form1099B]) -> dict:
    proceeds = irs_round(sum(lot.proceeds for lot in lots))
    basis = irs_round(sum(lot.cost_basis for lot in lots))
    return {"proceeds": proceeds, "basis": basis, "gain": proceeds - basis}
