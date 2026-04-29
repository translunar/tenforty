"""California Form 540 constants for tax year 2024.

Values extracted from FTB Form 540 (TY2024) at ``pdfs/california/2024/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $149 (TY2024); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($461 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $244,857, see instructions")

Rate schedules extracted from FTB ``pdfs/california/2024/tax_rate_schedules.pdf``
(2024 California Tax Rate Schedules, Personal Income Tax Booklet 2024 page 75):

- ``RATE_SCHEDULE``: Schedule X (Single/MFS), Schedule Y (MFJ/QSS), Schedule
  Z (HoH); 9 brackets each, top rate 12.30%. Schedule Y thresholds are
  exactly 2× Schedule X. Schedule Z is FTB-published independently and does
  NOT equal Schedule X × 2 (e.g., HoH first non-zero threshold $21,527 vs
  SINGLE×2 = $21,512, a $15 quirk).
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 5_540,
    FilingStatus.MARRIED_SEPARATELY: 5_540,
    FilingStatus.MARRIED_JOINTLY: 11_080,
    FilingStatus.HEAD_OF_HOUSEHOLD: 11_080,
    FilingStatus.QUALIFYING_WIDOW: 11_080,
}

EXEMPTION_CREDIT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 149,             # 1 × $149
    FilingStatus.MARRIED_SEPARATELY: 149,  # 1 × $149
    FilingStatus.HEAD_OF_HOUSEHOLD: 149,   # 1 × $149
    FilingStatus.MARRIED_JOINTLY: 298,     # 2 × $149
    FilingStatus.QUALIFYING_WIDOW: 298,    # 2 × $149
}

DEPENDENT_EXEMPTION_AMOUNT: int = 461

AGI_PHASEOUT_THRESHOLD: int = 244_857
# Used by T11 final-liability compute as a gate. If federal AGI exceeds
# this, the exemption credit phases out (FTB instructions formula); v1
# raises NotImplementedError rather than computing the phaseout.

# Rate schedules — Source: tax_rate_schedules.pdf (FTB 2024, p. 75 in booklet).

_SCHEDULE_X = [  # Single / MFS
    (0, 0.01),
    (10_756, 0.02),
    (25_499, 0.04),
    (40_245, 0.06),
    (55_866, 0.08),
    (70_606, 0.093),
    (360_659, 0.103),
    (432_787, 0.113),
    (721_314, 0.123),
]

_SCHEDULE_Y = [  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01),
    (21_512, 0.02),
    (50_998, 0.04),
    (80_490, 0.06),
    (111_732, 0.08),
    (141_212, 0.093),
    (721_318, 0.103),
    (865_574, 0.113),
    (1_442_628, 0.123),
]

_SCHEDULE_Z = [  # HoH — FTB-published independently; close to but not equal to X × 2
    (0, 0.01),
    (21_527, 0.02),
    (51_000, 0.04),
    (65_744, 0.06),
    (81_364, 0.08),
    (96_107, 0.093),
    (490_493, 0.103),
    (588_593, 0.113),
    (980_987, 0.123),
]

RATE_SCHEDULE: dict[FilingStatus, list[tuple[int, float]]] = {
    FilingStatus.SINGLE: _SCHEDULE_X,
    FilingStatus.MARRIED_SEPARATELY: _SCHEDULE_X,
    FilingStatus.MARRIED_JOINTLY: _SCHEDULE_Y,
    FilingStatus.QUALIFYING_WIDOW: _SCHEDULE_Y,
    FilingStatus.HEAD_OF_HOUSEHOLD: _SCHEDULE_Z,
}
