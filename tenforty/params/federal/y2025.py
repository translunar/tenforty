"""IRS-published 2025 federal parameters (Rev. Proc. 2024-40, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S = FilingStatus.SINGLE.value

PARAMS = FederalParams(
    year=2025,
    standard_deduction={_S: 15_750},
    # 2025 single tax-rate schedule: (upper_bound, marginal_rate).
    ordinary_brackets=(
        (11_925.0, 0.10),
        (48_475.0, 0.12),
        (103_350.0, 0.22),
        (197_300.0, 0.24),
        (250_525.0, 0.32),
        (626_350.0, 0.35),
        (math.inf, 0.37),
    ),
    qdcgt_breakpoints={_S: (48_350, 533_400)},
    addl_medicare_threshold={_S: 200_000},
    qbi_threshold={_S: 197_300},
    salt_cap={_S: 40_000},
)
