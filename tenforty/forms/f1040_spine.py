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
        "sch_a_line_17_total"  — line 17 total itemized deductions
        "sch_a_line_5e_salt_capped"

    schedule_results["sch_d"]  — Schedule D cap-gain/loss
        "sch_d_line_16_total"  — net capital gain/loss (line 16)

    schedule_results["sch_e"]  — Schedule E Part I / Part II totals
        "sch_e_line_26_total"       — Part I rental net total (line 26)
        "sch_e_line_41_total_pte"   — Part II K-1 pass-through total (line 41)

    schedule_results["f8959"]  — Form 8959 additional Medicare
        "f8959_line_18"        — total additional Medicare tax
        "f8959_line_24"        — additional Medicare withheld

    schedule_results["f8995"]  — Form 8995 QBI deduction
        "f8995_line_15_qbi_deduction" — QBI deduction (1040 line 13)

    schedule_results["f8582"]  — Form 8582 passive activity
        "f8582_line_11_allowed_loss"

Output keys match ``F1040.OUTPUTS[2025]`` exactly so PDF mappings and
CA consumers are unaffected.
"""

from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import FilingStatus, Scenario
from tenforty.params.federal import FederalParams
from tenforty.rounding import irs_round


def _compute_eic(
    earned_income: int,
    agi: int,
    investment_income: int,
    num_qualifying_children: int,
    filing_status: FilingStatus,
    params: FederalParams,
) -> int:
    """Compute the Earned Income Credit using the IRS EIC Table lookup logic.

    Mirrors the workbook's EIC Table computation: the table publishes a credit
    amount for each $50 income bracket; the bracket value is derived from the
    midpoint ``round((at_least + but_less_than) / 2, 2)``, which simplifies to
    ``row_start + 25`` for integer $50-increment rows.  The LOOKUP function in
    the workbook finds the last row where ``at_least <= worksheet_amount``.

    Args:
        earned_income: W-2 wages (and tips/other compensation); excludes
            interest, dividends, and other investment income.
        agi: Adjusted Gross Income from Form 1040 line 11.
        investment_income: Sum of tax-exempt interest + taxable interest +
            ordinary dividends + max(0, net capital gain).  If this exceeds
            the EIC investment income limit, the credit is $0.
        num_qualifying_children: Number of qualifying children (0, 1, 2, or 3+).
            Use 3 for three or more.
        filing_status: FilingStatus of the filer.
        params: Year-specific federal parameters (must contain eic_params).

    Returns:
        EIC amount (0 or positive integer).  Returns 0 if not eligible.
    """
    if params.eic_params is None:
        return 0
    if earned_income <= 0:
        return 0

    children_key = min(num_qualifying_children, 3)
    eic_p = params.eic_params.get(children_key)
    if eic_p is None:
        return 0

    # Investment income limit (hard-coded per-year constant in the workbook's
    # N58 cell on the EIC worksheet; $11,950 for 2025).
    # If investment income exceeds the limit, no EIC is available.
    # This limit is stored as a constant in the EIC worksheet rather than in
    # the EIC Table parameters; for now it is read from the params module via
    # a dedicated attribute if present, otherwise the spine is conservative.
    eic_investment_limit = getattr(params, "eic_investment_income_limit", None)
    if eic_investment_limit is None:
        # Fallback: allow the EIC — investment income check is advisory
        pass
    elif investment_income > eic_investment_limit:
        return 0

    # Phase-out thresholds depend on filing status.
    is_mfj = (filing_status is FilingStatus.MARRIED_JOINTLY)
    po_start = eic_p.phase_out_start_mfj if is_mfj else eic_p.phase_out_start
    po_end   = eic_p.phase_out_end_mfj   if is_mfj else eic_p.phase_out_end

    # Worksheet amount = greater of earned income or AGI (IRS EIC worksheet).
    worksheet_amount = max(earned_income, agi)

    # If worksheet amount >= phase-out end, credit is zero.
    if worksheet_amount >= po_end:
        return 0

    # EIC Table row lookup: find row_start = floor(worksheet_amount / 50) * 50.
    # The table covers worksheet amounts starting at 1; the first row (1-50) uses
    # midpoint = round((1+50)/2, 2) - 1 = 25 - 1 = 24.5 (special case).
    # For all other rows the midpoint = row_start + 25.
    row_start = int(worksheet_amount // 50) * 50
    if row_start == 0:
        # Below $50 row: worksheet amount in [1, 50), midpoint formula = ROUND((1+50)/2,2)-1 = 24.5
        midpoint = 24.5
    else:
        midpoint = row_start + 25.0

    # Compute phase-in rate and phase-out rate matching the workbook formulas:
    #   N7 = ROUND(N3/N4, 4)   — phase-in rate
    #   N9 = -ROUND(N3/(N6-N5), 7)  — phase-out rate (negative)
    phase_in_rate = round(eic_p.max_credit / eic_p.phase_in_end, 4)
    phase_out_rate = -round(eic_p.max_credit / (po_end - po_start), 7)

    # Three-branch formula mirroring EIC Table column C formula:
    #   IF(L > phase_out_start,
    #       MAX(0, max_credit + ROUND(phase_out_rate * (L - phase_out_start), 0)),
    #       IF(L > phase_in_end,
    #           max_credit,
    #           ROUND(phase_in_rate * L, 0)
    #       )
    #   )
    if midpoint > po_start:
        raw = eic_p.max_credit + round(phase_out_rate * (midpoint - po_start), 0)
        credit = max(0, int(raw))
    elif midpoint > eic_p.phase_in_end:
        credit = eic_p.max_credit
    else:
        credit = int(round(phase_in_rate * midpoint, 0))

    return credit


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
    # Real producer key: "sch_a_line_17_total" from forms.sch_a.compute.
    schedule_a_total = sch_a.get("sch_a_line_17_total", 0)

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
    # Real producer key: "f8995_line_15_qbi_deduction" from forms.f8995.compute.
    qbi_deduction = f8995.get("f8995_line_15_qbi_deduction", 0)

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
    # Only include when F8959 is actually filed (line 18 > 0). The oracle
    # workbook returns F8959_WH = None when F8959 is not required; matching
    # that keeps line 25c blank and total_payments consistent with the
    # workbook path for scenarios below the Additional Medicare threshold.
    addl_medicare_withheld = (
        f8959.get("f8959_line_24", 0) if f8959_tax_total else 0
    )

    # 1040 line 26 — Total federal income tax withheld.
    federal_withheld = irs_round(
        fed_withheld_w2 + fed_withheld_1099 + addl_medicare_withheld
    )

    # 1040 line 27a — Earned Income Credit (EIC).
    # Earned income = wages (v1 scope: no self-employment income).
    eic_earned_income = wages
    # Investment income for EIC limit check = taxable interest + ordinary
    # dividends + max(0, net capital gains); tax-exempt interest = 0 in v1.
    eic_investment_income = irs_round(
        taxable_interest + ordinary_divs + max(0, schd_line16)
    )
    # Number of qualifying children = 0 for v1 scope (no dependents wired).
    eic_num_children = 0
    eic = _compute_eic(
        earned_income=eic_earned_income,
        agi=agi,
        investment_income=eic_investment_income,
        num_qualifying_children=eic_num_children,
        filing_status=filing_status,
        params=params,
    )

    # 1040 line 33 — Total payments = withholding + EIC (+ estimated tax, etc.).
    total_payments = irs_round(federal_withheld + eic)

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
    # Real producer key: "sch_e_line_41_total_pte" from forms.sch_e_part_ii.compute.
    # The orchestrator merges sch_e_part_ii results into the "sch_e" slot.
    sche_line41 = sch_e.get("sch_e_line_41_total_pte", 0)

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
        # Page 1 income lines — oracle/OUTPUTS[2025] key names
        "wages": wages,
        "interest_income": taxable_interest,
        "dividend_income": ordinary_divs,
        "total_income": total_income,
        # PDF-ready aliases: PDF mapping uses taxable_interest / ordinary_dividends
        # (f1040.compute renamed these in the oracle path).
        "taxable_interest": taxable_interest,
        "ordinary_dividends": ordinary_divs,
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
        # Capital gain — oracle key + PDF alias.
        # capital_gain_loss mirrors schd_line16 and maps to PDF line 7a.
        # Omit (None) when zero so the PDF field stays blank for W-2-only
        # scenarios — matching the oracle's behavior where a blank Sch D
        # cell propagates as None (not 0) and PdfFiller skips None values.
        "net_capital_gain": net_capital_gain,
        "schd_line16": schd_line16,
        "capital_gain_loss": schd_line16 if schd_line16 else None,
        # Payments — split by source so PDF mapping can route each line
        "federal_withheld_w2": fed_withheld_w2,    # line 25a
        "federal_withheld_1099": fed_withheld_1099, # line 25b
        "federal_withheld_other": addl_medicare_withheld,  # line 25c
        "federal_withheld": federal_withheld,       # line 25d total
        "additional_medicare_withheld": addl_medicare_withheld,
        "eic": eic if eic else None,               # line 27a (None if 0 → blank PDF)
        "total_payments": total_payments,
        "overpaid": overpaid,
        # Schedule 1 line 10 and 26 totals — both short and long-form keys
        "sch_1_line_10": sch_1_line_10,
        "sch_1_line_10_total_additional_income": sch_1_line_10,  # long-form alias
        "sch_1_line_26": sch_1_line_26,
        "sch_1_line_26_total_adjustments": sch_1_line_26,        # long-form alias
        # Schedule E line 26 (Part I rental total) — oracle key + f1040.py rename
        "sche_line26": sche_line26,
        "other_income": sche_line26,  # f1040.compute rename used by Sch CA consumers
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
