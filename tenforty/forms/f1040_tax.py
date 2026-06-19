"""Federal 1040 tax-figure calculation (scoped path).

Implements the marginal-rate ordinary tax and the Qualified Dividends &
Capital Gain Tax Worksheet. Year-specific values come from FederalParams;
no `if year ==` branches here.
"""
from tenforty.params.federal import FederalParams
from tenforty.rounding import irs_round


def tax_from_schedule(taxable_income: float, params: FederalParams) -> int:
    """Tax on ordinary income from the year's rate schedule."""
    if taxable_income <= 0:
        return 0
    tax = 0.0
    lower = 0.0
    for upper, rate in params.ordinary_brackets:
        if taxable_income <= lower:
            break
        slice_top = min(taxable_income, upper)
        tax += (slice_top - lower) * rate
        lower = upper
    return irs_round(tax)
