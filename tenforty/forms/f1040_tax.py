"""Federal 1040 tax-figure calculation (scoped path).

Implements the marginal-rate ordinary tax and the Qualified Dividends &
Capital Gain Tax Worksheet. Year-specific values come from FederalParams;
no `if year ==` branches here.
"""
from tenforty.models import FilingStatus
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


def qdcgt_tax(
    taxable_income: float,
    qualified_dividends: float,
    net_capital_gain: float,
    params: FederalParams,
    filing_status: FilingStatus,
) -> int:
    """Qualified Dividends & Capital Gain Tax Worksheet (scoped: single)."""
    if filing_status is not FilingStatus.SINGLE:
        raise NotImplementedError(
            "QDCGT worksheet is implemented only for single filers in this "
            "scope; other statuses are a guarded follow-up."
        )
    ti = max(taxable_income, 0.0)
    preferential = max(min(qualified_dividends + net_capital_gain, ti), 0.0)
    ordinary = ti - preferential                                   # line 7
    zero_top, fifteen_top = params.qdcgt_breakpoints[filing_status.value]

    # 0% band: fills from ordinary income up to zero_top.
    amt_taxed_0 = max(min(ti, zero_top) - ordinary, 0.0)           # pref in 0% band
    remaining = preferential - amt_taxed_0
    # 15% band: from max(zero_top, ordinary) up to fifteen_top.
    fifteen_base = max(ordinary, zero_top)
    amt_taxed_15 = max(min(ti, fifteen_top) - fifteen_base, 0.0)
    amt_taxed_15 = min(amt_taxed_15, remaining)
    # 20% band: whatever preferential income is left.
    amt_taxed_20 = remaining - amt_taxed_15

    worksheet_tax = (
        tax_from_schedule(ordinary, params)
        + irs_round(amt_taxed_15 * 0.15)
        + irs_round(amt_taxed_20 * 0.20)
    )
    return min(worksheet_tax, tax_from_schedule(ti, params))
