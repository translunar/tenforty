"""California Form 540 constants for tax year 2021.

Values extracted from FTB Form 540 (TY2021) at ``pdfs/california/2021/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $129 (TY2021); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($400 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $212,288, see instructions")

Rate schedules extracted from FTB ``pdfs/california/2021/tax_rate_schedules.pdf``
(2021 California Tax Rate Schedules, Personal Income Tax Booklet 2021 page 93):

- ``RATE_SCHEDULE``: Schedule X (Single/MFS), Schedule Y (MFJ/QSS), Schedule
  Z (HoH); 9 brackets each, top rate 12.30%. Schedule Y thresholds are
  exactly 2× Schedule X. Schedule Z is FTB-published independently and does
  NOT equal Schedule X × 2 (e.g., HoH first non-zero threshold $18,663 vs
  SINGLE×2 = $18,650, a $13 quirk). Note: TY2021 FTB form still used the
  older "Qualifying Widow(er)" terminology; tenforty maps QSS to QUALIFYING_WIDOW.
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 4_803,
    FilingStatus.MARRIED_SEPARATELY: 4_803,
    FilingStatus.MARRIED_JOINTLY: 9_606,
    FilingStatus.HEAD_OF_HOUSEHOLD: 9_606,
    FilingStatus.QUALIFYING_WIDOW: 9_606,
}

EXEMPTION_CREDIT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 129,             # 1 × $129
    FilingStatus.MARRIED_SEPARATELY: 129,  # 1 × $129
    FilingStatus.HEAD_OF_HOUSEHOLD: 129,   # 1 × $129
    FilingStatus.MARRIED_JOINTLY: 258,     # 2 × $129
    FilingStatus.QUALIFYING_WIDOW: 258,    # 2 × $129
}

DEPENDENT_EXEMPTION_AMOUNT: int = 400

AGI_PHASEOUT_THRESHOLD: int = 212_288
# Used by T11 final-liability compute as a gate. If federal AGI exceeds
# this, the exemption credit phases out (FTB instructions formula); v1
# raises NotImplementedError rather than computing the phaseout.

# Rate schedules — Source: tax_rate_schedules.pdf (FTB 2021, p. 93 in booklet).

_SCHEDULE_X = [  # Single / MFS
    (0, 0.01),
    (9_325, 0.02),
    (22_107, 0.04),
    (34_892, 0.06),
    (48_435, 0.08),
    (61_214, 0.093),
    (312_686, 0.103),
    (375_221, 0.113),
    (625_369, 0.123),
]

_SCHEDULE_Y = [  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01),
    (18_650, 0.02),
    (44_214, 0.04),
    (69_784, 0.06),
    (96_870, 0.08),
    (122_428, 0.093),
    (625_372, 0.103),
    (750_442, 0.113),
    (1_250_738, 0.123),
]

_SCHEDULE_Z = [  # HoH — FTB-published independently; close to but not equal to X × 2
    (0, 0.01),
    (18_663, 0.02),
    (44_217, 0.04),
    (56_999, 0.06),
    (70_542, 0.08),
    (83_324, 0.093),
    (425_251, 0.103),
    (510_303, 0.113),
    (850_503, 0.123),
]

RATE_SCHEDULE: dict[FilingStatus, list[tuple[int, float]]] = {
    FilingStatus.SINGLE: _SCHEDULE_X,
    FilingStatus.MARRIED_SEPARATELY: _SCHEDULE_X,
    FilingStatus.MARRIED_JOINTLY: _SCHEDULE_Y,
    FilingStatus.QUALIFYING_WIDOW: _SCHEDULE_Y,
    FilingStatus.HEAD_OF_HOUSEHOLD: _SCHEDULE_Z,
}
