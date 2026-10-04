"""CA Schedule D (540) compute — federal pass-through.

Federal Sch D net (Sch D line 16) flows through unchanged. The
``worksheet_adjustments`` parameter is a dormant hook for the future CA
Schedule D (540) user-divergence compute follow-up (§1202 QSBS exclusion,
§1045 QSBS rollover, §1400Z QOZ deferrals, pre-1987 inherited basis,
Peace Corps principal-residence service): when supplied, adjustments are
summed and applied to the federal net. No caller populates it today — the
retired FODS worksheet import that once fed it was removed (see
docs/specs/2026-07-19-ca-divergence-catalog-redesign.md §3); the
``CASchD540Adjustment`` schema is retained for that follow-up.
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


def is_required(results: dict) -> bool:
    """Whether Schedule D (540) belongs in the return at all.

    The schedule's own instructions (2021-2025): "Do not complete this schedule
    if all of your California gains (losses) are the same as your federal gains
    (losses)." California differs from federal exactly when ``compute`` applied
    an adjustment, so the test is on the two adjustment totals, not on the net
    (offsetting adjustments leave the net unchanged yet still differ line by
    line). Reads the keys strictly: a results dict without them is a caller
    error, never a silent "not required".
    """
    return bool(results["sch_d_540_total_subtractions"]
                or results["sch_d_540_total_additions"])
