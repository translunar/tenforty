"""IRS-published 2024 federal parameters (Rev. Proc. 2023-34, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S = FilingStatus.SINGLE.value

# EIC income ceilings keyed by number of qualifying children (0, 1, 2, 3+).
# These are the MFJ phase-out-end amounts from the 2024 EIC Table — the
# maximum AGI at which any filing status can still claim EIC for that child
# count. Using the MFJ (largest) ceiling makes the orchestrator's scope-gate
# conservative: a scenario below the ceiling MIGHT be EIC-eligible and is
# routed to the workbook oracle (no EIC math happens in the native spine).
_EIC_CEILING = {0: 26_260, 1: 55_952, 2: 61_511, 3: 66_372}

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
