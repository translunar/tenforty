"""California Form 540 constants for tax year 2022.

Values extracted from FTB Form 540 (TY2022) at ``pdfs/california/2022/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $140 (TY2022); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($433 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $229,908, see instructions")

Rate schedules extracted from FTB ``pdfs/california/2022/tax_rate_schedules.pdf``
(2022 California Tax Rate Schedules, Personal Income Tax Booklet 2022 page 93):

- ``RATE_SCHEDULE``: Schedule X (Single/MFS), Schedule Y (MFJ/QSS), Schedule
  Z (HoH); 9 brackets each, top rate 12.30%. Schedule Y thresholds are
  exactly 2× Schedule X. Schedule Z is FTB-published independently and does
  NOT equal Schedule X × 2 (e.g., HoH first non-zero threshold $20,212 vs
  SINGLE×2 = $20,198, a $14 quirk).

Nonrefundable Renter's Credit values extracted from FTB Personal Income Tax
Booklet (TY2022) at ``pdfs/california/2022/booklet.pdf`` p.23, "Nonrefundable
Renter's Credit Qualification Record" Q2 (AGI threshold) and Q11 (amount):

- ``RENTER_CREDIT_AGI_THRESHOLD``: $49,220 single/MFS, $98,440 MFJ/HoH/QSS
- ``RENTER_CREDIT_AMOUNT``: $60 single/MFS, $120 MFJ/HoH/QSS
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 5_202,
    FilingStatus.MARRIED_SEPARATELY: 5_202,
    FilingStatus.MARRIED_JOINTLY: 10_404,
    FilingStatus.HEAD_OF_HOUSEHOLD: 10_404,
    FilingStatus.QUALIFYING_WIDOW: 10_404,
}

EXEMPTION_CREDIT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 140,             # 1 × $140
    FilingStatus.MARRIED_SEPARATELY: 140,  # 1 × $140
    FilingStatus.HEAD_OF_HOUSEHOLD: 140,   # 1 × $140
    FilingStatus.MARRIED_JOINTLY: 280,     # 2 × $140
    FilingStatus.QUALIFYING_WIDOW: 280,    # 2 × $140
}

DEPENDENT_EXEMPTION_AMOUNT: int = 433

AGI_PHASEOUT_THRESHOLD: int = 229_908
# Used by T11 final-liability compute as a gate. If federal AGI exceeds
# this, the exemption credit phases out (FTB instructions formula); v1
# raises NotImplementedError rather than computing the phaseout.

# Rate schedules — Source: tax_rate_schedules.pdf (FTB 2022, p. 93 in booklet).

_SCHEDULE_X = [  # Single / MFS
    (0, 0.01),
    (10_099, 0.02),
    (23_942, 0.04),
    (37_788, 0.06),
    (52_455, 0.08),
    (66_295, 0.093),
    (338_639, 0.103),
    (406_364, 0.113),
    (677_275, 0.123),
]

_SCHEDULE_Y = [  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01),
    (20_198, 0.02),
    (47_884, 0.04),
    (75_576, 0.06),
    (104_910, 0.08),
    (132_590, 0.093),
    (677_278, 0.103),
    (812_728, 0.113),
    (1_354_550, 0.123),
]

_SCHEDULE_Z = [  # HoH — FTB-published independently; close to but not equal to X × 2
    (0, 0.01),
    (20_212, 0.02),
    (47_887, 0.04),
    (61_730, 0.06),
    (76_397, 0.08),
    (90_240, 0.093),
    (460_547, 0.103),
    (552_658, 0.113),
    (921_095, 0.123),
]

RATE_SCHEDULE: dict[FilingStatus, list[tuple[int, float]]] = {
    FilingStatus.SINGLE: _SCHEDULE_X,
    FilingStatus.MARRIED_SEPARATELY: _SCHEDULE_X,
    FilingStatus.MARRIED_JOINTLY: _SCHEDULE_Y,
    FilingStatus.QUALIFYING_WIDOW: _SCHEDULE_Y,
    FilingStatus.HEAD_OF_HOUSEHOLD: _SCHEDULE_Z,
}

# Nonrefundable Renter's Credit — Source: pdfs/california/2022/booklet.pdf p.23
# Q2 (AGI threshold) and Q11 (amount). Filing-status mapping per FTB Q11 bullet
# rules; the MFS-living-apart $30 split edge case is out of v1 scope.

RENTER_CREDIT_AGI_THRESHOLD: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 49_220,
    FilingStatus.MARRIED_SEPARATELY: 49_220,
    FilingStatus.MARRIED_JOINTLY: 98_440,
    FilingStatus.HEAD_OF_HOUSEHOLD: 98_440,
    FilingStatus.QUALIFYING_WIDOW: 98_440,
}

RENTER_CREDIT_AMOUNT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 60,
    FilingStatus.MARRIED_SEPARATELY: 60,
    FilingStatus.MARRIED_JOINTLY: 120,
    FilingStatus.HEAD_OF_HOUSEHOLD: 120,
    FilingStatus.QUALIFYING_WIDOW: 120,
}
