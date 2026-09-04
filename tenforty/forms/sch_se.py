"""Schedule SE — Self-Employment Tax (sole proprietor, short/long method).

Reads Schedule C aggregate net profit (upstream["sch_c"]) and computes net
earnings from self-employment (x 92.35%), the Social Security portion
(12.4%, capped at the per-year OASDI wage base and COORDINATED with W-2 Social
Security wages), the Medicare portion (2.9%, uncapped), the SE tax (line 12),
and the deductible half (line 13, Schedule 1 line 15).

v1 scope: sole-proprietor SE only. No SE tax and no half-deduction when net
earnings < $400. Optional method, church-employee income, and farm income are
NOT modeled. There is no input channel for those (no field to set), so the
scope-out is by ABSENCE, not a dead guard (U-1: a refusal that can never fire
is the anti-pattern; adding a field only to refuse it would be fabrication).
Partnership self-employment earnings are refused elsewhere via the always-on
acknowledges_no_partnership_se_earnings attestation (models.py).

ROUNDING CONVENTION (load-bearing — matches the oracle and forms/f8959.py):
carry ALL intermediate line values UNROUNDED and apply irs_round ONLY at emit,
mirroring the IRS whole-dollar rule "if you have to add two or more amounts to
figure the amount on a line, include cents when adding and only round off the
total." Concretely: line_10/line_11 stay unrounded; line_12 = line_10 + line_11
(unrounded) then emit irs_round(line_12); line_13 = line_12 * 0.5 (from the
UNROUNDED line_12) then emit irs_round(line_13). Rounding line 10/11 before
summing, or halving a pre-rounded line 12, diverges from the hand-derived
oracle by $1.
"""
from tenforty.models import Scenario
from tenforty.params.federal import load as load_federal_params
from tenforty.rounding import irs_round

_NET_EARNINGS_PCT = 0.9235
_SS_RATE = 0.124
_MEDICARE_RATE = 0.029
_MIN_NET_EARNINGS = 400.0


def compute(scenario: Scenario, upstream: dict) -> dict:
    sch_c = upstream.get("sch_c", {})
    net_profit = float(sch_c.get("sch_c_line_31_net_profit_total", 0.0))
    if net_profit <= 0:
        return {}
    params = load_federal_params(scenario.config.year)

    line_3 = net_profit
    line_4c = line_3 * _NET_EARNINGS_PCT           # net earnings from SE
    line_6 = line_4c                               # + church income (0 in v1)
    if line_6 < _MIN_NET_EARNINGS:
        return {
            "sch_se_line_3_net_profit": irs_round(line_3),
            "sch_se_line_4c_net_earnings": irs_round(line_4c),
            "sch_se_line_6_total_net_earnings": irs_round(line_6),
            "sch_se_line_12_se_tax": 0,
            "sch_se_line_13_half_deduction": 0,
        }
    line_7 = float(params.ss_wage_base)            # OASDI wage base
    ss_wages = sum(w.ss_wages for w in scenario.w2s)  # line 8a/8d
    line_9 = max(0.0, line_7 - ss_wages)           # SS earnings still taxable
    line_10 = min(line_6, line_9) * _SS_RATE       # SS portion (unrounded)
    line_11 = line_6 * _MEDICARE_RATE              # Medicare portion (uncapped)
    line_12 = line_10 + line_11                    # SE tax (unrounded sum)
    line_13 = line_12 * 0.5                        # deductible half (unrounded)
    return {
        "sch_se_line_3_net_profit": irs_round(line_3),
        "sch_se_line_4c_net_earnings": irs_round(line_4c),
        "sch_se_line_6_total_net_earnings": irs_round(line_6),
        "sch_se_line_7_ss_wage_base": irs_round(line_7),
        "sch_se_line_8d_wages_subject_to_ss": irs_round(ss_wages),
        "sch_se_line_9_ss_earnings_remaining": irs_round(line_9),
        "sch_se_line_10_ss_portion": irs_round(line_10),
        "sch_se_line_11_medicare_portion": irs_round(line_11),
        "sch_se_line_12_se_tax": irs_round(line_12),
        "sch_se_line_13_half_deduction": irs_round(line_13),
    }
