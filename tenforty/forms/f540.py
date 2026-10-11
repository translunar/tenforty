"""California Form 540 main-form compute helpers.

Year-parameterized lookups for the standard deduction and the
basic exemption credit (un-phased-out). Year-specific values live
in tenforty/params/california/y{year}.py modules, loaded via the
manifest-gated params.california.load().

The exemption credit returned here is the un-phased-out lookup;
the AGI phaseout (when federal AGI exceeds the per-year threshold)
is gated in the final-liability compute, not here.
"""

import datetime
import math
from collections.abc import Mapping, Sequence

from tenforty.attestations import refund_direct_deposit
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
    ca_withholding: int = 0,
) -> dict[str, int | FilingStatus | None]:
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
    promotion to a CA540Return field (v1 follow-up). ``ca_withholding``
    is Form 540 line 71 — the sum of CA-attributed W-2 box-17 withholding
    (see the orchestrator call-site, which sums ``scenario.w2s`` by
    ``w.state == "CA"``); it stays a separate kwarg for the same reason
    ``num_dependents`` does — it derives from the federal scenario's W-2s,
    not from CA540Return. Carried verbatim; never computed or capped here.

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
    # Line 112: carried verbatim, stays None when unstated (the emit step
    # decides whether unstated is acceptable). Deliberately NOT part of
    # f540_total_liability, which is the tax position.
    interest_and_penalties = (
        None if ca540.interest_and_penalties is None
        else int(ca540.interest_and_penalties))
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

    # The credits are NONREFUNDABLE, and the liability follows the form's own
    # two clamps (wording verified identical on all five years' forms and
    # booklets, 2021-2025):
    #   line 33: "Subtract line 32 from line 31. If less than zero, enter 0."
    #   line 48: "Subtract line 47 from line 35. If less than zero, enter 0."
    # Line 35 == line 33 here (line 34 is not modeled); line 47 is the renter
    # credit plus the PTET credit. A single unclamped `tax − credits` let a
    # credit larger than the tax surface as a phantom overpayment in
    # f540_total_liability (which Schedule X reads), while the printed lines —
    # clamped in mappings/pdf_f540 — showed zero.
    line_33 = max(0, ca_tax - exemption)
    line_47 = renters + ptet_credit
    # The exemption and renter credits are use-or-lose, so the clamp is the
    # whole story for them. An unused PTET credit instead CARRIES FORWARD (form
    # FTB 3804-CR), and no credit carryover is modeled: clamping it away would
    # leave next year's return wrong with no warning. Refuse instead.
    #
    # BOUNDARY: "a PTET credit is present AND line 47 exceeds line 35". The
    # order in which the renter and PTET credits are applied (R&TC §17039) has
    # NOT been verified from an authoritative source, so the broad side is
    # chosen. If the renter credit is applied first, this boundary is EXACT:
    # the unused PTET credit, PTET − min(PTET, max(0, line 35 − renter)), is
    # positive precisely when PTET > 0 and renter + PTET > line 35. Only if
    # the PTET credit were applied first would it refuse some returns whose
    # PTET credit is in fact fully used. So it is either exact or safely
    # conservative; narrow it only if the §17039 order is pinned from source.
    if ptet_credit > 0 and line_47 > line_33:
        raise NotImplementedError(
            f"`ptet_credit` ({ptet_credit}) cannot be fully used in {year}: "
            f"line 47 credits ({line_47} = renter's credit {renters} + PTET "
            f"credit {ptet_credit}) exceed the tax they can offset (Form 540 "
            f"line 35, {line_33}). The unused pass-through entity elective tax "
            "credit is a carryover to later years, figured on form FTB "
            "3804-CR, and tenforty does not model credit carryovers — "
            "clamping it to the tax would silently drop the carryover. File "
            "by hand, or enter only the PTET credit used this year and track "
            "the FTB 3804-CR carryover yourself."
        )
    line_48 = max(0, line_33 - line_47)

    final = (
        line_48
        + voluntary_total      # voluntary contributions ADD to liability
        + use_tax
        + estimated_tax_penalty
        - estimated_payments
        # CA 540 line 71 — W-2 box-17 CA withholding. This term was OMITTED
        # entirely until 2026-07-16 (f540 balance had no withholding line;
        # f540_line71_ca_withholding was producer-less), making
        # total_liability wrong by the full withholding for every CA W-2
        # return. Carried verbatim from the scenario (summed upstream by
        # state=="CA"), never computed or capped. Reference oracle models it
        # identically (ca_540_reference line 71 → line 78 → balance).
        - ca_withholding
    )

    return {
        # Line 13 — federal AGI carried from federal Form 1040 line 11. The
        # CA return starts from this; it was never emitted, so 540 line 13
        # printed blank on every emit.
        "f540_federal_agi": irs_round(federal_agi),
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
        "f540_interest_and_penalties": (
            None if interest_and_penalties is None
            else irs_round(interest_and_penalties)),
        "f540_estimated_payments": irs_round(estimated_payments),
        "f540_line71_ca_withholding": irs_round(ca_withholding),
        "f540_total_liability": irs_round(final),
        "f540_filing_status": filing_status,
    }


# Form 540 line 7 "Personal": enter 1 in the box for filing status 1, 3 or 4
# (Single, MFS, HOH) and 2 for filing status 2 or 5 (MFJ, QSS). Line 6 ("someone
# can claim you") reduces this, but that box is not modeled, so it stays unset.
_PERSONAL_EXEMPTION_COUNT: dict[FilingStatus, int] = {
    FilingStatus.SINGLE: 1,
    FilingStatus.MARRIED_SEPARATELY: 1,
    FilingStatus.HEAD_OF_HOUSEHOLD: 1,
    FilingStatus.MARRIED_JOINTLY: 2,
    FilingStatus.QUALIFYING_WIDOW: 2,
}


def presentation_keys(
    config,
    w2s: Sequence,
    year: int,
) -> dict[str, object]:
    """Non-money / presentation values for the Form 540 face, from the scenario.

    Header identity, date of birth, the "address is the same as your principal
    residence" box (only when the scenario states it), the line 92 full-year
    health-care-coverage box (a stated coverage gap raises: FTB 3853 is not
    modeled), the line 7 / line 10
    exemption count-and-amount boxes, line 11 and line 12. Values here are
    SCENARIO-derived (not compute outputs); the orchestrator merges them into
    the CA results dict and ``pdf_f540`` places them.

    * Line 7 amount = count x per-person credit, where the per-person credit is
      the year's ``exemption_credit[filing_status]`` split over the count (the
      param table already stores the MFJ/QSS figure as 2 x the single figure).
    * Line 10 = number of dependents x the year's dependent exemption amount;
      omitted entirely at zero (blank-by-design). Lines 8 and 9 (blind / senior)
      are not modeled and stay blank.
    * Line 11 = line 7 + line 8 + line 9 + line 10, so it equals
      ``f540_exemption_credit`` (line 32) by construction.
    * Line 12 = the sum of W-2 box 16 (``W2.state_wages``) across all W-2s, per
      the 540 instruction "State wages from your federal Form(s) W-2, box 16".
      Printed only when the return has W-2s. (The CA compute does not aggregate
      box 16 anywhere else — only the test oracle takes it as an input.)
    """
    params = ca_params.load(year)
    fs = config.filing_status
    count = _PERSONAL_EXEMPTION_COUNT[fs]
    personal_total = compute_exemption_credit(year, fs)
    if personal_total % count:
        raise ValueError(
            f"{year} exemption credit {personal_total} for {fs.value} is not a "
            f"multiple of the personal-exemption count {count}")
    dependents = len(config.dependents)
    dependent_total = params.dependent_exemption_amount * dependents

    out: dict[str, object] = {
        "f540_taxpayer_first_name": config.first_name,
        "f540_taxpayer_middle_initial": config.middle_initial,
        "f540_taxpayer_last_name": config.last_name,
        "f540_taxpayer_dob": _mm_dd_yyyy(config.birthdate),
        "f540_address_street": config.address,
        "f540_address_city": config.address_city,
        "f540_address_state": config.address_state,
        "f540_address_zip": config.address_zip,
        "f540_residence_county": config.county,
        "f540_line7_count": count,
        "f540_line7_amount": personal_total,
        "f540_line11_exemption_amount": personal_total + dependent_total,
    }
    if config.spouse_first_name or config.spouse_last_name:
        out["f540_spouse_first_name"] = config.spouse_first_name
        out["f540_spouse_last_name"] = config.spouse_last_name
        out["f540_spouse_ssn"] = config.spouse_ssn
    if config.full_year_health_care_coverage is False:
        raise NotImplementedError(
            "`full_year_health_care_coverage` is false: the household did not "
            f"have full-year health care coverage in {year}, so the return owes "
            "an Individual Shared Responsibility penalty (Form 540 line 92) or "
            "an exemption from it, both figured on form FTB 3853. tenforty does "
            "not model FTB 3853, and printing line 92 blank would understate "
            "the tax. File by hand, or set the flag to true if every household "
            "member in fact had qualifying coverage for the whole year."
        )
    if config.full_year_health_care_coverage:
        # Line 92 box; its on-state on every year's template (see pdf_f540).
        # Unstated (None) emits nothing here — the orchestrator refuses it at
        # PDF-emit time.
        out["f540_full_year_coverage_checkbox"] = "/Yes"
    if config.address_is_principal_residence:
        # The box's on-state on every year's template (see pdf_f540).
        out["f540_address_is_residence_checkbox"] = "/Yes"
    if dependents:
        out["f540_line10_count"] = dependents
        out["f540_line10_amount"] = dependent_total
    if w2s:
        out["f540_line12_state_wages"] = irs_round(sum(w.state_wages for w in w2s))
    # Line 116 direct deposit, as stated; `pdf_f540` prints it only when
    # line 115 shows a refund.
    deposit = refund_direct_deposit(config)
    if deposit is not None:
        (out["f540_refund_routing_number"], out["f540_refund_account_number"],
         out["f540_refund_account_type"]) = deposit
    # Drop empty identity strings so a missing field stays blank, never "".
    return {k: v for k, v in out.items() if v != ""}


def _mm_dd_yyyy(iso_date: str) -> str:
    """ISO ``YYYY-MM-DD`` -> the form's ``mm/dd/yyyy``. Loud on any other shape."""
    return datetime.date.fromisoformat(iso_date).strftime("%m/%d/%Y")
