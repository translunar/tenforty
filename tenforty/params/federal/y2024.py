"""IRS-published 2024 federal parameters (Rev. Proc. 2023-34, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

# 2024 MFJ EITC maximum-AGI limits keyed by number of qualifying children
# (0, 1, 2, 3+). The largest AGI at which any filing status can claim EITC.
# Conservative scope-gate threshold only; no credit math in the native spine.
_EIC_CEILING = {0: 25_511, 1: 56_004, 2: 62_688, 3: 66_819}

PARAMS = FederalParams(
    year=2024,
    standard_deduction={
        _S: 14_600, _MFJ: 29_200, _MFS: 14_600, _HOH: 21_900, _QW: 29_200,
    },
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
    ss_wage_base=168_600,  # SSA 2024 OASDI wage base
    # Form 8995 simple-path threshold (Rev. Proc. 2023-34): single $191,950,
    # MFJ = 2× = $383,900 (confirmed against Rev. Proc. 2023-34).
    qbi_threshold={
        _S: 191_950, _MFS: 191_950, _HOH: 191_950,
        _MFJ: 383_900, _QW: 383_900,
    },
    # 2024 SALT cap: flat pre-OBBBA $10k / $5k MFS, no income phaseout.
    # salt_phaseout_threshold = None → flat cap, never raises for high MAGI.
    salt_cap_starting={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    salt_phaseout_threshold=None,
    salt_phaseout_rate=0.0,
    salt_cap_floor={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    medical_agi_floor_pct=0.075,  # IRC §213(a), unchanged
    # Prior-year SALT cap: a 2024 return looks back at 2023 (also $10k/$5k).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
)
