"""Independent reference (oracle) for federal Form 1120-S, tax years 2021-2025.

AIR-GAPPED, hand-derived reference implementation used to cross-check a
separate production implementation. Every rule below was transcribed from the
official IRS form faces and instructions for each year; it does NOT import from
or consult any production code in this repository. Divergence between
production and this oracle is the signal we want -- do not smooth it over.

Covered: the page 1 ordinary-business-income chain, the tax-and-payments
block, Schedule K totals (incl. the line 18 income/loss reconciliation),
per-shareholder Schedule K-1 pro-rata allocation (fractional ownership), and
the section 199A / QBI statement quantities (Schedule K-1 box 17 code V,
Statement A).

Primary sources (all fetched from irs.gov's prior-year portal, 2026-10-03):
  Form 1120-S:                 https://www.irs.gov/pub/irs-prior/f1120s--<YEAR>.pdf
  Instructions for Form 1120-S https://www.irs.gov/pub/irs-prior/i1120s--<YEAR>.pdf
  Schedule K-1 (Form 1120-S):  https://www.irs.gov/pub/irs-prior/f1120ssk--<YEAR>.pdf
  Shareholder's Instructions for Schedule K-1 (Form 1120-S):
                               https://www.irs.gov/pub/irs-prior/i1120ssk--<YEAR>.pdf
for <YEAR> in 2021, 2022, 2023, 2024, 2025.

### Input contract

Inputs are duck-typed against the S-corp input schema (``SCorpReturn`` and its
``SCorpIncome`` / ``SCorpDeductions`` / ``SCorpScopeOuts`` / ``SCorpPayments``
/ ``SCorp199AInfo`` / ``SCorpShareholder`` / ``SCorpScheduleBAnswers``
members). The oracle reads attributes only, so it has no import from
``tenforty`` at all; a real ``SCorpReturn`` or any object with the same
attribute names works.

### Output contract

``reference_f1120s(year, scorp)`` returns a flat ``dict`` keyed by the
``f1120s_*`` output-key surface. Amounts are ``float`` and UNROUNDED (charter
rules 2 and 3): the IRS permits whole-dollar rounding, but rounding is the
production side's job and comparison tests round.

### Line-number drift

The 2023 revision inserted a new page 1 line 19 (energy efficient commercial
buildings deduction, Form 7205), shifting every later page 1 line down by one,
and added line 24d (elective payment election amount). ``PAGE1_LINES`` records
the per-year numbering so each citation can be diffed against the form face.

### FLAGS (ambiguities resolved by interpretation, for team-lead adjudication)

See the ``FLAG-n`` comments inline; the full list is repeated in
``tests/oracles/README.md``.
"""

from __future__ import annotations

from typing import Any, Mapping

SUPPORTED_YEARS = (2021, 2022, 2023, 2024, 2025)


# ---------------------------------------------------------------------------
# Per-year page 1 line numbering (transcribed from each year's form face).
# ---------------------------------------------------------------------------
# SOURCE: Form 1120-S (2021) and (2022), page 1:
#   "1a Gross receipts or sales" / "b Returns and allowances" /
#   "c Balance. Subtract line 1b from line 1a" /
#   "2 Cost of goods sold (attach Form 1125-A)" /
#   "3 Gross profit. Subtract line 2 from line 1c" /
#   "4 Net gain (loss) from Form 4797, line 17 (attach Form 4797)" /
#   "5 Other income (loss) (see instructions--attach statement)" /
#   "6 Total income (loss). Add lines 3 through 5" /
#   "7 Compensation of officers" ... "19 Other deductions (attach statement)" /
#   "20 Total deductions. Add lines 7 through 19" /
#   "21 Ordinary business income (loss). Subtract line 20 from line 6" /
#   "22a Excess net passive income or LIFO recapture tax" /
#   "b Tax from Schedule D (Form 1120-S)" /
#   "c Add lines 22a and 22b (see instructions for additional taxes)" /
#   "23a <year> estimated tax payments and <year-1> overpayment credited to
#    <year>" / "b Tax deposited with Form 7004" /
#   "c Credit for federal tax paid on fuels (attach Form 4136)" /
#   "d Add lines 23a through 23c" /
#   "24 Estimated tax penalty (see instructions)" /
#   "25 Amount owed. If line 23d is smaller than the total of lines 22c and
#    24, enter amount owed" /
#   "26 Overpayment. If line 23d is larger than the total of lines 22c and 24,
#    enter amount overpaid" /
#   "27 Enter amount from line 26: Credited to <year+1> estimated tax /
#    Refunded"
_LINES_2021_2022 = {
    "gross_receipts": "1a",
    "returns_and_allowances": "1b",
    "net_receipts": "1c",
    "cost_of_goods_sold": "2",
    "gross_profit": "3",
    "net_gain_loss_4797": "4",
    "other_income": "5",
    "total_income": "6",
    "compensation_of_officers": "7",
    "salaries_wages": "8",
    "repairs_maintenance": "9",
    "bad_debts": "10",
    "rents": "11",
    "taxes_licenses": "12",
    "interest": "13",
    "depreciation": "14",
    "depletion": "15",
    "advertising": "16",
    "pension_profit_sharing": "17",
    "employee_benefits": "18",
    "other_deductions": "19",
    "total_deductions": "20",
    "ordinary_business_income": "21",
    "net_passive_income_tax": "22a",
    "built_in_gains_tax": "22b",
    "total_tax": "22c",
    "estimated_tax_and_prior_year_overpayment": "23a",
    "tax_deposited_with_7004": "23b",
    "credit_for_federal_excise_tax": "23c",
    "total_payments": "23d",
    "estimated_tax_penalty": "24",
    "amount_owed": "25",
    "overpayment": "26",
    "credited_to_next_year": "27",
}

# SOURCE: Form 1120-S (2023), (2024), (2025), page 1:
#   lines 1a-18 as above (2023+ prints 1a/1b/1c on one row: "1a Gross receipts
#   or sales / b Less returns and allowances / c Balance"), then
#   "19 Energy efficient commercial buildings deduction (attach Form 7205)" /
#   "20 Other deductions (attach statement)" /
#   "21 Total deductions. Add lines 7 through 20" /
#   "22 Ordinary business income (loss). Subtract line 21 from line 6" /
#   "23a Excess net passive income or LIFO recapture tax" /
#   "b Tax from Schedule D (Form 1120-S)" /
#   "c Add lines 23a and 23b (see instructions for additional taxes)" /
#   "24a Current year's estimated tax payments and preceding year's
#    overpayment credited to the current year" /
#   "b Tax deposited with Form 7004" /
#   "c Credit for federal tax paid on fuels (attach Form 4136)" /
#   "d Elective payment election amount from Form 3800" /
#   "z Add lines 24a through 24d" /
#   "25 Estimated tax penalty" /
#   "26 Amount owed. If line 24z is smaller than the total of lines 23c and
#    25, enter amount owed" /
#   "27 Overpayment. If line 24z is larger than the total of lines 23c and 25,
#    enter amount overpaid" /
#   "28 Enter amount from line 27: Credited to <year+1> estimated tax /
#    Refunded" (2025 splits this into 28a credited / 28b refunded).
_LINES_2023_2025 = {
    **{k: v for k, v in _LINES_2021_2022.items() if k in (
        "gross_receipts", "returns_and_allowances", "net_receipts",
        "cost_of_goods_sold", "gross_profit", "net_gain_loss_4797",
        "other_income", "total_income", "compensation_of_officers",
        "salaries_wages", "repairs_maintenance", "bad_debts", "rents",
        "taxes_licenses", "interest", "depreciation", "depletion",
        "advertising", "pension_profit_sharing", "employee_benefits",
    )},
    "energy_efficient_commercial_buildings_deduction": "19",
    "other_deductions": "20",
    "total_deductions": "21",
    "ordinary_business_income": "22",
    "net_passive_income_tax": "23a",
    "built_in_gains_tax": "23b",
    "total_tax": "23c",
    "estimated_tax_and_prior_year_overpayment": "24a",
    "tax_deposited_with_7004": "24b",
    "credit_for_federal_excise_tax": "24c",
    "refundable_credits": "24d",
    "total_payments": "24z",
    "estimated_tax_penalty": "25",
    "amount_owed": "26",
    "overpayment": "27",
    "credited_to_next_year": "28",
}

PAGE1_LINES: dict[int, dict[str, str]] = {
    2021: _LINES_2021_2022,
    2022: _LINES_2021_2022,
    2023: _LINES_2023_2025,
    2024: _LINES_2023_2025,
    2025: {**_LINES_2023_2025, "credited_to_next_year": "28a"},
}


def _check_year(year: int) -> None:
    if year not in SUPPORTED_YEARS:
        raise ValueError(
            f"year {year} is outside the supported range {SUPPORTED_YEARS}"
        )


# ---------------------------------------------------------------------------
# Page 1 -- Income (lines 1a-6)
# ---------------------------------------------------------------------------
def page1_income(year: int, income: Any) -> dict[str, float]:
    """Lines 1a through 6. Identical arithmetic in all five years.

    SOURCE: Form 1120-S (2021-2025), page 1, lines 1c, 3, 6 (quoted at
    ``_LINES_2021_2022`` above): 1c = 1a - 1b; 3 = 1c - 2; 6 = 3 + 4 + 5.
    SOURCE: line 2 -- "Cost of goods sold (attach Form 1125-A)"; the input
    schema defines ``cogs_aggregate`` as the Form 1125-A line 8 total.
    """
    _check_year(year)
    gross_receipts = float(income.gross_receipts)
    returns_and_allowances = float(income.returns_and_allowances)
    cogs = float(income.cogs_aggregate)
    gain_4797 = float(income.net_gain_loss_4797)
    other_income = float(income.other_income)

    net_receipts = gross_receipts - returns_and_allowances      # line 1c
    gross_profit = net_receipts - cogs                          # line 3
    total_income = gross_profit + gain_4797 + other_income      # line 6
    return {
        "f1120s_gross_receipts": gross_receipts,
        "f1120s_returns_and_allowances": returns_and_allowances,
        "f1120s_net_receipts": net_receipts,
        "f1120s_cost_of_goods_sold": cogs,
        "f1120s_gross_profit": gross_profit,
        "f1120s_net_gain_loss_4797": gain_4797,
        "f1120s_other_income": other_income,
        "f1120s_total_income": total_income,
    }


# ---------------------------------------------------------------------------
# Page 1 -- Deductions (lines 7-20 / 7-21)
# ---------------------------------------------------------------------------
# (output key suffix, input attribute) in form order, lines 7-18 then the
# "Other deductions" line (19 in 2021-2022, 20 in 2023-2025).
_DEDUCTION_FIELDS = (
    ("compensation_of_officers", "compensation_of_officers"),   # line 7
    ("salaries_wages", "salaries_wages"),                       # line 8
    ("repairs_maintenance", "repairs_maintenance"),             # line 9
    ("bad_debts", "bad_debts"),                                 # line 10
    ("rents", "rents"),                                         # line 11
    ("taxes_licenses", "taxes_licenses"),                       # line 12
    ("interest", "interest"),                                   # line 13
    ("depreciation", "depreciation"),                           # line 14
    ("depletion", "depletion"),                                 # line 15
    ("advertising", "advertising"),                             # line 16
    ("pension_profit_sharing", "pension_profit_sharing_plans"), # line 17
    ("employee_benefits", "employee_benefits"),                 # line 18
    ("other_deductions", "other_deductions"),                   # line 19 / 20
)


def page1_deductions(year: int, deductions: Any) -> dict[str, float]:
    """Deduction lines and their total.

    SOURCE: Form 1120-S (2021, 2022), line 20: "Total deductions. Add lines 7
    through 19".
    SOURCE: Form 1120-S (2023, 2024, 2025), line 21: "Total deductions. Add
    lines 7 through 20".

    The 2023+ line 19 ("Energy efficient commercial buildings deduction
    (attach Form 7205)") has no field in the input schema and no output key;
    the oracle treats it as zero, so the 2023+ total is still the sum of the
    thirteen schema fields. (A caller with a section 179D deduction has no
    place to put it other than ``other_deductions``, which leaves the total
    unchanged.)
    """
    _check_year(year)
    out: dict[str, float] = {}
    total = 0.0
    for key, attr in _DEDUCTION_FIELDS:
        amount = float(getattr(deductions, attr))
        out[f"f1120s_{key}"] = amount
        total += amount
    out["f1120s_total_deductions"] = total
    return out


def ordinary_business_income(total_income: float, total_deductions: float) -> float:
    """SOURCE: Form 1120-S (2021, 2022), line 21: "Ordinary business income
    (loss). Subtract line 20 from line 6"; (2023-2025), line 22: "Ordinary
    business income (loss). Subtract line 21 from line 6". May be negative."""
    return total_income - total_deductions


# ---------------------------------------------------------------------------
# Page 1 -- Tax and Payments
# ---------------------------------------------------------------------------
def tax_and_payments(
    year: int,
    scope_outs: Any,
    payments: Any,
    *,
    estimated_tax_penalty: float = 0.0,
    credited_to_next_year: float = 0.0,
) -> dict[str, float]:
    """Lines 22a-27 (2021-2022) / 23a-28 (2023-2025).

    TAX.
    SOURCE: Instructions for Form 1120-S (2021), "Line 22a. Excess Net Passive
    Income and LIFO Recapture Tax"; "Line 22b. Tax From Schedule D (Form
    1120-S) -- Enter the built-in gains tax from line 23 of Part III of
    Schedule D."; form face line 22c "Add lines 22a and 22b (see instructions
    for additional taxes)". (2023-2025: same text at lines 23a/23b/23c.)

    FLAG-1 (section 453 interest): the input schema says
    ``interest_on_453_deferred`` is passed "through to Form 1120-S line 22".
    The IRS instructions do not support adding it to the entity's tax line.
    The only "additional taxes" the instructions list for line 22c/23c are
    Form 4255 recapture and look-back interest from Forms 8697 and 8866. For
    section 453/453A the instructions put the liability on the SHAREHOLDER:
      Instructions for Form 1120-S (2021-2025), Schedule K-1 box 17,
      "Section 453(l)(3) information (code M) ... each shareholder's tax
      liability must be increased by the shareholder's pro rata share of the
      interest on tax attributable to the installment payments received during
      the tax year." and "Section 453A(c) information (code N). Supply any
      information ... a shareholder [needs] to figure the interest due under
      section 453A(c)."
    INTERPRETATION USED: ``f1120s_interest_on_453_deferred`` is reported as a
    passthrough of the input but is EXCLUDED from ``f1120s_total_tax``.

    PAYMENTS.
    SOURCE: form face lines 23a-23d (2021-2022) and 24a-24z (2023-2025),
    quoted at the line maps above. Line 23a / 24a is a single form line
    combining estimated tax payments and the prior-year overpayment credited;
    the output surface reports the two components separately.

    FLAG-2 (refundable credits): ``SCorpPayments.refundable_credits`` has no
    labelled form line. INTERPRETATION USED: for 2023-2025 it is line 24d,
    the only refundable-credit payment line on the form (Instructions for Form
    1120-S (2024, 2025), "Line 24d. Elective Payment Election Amount From Form
    3800 -- Enter the total gross EPE amount from Form 3800, Part III, line 6,
    column (h)."). The 2021 and 2022 forms have NO such line (line 23d is "Add
    lines 23a through 23c"), so a nonzero amount in those years raises
    ``NotImplementedError`` rather than being silently added or dropped.

    FLAG-3 (estimated tax penalty; credited to next year): both appear on the
    output-key surface but neither has an input field. INTERPRETATION USED:
    both are keyword arguments defaulting to 0.0.
    SOURCE: Instructions for Form 1120-S (2021) "Line 24. Estimated Tax
    Penalty -- If Form 2220 is attached, check the box on line 24 and enter
    the amount of any penalty on this line." (2023-2025: line 25.)
    SOURCE: Instructions for Form 1120-S (2025) "Line 28a. Credited To
    Estimated Tax -- Enter the amount of any overpayment from line 27 that
    should be applied to next year's estimated tax."

    BALANCE.
    SOURCE: form face -- "Amount owed. If line 23d [24z] is smaller than the
    total of lines 22c and 24 [23c and 25], enter amount owed" /
    "Overpayment. If line 23d [24z] is larger than the total of lines 22c and
    24 [23c and 25], enter amount overpaid". When the two are equal both
    lines are zero.
    """
    _check_year(year)
    net_passive_income_tax = float(scope_outs.net_passive_income_tax)
    built_in_gains_tax = float(scope_outs.built_in_gains_tax)
    interest_453 = float(scope_outs.interest_on_453_deferred)

    # Line 22c / 23c. FLAG-1: section 453 interest deliberately excluded.
    total_tax = net_passive_income_tax + built_in_gains_tax

    estimated = float(payments.estimated_tax_payments)
    prior_year_credit = float(payments.prior_year_overpayment_credited)
    with_7004 = float(payments.tax_deposited_with_7004)
    excise_credit = float(payments.credit_for_federal_excise_tax)
    refundable = float(payments.refundable_credits)

    # Line 23a + 23b + 23c (2021-2022); 24a + 24b + 24c + 24d (2023-2025).
    total_payments = estimated + prior_year_credit + with_7004 + excise_credit
    if year >= 2023:
        total_payments += refundable          # line 24d (FLAG-2)
    elif refundable != 0.0:
        raise NotImplementedError(
            f"Form 1120-S ({year}) has no payment line for refundable credits "
            f"(line 23d is 'Add lines 23a through 23c'); got {refundable}. "
            f"See FLAG-2."
        )

    penalty = float(estimated_tax_penalty)
    liability = total_tax + penalty
    if total_payments < liability:
        amount_owed, overpayment = liability - total_payments, 0.0
    elif total_payments > liability:
        amount_owed, overpayment = 0.0, total_payments - liability
    else:
        amount_owed, overpayment = 0.0, 0.0

    credited = float(credited_to_next_year)
    if credited < 0.0 or credited > overpayment:
        raise ValueError(
            f"credited_to_next_year ({credited}) must be between 0 and the "
            f"overpayment ({overpayment})"
        )

    return {
        "f1120s_net_passive_income_tax": net_passive_income_tax,
        "f1120s_built_in_gains_tax": built_in_gains_tax,
        "f1120s_interest_on_453_deferred": interest_453,
        "f1120s_total_tax": total_tax,
        "f1120s_estimated_tax_payments": estimated,
        "f1120s_prior_year_overpayment_credited": prior_year_credit,
        "f1120s_tax_deposited_with_7004": with_7004,
        "f1120s_credit_for_federal_excise_tax": excise_credit,
        "f1120s_refundable_credits": refundable,
        "f1120s_total_payments": total_payments,
        "f1120s_estimated_tax_penalty": penalty,
        "f1120s_amount_owed": amount_owed,
        "f1120s_overpayment": overpayment,
        "f1120s_credited_to_next_year": credited,
    }


# ---------------------------------------------------------------------------
# Schedule B passthroughs
# ---------------------------------------------------------------------------
def schedule_b(answers: Any) -> dict[str, Any]:
    """Identity passthroughs of the Schedule B answers.

    SOURCE: Form 1120-S (2021-2025), Schedule B, item 1: "Check accounting
    method: a Cash  b Accrual  c Other (specify)"; item 2: "See the
    instructions and enter the: a Business activity  b Product or service".

    FLAG-4 (accounting-method enum): the ``AccountingMethod`` definition is
    not in the schema excerpt. INTERPRETATION USED: the member's ``value`` (or
    the object itself if it has none) and its ``name`` are lower-cased; a
    match on "cash" or "accrual" checks that box, anything else checks
    "other". Exactly one of the three is True.
    """
    method = answers.accounting_method
    labels = {
        str(getattr(method, "value", method)).strip().lower(),
        str(getattr(method, "name", "")).strip().lower(),
    }
    is_cash = "cash" in labels
    is_accrual = (not is_cash) and "accrual" in labels
    return {
        "f1120s_sch_b_accounting_method_cash": is_cash,
        "f1120s_sch_b_accounting_method_accrual": is_accrual,
        "f1120s_sch_b_accounting_method_other": not (is_cash or is_accrual),
        "f1120s_sch_b_business_activity_code": answers.business_activity_code,
        "f1120s_sch_b_business_activity_description":
            answers.business_activity_description,
        "f1120s_sch_b_product_or_service": answers.product_or_service,
        "f1120s_sch_b_any_c_corp_subsidiaries": answers.any_c_corp_subsidiaries,
        "f1120s_sch_b_has_any_foreign_shareholders":
            answers.has_any_foreign_shareholders,
        "f1120s_sch_b_owns_foreign_entity": answers.owns_foreign_entity,
    }


# ---------------------------------------------------------------------------
# Schedule K
# ---------------------------------------------------------------------------
# Schedule K items on the output-key surface, in form order, with the form
# line each one mirrors.
# SOURCE: Form 1120-S (2021-2025), Schedule K, "Shareholders' Pro Rata Share
# Items": 1 Ordinary business income (loss); 2 Net rental real estate income
# (loss); 3c Other net rental income (loss); 4 Interest income; 5a Ordinary
# dividends; 6 Royalties; 7 Net short-term capital gain (loss); 8a Net
# long-term capital gain (loss); 9 Net section 1231 gain (loss); 10 Other
# income (loss); 11 Section 179 deduction; 12a Charitable contributions
# (2021-2023; split into 12a cash / 12b noncash from 2024); 13a/13b
# Low-income housing credit; 15a-15f AMT items; 16a Tax-exempt interest
# income; 17a Investment income.
#
# FLAG-5 (aggregate Schedule K keys): three output keys name a GROUP of form
# lines rather than one line, and none has an input field, so the grouping
# never affects a computed value here (all are zero from ``SCorpReturn``):
#   * ``sch_k_charitable_contributions`` -- line 12a (2021-2023); 12a + 12b
#     (2024-2025). Enters line 18.
#   * ``sch_k_foreign_transactions`` -- from 2021 on, Schedule K line 14 is a
#     checkbox ("Attach Schedule K-2 ... check this box"), not an amount.
#     INTERPRETATION USED: treated as an information-only amount that does
#     NOT enter line 18. Line 18's "16f Foreign taxes paid or accrued" has no
#     output key; it is a separate ``foreign_taxes_paid_or_accrued`` argument.
#   * ``sch_k_low_income_housing_credit`` (13a + 13b) and ``sch_k_amt_items``
#     (15a-15f): credits and AMT items never enter line 18.
SCH_K_ITEMS = (
    "ordinary_business_income",       # line 1
    "net_rental_real_estate",         # line 2
    "other_net_rental_income",        # line 3c
    "interest_income",                # line 4
    "ordinary_dividends",             # line 5a
    "royalties",                      # line 6
    "net_short_term_capital_gain",    # line 7
    "net_long_term_capital_gain",     # line 8a
    "net_section_1231_gain",          # line 9
    "other_income",                   # line 10
    "section_179_deduction",          # line 11
    "charitable_contributions",       # line 12a (12a + 12b from 2024)
    "low_income_housing_credit",      # lines 13a + 13b
    "foreign_transactions",           # line 14 (see FLAG-5)
    "amt_items",                      # lines 15a-15f
    "tax_exempt_interest",            # line 16a
    "investment_income",              # line 17a
)

# Lines combined in line 18 ("lines 1 through 10" far-right column: 1, 2, 3c,
# 4, 5a, 6, 7, 8a, 9, 10 -- 5b, 8b and 8c are inner-column subsets).
_LINE_18_INCOME_ITEMS = SCH_K_ITEMS[:10]
# Lines subtracted in line 18 that have an output key ("lines 11 through 12d"
# [12e from 2024] "and 16f"). Investment interest expense, section 59(e)(2)
# expenditures and other deductions (12b-12d / 12c-12e) have no output key and
# no input; they enter via ``other_line_12_deductions``.
_LINE_18_DEDUCTION_ITEMS = ("section_179_deduction", "charitable_contributions")


def schedule_k(
    year: int,
    ordinary_business_income_amount: float,
    separately_stated: Mapping[str, float] | None = None,
    *,
    other_line_12_deductions: float = 0.0,
    foreign_taxes_paid_or_accrued: float = 0.0,
) -> dict[str, float]:
    """Schedule K totals and the line 18 income/loss reconciliation.

    Line 1.
    SOURCE: Form 1120-S (2021, 2022), Schedule K line 1: "Ordinary business
    income (loss) (page 1, line 21)"; (2023-2025): "(page 1, line 22)".

    Line 18.
    SOURCE: Form 1120-S (2021, 2022), Schedule K line 18: "Income (loss)
    reconciliation. Combine the amounts on lines 1 through 10 in the far right
    column. From the result, subtract the sum of the amounts on lines 11
    through 12d and 16f".
    SOURCE: Form 1120-S (2023): "Combine the total amounts on lines 1 through
    10. From the result, subtract the sum of the amounts on lines 11 through
    12d and 16f".
    SOURCE: Form 1120-S (2024, 2025): "... subtract the sum of the amounts on
    lines 11 through 12e and 16f" (12a split into cash/noncash).
    SOURCE: Instructions for Form 1120-S (2021), "Line 18. Income/Loss
    Reconciliation (Schedule K Only) -- To the extent the corporation has an
    amount on line 16f of Schedule K (foreign taxes paid and accrued),
    subtract that amount for purposes of figuring the corporation's net
    income (loss)."

    ``separately_stated`` maps ``SCH_K_ITEMS`` names (other than
    ``ordinary_business_income``) to Schedule K totals. The ``SCorpReturn``
    input schema carries NO separately stated items, so the top-level entry
    point passes none and every such key is 0.0; the mapping exists so the
    line 18 arithmetic is real and testable rather than a degenerate copy of
    line 1.
    """
    _check_year(year)
    stated = dict(separately_stated or {})
    unknown = set(stated) - set(SCH_K_ITEMS[1:])
    if unknown:
        raise ValueError(f"unknown Schedule K item(s): {sorted(unknown)}")

    amounts = {name: float(stated.get(name, 0.0)) for name in SCH_K_ITEMS}
    amounts["ordinary_business_income"] = float(ordinary_business_income_amount)

    income = 0.0
    for name in _LINE_18_INCOME_ITEMS:
        income += amounts[name]
    deductions = 0.0
    for name in _LINE_18_DEDUCTION_ITEMS:
        deductions += amounts[name]
    deductions += float(other_line_12_deductions)
    deductions += float(foreign_taxes_paid_or_accrued)

    out = {f"f1120s_sch_k_{name}": amounts[name] for name in SCH_K_ITEMS}
    out["f1120s_sch_k_income_loss_reconciliation"] = income - deductions
    return out


# ---------------------------------------------------------------------------
# Section 199A (Schedule K-1 box 17 code V, Statement A) -- entity totals
# ---------------------------------------------------------------------------
def section_199a_totals(
    ordinary_business_income_amount: float, section_199a: Any | None
) -> dict[str, float] | None:
    """Entity-level Statement A quantities, or None when no statement is made.

    SOURCE: Instructions for Form 1120-S (2021-2025), Schedule K-1 box 17,
    "Section 199A information (code V) ... S corporations are required to
    report information necessary for their shareholders to figure the
    deduction ... separately identifying the shareholder's pro rata share of:
    Qualified items of income, gain, deduction, and loss; W-2 wages;
    Unadjusted basis immediately after acquisition (UBIA) of qualified
    property; ..."
    SOURCE: same, "Specific Instructions for Statement A" -- "the amount
    reported on the 'Ordinary business income (loss)' line of this statement
    should reflect the attributable portion of qualified items of income,
    gain, deduction, and loss for each trade or business included in the
    'Ordinary business income (loss)' reported in box 1 of the shareholder's
    Schedule K-1."

    Default QBI = Schedule K line 1 is the input schema's stated default
    (``qbi_override=None``); it equals the Statement A figure only when every
    item inside ordinary business income is a qualified item. The oracle does
    not re-run the instructions' QBI flowchart; a caller whose line 1 contains
    non-qualified items must supply ``qbi_override``.

    FLAG-6 (``section_199a is None``): the schema does not say whether a
    missing ``SCorp199AInfo`` means "no Statement A" or "Statement A with
    default QBI and zero wages/UBIA". INTERPRETATION USED: no statement --
    this function returns None and each K-1 allocation carries
    ``"section_199a": None``.
    """
    if section_199a is None:
        return None
    override = section_199a.qbi_override
    qbi = (
        float(ordinary_business_income_amount)
        if override is None
        else float(override)
    )
    return {
        "qbi": qbi,
        "w2_wages": float(section_199a.w2_wages),
        "ubia": float(section_199a.ubia),
    }


# ---------------------------------------------------------------------------
# Schedule K-1 pro-rata allocation
# ---------------------------------------------------------------------------
# Tolerance on "ownership percentages total 100", in percentage points. Wide
# enough for thirds entered to four decimals (33.3333 x 3 = 99.9999).
OWNERSHIP_TOTAL_TOLERANCE = 0.001


def pro_rata_share(total: float, ownership_percentage: float) -> float:
    """One shareholder's share of one Schedule K total. UNROUNDED.

    SOURCE: Instructions for Form 1120-S (2021-2025), Schedule K-1 Part II,
    item G: "If there was no change in shareholders or in the relative
    interest in stock the shareholders owned during the tax year, enter the
    percentage of total stock owned by each shareholder during the tax year
    ... For example, if shareholders X and Y each owned 50% for the entire tax
    year, enter 50% in item G for each shareholder. Each shareholder's pro
    rata share items (boxes 1 through 17 of Schedule K-1) are figured by
    multiplying the corresponding Schedule K amount by the percentage in item
    G."
    SOURCE: Schedule K-1 (Form 1120-S) (2021-2025), Part II, "G Current year
    allocation percentage ... %".

    ``ownership_percentage`` is on the 0-100 scale of the item G literal.

    NOTE: the input schema's docstring calls this "Schedule K-1 Part II box
    D"; on every 2021-2025 Schedule K-1 the allocation percentage is item G.
    Label mismatch only; no arithmetic consequence.

    OUT OF SCOPE: a change in ownership during the year. The instructions
    then weight each shareholder's percentage by days held (per-share,
    per-day), or allow a section 1377(a)(2) closing-of-the-books election.
    The schema carries one static percentage per shareholder, so the caller
    must already have weighted it.
    """
    return float(total) * float(ownership_percentage) / 100.0


def k1_allocations(
    schedule_k_amounts: Mapping[str, float],
    shareholders: Any,
    section_199a_entity: Mapping[str, float] | None,
) -> list[dict[str, Any]]:
    """One allocation record per shareholder, in input order.

    FLAG-7 (shape of ``f1120s_sch_k1_allocations``): the output-key list names
    the key but not its structure. INTERPRETATION USED: a list (shareholder
    input order) of dicts with
        "name", "ssn_or_ein", "ownership_percentage"   -- passthroughs
        one key per ``SCH_K_ITEMS`` name                -- pro-rata share
        "section_199a": None | {"qbi", "w2_wages", "ubia"}  -- pro-rata share
    The comparison author should adapt key names, not arithmetic.

    Every Schedule K item is allocated by the same item G percentage
    (SOURCE: ``pro_rata_share``). Line 18 is "(Schedule K Only)" per the
    instructions and is not allocated.

    SOURCE (section 199A shares): Instructions for Form 1120-S (2021-2025),
    "W-2 wages and UBIA of qualified property. The S corporation must
    determine the W-2 wages and UBIA of qualified property properly allocable
    to QBI for each qualified trade or business ... and report the pro rata
    share to each shareholder on Statement A".

    FLAG-8 (ownership total): the oracle raises ``ValueError`` when
    shareholders are present and their percentages do not total 100 (within
    ``OWNERSHIP_TOTAL_TOLERANCE``) or any percentage is outside (0, 100]:
    the item G instructions describe each percentage as a share "of total
    stock", so a set that does not total 100% leaves Schedule K partly
    unallocated or over-allocated. An empty shareholder list returns [].
    """
    holders = list(shareholders)
    if not holders:
        return []

    total_pct = 0.0
    for holder in holders:
        pct = float(holder.ownership_percentage)
        if not (0.0 < pct <= 100.0):
            raise ValueError(
                f"ownership_percentage {pct} for {holder.name!r} is outside "
                f"(0, 100]"
            )
        total_pct += pct
    if abs(total_pct - 100.0) > OWNERSHIP_TOTAL_TOLERANCE:
        raise ValueError(
            f"shareholder ownership percentages total {total_pct}, not 100"
        )

    records: list[dict[str, Any]] = []
    for holder in holders:
        pct = float(holder.ownership_percentage)
        record: dict[str, Any] = {
            "name": holder.name,
            "ssn_or_ein": holder.ssn_or_ein,
            "ownership_percentage": pct,
        }
        for name in SCH_K_ITEMS:
            record[name] = pro_rata_share(
                schedule_k_amounts[f"f1120s_sch_k_{name}"], pct
            )
        if section_199a_entity is None:
            record["section_199a"] = None
        else:
            record["section_199a"] = {
                key: pro_rata_share(value, pct)
                for key, value in section_199a_entity.items()
            }
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------
def reference_f1120s(
    year: int,
    scorp: Any,
    *,
    estimated_tax_penalty: float = 0.0,
    credited_to_next_year: float = 0.0,
) -> dict[str, Any]:
    """Full Form 1120-S reference result, keyed by the ``f1120s_*`` surface.

    ``scorp`` is an ``SCorpReturn``-shaped object. The entity-identity fields
    (name, EIN, address, dates, total assets), the CA inputs and the
    amended-return flag carry no federal arithmetic and are not read.
    """
    _check_year(year)
    out: dict[str, Any] = {}
    out.update(page1_income(year, scorp.income))
    out.update(page1_deductions(year, scorp.deductions))
    obi = ordinary_business_income(
        out["f1120s_total_income"], out["f1120s_total_deductions"]
    )
    out["f1120s_ordinary_business_income"] = obi
    out.update(
        tax_and_payments(
            year,
            scorp.scope_outs,
            scorp.payments,
            estimated_tax_penalty=estimated_tax_penalty,
            credited_to_next_year=credited_to_next_year,
        )
    )
    out.update(schedule_b(scorp.schedule_b_answers))
    sch_k = schedule_k(year, obi)
    out.update(sch_k)
    out["f1120s_sch_k1_allocations"] = k1_allocations(
        sch_k,
        scorp.shareholders,
        section_199a_totals(obi, getattr(scorp, "section_199a", None)),
    )
    return out


__all__ = [
    "SUPPORTED_YEARS",
    "PAGE1_LINES",
    "SCH_K_ITEMS",
    "OWNERSHIP_TOTAL_TOLERANCE",
    "page1_income",
    "page1_deductions",
    "ordinary_business_income",
    "tax_and_payments",
    "schedule_b",
    "schedule_k",
    "section_199a_totals",
    "pro_rata_share",
    "k1_allocations",
    "reference_f1120s",
]
