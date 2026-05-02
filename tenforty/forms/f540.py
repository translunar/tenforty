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
import math

from tenforty.models import CA540Return, FilingStatus
from tenforty.rounding import irs_round


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
        bin_high = 50 + 100 * math.ceil((taxable_income - 50) / 100)
        midpoint = bin_high - 49.5
        return round(_walk_rate_schedule(rate_schedule, midpoint))

    if taxable_income <= 100_000:
        # Truncated last bin: $99,951–$100,000, midpoint $99,975.5
        midpoint = 99_975.5
        return round(_walk_rate_schedule(rate_schedule, midpoint))

    # Rate Schedule branch: income > $100,000 — walk directly on taxable_income
    return round(_walk_rate_schedule(rate_schedule, taxable_income))


def _compute_renters_credit(
    year: int,
    filing_status: FilingStatus,
    ca_agi: int,
) -> int:
    """CA renter's credit. Per oracle Q4: gate uses CA AGI (not federal)."""
    constants = _load_ca_constants(year)
    if ca_agi > constants.RENTER_CREDIT_AGI_THRESHOLD[filing_status]:
        return 0
    return constants.RENTER_CREDIT_AMOUNT[filing_status]


def compute(
    year: int,
    filing_status: FilingStatus,
    federal_agi: int,
    ca_agi: int,
    ca540: CA540Return,
    *,
    num_dependents: int = 0,
    ca_itemized: int | None = None,
    renter_credit_eligible: bool = False,
) -> dict[str, int | FilingStatus]:
    """California Form 540 final-liability compute.

    Pipeline: AGI phaseout gate → deduction selection → taxable income →
    CA tax → exemption credit (base + dependent) → renter's credit (CA AGI
    gate per oracle Q4) → voluntary contributions → final liability.

    The ``ca540`` dataclass carries the user-supplied CA-return inputs
    that don't fit on Form 540's per-line schema:
    ``estimated_payments``, ``use_tax``, ``estimated_tax_penalty``,
    ``ptet_credit``, ``voluntary_contributions``. ``num_dependents``
    stays a separate kwarg because it derives from the federal scenario
    (``len(scenario.config.dependents)``), not from CA540Return.
    ``ca_itemized`` stays a separate kwarg because it's a scenario-time
    decision (Sch CA-derived), not stored on CA540Return.
    ``renter_credit_eligible`` likewise stays a kwarg pending its
    promotion to a CA540Return field (v1 follow-up).

    Returns flat dict keyed by ``f540_<semantic>``; all values are int
    (post-``irs_round`` where the input is float).

    Raises NotImplementedError if ``federal_agi`` exceeds the year's
    AGI_PHASEOUT_THRESHOLD (exemption-credit phaseout formula deferred
    from v1 per plan).
    """
    constants = _load_ca_constants(year)

    # AGI phaseout gate
    if federal_agi > constants.AGI_PHASEOUT_THRESHOLD:
        raise NotImplementedError(
            f"Federal AGI ${federal_agi} exceeds CA exemption-credit phaseout "
            f"threshold ${constants.AGI_PHASEOUT_THRESHOLD} for tax year {year}; "
            f"phaseout formula not implemented in v1."
        )

    # Truncate CA540Return float fields to int — preserves the
    # pre-existing call-site contract (orchestrator did int(...) before
    # passing in; tests/oracles assume the same truncation behavior).
    estimated_payments = int(ca540.estimated_payments)
    use_tax = int(ca540.use_tax)
    estimated_tax_penalty = int(ca540.estimated_tax_penalty)
    ptet_credit = int(ca540.ptet_credit)

    std_ded = compute_standard_deduction(year, filing_status)
    deduction = max(std_ded, ca_itemized or 0)
    taxable_income = max(0, ca_agi - deduction)
    ca_tax = compute_ca_tax(year, filing_status, taxable_income)

    # Exemption credits
    base = compute_exemption_credit(year, filing_status)
    dep = constants.DEPENDENT_EXEMPTION_AMOUNT * num_dependents
    exemption = base + dep

    # Renter's credit
    renters = _compute_renters_credit(year, filing_status, ca_agi) if renter_credit_eligible else 0

    # Voluntary contributions
    voluntary_total = sum(vc.amount for vc in ca540.voluntary_contributions)

    total_credits = exemption + renters + ptet_credit

    final = (
        ca_tax
        - total_credits
        + voluntary_total      # voluntary contributions ADD to liability
        + use_tax
        + estimated_tax_penalty
        - estimated_payments
    )

    return {
        "f540_ca_agi": irs_round(ca_agi),
        "f540_deduction": irs_round(deduction),
        "f540_taxable_income": irs_round(taxable_income),
        "f540_ca_tax": ca_tax,
        "f540_exemption_credit": exemption,
        "f540_renter_credit": renters,
        "f540_ptet_credit": ptet_credit,
        "f540_total_credits": irs_round(total_credits),
        "f540_voluntary_contributions": irs_round(voluntary_total),
        "f540_use_tax": irs_round(use_tax),
        "f540_estimated_tax_penalty": irs_round(estimated_tax_penalty),
        "f540_estimated_payments": irs_round(estimated_payments),
        "f540_total_liability": irs_round(final),
        "f540_filing_status": filing_status,
    }
