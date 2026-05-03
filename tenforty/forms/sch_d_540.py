"""CA Schedule D (540) compute — federal-pass-through with QSBS scope-out.

CA mostly mirrors federal Sch D; the divergences (§1202 QSBS exclusion,
§1045 QSBS rollover, §1400Z QOZ deferrals, pre-1987 inherited basis,
Peace Corps principal residence) are scoped out for v1 via the
acknowledges_no_ca_sch_d_federal_state_divergence attestation. When True,
Sch D 540 = federal Sch D net result. When False, raise.
"""

from tenforty.rounding import irs_round


def compute(federal_results: dict, config: dict) -> dict:
    if not config.get("acknowledges_no_ca_sch_d_federal_state_divergence", False):
        raise NotImplementedError(
            "CA Schedule D federal-state divergences (§1202/§1045/§1400Z/"
            "pre-1987 inherited basis/Peace Corps) are not implemented in v1. "
            "Set acknowledges_no_ca_sch_d_federal_state_divergence=True to "
            "affirm none apply."
        )
    federal_net = federal_results.get("schd_line16", 0.0) or 0.0
    return {
        "sch_d_540_net_capital_gain": irs_round(federal_net),
    }
