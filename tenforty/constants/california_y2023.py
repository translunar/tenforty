"""California Form 540 constants for tax year 2023.

All values extracted from FTB Form 540 (TY2023) at
``pdfs/california/2023/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $144 (TY2023); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($446 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $237,035, see instructions")
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
