"""Schedule A — Itemized Deductions.

Native-Python compute. Consumes scenario itemized-deduction fields and
upstream 1040 AGI/MAGI. Output keys match PdfSchA field names.

V1 scope notes (read before extending):

  1. Line 5a (state/local income OR sales tax). V1 assumes state income
     tax; the sales-tax checkbox is left unchecked. Filers in no-income-
     tax states (TX, FL, WA, NV, SD, WY, AK, TN, NH) who prefer the
     sales-tax deduction are not supported — their Sch A will be
     under-deducted. Adding support requires a scenario sales-tax field
     and a `prefer_sales_tax` flag gating line 5a.

  2. SALT cap is year-aware via FederalParams. When params.salt_phaseout_threshold
     is None (2024 and earlier flat-cap years), the cap = salt_cap_starting[status]
     and high MAGI never raises. When threshold is set (2025 OBBBA), below-threshold
     scenarios use salt_cap_starting[status]; above-threshold raises NotImplementedError
     (phaseout math is scoped out of v1).

  3. Lines 15 (casualty) and 16 (other) are hardcoded to 0. Line 17's
     sum references them by variable, so wiring a future scenario field
     is a one-line edit.
"""

from tenforty.params.federal import load as load_federal_params
from tenforty.models import ItemizedDeductions, Scenario
from tenforty.rounding import irs_round


NO_INCOME_TAX_STATES = frozenset({
    "TX", "FL", "WA", "NV", "SD", "WY", "AK", "TN", "NH",
})


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    params = load_federal_params(scenario.config.year)
    f1040 = upstream["f1040"]
    agi = f1040["agi"]
    magi = f1040.get("magi", agi)
    status = scenario.config.filing_status.value

    state = (scenario.config.state or "").upper()
    if (
        state in NO_INCOME_TAX_STATES
        and not scenario.config.acknowledges_sch_a_sales_tax_unsupported
    ):
        raise NotImplementedError(
            f"Schedule A line 5a sales tax election is not implemented in v1. "
            f"Filer state is {state!r} (no state income tax). Set "
            "`acknowledges_sch_a_sales_tax_unsupported: true` on the scenario "
            "config to proceed with a (likely under-deducted) income-tax-path "
            "Sch A, or wait until sales-tax support lands."
        )

    # Year-aware SALT phaseout gate.
    # salt_phaseout_threshold = None → flat cap year (e.g. 2024); no phaseout check.
    # threshold set → if MAGI exceeds it, phaseout math is unimplemented (v1 scope-out).
    if (
        params.salt_phaseout_threshold is not None
        and magi > params.salt_phaseout_threshold
    ):
        raise NotImplementedError(
            f"SALT phaseout (MAGI > ${params.salt_phaseout_threshold:,}) "
            "not supported in v1. Expected behaviour: cap reduces from "
            f"{params.salt_cap_starting[status]:,} "
            f"at rate {params.salt_phaseout_rate} toward "
            f"{params.salt_cap_floor[status]:,} "
            "per OBBBA. Implement in forms.sch_a.compute when the first "
            "taxpayer above threshold appears."
        )

    it = scenario.itemized_deductions or ItemizedDeductions()

    medical_gross = irs_round(it.medical_expenses)
    medical_floor = irs_round(agi * params.medical_agi_floor_pct)
    medical_deductible = max(0, medical_gross - medical_floor)

    state_income_tax_line_5a = irs_round(it.state_income_tax)
    property_tax_line_5b = irs_round(it.property_tax)
    personal_property_tax_line_5c = 0
    line_5d = (
        state_income_tax_line_5a
        + property_tax_line_5b
        + personal_property_tax_line_5c
    )
    starting_cap = params.salt_cap_starting[status]
    line_5e_salt_capped = min(line_5d, starting_cap)

    other_taxes_line_6 = 0
    line_7_taxes_total = line_5e_salt_capped + other_taxes_line_6

    mortgage_interest_line_8a = irs_round(it.mortgage_interest)
    line_10_interest_total = mortgage_interest_line_8a

    charity_cash_line_11 = irs_round(it.charitable_contributions)
    charity_noncash_line_12 = 0
    charity_carryover_line_13 = 0
    line_14_charity_total = (
        charity_cash_line_11
        + charity_noncash_line_12
        + charity_carryover_line_13
    )

    line_15_casualty = 0
    line_16_other = 0

    line_17_total = (
        medical_deductible
        + line_7_taxes_total
        + line_10_interest_total
        + line_14_charity_total
        + line_15_casualty
        + line_16_other
    )

    return {
        **scenario.config.pdf_header(),
        "sch_a_line_1_medical_gross": medical_gross,
        "sch_a_line_2_agi": agi,
        "sch_a_line_3_medical_floor": medical_floor,
        "sch_a_line_4_medical_deductible": medical_deductible,
        "sch_a_line_5a_state_income_tax": state_income_tax_line_5a,
        # sch_a_line_5a_sales_tax_checkbox is intentionally omitted here.
        #
        # Today there is no compute path that drives this checkbox True — the
        # sales-tax election is out of scope for v1 (see module docstring).
        # Emitting `False` would route through fill_with_repeaters's scalar
        # path, which (before the _render → _render_scalar unification in this
        # commit) silently coerced the bool via _render's "Off" branch instead
        # of going through the project-required checkbox_states registry. That
        # was a latent policy bypass.
        #
        # When a future implementation adds the sales-tax election:
        #   • emit True only when the filer actually elects sales tax;
        #   • add a _CHECKBOX_STATES registry entry on pdf_sch_a (see
        #     tenforty/filing/pdf_sch_a.py) so the value is routed through
        #     the checkbox-state-aware fill path;
        #   • do NOT re-introduce a bare True/False literal in this dict,
        #     because _render_scalar now raises on bool to enforce that policy.
        "sch_a_line_5b_property_tax": property_tax_line_5b,
        "sch_a_line_5c_personal_property_tax": personal_property_tax_line_5c,
        "sch_a_line_5d_salt_sum": line_5d,
        "sch_a_line_5e_salt_capped": line_5e_salt_capped,
        "sch_a_line_6_other_taxes": other_taxes_line_6,
        "sch_a_line_7_taxes_total": line_7_taxes_total,
        "sch_a_line_8a_mortgage_interest": mortgage_interest_line_8a,
        "sch_a_line_10_interest_total": line_10_interest_total,
        "sch_a_line_11_charity_cash": charity_cash_line_11,
        "sch_a_line_12_charity_noncash": charity_noncash_line_12,
        "sch_a_line_14_charity_total": line_14_charity_total,
        "sch_a_line_15_casualty": line_15_casualty,
        "sch_a_line_16_other": line_16_other,
        "sch_a_line_17_total": line_17_total,
    }
