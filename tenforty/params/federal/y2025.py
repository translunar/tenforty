"""IRS-published 2025 federal parameters (Rev. Proc. 2024-40, Form 1040 instr.)."""
import math

from tenforty.models import FilingStatus
from tenforty.params.federal import EicParams, FederalParams

_S = FilingStatus.SINGLE.value

# EIC table parameters sourced from the 2025 federal 1040 workbook (EIC Table
# sheet, rows N3:U6 and N9 phase-out rates).  The midpoint-based lookup approach
# matches the workbook's ROUND((A+B)/2,2) formula for column L; see the EIC
# implementation in forms.f1040_spine for the full lookup logic.
_EIC_0  = EicParams(max_credit=649,  phase_in_end=8_490,  phase_out_start=10_620, phase_out_end=19_104, phase_out_start_mfj=17_730, phase_out_end_mfj=26_214)
_EIC_1  = EicParams(max_credit=4_328, phase_in_end=12_730, phase_out_start=23_350, phase_out_end=50_434, phase_out_start_mfj=30_470, phase_out_end_mfj=57_310)
_EIC_2  = EicParams(max_credit=7_152, phase_in_end=17_880, phase_out_start=23_350, phase_out_end=57_310, phase_out_start_mfj=30_470, phase_out_end_mfj=63_398)
_EIC_3  = EicParams(max_credit=8_046, phase_in_end=17_880, phase_out_start=23_350, phase_out_end=61_555, phase_out_start_mfj=30_470, phase_out_end_mfj=68_675)

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
    eic_params={0: _EIC_0, 1: _EIC_1, 2: _EIC_2, 3: _EIC_3},
    eic_investment_income_limit=11_950,
)
