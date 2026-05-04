"""CA Schedule D (540) compute — federal pass-through with worksheet divergence support.

When the user supplies federal-state Sch D divergences (§1202 QSBS exclusion,
§1045 QSBS rollover, §1400Z QOZ deferrals, pre-1987 inherited basis,
Peace Corps principal-residence service) via the `<basename>.ca.fods`
Sch D 540 tab, those adjustments are summed and applied to the federal
net (Sch D line 16). Without worksheet entries, federal Sch D net flows
through unchanged.
"""

from collections.abc import Sequence

from tenforty.models import CASchD540Adjustment, DivergenceDirection
from tenforty.rounding import irs_round


def compute(
    federal_results: dict,
    worksheet_adjustments: Sequence[CASchD540Adjustment] = (),
) -> dict:
    federal_net = federal_results.get("schd_line16", 0.0) or 0.0
    subs = sum(a.amount for a in worksheet_adjustments
               if a.direction == DivergenceDirection.SUBTRACTION)
    adds = sum(a.amount for a in worksheet_adjustments
               if a.direction == DivergenceDirection.ADDITION)
    net = federal_net - subs + adds

    return {
        "sch_d_540_federal_net": irs_round(federal_net),
        "sch_d_540_net_capital_gain": irs_round(net),
        "sch_d_540_total_subtractions": irs_round(subs),
        "sch_d_540_total_additions": irs_round(adds),
    }
