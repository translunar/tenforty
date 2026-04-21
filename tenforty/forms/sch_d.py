"""Schedule D — Capital Gains and Losses.

v1: SUMMARY PATH ONLY. Collapses 1099-B transactions where basis was
reported to the IRS and no adjustments apply into per-term line 1a / 8a
summary totals.

Form 8949 scope-out gate (enforced here, pre-gated at scenario load via
``TaxReturnConfig.acknowledges_form_8949_unsupported``):

  * ack == False + any 8949-required lot  → raise EightFortyNineRequired
    (the return cannot be produced; 8949 support is deferred).
  * ack == True  + any 8949-required lot  → drop the lot from totals,
    log a WARNING per dropped lot; the taxpayer has explicitly accepted
    the incompleteness so they can reconcile manually.
  * ack either value + only-covered-no-adjustment lots → totals
    unchanged; the gate does not fire.

There is no "skip Sch D with a warning" orchestrator behavior — that
was the prior design and it silently dropped reportable capital-gain
activity, the same failure class as Sch B Part III. The gate now
forces an explicit attestation at scenario load.
"""

import logging

from tenforty.models import Form1099B, K1FanoutData, Scenario
from tenforty.rounding import irs_round

log = logging.getLogger(__name__)


class EightFortyNineRequired(NotImplementedError):
    """Raised when a 1099-B lot needs Form 8949 and the scenario has not
    acknowledged the 8949 scope-out. Subclasses NotImplementedError so
    callers that catch the Sch B Part III gate's error type also catch
    this gate.
    """


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    ack = scenario.config.acknowledges_form_8949_unsupported
    short_lots: list[Form1099B] = []
    long_lots: list[Form1099B] = []
    for lot in scenario.form1099_b:
        if not lot.basis_reported_to_irs or lot.has_adjustments:
            if not ack:
                raise EightFortyNineRequired(
                    f"1099-B lot {lot.broker} {lot.description!r} requires "
                    "Form 8949 (basis not reported to IRS or has adjustments). "
                    "Form 8949 is not implemented in tenforty v1. Either "
                    "correct the lot's flags (set basis_reported_to_irs=True "
                    "and has_adjustments=False if the 1099-B truly shows "
                    "that), or set `acknowledges_form_8949_unsupported: true` "
                    "in scenario config to accept that this lot will be "
                    "dropped from Sch D totals (a WARNING is logged per "
                    "dropped lot so you can reconcile manually)."
                )
            log.warning(
                "Dropping 1099-B lot %s %r from Sch D totals: requires Form "
                "8949 (acknowledges_form_8949_unsupported=True). Reconcile "
                "manually.",
                lot.broker, lot.description,
            )
            continue
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
        "taxpayer_name": _format_taxpayer_name(scenario),
        "taxpayer_ssn": scenario.config.ssn,
    }


def _summarize(lots: list[Form1099B]) -> dict:
    proceeds = irs_round(sum(lot.proceeds for lot in lots))
    basis = irs_round(sum(lot.cost_basis for lot in lots))
    return {"proceeds": proceeds, "basis": basis, "gain": proceeds - basis}


def _format_taxpayer_name(scenario: Scenario) -> str:
    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return f"{first} {last}".strip()
