"""IRS-published 2024 federal parameters (Rev. Proc. 2023-34, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S = FilingStatus.SINGLE.value

# 2024 MFJ EITC maximum-AGI limits keyed by number of qualifying children
# (0, 1, 2, 3+). These are the married-filing-jointly maximum-AGI limits from
# the IRS 2024 EITC tables (the largest column). Using the MFJ ceiling makes
# the orchestrator's scope-gate conservative across all filing statuses: a
# scenario below the ceiling MIGHT be EIC-eligible and is routed to the
# workbook oracle. Used ONLY as a scope-gate threshold, NOT a credit
# computation (no EIC math happens in the native spine).
_EIC_CEILING = {0: 25_511, 1: 56_004, 2: 62_688, 3: 66_819}

PARAMS = FederalParams(
    year=2024,
    standard_deduction={_S: 14_600},
    # 2024 single tax-rate schedule: (upper_bound, marginal_rate).
    ordinary_brackets=(
        (11_600.0, 0.10),
        (47_150.0, 0.12),
        (100_525.0, 0.22),
        (191_950.0, 0.24),
        (243_725.0, 0.32),
        (609_350.0, 0.35),
        (math.inf, 0.37),
    ),
    qdcgt_breakpoints={_S: (47_025, 518_900)},
    addl_medicare_threshold={_S: 200_000},
    qbi_threshold={_S: 191_950},
    salt_cap={_S: 10_000},
    eic_income_ceiling=_EIC_CEILING,
)
