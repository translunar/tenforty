"""IRS-published 2025 federal parameters (Rev. Proc. 2024-40, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import FederalParams

_S   = FilingStatus.SINGLE.value
_MFJ = FilingStatus.MARRIED_JOINTLY.value
_MFS = FilingStatus.MARRIED_SEPARATELY.value
_HOH = FilingStatus.HEAD_OF_HOUSEHOLD.value
_QW  = FilingStatus.QUALIFYING_WIDOW.value

# EIC income ceilings keyed by number of qualifying children (0, 1, 2, 3+).
# These are the 2025 MFJ EITC maximum-AGI limits (Rev. Proc. 2024-40) — the
# largest AGI at which any filing status can still claim EITC for that child
# count. Using the MFJ (largest) ceiling makes the orchestrator's scope-gate
# conservative: a scenario below the ceiling MIGHT be EIC-eligible and is
# routed to the workbook oracle (no EIC math happens in the native spine).
_EIC_CEILING = {0: 26_214, 1: 57_554, 2: 64_430, 3: 68_675}

PARAMS = FederalParams(
    year=2025,
    standard_deduction={
        _S: 15_750, _MFJ: 31_500, _MFS: 15_750, _HOH: 23_625, _QW: 31_500,
    },
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
    ss_wage_base=176_100,  # SSA 2025 OASDI wage base
    # Form 8995 simple-path threshold (Rev. Proc. 2024-40).
    # Single/MFS/HoH may use Form 8995; MFJ/QW threshold is exactly double.
    qbi_threshold={
        _S: 197_300, _MFS: 197_300, _HOH: 197_300,
        # QSS = Rev. Proc. 2024-40 "All Other Returns" (197_300), NOT the MFJ
        # amount — adjudicated by Juno 2026-07-11 (Layer-1 catch).
        _MFJ: 394_600, _QW: 197_300,
    },
    # OBBBA SALT cap structure for TY2025–2029 (IRC §164(b)(6) as amended).
    # Starting caps: $40k single/MFJ/HoH/QW; $20k MFS.
    # Phaseout: begins at $500k MAGI, rate 30%, floor at pre-OBBBA values.
    # V1: phaseout *calculation* is scoped out; forms.sch_a.compute raises
    # NotImplementedError when MAGI > salt_phaseout_threshold.
    salt_cap_starting={
        _S: 40_000, _MFJ: 40_000, _HOH: 40_000, _QW: 40_000, _MFS: 20_000,
    },
    salt_phaseout_threshold=500_000,
    salt_phaseout_rate=0.30,
    salt_cap_floor={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    medical_agi_floor_pct=0.075,  # Rev. Proc. 2024-40 / IRC §213(a)
    # CARES/CAA above-the-line non-itemizer charitable deduction (Form 1040
    # line 12b) was a 2021-only provision, not extended to 2025.
    nonitemizer_charitable_cap=None,
    # Prior-year SALT cap: a 2025 return looks back at 2024 (pre-OBBBA).
    prior_year_salt_cap={
        _S: 10_000, _MFJ: 10_000, _HOH: 10_000, _QW: 10_000, _MFS: 5_000,
    },
    eic_income_ceiling=_EIC_CEILING,
    # IRC §1211(b) net-capital-loss limitation: $3,000 ($1,500 MFS), NOT
    # inflation-indexed — identical across all supported years.
    capital_loss_limit={
        _S: 3_000, _MFJ: 3_000, _HOH: 3_000, _QW: 3_000, _MFS: 1_500,
    },
)
