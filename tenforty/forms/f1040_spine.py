"""Form 1040 native spine assembly.

Replaces the Excel-workbook evaluation path with native Python. Mirrors
the 1040 line flow year-agnostically: every year-specific value comes
from ``params`` (a ``FederalParams`` instance). No ``if year ==`` branches
and no year-specific numeric literals here.

Scoped path: single filers only. Non-single status raises NotImplementedError
at entry. Multi-status support is a guarded follow-up.

``compute_spine`` does NOT invoke the schedules itself; the orchestrator
calls each schedule's ``compute`` and passes the results as
``schedule_results: dict[str, dict]``.  Key contract for each schedule's
sub-dict (the orchestrator is responsible for providing these keys):

    schedule_results["sch_1"]  — Schedule 1 Part I / Part II line totals
        "sch_1_line_10_total_additional_income"   — Sch 1 line 10 total
        "sch_1_line_26_total_adjustments"          — Sch 1 line 26 total
        per-line breakdown keys (see OUTPUTS[2025])

    schedule_results["sch_a"]  — Schedule A itemized total
        "schedule_a_total"     — line 17 total itemized deductions
        "sch_a_line_5e_salt_capped"

    schedule_results["sch_d"]  — Schedule D cap-gain/loss
        "sch_d_line_16_total"  — net capital gain/loss (line 16)

    schedule_results["sch_e"]  — Schedule E Part I / Part II totals
        "sch_e_line_26_total"  — Part I rental net total (line 26)
        "sche_line41"          — Part II K-1 pass-through total (line 41)

    schedule_results["f8959"]  — Form 8959 additional Medicare
        "f8959_line_18"        — total additional Medicare tax
        "f8959_line_24"        — additional Medicare withheld

    schedule_results["f8995"]  — Form 8995 QBI deduction
        "f8995_line_15"        — QBI deduction (1040 line 13)

    schedule_results["f8582"]  — Form 8582 passive activity
        "f8582_line_11_allowed_loss"

Output keys match ``F1040.OUTPUTS[2025]`` exactly so PDF mappings and
CA consumers are unaffected.
"""

from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import FilingStatus, Scenario
from tenforty.params.federal import FederalParams
from tenforty.rounding import irs_round


def compute_spine(
    scenario: Scenario,
    params: FederalParams,
    schedule_results: dict[str, dict],
) -> dict:
    """Assemble the 1040 lines from scenario inputs and schedule results.

    Args:
        scenario: The tax scenario (filer inputs).
        params: Year-specific federal parameters (from tenforty.params.federal).
        schedule_results: Keyed dict of pre-computed schedule return dicts.
            Each sub-dict may be absent; missing values default to 0.

    Returns:
        Dict of 1040 output fields using OUTPUTS[2025] production key names.

    Raises:
        NotImplementedError: For non-single filing status.
    """
    filing_status = scenario.config.filing_status
    if filing_status is not FilingStatus.SINGLE:
        raise NotImplementedError(
            f"compute_spine is scoped to single filers; "
            f"filing status {filing_status.value!r} is not supported."
        )

    # Convenience accessors for each schedule sub-dict.
    sch_1 = schedule_results.get("sch_1", {})
    sch_a = schedule_results.get("sch_a", {})
    sch_d = schedule_results.get("sch_d", {})
    sch_e = schedule_results.get("sch_e", {})
    f8959 = schedule_results.get("f8959", {})
    f8995 = schedule_results.get("f8995", {})
    f8582 = schedule_results.get("f8582", {})

    # -----------------------------------------------------------------------
    # Page 1 — Income
    # -----------------------------------------------------------------------

    # 1040 line 1a — Wages (sum of all W-2 boxes 1).
    wages = irs_round(sum(w.wages for w in scenario.w2s))

    # 1040 line 2b — Taxable interest (sum of 1099-INT box 1).
    taxable_interest = irs_round(
        sum(f.interest for f in scenario.form1099_int)
    )

    # 1040 line 3b — Ordinary dividends (sum of 1099-DIV box 1a).
    ordinary_divs = irs_round(
        sum(f.ordinary_dividends for f in scenario.form1099_div)
    )

    # 1040 line 3a — Qualified dividends (sum of 1099-DIV box 1b).
    qualified_divs = irs_round(
        sum(f.qualified_dividends for f in scenario.form1099_div)
    )

    # 1040 line 7 — Net capital gain/loss from Schedule D line 16.
    # Key: sch_d_line_16_total from forms.sch_d.compute.
    schd_line16 = sch_d.get("sch_d_line_16_total", 0)

    # Schedule 1 line 10 — Total additional income.
    # Key: sch_1_line_10_total_additional_income from forms.sch_1.compute.
    sch_1_line_10 = sch_1.get("sch_1_line_10_total_additional_income", 0)

    # 1040 line 8 — Additional income from Schedule 1 line 10.
    # 1040 line 9 — Total income = lines 1 + 2b + 3b + 7 + 8.
    total_income = irs_round(
        wages + taxable_interest + ordinary_divs + schd_line16 + sch_1_line_10
    )

    # -----------------------------------------------------------------------
    # Page 1 — Adjustments to Income (Schedule 1 Part II)
    # -----------------------------------------------------------------------

    # 1040 line 10 — Adjustments from Schedule 1 line 26.
    # Key: sch_1_line_26_total_adjustments from forms.sch_1.compute.
    sch_1_line_26 = sch_1.get("sch_1_line_26_total_adjustments", 0)

    # 1040 line 11 — Adjusted Gross Income = total income − adjustments.
    agi = irs_round(total_income - sch_1_line_26)

    # MAGI: for v1 single-filer scope, MAGI = AGI (no foreign income exclusion
    # or other MAGI-specific add-backs apply in the supported scenario set).
    magi = agi

    # -----------------------------------------------------------------------
    # Page 2 — Deductions
    # -----------------------------------------------------------------------

    # Standard deduction for filing status from params.
    std_deduction = params.standard_deduction[filing_status.value]

    # Schedule A total (line 17) from schedule_results["sch_a"].
    # Key: "schedule_a_total" — orchestrator maps sch_a_line_17_total → this.
    schedule_a_total = sch_a.get("schedule_a_total", 0)

    # 1040 line 12: deduction = max(standard, itemized).
    if schedule_a_total >= std_deduction:
        # Itemized selected.
        standard_deduction_amount = 0
        total_deductions = schedule_a_total
        standard_deduction_applied = False
    else:
        # Standard deduction selected.
        standard_deduction_amount = std_deduction
        total_deductions = std_deduction
        standard_deduction_applied = True

    # 1040 line 13 — QBI deduction from Form 8995 line 15.
    # Key: "f8995_line_15" from schedule_results["f8995"].
    qbi_deduction = f8995.get("f8995_line_15", 0)

    # 1040 line 15 — Taxable income before QBI deduction (no named range in XLS;
    # derived here as AGI − deduction).
    taxable_income_before_qbi = irs_round(agi - total_deductions)

    # 1040 line 15 — Taxable income = taxable_income_before_qbi − QBI deduction.
    taxable_income = max(0, irs_round(taxable_income_before_qbi - qbi_deduction))

    # -----------------------------------------------------------------------
    # Page 2 — Tax and Credits
    # -----------------------------------------------------------------------

    # Net capital gain for QDCGT worksheet: qualified dividends + max(0, LTCG).
    # Use Sch D line 16 as the net cap gain input.
    net_capital_gain = irs_round(max(0, schd_line16) + qualified_divs)

    # 1040 line 16 — Tax from Qualified Dividends & Capital Gain Tax Worksheet.
    income_tax = qdcgt_tax(
        taxable_income=taxable_income,
        qualified_dividends=qualified_divs,
        net_capital_gain=net_capital_gain,
        params=params,
        filing_status=filing_status,
    )

    # -----------------------------------------------------------------------
    # Other Taxes (Schedule 2)
    # -----------------------------------------------------------------------

    # Form 8959 line 18 — Additional Medicare Tax.
    # Key: "f8959_line_18" from forms.f8959.compute.
    f8959_tax_total = f8959.get("f8959_line_18", 0)

    # 1040 line 17 — Total tax = income tax + additional Medicare.
    total_tax = irs_round(income_tax + f8959_tax_total)

    # -----------------------------------------------------------------------
    # Page 2 — Payments
    # -----------------------------------------------------------------------

    # 1040 line 25a — W-2 federal income tax withheld.
    fed_withheld_w2 = irs_round(sum(w.federal_tax_withheld for w in scenario.w2s))

    # 1040 line 25b — 1099 federal tax withheld (INT + DIV + G).
    fed_withheld_1099 = irs_round(
        sum(f.federal_tax_withheld for f in scenario.form1099_int)
        + sum(f.federal_tax_withheld for f in scenario.form1099_div)
        + sum(g.federal_tax_withheld for g in scenario.form1099_g)
    )

    # 1040 line 25c — Additional Medicare withheld (Form 8959 line 24).
    # Key: "f8959_line_24" from forms.f8959.compute.
    addl_medicare_withheld = f8959.get("f8959_line_24", 0)

    # 1040 line 26 — Total federal income tax withheld.
    federal_withheld = irs_round(
        fed_withheld_w2 + fed_withheld_1099 + addl_medicare_withheld
    )

    # 1040 line 33 — Total payments.
    total_payments = federal_withheld  # v1: withholding only; estimated tax not yet wired

    # 1040 line 35a — Amount overpaid = max(total_payments − total_tax, 0).
    overpaid = max(0, irs_round(total_payments - total_tax))

    # -----------------------------------------------------------------------
    # Schedule 1 per-line breakdown keys (pass-through from sch_1 results)
    # -----------------------------------------------------------------------

    sch_1_line_1_taxable_refunds = sch_1.get("sch_1_line_1_taxable_refunds", 0)
    sch_1_line_3_business_income = sch_1.get("sch_1_line_3_business_income", 0)
    sch_1_line_4_other_gains = sch_1.get("sch_1_line_4_other_gains", 0)
    sch_1_line_5_rental_re_royalty = sch_1.get("sch_1_line_5_rental_re_royalty", 0)
    sch_1_line_6_farm_income = sch_1.get("sch_1_line_6_farm_income", 0)
    sch_1_line_7_unemployment = sch_1.get("sch_1_line_7_unemployment", 0)
    sch_1_line_11_educator = sch_1.get("sch_1_line_11_educator", 0)
    sch_1_line_13_hsa = sch_1.get("sch_1_line_13_hsa", 0)
    sch_1_line_15_se_tax = sch_1.get("sch_1_line_15_se_tax", 0)
    sch_1_line_17_se_health = sch_1.get("sch_1_line_17_se_health", 0)
    sch_1_line_20_ira = sch_1.get("sch_1_line_20_ira", 0)
    sch_1_line_21_student_loan_interest = sch_1.get(
        "sch_1_line_21_student_loan_interest", 0
    )

    # Schedule E line 26 (Part I rental total) — oracle named range SchE1_Line26.
    # Key: "sch_e_line_26_total" from forms.sch_e.compute.
    # Renamed to "other_income" by f1040.py shim.
    sche_line26 = sch_e.get("sch_e_line_26_total", 0)

    # Schedule E line 41 (Part II K-1 pass-through total).
    # Key: "sche_line41" from forms.sch_e or sch_e_part_ii.
    sche_line41 = sch_e.get("sche_line41", 0)

    # Schedule A line 5e (SALT capped) — pass-through from sch_a.
    sch_a_line_5e_salt_capped = sch_a.get("sch_a_line_5e_salt_capped", 0)

    # Form 8995 line 15 oracle (same value as f8995_line_15 — for cross-check).
    f8995_line_15_oracle = qbi_deduction

    # Form 8582 line 11 oracle — allowed passive loss.
    # Key: "f8582_line_11_allowed_loss" from forms.f8582.compute.
    f8582_line_11_oracle = f8582.get("f8582_line_11_allowed_loss", 0)

    # Form 8959 required gate: True if any f8959 tax was computed.
    f8959_required = bool(f8959_tax_total)

    # -----------------------------------------------------------------------
    # Assemble output dict — OUTPUTS[2025] production keys exactly.
    # -----------------------------------------------------------------------

    return {
        # Page 1 income lines
        "wages": wages,
        "interest_income": taxable_interest,
        "dividend_income": ordinary_divs,
        "total_income": total_income,
        # AGI
        "agi": agi,
        "agi_page2": agi,
        "magi": magi,
        # Deductions
        "standard_deduction": standard_deduction_amount,
        "schedule_a_total": schedule_a_total,
        "sch_a_line_5e_salt_capped": sch_a_line_5e_salt_capped,
        "total_deductions": total_deductions,
        # Taxable income
        "taxable_income_before_qbi_deduction": taxable_income_before_qbi,
        "_qbi_deduction_1040": qbi_deduction,
        "taxable_income": taxable_income,
        # Tax
        "total_tax": total_tax,
        # Capital gain
        "net_capital_gain": net_capital_gain,
        "schd_line16": schd_line16,
        # Payments
        "federal_withheld": federal_withheld,
        "additional_medicare_withheld": addl_medicare_withheld,
        "total_payments": total_payments,
        "overpaid": overpaid,
        # Schedule 1 line 10 and 26 totals (short-name production keys)
        "sch_1_line_10": sch_1_line_10,
        "sch_1_line_26": sch_1_line_26,
        # Schedule E line 26 (Part I rental total) → renamed "other_income" by f1040.py
        "sche_line26": sche_line26,
        # Schedule 1 Part I per-line breakdown
        "sch_1_line_1_taxable_refunds": sch_1_line_1_taxable_refunds,
        "sch_1_line_3_business_income": sch_1_line_3_business_income,
        "sch_1_line_4_other_gains": sch_1_line_4_other_gains,
        "sch_1_line_5_rental_re_royalty": sch_1_line_5_rental_re_royalty,
        "sch_1_line_6_farm_income": sch_1_line_6_farm_income,
        "sch_1_line_7_unemployment": sch_1_line_7_unemployment,
        # Schedule 1 Part II per-line breakdown
        "sch_1_line_11_educator": sch_1_line_11_educator,
        "sch_1_line_13_hsa": sch_1_line_13_hsa,
        "sch_1_line_15_se_tax": sch_1_line_15_se_tax,
        "sch_1_line_17_se_health": sch_1_line_17_se_health,
        "sch_1_line_20_ira": sch_1_line_20_ira,
        "sch_1_line_21_student_loan_interest": sch_1_line_21_student_loan_interest,
        # Schedule E line 41
        "sche_line41": sche_line41,
        # Form 8959
        "f8959_tax_total": f8959_tax_total,
        "f8959_required": f8959_required,
        # Form 8995 oracle
        "f8995_line_15_oracle": f8995_line_15_oracle,
        # Form 8582 oracle
        "f8582_line_11_oracle": f8582_line_11_oracle,
    }
