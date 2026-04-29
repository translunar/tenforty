"""California Form 540 constants for tax year 2025.

All values extracted from FTB Form 540 (TY2025) at
``pdfs/california/2025/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $153 (TY2025); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($475 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $252,203, see instructions")
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
