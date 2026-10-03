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

ROUNDING CONVENTION (load-bearing) -- THE ROUNDING ELECTION. A filer may
either carry cents throughout and round only the final figure, or round every
line to whole dollars. tenforty prints every line in whole dollars: it has
ELECTED rounding. Under that election the printed form must add its own
printed lines. So lines 10 and 11 are each rounded; line 12 is the SUM OF
THOSE ROUNDED lines ("Add lines 10 and 11"); and line 13 is half of that line
12, rounded ("Multiply line 12 by 50%").

The other reading -- sum the unrounded portions, round once -- is the
NON-rounding filer's figure. It can differ by $1, and printing it beside
whole-dollar lines 10 and 11 makes the form's visible addition wrong. Worked
on the two cases pinned in tests/test_sch_se_oracle.py: case A's portions are
10,306.26 and 2,410.335, so the non-rounding reading gives round(12,716.595)
= 12,717 while the printed lines give 10,306 + 2,410 = 12,716; case B gives
4,985 against 4,984 the same way. The printed-lines figure is the one this
module emits. Lines 2 through 9 are single amounts, products or differences
and are rounded independently at emit.
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

    # Lines 2 and 4a are printed explicitly so the form's chain is complete.
    # Line 2 is the Schedule C net profit; line 3 combines it with the farm
    # lines (1a, 1b), which are unmodeled, so line 3 = line 2. Line 4a is
    # line 3 x 92.35%; line 4b (optional methods) is unmodeled, so 4c = 4a.
    line_3 = net_profit
    line_4c = line_3 * _NET_EARNINGS_PCT           # net earnings from SE
    line_6 = line_4c                               # + church income (0 in v1)
    if line_6 < _MIN_NET_EARNINGS:
        return {
            "sch_se_line_2_net_profit": irs_round(line_3),
            "sch_se_line_3_net_profit": irs_round(line_3),
            "sch_se_line_4a_net_earnings": irs_round(line_4c),
            "sch_se_line_4c_net_earnings": irs_round(line_4c),
            "sch_se_line_6_total_net_earnings": irs_round(line_6),
            "sch_se_line_12_se_tax": 0,
            "sch_se_line_13_half_deduction": 0,
        }
    line_7 = float(params.ss_wage_base)            # OASDI wage base
    ss_wages = sum(w.ss_wages for w in scenario.w2s)  # line 8a/8d
    line_9 = max(0.0, line_7 - ss_wages)           # SS earnings still taxable
    line_10 = irs_round(min(line_6, line_9) * _SS_RATE)   # SS portion
    line_11 = irs_round(line_6 * _MEDICARE_RATE)          # Medicare (uncapped)
    line_12 = line_10 + line_11        # SE tax: sum of the PRINTED lines
    line_13 = irs_round(line_12 * 0.5)  # deductible half of the printed line 12
    return {
        "sch_se_line_2_net_profit": irs_round(line_3),
        "sch_se_line_3_net_profit": irs_round(line_3),
        "sch_se_line_4a_net_earnings": irs_round(line_4c),
        "sch_se_line_4c_net_earnings": irs_round(line_4c),
        "sch_se_line_6_total_net_earnings": irs_round(line_6),
        "sch_se_line_7_ss_wage_base": irs_round(line_7),
        "sch_se_line_8d_wages_subject_to_ss": irs_round(ss_wages),
        "sch_se_line_9_ss_earnings_remaining": irs_round(line_9),
        "sch_se_line_10_ss_portion": line_10,
        "sch_se_line_11_medicare_portion": line_11,
        "sch_se_line_12_se_tax": line_12,
        "sch_se_line_13_half_deduction": line_13,
    }
