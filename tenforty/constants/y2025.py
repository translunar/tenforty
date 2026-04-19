"""Year-parameterized tax constants for tax year 2025.

Standard deduction and medical floor are from Rev. Proc. 2024-40.
SALT cap structure reflects the One Big Beautiful Bill Act (OBBBA,
enacted July 2025), which amended IRC §164(b)(6) for tax years
2025-2029:

  - Starting caps: $40,000 single/MFJ/HoH, $20,000 MFS
  - Phaseout: begins at $500,000 MAGI, rate 30%
  - Floor: cap does not reduce below $10,000 single/MFJ/HoH or
    $5,000 MFS (pre-OBBBA values)

Formula (for MAGI > $500,000):
    cap = max(floor, starting_cap - 0.30 * (MAGI - 500_000))

V1 does NOT implement phaseout — forms.sch_a.compute raises
NotImplementedError when MAGI > SALT_PHASEOUT_THRESHOLD. The base
and floor dicts are published here so that the phaseout implementation
(scoped out of v1) is a single-function addition in Sch A.
"""

from tenforty.models import FilingStatus

STANDARD_DEDUCTION: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 15_000,
    FilingStatus.MARRIED_JOINTLY: 30_000,
    FilingStatus.MARRIED_SEPARATELY: 15_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 22_500,
    FilingStatus.QUALIFYING_WIDOW: 30_000,
}

MEDICAL_AGI_FLOOR_PCT: float = 0.075

SALT_CAP_STARTING: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 40_000,
    FilingStatus.MARRIED_JOINTLY: 40_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 40_000,
    FilingStatus.MARRIED_SEPARATELY: 20_000,
    FilingStatus.QUALIFYING_WIDOW: 40_000,
}

SALT_CAP_FLOOR: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 10_000,
    FilingStatus.MARRIED_JOINTLY: 10_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 10_000,
    FilingStatus.MARRIED_SEPARATELY: 5_000,
    FilingStatus.QUALIFYING_WIDOW: 10_000,
}

SALT_PHASEOUT_THRESHOLD: int = 500_000
SALT_PHASEOUT_RATE: float = 0.30

# Form 8995 simple-path threshold per Rev. Proc. 2024-40.
# Filers AT or BELOW this may use Form 8995 (simple). Filers above must
# use Form 8995-A (not implemented in v1).
QBI_THRESHOLD: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 197_300,
    FilingStatus.MARRIED_SEPARATELY: 197_300,
    FilingStatus.HEAD_OF_HOUSEHOLD: 197_300,
    FilingStatus.MARRIED_JOINTLY: 394_600,
    FilingStatus.QUALIFYING_WIDOW: 394_600,
}

# SALT cap that applied in the year the refund originated. For a TY2025
# return, this is TY2024 values (pre-OBBBA flat $10k / $5k MFS).
PRIOR_YEAR_SALT_CAP: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 10_000,
    FilingStatus.HEAD_OF_HOUSEHOLD: 10_000,
    FilingStatus.MARRIED_JOINTLY: 10_000,
    FilingStatus.QUALIFYING_WIDOW: 10_000,
    FilingStatus.MARRIED_SEPARATELY: 5_000,
}
