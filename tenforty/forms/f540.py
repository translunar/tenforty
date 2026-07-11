"""California Form 540 main-form compute helpers.

Year-parameterized lookups for the standard deduction and the
basic exemption credit (un-phased-out). Year-specific values live
in tenforty/params/california/y{year}.py modules, loaded via the
manifest-gated params.california.load().

The exemption credit returned here is the un-phased-out lookup;
the AGI phaseout (when federal AGI exceeds the per-year threshold)
is gated in the final-liability compute, not here.
"""

import math

from tenforty.models import CA540Return, FilingStatus
from tenforty.params import california as ca_params
from tenforty.rounding import irs_round


def compute_standard_deduction(year: int, filing_status: FilingStatus) -> int:
    return ca_params.load(year).standard_deduction[filing_status.value]


def compute_exemption_credit(year: int, filing_status: FilingStatus) -> int:
    return ca_params.load(year).exemption_credit[filing_status.value]


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

    For unsupported years raises NotImplementedError (manifest-gated
    params.california.load).

    For taxable_income ≤ 0 returns 0.
    For 0 < taxable_income ≤ 100_000 uses the FTB Tax Table branch
    (see bin enumeration below); for taxable_income > 100_000 uses
    the FTB Rate Schedule branch directly. Returns the computed
    tax rounded to the nearest dollar (FTB convention).
    """
    rate_schedule = ca_params.load(year).rate_schedule[filing_status.value]

    if taxable_income <= 0:
        return 0

    if taxable_income <= 50:
        # Special first bin: $1–$50 → tax 0 (status/year invariant)
        return 0

    if taxable_income <= 99_950:
        # Why: FTB Tax Table covers $1–$100,000 in fixed bins. Each regular
        # bin is 100 integers wide; the bin's published tax equals
        # round(rate_schedule_walk(bin_midpoint)), where the FTB uses the
        # INTEGER midpoint (bin_high - 50, e.g. 70,700 for the $70,651–$70,750
        # bin). Empirically the integer midpoint reproduces 8,008/8,008
        # published CA cells for 2024–2025 exactly; the half-dollar midpoint
        # (bin_high - 49.5) mismatched 64 of them by +$1 at rounding
        # boundaries (Layer-2 oracle, tests/test_tax_table_oracle.py). The
        # boundary discontinuity at $100,000 (Tax Table) → $100,001 (Rate
        # Schedule) is real (~$3–5 difference per FTB encoding) and is not a
        # bug — the two branches use distinct computation methods by FTB design.
        bin_high = 50 + 100 * math.ceil((taxable_income - 50) / 100)
        midpoint = bin_high - 50
        return irs_round(_walk_rate_schedule(rate_schedule, midpoint))

    if taxable_income <= 100_000:
        # Truncated last bin: $99,951–$100,000, integer midpoint $99,975
        midpoint = 99_975
        return irs_round(_walk_rate_schedule(rate_schedule, midpoint))

    # Rate Schedule branch: income > $100,000 — walk directly on taxable_income
    return irs_round(_walk_rate_schedule(rate_schedule, taxable_income))


def _compute_renters_credit(
    year: int,
    filing_status: FilingStatus,
    ca_agi: int,
) -> int:
    """CA renter's credit. Per oracle Q4: gate uses CA AGI (not federal)."""
    params = ca_params.load(year)
    if ca_agi > params.renter_credit_agi_threshold[filing_status.value]:
        return 0
    return params.renter_credit_amount[filing_status.value]


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
    params = ca_params.load(year)

    # AGI phaseout gate
    if federal_agi > params.agi_phaseout_threshold:
        raise NotImplementedError(
            f"Federal AGI ${federal_agi} exceeds CA exemption-credit phaseout "
            f"threshold ${params.agi_phaseout_threshold} for tax year {year}; "
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
    dep = params.dependent_exemption_amount * num_dependents
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
