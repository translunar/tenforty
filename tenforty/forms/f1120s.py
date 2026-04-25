"""Federal Form 1120-S — S-corporation return.

Computes main form lines 1-28, Schedule B pass-through, Schedule K totals,
and per-shareholder Schedule K-1 allocations from a Scenario whose
`s_corp_return` is set.

Scope follows Sub-plan 2: §1375, §1374, §453 interest are scope-outs
(caller supplies amounts); Sch L, M-1, M-2, M-3 are out of scope (gated
by attestations); Sch D (corporate) and 1125-A/E detail are out of scope.

Caller contract: `compute(scenario, upstream)` runs both the load-time
and compute-time attestation gates. Direct importers DO NOT bypass the
load-time gate by skipping `tenforty.scenario.load_scenario` — calling
`compute` on a Scenario whose config has any required attestation field
left as None will raise from inside `validate_load_time(...)` here, not
silently produce wrong output. This makes `compute` safe to call as a
library function in addition to its primary use through the orchestrator.
"""

from tenforty.attestations import enforce_compute_time, validate_load_time
from tenforty.models import Scenario, SCorpReturn


def _compute_income(r: SCorpReturn) -> dict:
    """Form 1120-S Income section (lines 1a-6)."""
    line_1a = r.income.gross_receipts
    line_1b = r.income.returns_and_allowances
    line_1c = line_1a - line_1b
    line_2 = r.income.cogs_aggregate
    line_3 = line_1c - line_2
    line_4 = r.income.net_gain_loss_4797
    line_5 = r.income.other_income
    line_6 = line_3 + line_4 + line_5
    return {
        "f1120s_line_1a_gross_receipts": line_1a,
        "f1120s_line_1b_returns_and_allowances": line_1b,
        "f1120s_line_1c_net_receipts": line_1c,
        "f1120s_line_2_cost_of_goods_sold": line_2,
        "f1120s_line_3_gross_profit": line_3,
        "f1120s_line_4_net_gain_loss_4797": line_4,
        "f1120s_line_5_other_income": line_5,
        "f1120s_line_6_total_income": line_6,
    }


def compute(scenario: Scenario, upstream: dict) -> dict:
    if scenario.s_corp_return is None:
        return {}
    # Run BOTH gates here, not just compute-time. Direct importers (callers
    # who construct Scenario in code rather than via load_scenario) would
    # otherwise bypass the load-time None-attestation check.
    validate_load_time(scenario.config)
    enforce_compute_time(scenario)

    r = scenario.s_corp_return

    # Per-section helpers contribute to the return dict additively. Each
    # later task in this sub-plan adds one helper and one update line.
    out: dict = {}
    out.update(_compute_income(r))
    return out
