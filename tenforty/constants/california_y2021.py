"""California Form 540 constants for tax year 2021.

All values extracted from FTB Form 540 (TY2021) at
``pdfs/california/2021/f540.pdf``:

- ``STANDARD_DEDUCTION``: side 2, line 18 worksheet
- ``EXEMPTION_CREDIT``: side 1, lines 7-10 multipliers (N × per-person)
  where per-person = $129 (TY2021); N=1 for SINGLE/MFS/HoH and N=2 for
  MFJ/QSS per the form's check-box-driven multiplier
- ``DEPENDENT_EXEMPTION_AMOUNT``: side 2, line 10 ($400 each)
- ``AGI_PHASEOUT_THRESHOLD``: side 2, line 32 ("If your federal AGI is
  more than $212,288, see instructions")
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
