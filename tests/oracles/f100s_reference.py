"""CA FTB Form 100S reference oracle (TY2025).

Computes CA S Corporation Franchise or Income Tax Return: Schedule F
(trade/business income → OBI), main form state adjustments → net income →
entity-level tax, Schedule K entity-level totals, and Schedule K-1 per-
shareholder allocations.

### Output contract

``compute_f100s(inp: F100SInput) -> dict`` returns a flat dict.
See ``README.md`` for the full output contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FilingStatus = Literal["single", "mfj", "mfs", "hoh", "qss"]


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntityIdentity:
    """Form 100S header identity and structural flags."""
    name: str
    ein: str
    accounting_method: Literal["cash", "accrual", "other"]
    is_financial_s_corp: bool  # 3.5% rate per R&TC §23186
    is_first_year: bool        # exempt from $800 minimum per R&TC §23153(f)
    num_qsubs: int             # each QSub adds $800 per R&TC §23802(b)(5)


@dataclass(frozen=True)
class CreditEntry:
    """A single nonrefundable credit for lines 22-24."""
    code: str
    amount: float


@dataclass(frozen=True)
class AdditionalTaxes:
    """Lines 27-29: additional entity-level taxes (caller-supplied)."""
    tax_from_schedule_d: float            # line 27 — built-in gains
    excess_net_passive_income_tax: float  # line 28 — R&TC §23811
    pte_elective_tax: float               # line 29 — R&TC §19900


@dataclass(frozen=True)
class ScheduleFIncome:
    """Schedule F (Side 4) income lines 1a-6.

    Lines 1c, 3, 6 are computed; the rest are inputs.
    """
    gross_receipts_or_sales: float       # line 1a
    returns_and_allowances: float        # line 1b
    cost_of_goods_sold: float            # line 2 (from Schedule V line 8)
    net_gain_or_loss: float              # line 4 — attach schedule
    other_income: float                  # line 5 — attach schedule


@dataclass(frozen=True)
class ScheduleFDeductions:
    """Schedule F (Side 4) deduction lines 7-20.

    Line 21 is computed (sum). Line 14c = 14a − 14b. Line 19b (deductible)
    is used in total, not 19a (total travel).
    """
    compensation_of_officers: float      # line 7
    salaries_and_wages: float            # line 8
    repairs_and_maintenance: float       # line 9
    bad_debts: float                     # line 10
    rents: float                         # line 11
    taxes: float                         # line 12
    interest: float                      # line 13
    depreciation_total: float            # line 14a (Form 3885A)
    depreciation_elsewhere: float        # line 14b
    depletion: float                     # line 15
    advertising: float                   # line 16
    pension_profit_sharing: float        # line 17
    employee_benefit_programs: float     # line 18
    travel_total: float                  # line 19a
    travel_deductible: float             # line 19b
    other_deductions: float              # line 20


# ---------------------------------------------------------------------------
# Schedule F compute (lines 1-22)
# ---------------------------------------------------------------------------
def _compute_schedule_f_income(inc: ScheduleFIncome) -> dict[str, float]:
    """Schedule F lines 1a-6: Income."""
    # SOURCE: 2025 Form 100S Schedule F (Side 4), Income section.
    line_1c = inc.gross_receipts_or_sales - inc.returns_and_allowances
    line_3 = line_1c - inc.cost_of_goods_sold
    line_6 = line_3 + inc.net_gain_or_loss + inc.other_income
    return {
        "f100s_schf_line_1a_gross_receipts": inc.gross_receipts_or_sales,
        "f100s_schf_line_1b_returns_and_allowances": inc.returns_and_allowances,
        "f100s_schf_line_1c_net_receipts": line_1c,
        "f100s_schf_line_2_cogs": inc.cost_of_goods_sold,
        "f100s_schf_line_3_gross_profit": line_3,
        "f100s_schf_line_4_net_gain_or_loss": inc.net_gain_or_loss,
        "f100s_schf_line_5_other_income": inc.other_income,
        "f100s_schf_line_6_total_income": line_6,
    }


def _compute_schedule_f_deductions(ded: ScheduleFDeductions) -> dict[str, float]:
    """Schedule F lines 7-21: Deductions."""
    # SOURCE: 2025 Form 100S Schedule F (Side 4), Deductions section.
    line_14c = ded.depreciation_total - ded.depreciation_elsewhere
    line_21 = (
        ded.compensation_of_officers
        + ded.salaries_and_wages
        + ded.repairs_and_maintenance
        + ded.bad_debts
        + ded.rents
        + ded.taxes
        + ded.interest
        + line_14c
        + ded.depletion
        + ded.advertising
        + ded.pension_profit_sharing
        + ded.employee_benefit_programs
        + ded.travel_deductible
        + ded.other_deductions
    )
    return {
        "f100s_schf_line_7_compensation_of_officers": ded.compensation_of_officers,
        "f100s_schf_line_8_salaries_and_wages": ded.salaries_and_wages,
        "f100s_schf_line_9_repairs_and_maintenance": ded.repairs_and_maintenance,
        "f100s_schf_line_10_bad_debts": ded.bad_debts,
        "f100s_schf_line_11_rents": ded.rents,
        "f100s_schf_line_12_taxes": ded.taxes,
        "f100s_schf_line_13_interest": ded.interest,
        "f100s_schf_line_14a_depreciation_total": ded.depreciation_total,
        "f100s_schf_line_14b_depreciation_elsewhere": ded.depreciation_elsewhere,
        "f100s_schf_line_14c_depreciation": line_14c,
        "f100s_schf_line_15_depletion": ded.depletion,
        "f100s_schf_line_16_advertising": ded.advertising,
        "f100s_schf_line_17_pension_profit_sharing": ded.pension_profit_sharing,
        "f100s_schf_line_18_employee_benefit_programs": ded.employee_benefit_programs,
        "f100s_schf_line_19a_travel_total": ded.travel_total,
        "f100s_schf_line_19b_travel_deductible": ded.travel_deductible,
        "f100s_schf_line_20_other_deductions": ded.other_deductions,
        "f100s_schf_line_21_total_deductions": line_21,
    }


def _compute_schedule_f_obi(line_6: float, line_21: float) -> dict[str, float]:
    """Schedule F line 22: OBI = line 6 − line 21."""
    # SOURCE: 2025 Form 100S Schedule F (Side 4), line 22.
    return {"f100s_schf_line_22_obi": line_6 - line_21}


# ---------------------------------------------------------------------------
# Input dataclasses — Main Form State Adjustments
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StateAdjustmentAdditions:
    """Main form Side 1, lines 2-7 (additions to OBI)."""
    taxes_deducted: float                        # line 2
    interest_on_government_obligations: float    # line 3
    net_capital_gain: float                      # line 4
    depreciation_amortization_adjustment: float  # line 5
    portfolio_income: float                      # line 6
    other_additions: float                       # line 7


@dataclass(frozen=True)
class StateAdjustmentDeductions:
    """Main form Side 1, lines 9-12 (deductions from adjusted income)."""
    dividends_received_deduction: float    # line 9 (Schedule H)
    waters_edge_dividend_deduction: float  # line 10 (Schedule H)
    charitable_contributions: float        # line 11
    other_deductions: float                # line 12


@dataclass(frozen=True)
class NOLDeductions:
    """Main form Side 2, lines 16-19 (NOL and special deductions)."""
    section_23802e_deduction: float  # line 16 — R&TC §23802(e)
    nol_deduction: float             # line 17
    ez_tta_lambra_nol: float         # line 18
    disaster_loss_deduction: float   # line 19


# ---------------------------------------------------------------------------
# Main Form — State Adjustments (lines 1-20)
# ---------------------------------------------------------------------------
def _compute_state_adjustments(
    obi: float,
    additions: StateAdjustmentAdditions,
    deductions: StateAdjustmentDeductions,
    nol: NOLDeductions,
) -> dict:
    """Main form lines 1-20: state adjustments → net income for tax."""
    # SOURCE: 2025 Form 100S Side 1-2, State Adjustments + Net Income.
    a = additions
    d = deductions
    n = nol

    line_1 = obi
    line_2 = a.taxes_deducted
    line_3 = a.interest_on_government_obligations
    line_4 = a.net_capital_gain
    line_5 = a.depreciation_amortization_adjustment
    line_6 = a.portfolio_income
    line_7 = a.other_additions
    line_8 = line_1 + line_2 + line_3 + line_4 + line_5 + line_6 + line_7

    line_9 = d.dividends_received_deduction
    line_10 = d.waters_edge_dividend_deduction
    line_11 = d.charitable_contributions
    line_12 = d.other_deductions
    line_13 = line_9 + line_10 + line_11 + line_12

    line_14 = line_8 - line_13

    # SOURCE: line 15 = line 14 for CA-only S-corps (no Schedule R).
    # Apportionment via Schedule R is a scope-out.
    line_15 = line_14

    line_16 = n.section_23802e_deduction
    line_17 = n.nol_deduction
    line_18 = n.ez_tta_lambra_nol
    line_19 = n.disaster_loss_deduction
    line_20 = line_15 - (line_16 + line_17 + line_18 + line_19)

    return {
        "f100s_line_1_obi": line_1,
        "f100s_line_2_taxes_deducted": line_2,
        "f100s_line_3_interest_govt_obligations": line_3,
        "f100s_line_4_net_capital_gain": line_4,
        "f100s_line_5_depreciation_adjustment": line_5,
        "f100s_line_6_portfolio_income": line_6,
        "f100s_line_7_other_additions": line_7,
        "f100s_line_8_total_additions": line_8,
        "f100s_line_9_dividends_received": line_9,
        "f100s_line_10_waters_edge_dividend": line_10,
        "f100s_line_11_charitable_contributions": line_11,
        "f100s_line_12_other_deductions": line_12,
        "f100s_line_13_total_deductions": line_13,
        "f100s_line_14_net_income_after_adjustments": line_14,
        "f100s_line_15_net_income_state": line_15,
        "f100s_line_16_section_23802e": line_16,
        "f100s_line_17_nol_deduction": line_17,
        "f100s_line_18_ez_tta_lambra_nol": line_18,
        "f100s_line_19_disaster_loss": line_19,
        "f100s_line_20_net_income_for_tax": line_20,
    }


# ---------------------------------------------------------------------------
# Tax Computation (lines 21-30)
# ---------------------------------------------------------------------------
# SOURCE: R&TC §23802(a) — 1.5% in lieu of regular corporate rate.
_S_CORP_TAX_RATE = 0.015
# SOURCE: R&TC §23186 — financial S-corps taxed at 3.5%.
_FINANCIAL_S_CORP_TAX_RATE = 0.035
# SOURCE: R&TC §23153 — minimum franchise tax.
_MINIMUM_FRANCHISE_TAX = 800.0
# SOURCE: R&TC §23802(b)(5) — QSub annual tax per subsidiary.
_QSUB_ANNUAL_TAX = 800.0


def _compute_tax(
    net_income_for_tax: float,
    entity: EntityIdentity,
    credits: tuple[CreditEntry, ...],
    additional_taxes: AdditionalTaxes,
) -> dict:
    """Main form lines 21-30: entity-level tax computation."""
    # SOURCE: 2025 Form 100S Side 2, Tax section.
    rate = _FINANCIAL_S_CORP_TAX_RATE if entity.is_financial_s_corp else _S_CORP_TAX_RATE
    income_tax = max(0.0, rate * net_income_for_tax)

    # SOURCE: R&TC §23153(f) — first-year exemption from minimum franchise tax.
    if entity.is_first_year:
        line_21 = income_tax
    else:
        line_21 = max(income_tax, _MINIMUM_FRANCHISE_TAX)

    total_credits = sum(c.amount for c in credits)

    # SOURCE: Form face line 26 — "not less than minimum franchise tax
    # plus QSub annual tax(es), if applicable."
    qsub_taxes = entity.num_qsubs * _QSUB_ANNUAL_TAX
    if entity.is_first_year:
        credit_floor = qsub_taxes
    else:
        credit_floor = _MINIMUM_FRANCHISE_TAX + qsub_taxes
    line_26 = max(line_21 - total_credits, credit_floor)

    line_27 = additional_taxes.tax_from_schedule_d
    line_28 = additional_taxes.excess_net_passive_income_tax
    line_29 = additional_taxes.pte_elective_tax
    line_30 = line_26 + line_27 + line_28 + line_29

    return {
        "f100s_line_21_tax": line_21,
        "f100s_line_25_total_credits": total_credits,
        "f100s_line_26_balance": line_26,
        "f100s_line_27_tax_from_schedule_d": line_27,
        "f100s_line_28_excess_passive_income_tax": line_28,
        "f100s_line_29_pte_elective_tax": line_29,
        "f100s_line_30_total_tax": line_30,
        "f100s_tax": line_21,
        "f100s_total_tax": line_30,
    }


# ---------------------------------------------------------------------------
# Input dataclass — Payments
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Payments:
    """Main form lines 31-35 payment inputs."""
    prior_year_overpayment: float           # line 31
    estimated_tax_payments: float           # line 32 (including QSub payments)
    withholding: float                      # line 33 (Forms 592-B / 593)
    amount_paid_with_extension: float       # line 34
    pte_elective_tax_payments: float        # line 35
    amount_credited_to_next_year: float     # line 42 (portion of overpayment)


# ---------------------------------------------------------------------------
# Payments + Balance (lines 31-45)
# ---------------------------------------------------------------------------
def _compute_payments(
    total_tax: float,
    payments: Payments,
) -> dict:
    """Main form lines 31-45: payments, balance due, overpayment."""
    # SOURCE: 2025 Form 100S Side 2, Payments / Refund or Amount Due.
    p = payments
    line_31 = p.prior_year_overpayment
    line_32 = p.estimated_tax_payments
    line_33 = p.withholding
    line_34 = p.amount_paid_with_extension
    line_35 = p.pte_elective_tax_payments
    line_36 = line_31 + line_32 + line_33 + line_34 + line_35

    # Use tax is scope-out (assume 0).
    line_38 = line_36  # payments balance (line 36 − use tax)

    if total_tax > line_38:
        line_40 = total_tax - line_38
        line_41 = 0.0
    else:
        line_40 = 0.0
        line_41 = line_38 - total_tax

    line_42 = min(p.amount_credited_to_next_year, line_41)
    line_43 = line_41 - line_42

    return {
        "f100s_line_31_prior_year_overpayment": line_31,
        "f100s_line_32_estimated_tax_payments": line_32,
        "f100s_line_33_withholding": line_33,
        "f100s_line_34_paid_with_extension": line_34,
        "f100s_line_35_pte_elective_tax_payments": line_35,
        "f100s_line_36_total_payments": line_36,
        "f100s_line_38_payments_balance": line_38,
        "f100s_line_40_tax_due": line_40,
        "f100s_line_41_overpayment": line_41,
        "f100s_line_42_credited_to_next_year": line_42,
        "f100s_line_43_refund": line_43,
    }


# ---------------------------------------------------------------------------
# Input dataclass — Schedule K
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduleKItems:
    """Entity-level separately-stated items for Schedule K (100S).

    OBI (line 1) is NOT a field — it comes from Schedule F line 22.
    No §199A QBI — CA does not conform to IRC §199A.
    Lines 9, 13a-d, 15a-f, 18a-e are scope-out for v1.
    """
    net_rental_real_estate_income: float    # line 2
    other_gross_rental_income: float        # line 3a
    other_gross_rental_expenses: float      # line 3b
    interest_income: float                  # line 4
    dividends: float                        # line 5
    royalties: float                        # line 6
    net_short_term_capital_gain: float      # line 7
    net_long_term_capital_gain: float       # line 8
    other_portfolio_income: float           # line 10a
    other_income: float                     # line 10b
    section_179_expense: float              # line 11
    charitable_contributions_cash: float    # line 12a
    charitable_contributions_noncash: float # line 12b
    investment_interest_expense: float      # line 12c
    other_deductions: float                 # line 12f
    tax_exempt_interest: float              # line 16a
    other_tax_exempt_income: float          # line 16b
    nondeductible_expenses: float           # line 16c
    total_property_distributions: float     # line 16d
    investment_income: float                # line 17a
    investment_expenses: float              # line 17b


# ---------------------------------------------------------------------------
# Schedule K (100S) — Entity-Level Totals
# ---------------------------------------------------------------------------
def _compute_schedule_k(
    sch_k: ScheduleKItems,
    obi: float,
) -> dict:
    """Schedule K (100S) — entity-level shareholder pro-rata share items."""
    # SOURCE: 2025 Form 100S Schedule K (Side 5-6).
    k = sch_k
    line_3c = k.other_gross_rental_income - k.other_gross_rental_expenses

    # Line 19: reconciliation = income lines − deduction lines.
    income_total = (
        obi
        + k.net_rental_real_estate_income
        + line_3c
        + k.interest_income
        + k.dividends
        + k.royalties
        + k.net_short_term_capital_gain
        + k.net_long_term_capital_gain
        + k.other_portfolio_income
        + k.other_income
    )
    deduction_total = (
        k.section_179_expense
        + k.charitable_contributions_cash
        + k.charitable_contributions_noncash
        + k.investment_interest_expense
        + k.other_deductions
    )
    line_19 = income_total - deduction_total

    return {
        "f100s_sch_k_line_1_obi": obi,
        "f100s_sch_k_line_2_net_rental_real_estate": k.net_rental_real_estate_income,
        "f100s_sch_k_line_3a_other_gross_rental_income": k.other_gross_rental_income,
        "f100s_sch_k_line_3b_other_gross_rental_expenses": k.other_gross_rental_expenses,
        "f100s_sch_k_line_3c_other_net_rental": line_3c,
        "f100s_sch_k_line_4_interest_income": k.interest_income,
        "f100s_sch_k_line_5_dividends": k.dividends,
        "f100s_sch_k_line_6_royalties": k.royalties,
        "f100s_sch_k_line_7_net_short_term_capital_gain": k.net_short_term_capital_gain,
        "f100s_sch_k_line_8_net_long_term_capital_gain": k.net_long_term_capital_gain,
        "f100s_sch_k_line_10a_other_portfolio_income": k.other_portfolio_income,
        "f100s_sch_k_line_10b_other_income": k.other_income,
        "f100s_sch_k_line_11_section_179_expense": k.section_179_expense,
        "f100s_sch_k_line_12a_charitable_cash": k.charitable_contributions_cash,
        "f100s_sch_k_line_12b_charitable_noncash": k.charitable_contributions_noncash,
        "f100s_sch_k_line_12c_investment_interest_expense": k.investment_interest_expense,
        "f100s_sch_k_line_12f_other_deductions": k.other_deductions,
        "f100s_sch_k_line_16a_tax_exempt_interest": k.tax_exempt_interest,
        "f100s_sch_k_line_16b_other_tax_exempt_income": k.other_tax_exempt_income,
        "f100s_sch_k_line_16c_nondeductible_expenses": k.nondeductible_expenses,
        "f100s_sch_k_line_16d_total_property_distributions": k.total_property_distributions,
        "f100s_sch_k_line_17a_investment_income": k.investment_income,
        "f100s_sch_k_line_17b_investment_expenses": k.investment_expenses,
        "f100s_sch_k_line_19_reconciliation": line_19,
    }


# ---------------------------------------------------------------------------
# Input dataclass — Shareholder
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Shareholder:
    """A single shareholder of the S corporation.

    Oracle requires constant ownership across the full tax year.
    """
    shareholder_id: str
    name: str
    tin: str
    ownership_percentage: float  # 0.0-1.0
    is_ca_resident: bool
    material_participation: bool


# ---------------------------------------------------------------------------
# Schedule K-1 (100S) — Per-Shareholder Pro-Rata Allocation
# ---------------------------------------------------------------------------
# K items that get allocated pro-rata; maps sch_k output key → K-1 line suffix.
_K1_ALLOCABLE_ITEMS = [
    ("f100s_sch_k_line_1_obi", "line_1_obi"),
    ("f100s_sch_k_line_2_net_rental_real_estate", "line_2_net_rental_real_estate"),
    ("f100s_sch_k_line_3c_other_net_rental", "line_3c_other_net_rental"),
    ("f100s_sch_k_line_4_interest_income", "line_4_interest_income"),
    ("f100s_sch_k_line_5_dividends", "line_5_dividends"),
    ("f100s_sch_k_line_6_royalties", "line_6_royalties"),
    ("f100s_sch_k_line_7_net_short_term_capital_gain", "line_7_net_short_term_capital_gain"),
    ("f100s_sch_k_line_8_net_long_term_capital_gain", "line_8_net_long_term_capital_gain"),
    ("f100s_sch_k_line_10a_other_portfolio_income", "line_10a_other_portfolio_income"),
    ("f100s_sch_k_line_10b_other_income", "line_10b_other_income"),
    ("f100s_sch_k_line_11_section_179_expense", "line_11_section_179_expense"),
    ("f100s_sch_k_line_12a_charitable_cash", "line_12a_charitable_cash"),
    ("f100s_sch_k_line_12b_charitable_noncash", "line_12b_charitable_noncash"),
    ("f100s_sch_k_line_12c_investment_interest_expense", "line_12c_investment_interest_expense"),
    ("f100s_sch_k_line_12f_other_deductions", "line_12f_other_deductions"),
    ("f100s_sch_k_line_16a_tax_exempt_interest", "line_16a_tax_exempt_interest"),
    ("f100s_sch_k_line_16b_other_tax_exempt_income", "line_16b_other_tax_exempt_income"),
    ("f100s_sch_k_line_16c_nondeductible_expenses", "line_16c_nondeductible_expenses"),
    ("f100s_sch_k_line_16d_total_property_distributions", "line_16d_total_property_distributions"),
    ("f100s_sch_k_line_17a_investment_income", "line_17a_investment_income"),
    ("f100s_sch_k_line_17b_investment_expenses", "line_17b_investment_expenses"),
]


def _compute_schedule_k1(
    entity: EntityIdentity,
    sch_k_out: dict,
    shareholders: tuple[Shareholder, ...],
) -> dict:
    """Allocate Schedule K items to each shareholder by ownership %.

    Emits two shapes per shareholder:
    1. Raw K-1 line values: f100s_sch_k1_<id>_line_<N>_<semantic>
    2. ca_540_carry_in convenience dict for CA 540 oracle integration
    """
    # SOURCE: 2025 Schedule K-1 (100S) — pro-rata allocation by ownership.
    out: dict = {}
    for s in shareholders:
        p = s.ownership_percentage
        prefix = f"f100s_sch_k1_{s.shareholder_id}"

        out[f"{prefix}_shareholder_name"] = s.name
        out[f"{prefix}_shareholder_tin"] = s.tin
        out[f"{prefix}_ownership_percentage"] = p
        out[f"{prefix}_is_ca_resident"] = s.is_ca_resident

        allocated: dict[str, float] = {}
        for k_key, k1_suffix in _K1_ALLOCABLE_ITEMS:
            val = sch_k_out[k_key] * p
            out[f"{prefix}_{k1_suffix}"] = val
            allocated[k1_suffix] = val

        # Shape 2: ca_540_carry_in — maps to CA 540 oracle input fields.
        # No §199A QBI — CA does not conform.
        out[f"{prefix}_ca_540_carry_in"] = {
            "entity_name": entity.name,
            "entity_ein": entity.ein,
            "entity_type": "s_corp",
            "material_participation": s.material_participation,
            "ordinary_business_income": allocated["line_1_obi"],
            "net_rental_real_estate": allocated["line_2_net_rental_real_estate"],
            "other_net_rental": allocated["line_3c_other_net_rental"],
            "interest_income": allocated["line_4_interest_income"],
            "ordinary_dividends": allocated["line_5_dividends"],
            "royalties": allocated["line_6_royalties"],
            "net_short_term_capital_gain": allocated["line_7_net_short_term_capital_gain"],
            "net_long_term_capital_gain": allocated["line_8_net_long_term_capital_gain"],
            "other_portfolio_income": allocated["line_10a_other_portfolio_income"],
            "other_income": allocated["line_10b_other_income"],
            "section_179_expense": allocated["line_11_section_179_expense"],
            "charitable_contributions": (
                allocated["line_12a_charitable_cash"]
                + allocated["line_12b_charitable_noncash"]
            ),
            "tax_exempt_interest": allocated["line_16a_tax_exempt_interest"],
            "nondeductible_expenses": allocated["line_16c_nondeductible_expenses"],
        }
    return out


# ---------------------------------------------------------------------------
# Top-level input dataclass
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class F100SInput:
    """Top-level input for the Form 100S oracle."""
    entity: EntityIdentity
    schf_income: ScheduleFIncome
    schf_deductions: ScheduleFDeductions
    additions: StateAdjustmentAdditions
    deductions: StateAdjustmentDeductions
    nol: NOLDeductions
    credits: tuple[CreditEntry, ...]
    additional_taxes: AdditionalTaxes
    payments: Payments
    sch_k: ScheduleKItems
    shareholders: tuple[Shareholder, ...]


# ---------------------------------------------------------------------------
# Scope gates
# ---------------------------------------------------------------------------
_OWNERSHIP_SUM_TOLERANCE = 1e-6


def _gate_scope(inp: F100SInput) -> None:
    """Reject inputs the oracle does not model."""
    if not inp.shareholders:
        raise ValueError("S corporation must have at least one shareholder.")

    total_ownership = sum(s.ownership_percentage for s in inp.shareholders)
    if abs(total_ownership - 1.0) > _OWNERSHIP_SUM_TOLERANCE:
        raise ValueError(
            f"Shareholder ownership percentages must sum to 1.0; "
            f"got {total_ownership}."
        )

    ids = [s.shareholder_id for s in inp.shareholders]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Shareholder IDs must be unique; got {ids}.")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def compute_f100s(inp: F100SInput) -> dict:
    """Compute the full Form 100S return plus K-1s.

    Returns a flat dict keyed per the module docstring.
    """
    _gate_scope(inp)

    out: dict = {}

    # Schedule F (Side 4)
    schf_income = _compute_schedule_f_income(inp.schf_income)
    out.update(schf_income)
    schf_deductions = _compute_schedule_f_deductions(inp.schf_deductions)
    out.update(schf_deductions)
    schf_obi = _compute_schedule_f_obi(
        schf_income["f100s_schf_line_6_total_income"],
        schf_deductions["f100s_schf_line_21_total_deductions"],
    )
    out.update(schf_obi)

    # Main form state adjustments (lines 1-20)
    state_adj = _compute_state_adjustments(
        obi=schf_obi["f100s_schf_line_22_obi"],
        additions=inp.additions,
        deductions=inp.deductions,
        nol=inp.nol,
    )
    out.update(state_adj)

    # Tax computation (lines 21-30)
    tax = _compute_tax(
        net_income_for_tax=state_adj["f100s_line_20_net_income_for_tax"],
        entity=inp.entity,
        credits=inp.credits,
        additional_taxes=inp.additional_taxes,
    )
    out.update(tax)

    # Payments + balance (lines 31-45)
    payments = _compute_payments(
        total_tax=tax["f100s_line_30_total_tax"],
        payments=inp.payments,
    )
    out.update(payments)

    # Schedule K
    sch_k = _compute_schedule_k(
        sch_k=inp.sch_k,
        obi=schf_obi["f100s_schf_line_22_obi"],
    )
    out.update(sch_k)

    # Schedule K-1 per shareholder
    k1s = _compute_schedule_k1(inp.entity, sch_k, inp.shareholders)
    out.update(k1s)

    return out
