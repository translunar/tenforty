"""California Form 540 constants for tax year 2024.

All values extracted from FTB Form 540 (TY2024) at
``pdfs/california/2024/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $149 (TY2024); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($461 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $244,857, see instructions")
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
