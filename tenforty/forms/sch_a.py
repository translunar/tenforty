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

  2. SALT cap uses the OBBBA structure from constants.y2025. Below the
     phaseout threshold, cap = SALT_CAP_STARTING[filing_status]. Above
     SALT_PHASEOUT_THRESHOLD MAGI, compute raises NotImplementedError —
     the 30%-rate phaseout math is scoped out of v1.

  3. Lines 15 (casualty) and 16 (other) are hardcoded to 0. Line 17's
     sum references them by variable, so wiring a future scenario field
     is a one-line edit.
"""

from tenforty.constants import y2025
from tenforty.models import ItemizedDeductions, Scenario
from tenforty.rounding import irs_round


NO_INCOME_TAX_STATES = frozenset({
    "TX", "FL", "WA", "NV", "SD", "WY", "AK", "TN", "NH",
})


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    f1040 = upstream["f1040"]
    agi = f1040["agi"]
    magi = f1040.get("magi", agi)

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

    if magi > y2025.SALT_PHASEOUT_THRESHOLD:
        raise NotImplementedError(
            f"SALT phaseout (MAGI > ${y2025.SALT_PHASEOUT_THRESHOLD:,}) "
            "not supported in v1. Expected behaviour: cap reduces from "
            f"{y2025.SALT_CAP_STARTING[scenario.config.filing_status]:,} "
            f"at rate {y2025.SALT_PHASEOUT_RATE} toward "
            f"{y2025.SALT_CAP_FLOOR[scenario.config.filing_status]:,} "
            "per OBBBA. Implement in forms.sch_a.compute when the first "
            "taxpayer above threshold appears."
        )

    it = scenario.itemized_deductions or ItemizedDeductions()

    medical_gross = irs_round(it.medical_expenses)
    medical_floor = irs_round(agi * y2025.MEDICAL_AGI_FLOOR_PCT)
    medical_deductible = max(0, medical_gross - medical_floor)

    state_income_tax_line_5a = irs_round(it.state_income_tax)
    property_tax_line_5b = irs_round(it.property_tax)
    personal_property_tax_line_5c = 0
    line_5d = (
        state_income_tax_line_5a
        + property_tax_line_5b
        + personal_property_tax_line_5c
    )
    starting_cap = y2025.SALT_CAP_STARTING[scenario.config.filing_status]
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

    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return {
        "sch_a_line_1_medical_gross": medical_gross,
        "sch_a_line_2_agi": agi,
        "sch_a_line_3_medical_floor": medical_floor,
        "sch_a_line_4_medical_deductible": medical_deductible,
        "sch_a_line_5a_state_income_tax": state_income_tax_line_5a,
        "sch_a_line_5a_sales_tax_checkbox": False,
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
        "taxpayer_name": f"{first} {last}".strip(),
        "taxpayer_ssn": scenario.config.ssn,
    }
