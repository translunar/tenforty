"""California Form 540 constants for tax year 2022.

All values extracted from FTB Form 540 (TY2022) at
``pdfs/california/2022/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $140 (TY2022); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($433 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $229,908, see instructions")
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
