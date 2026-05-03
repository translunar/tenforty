"""California Form 540 constants for tax year 2025.

Values extracted from FTB Form 540 (TY2025) at ``pdfs/california/2025/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $153 (TY2025); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($475 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $252,203, see instructions")

Rate schedules extracted from FTB ``pdfs/california/2025/tax_rate_schedules.pdf``
(2025 California Tax Rate Schedules, single-page extract from the 2025
Personal Income Tax Booklet):

- ``RATE_SCHEDULE``: Schedule X (Single/MFS), Schedule Y (MFJ/QSS), Schedule
  Z (HoH); 9 brackets each, top rate 12.30% over the highest threshold.
  Schedule Y thresholds are exactly 2× Schedule X. Schedule Z is FTB-
  published independently and does NOT equal Schedule X × 2 (e.g., HoH
  first non-zero threshold $22,173 vs SINGLE×2 = $22,158, a $15 quirk).

Nonrefundable Renter's Credit values extracted from the FTB 2025 540-2EZ
Booklet at ``pdfs/california/2025/booklet_2ez.pdf`` p.13, "Nonrefundable
Renter's Credit Qualification Record" Q2 (AGI threshold) and Q11 (amount).

The regular TY2025 540 Personal Income Tax Booklet was not yet published
at extraction time (April 2026); the 540-2EZ Booklet contains the identical
Renter's Credit values per FTB §17053.5 (the credit is form-agnostic).
Re-source from the regular 540 booklet at /simplify pass once published:

- ``RENTER_CREDIT_AGI_THRESHOLD``: $53,994 single/MFS, $107,988 MFJ/HoH/QSS
- ``RENTER_CREDIT_AMOUNT``: $60 single/MFS, $120 MFJ/HoH/QSS
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 5_706,
    FilingStatus.MARRIED_SEPARATELY: 5_706,
    FilingStatus.MARRIED_JOINTLY: 11_412,
    FilingStatus.HEAD_OF_HOUSEHOLD: 11_412,
    FilingStatus.QUALIFYING_WIDOW: 11_412,
}

EXEMPTION_CREDIT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 153,             # 1 × $153
    FilingStatus.MARRIED_SEPARATELY: 153,  # 1 × $153
    FilingStatus.HEAD_OF_HOUSEHOLD: 153,   # 1 × $153
    FilingStatus.MARRIED_JOINTLY: 306,     # 2 × $153
    FilingStatus.QUALIFYING_WIDOW: 306,    # 2 × $153
}

DEPENDENT_EXEMPTION_AMOUNT: int = 475

AGI_PHASEOUT_THRESHOLD: int = 252_203
# Used by T11 final-liability compute as a gate. If federal AGI exceeds
# this, the exemption credit phases out (FTB instructions formula); v1
# raises NotImplementedError rather than computing the phaseout.

# Rate schedules — Source: tax_rate_schedules.pdf (FTB 2025).
# Each entry is (income_threshold_inclusive, marginal_rate_at_or_above_threshold).
# A bracket walk applies prev_rate to the income between prev_threshold and the
# next threshold. See ``tenforty/forms/f540.compute_ca_tax`` for the algorithm.

_SCHEDULE_X = [  # Single / MFS
    (0, 0.01),
    (11_079, 0.02),
    (26_264, 0.04),
    (41_452, 0.06),
    (57_542, 0.08),
    (72_724, 0.093),
    (371_479, 0.103),
    (445_771, 0.113),
    (742_953, 0.123),
]

_SCHEDULE_Y = [  # MFJ / QSS — thresholds exactly 2× Schedule X
    (0, 0.01),
    (22_158, 0.02),
    (52_528, 0.04),
    (82_904, 0.06),
    (115_084, 0.08),
    (145_448, 0.093),
    (742_958, 0.103),
    (891_542, 0.113),
    (1_485_906, 0.123),
]

_SCHEDULE_Z = [  # HoH — FTB-published independently; close to but not equal to X × 2
    (0, 0.01),
    (22_173, 0.02),
    (52_530, 0.04),
    (67_716, 0.06),
    (83_805, 0.08),
    (98_990, 0.093),
    (505_208, 0.103),
    (606_251, 0.113),
    (1_010_417, 0.123),
]

RATE_SCHEDULE: dict[FilingStatus, list[tuple[int, float]]] = {
    FilingStatus.SINGLE: _SCHEDULE_X,
    FilingStatus.MARRIED_SEPARATELY: _SCHEDULE_X,
    FilingStatus.MARRIED_JOINTLY: _SCHEDULE_Y,
    FilingStatus.QUALIFYING_WIDOW: _SCHEDULE_Y,
    FilingStatus.HEAD_OF_HOUSEHOLD: _SCHEDULE_Z,
}

# Nonrefundable Renter's Credit — Source: pdfs/california/2025/booklet_2ez.pdf
# p.13 Q2 (AGI threshold) and Q11 (amount). The regular TY2025 540 booklet
# was not published at extraction time (April 2026); 2EZ booklet contains
# identical Renter's Credit values per FTB §17053.5 (form-agnostic).
# Filing-status mapping per FTB Q11 bullet rules; the MFS-living-apart
# $30 split edge case is out of v1 scope.

RENTER_CREDIT_AGI_THRESHOLD: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 53_994,
    FilingStatus.MARRIED_SEPARATELY: 53_994,
    FilingStatus.MARRIED_JOINTLY: 107_988,
    FilingStatus.HEAD_OF_HOUSEHOLD: 107_988,
    FilingStatus.QUALIFYING_WIDOW: 107_988,
}

RENTER_CREDIT_AMOUNT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 60,
    FilingStatus.MARRIED_SEPARATELY: 60,
    FilingStatus.MARRIED_JOINTLY: 120,
    FilingStatus.HEAD_OF_HOUSEHOLD: 120,
    FilingStatus.QUALIFYING_WIDOW: 120,
}
