"""California Form 540 constants for tax year 2023.

Values extracted from FTB Form 540 (TY2023) at ``pdfs/california/2023/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $144 (TY2023); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($446 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $237,035, see instructions")

Rate schedules extracted from FTB ``pdfs/california/2023/tax_rate_schedules.pdf``
(2023 California Tax Rate Schedules, Personal Income Tax Booklet 2023 page 75):

- ``RATE_SCHEDULE``: Schedule X (Single/MFS), Schedule Y (MFJ/QSS), Schedule
  Z (HoH); 9 brackets each, top rate 12.30%. Schedule Y thresholds are
  exactly 2× Schedule X. Schedule Z is FTB-published independently and does
  NOT equal Schedule X × 2 (e.g., HoH first non-zero threshold $20,839 vs
  SINGLE×2 = $20,824, a $15 quirk).
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 5_363,
    FilingStatus.MARRIED_SEPARATELY: 5_363,
    FilingStatus.MARRIED_JOINTLY: 10_726,
    FilingStatus.HEAD_OF_HOUSEHOLD: 10_726,
    FilingStatus.QUALIFYING_WIDOW: 10_726,
}

EXEMPTION_CREDIT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 144,             # 1 × $144
    FilingStatus.MARRIED_SEPARATELY: 144,  # 1 × $144
    FilingStatus.HEAD_OF_HOUSEHOLD: 144,   # 1 × $144
    FilingStatus.MARRIED_JOINTLY: 288,     # 2 × $144
    FilingStatus.QUALIFYING_WIDOW: 288,    # 2 × $144
}

DEPENDENT_EXEMPTION_AMOUNT: int = 446

AGI_PHASEOUT_THRESHOLD: int = 237_035
# Used by T11 final-liability compute as a gate. If federal AGI exceeds
# this, the exemption credit phases out (FTB instructions formula); v1
# raises NotImplementedError rather than computing the phaseout.

# Rate schedules — Source: tax_rate_schedules.pdf (FTB 2023, p. 75 in booklet).

_SCHEDULE_X = [  # Single / MFS
    (0, 0.01),
    (10_412, 0.02),
    (24_684, 0.04),
    (38_959, 0.06),
    (54_081, 0.08),
    (68_350, 0.093),
    (349_137, 0.103),
    (418_961, 0.113),
    (698_271, 0.123),
]

_SCHEDULE_Y = [  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01),
    (20_824, 0.02),
    (49_368, 0.04),
    (77_918, 0.06),
    (108_162, 0.08),
    (136_700, 0.093),
    (698_274, 0.103),
    (837_922, 0.113),
    (1_396_542, 0.123),
]

_SCHEDULE_Z = [  # HoH — FTB-published independently; close to but not equal to X × 2
    (0, 0.01),
    (20_839, 0.02),
    (49_371, 0.04),
    (63_644, 0.06),
    (78_765, 0.08),
    (93_037, 0.093),
    (474_824, 0.103),
    (569_790, 0.113),
    (949_649, 0.123),
]

RATE_SCHEDULE: dict[FilingStatus, list[tuple[int, float]]] = {
    FilingStatus.SINGLE: _SCHEDULE_X,
    FilingStatus.MARRIED_SEPARATELY: _SCHEDULE_X,
    FilingStatus.MARRIED_JOINTLY: _SCHEDULE_Y,
    FilingStatus.QUALIFYING_WIDOW: _SCHEDULE_Y,
    FilingStatus.HEAD_OF_HOUSEHOLD: _SCHEDULE_Z,
}
