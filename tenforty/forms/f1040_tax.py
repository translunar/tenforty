"""Federal 1040 tax-figure calculation (scoped path).

Implements the marginal-rate ordinary tax and the Qualified Dividends &
Capital Gain Tax Worksheet. Year-specific values come from FederalParams;
no `if year ==` branches here.
"""
from tenforty import years as year_manifest
from tenforty.models import FilingStatus, parse_filing_status
from tenforty.params.federal import FederalParams
from tenforty.params.status_view import StatusView
from tenforty.rounding import irs_round
from tenforty.tax_table import TABLE_CEILING, tax_from_table


def tax_from_schedule(taxable_income: float, view: StatusView) -> int:
    """Tax on ordinary income from the year's rate schedule for the view's
    filing status (``params.for_status(status)``). A raw FederalParams is
    refused: its ordinary_brackets is status-keyed, and reading it without a
    status would silently pick nothing meaningful."""
    if not isinstance(view, StatusView):
        raise TypeError(
            "tax_from_schedule takes a per-status view "
            "(params.for_status(filing_status)), not "
            f"{type(view).__name__}")
    if taxable_income <= 0:
        return 0
    tax = 0.0
    lower = 0.0
    for upper, rate in view.ordinary_brackets:
        if taxable_income <= lower:
            break
        slice_top = min(taxable_income, upper)
        tax += (slice_top - lower) * rate
        lower = upper
    return irs_round(tax)


def ordinary_tax(taxable_income: float, params: FederalParams,
                 filing_status: FilingStatus) -> int:
    """Tax the way the 1040 instructions direct: the published Tax Table
    for taxable income under $100,000, the rate schedule at or above.
    The two differ by a few dollars (table bins carry midpoint tax)."""
    if taxable_income <= 0:
        return 0
    if taxable_income < TABLE_CEILING:
        return tax_from_table(taxable_income, params.year, filing_status)
    return tax_from_schedule(taxable_income, params.for_status(filing_status))


def qdcgt_tax(
    taxable_income: float,
    qualified_dividends: float,
    net_capital_gain: float,
    params: FederalParams,
    filing_status: FilingStatus,
) -> int:
    """Qualified Dividends & Capital Gain Tax Worksheet (scoped to the
    statuses declared for the year in years.NATIVE_SPINE_STATUSES)."""
    filing_status = parse_filing_status(filing_status)
    if not year_manifest.native_spine_supports(params.year, filing_status.value):
        raise NotImplementedError(
            f"QDCGT worksheet: filing status {filing_status.value!r} is not "
            f"declared for tax year {params.year} in "
            f"years.NATIVE_SPINE_STATUSES (the native-spine support grid)."
        )
    ti = max(taxable_income, 0.0)
    preferential = max(min(qualified_dividends + net_capital_gain, ti), 0.0)
    ordinary = ti - preferential                                   # line 7
    zero_top, fifteen_top = params.for_status(filing_status).qdcgt_breakpoints

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
        ordinary_tax(ordinary, params, filing_status)
        + irs_round(amt_taxed_15 * 0.15)
        + irs_round(amt_taxed_20 * 0.20)
    )
    return min(worksheet_tax, ordinary_tax(ti, params, filing_status))
