"""California Form 540 main-form compute helpers.

Year-parameterized lookups for the standard deduction and the
basic exemption credit (un-phased-out). Year-specific constants
live in tenforty/constants/california_y{year}.py modules and are
loaded dynamically.

The exemption credit returned here is the un-phased-out lookup;
the AGI phaseout (when federal AGI exceeds the per-year threshold)
is gated in T11's final-liability compute, not here.
"""

import importlib

from tenforty.models import FilingStatus


def _load_ca_constants(year: int):
    try:
        return importlib.import_module(f"tenforty.constants.california_y{year}")
    except ImportError as e:
        raise NotImplementedError(
            f"CA Form 540 not implemented for tax year {year} "
            f"(tenforty v1 supports tax years 2021-2025)."
        ) from e


def compute_standard_deduction(year: int, filing_status: FilingStatus) -> int:
    constants = _load_ca_constants(year)
    return constants.STANDARD_DEDUCTION[filing_status]


def compute_exemption_credit(year: int, filing_status: FilingStatus) -> int:
    constants = _load_ca_constants(year)
    return constants.EXEMPTION_CREDIT[filing_status]


def _walk_rate_schedule(schedule: list[tuple[int, float]], income: float) -> float:
    """Accumulate tax by walking the bracket schedule up to *income*.

    Each entry is (threshold_inclusive, marginal_rate_at_or_above_threshold).
    The bracket starting at threshold[i] ends at threshold[i+1] (exclusive).
    The top bracket has no upper bound.
    """
    tax = 0.0
    for i, (threshold_low, rate) in enumerate(schedule):
        if income <= threshold_low:
            break
        # Upper bound: next bracket's threshold, or infinity for the top bracket
        if i + 1 < len(schedule):
            threshold_high = schedule[i + 1][0]
        else:
            threshold_high = float("inf")
        taxable_in_bracket = min(income, threshold_high) - threshold_low
        tax += taxable_in_bracket * rate
    return tax


def compute_ca_tax(
    year: int,
    filing_status: FilingStatus,
    taxable_income: float | int,
) -> int:
    """California Form 540 line 31 — tax on taxable income.

    For year ∉ {2021..2025} raises NotImplementedError (delegate to
    _load_ca_constants — same shape as compute_standard_deduction).

    For taxable_income ≤ 0 returns 0.
    For 0 < taxable_income ≤ 100_000 uses the FTB Tax Table branch
    (see bin enumeration below); for taxable_income > 100_000 uses
    the FTB Rate Schedule branch directly. Returns the computed
    tax rounded to the nearest dollar (FTB convention).
    """
    constants = _load_ca_constants(year)
    rate_schedule = constants.RATE_SCHEDULE[filing_status]

    if taxable_income <= 0:
        return 0

    if taxable_income <= 50:
        # Special first bin: $1–$50 → tax 0 (status/year invariant)
        return 0

    if taxable_income <= 99_950:
        # Why: FTB Tax Table covers $1–$100,000 in fixed bins. Each regular
        # bin is 100 integers wide; the bin's published tax equals
        # round(rate_schedule_walk(bin_midpoint)). The midpoint formula
        # bin_high - 49.5 works for all regular (100-wide) bins from $51–$99,950
        # but does NOT extend to the truncated last bin ($99,951–$100,000, width
        # 50, midpoint $99,975.5). The boundary discontinuity at $100,000
        # (Tax Table) → $100,001 (Rate Schedule) is real (~$3–5 difference per
        # FTB encoding) and is not a bug — the two branches use distinct
        # computation methods by FTB design.
        import math
        bin_high = 50 + 100 * math.ceil((taxable_income - 50) / 100)
        midpoint = bin_high - 49.5
        return round(_walk_rate_schedule(rate_schedule, midpoint))

    if taxable_income <= 100_000:
        # Truncated last bin: $99,951–$100,000, midpoint $99,975.5
        midpoint = 99_975.5
        return round(_walk_rate_schedule(rate_schedule, midpoint))

    # Rate Schedule branch: income > $100,000 — walk directly on taxable_income
    return round(_walk_rate_schedule(rate_schedule, taxable_income))
