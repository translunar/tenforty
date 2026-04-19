"""Schedule 1 — Additional Income and Adjustments to Income.

Native-Python compute. Aggregates additional-income categories from
upstream form results (primarily Sch E rental income) and
adjustment-to-income categories from scenario fields.

V1 scope: line 5 (rental/royalty via Sch E) is the only populated
additional-income line. Other Part I categories (business income,
unemployment, farm income, etc.) and all of Part II (adjustments)
are zero in v1 — the compute function writes 0 to those keys so the
PDF fills cleanly. When a future scenario drives one of those lines,
populate the value here; line 10 and line 26 sums already reference
the variables by name, so the wiring is a one-line edit.
"""

from tenforty.models import Scenario
from tenforty.rounding import irs_round


def compute(scenario: Scenario, upstream: dict[str, dict]) -> dict:
    """Compute Schedule 1 from scenario and upstream form results.

    Cross-check note: Plan C's oracle test asserts
    sch_1_line_10_total_additional_income == f1040["other_income"].
    That holds ONLY when Sch E is the sole Sch 1 contributor. The
    oracle test fixture carries the @pytest.mark.only_sch_e_contributes_to_sch_1
    marker; scenarios with unemployment / business / farm income should
    NOT run that oracle assertion.
    """
    sch_e = upstream.get("sch_e", {})

    taxable_refunds_line_1 = 0
    alimony_line_2a = 0
    business_income_line_3 = 0
    capital_gain_line_4 = 0
    rental_re_royalty_line_5 = irs_round(sch_e.get("sch_e_line_26_total", 0))
    farm_income_line_6 = 0
    unemployment_line_7 = irs_round(
        sum(g.unemployment_compensation for g in scenario.form1099_g),
    )
    other_income_line_8_sum = irs_round(
        sum(
            g.rtaa_payments + g.taxable_grants + g.agriculture_payments + g.market_gain
            for g in scenario.form1099_g
        ),
    )

    total_additional_income_line_10 = (
        taxable_refunds_line_1
        + alimony_line_2a
        + business_income_line_3
        + capital_gain_line_4
        + rental_re_royalty_line_5
        + farm_income_line_6
        + unemployment_line_7
        + other_income_line_8_sum
    )

    educator_expenses_line_11 = 0
    hsa_deduction_line_13 = 0
    self_employment_tax_deduction_line_15 = 0
    sep_simple_keogh_line_16 = 0
    self_employed_health_line_17 = 0
    penalty_early_withdrawal_line_18 = 0
    alimony_paid_line_19a = 0
    ira_deduction_line_20 = 0
    student_loan_interest_line_21 = 0
    other_adjustments_line_24_sum = 0

    total_adjustments_line_26 = (
        educator_expenses_line_11
        + hsa_deduction_line_13
        + self_employment_tax_deduction_line_15
        + sep_simple_keogh_line_16
        + self_employed_health_line_17
        + penalty_early_withdrawal_line_18
        + alimony_paid_line_19a
        + ira_deduction_line_20
        + student_loan_interest_line_21
        + other_adjustments_line_24_sum
    )

    first = scenario.config.first_name.strip()
    last = scenario.config.last_name.strip()
    return {
        "sch_1_line_1_taxable_refunds": taxable_refunds_line_1,
        "sch_1_line_3_business_income": business_income_line_3,
        "sch_1_line_4_other_gains": capital_gain_line_4,
        "sch_1_line_5_rental_re_royalty": rental_re_royalty_line_5,
        "sch_1_line_6_farm_income": farm_income_line_6,
        "sch_1_line_7_unemployment": unemployment_line_7,
        "sch_1_line_8z_other_income": other_income_line_8_sum,
        "sch_1_line_10_total_additional_income": total_additional_income_line_10,
        "sch_1_line_11_educator": educator_expenses_line_11,
        "sch_1_line_13_hsa": hsa_deduction_line_13,
        "sch_1_line_15_se_tax": self_employment_tax_deduction_line_15,
        "sch_1_line_17_se_health": self_employed_health_line_17,
        "sch_1_line_20_ira": ira_deduction_line_20,
        "sch_1_line_21_student_loan_interest": student_loan_interest_line_21,
        "sch_1_line_26_total_adjustments": total_adjustments_line_26,
        "taxpayer_name": f"{first} {last}".strip(),
        "taxpayer_ssn": scenario.config.ssn,
    }
