"""Federal Form 1120-S reference oracle (TY2025).

Hand-coded reference implementation for Form 1120-S (U.S. Income Tax Return
for an S Corporation) including Schedule B (Other Information), Schedule K
(Shareholders' Pro Rata Share Items — Totals), and Schedule K-1 per-
shareholder allocations.

Independent of the production ``tenforty/`` package. Reads IRS 2025 Form
1120-S instructions directly. Divergence between production and this oracle
is the signal we care about — do not smooth it over.

### Scope (v1)

IN scope:
- Main form lines 1-22 (Income lines 1-6, Deductions lines 7-21, OBI line 22)
- Main form lines 23-28 pass-through: caller provides §1375 / §1374 tax
  amounts directly; oracle performs the arithmetic to compute total tax,
  balance due, or overpayment.
- Schedule B Yes/No gates for questions that feed downstream behavior.
- Schedule K totals (lines 1-18 core items).
- Schedule K-1 per-shareholder allocations (pro-rata by ownership %).

OUT of scope (v1 — scope-gated, raise NotImplementedError if triggered):
- Excess Net Passive Income Tax computation per §1375 (caller supplies
  amount directly).
- Built-in Gains Tax / Tax from Schedule D per §1374 (caller supplies).
- Interest on §453/§453A deferred tax (caller supplies amount).
- Line 28 direct-deposit fields (28c routing number, 28d account type,
  28e account number). Payment-mechanism strings, not tax math.
- Mid-year ownership changes (short-period allocations). Oracle requires
  constant ownership per shareholder for the full tax year.
- Schedule L (balance sheet).
- Schedule M-1 (book/tax reconciliation).
- Schedule M-2 (AAA / PTEP / Other Adjustments Account).
- Schedule M-3 (required when total assets ≥ $10M — large-entity only).
- Form 1125-A COGS detail (caller provides line 2 aggregate).
- Form 1125-E compensation of officers detail (caller provides line 7).

### Output contract

``compute_f1120s(inp: F1120SInput) -> dict`` returns a flat dict keyed:

- ``f1120s_line_<N>_<semantic>``    — main form lines 1a-28
- ``sch_b_line_<N>_<semantic>``     — Schedule B answers (pass-through)
- ``sch_k_line_<N>_<semantic>``     — Schedule K entity-level totals
- ``sch_k1_<shareholder_id>_<field>`` — per-shareholder K-1 allocation

Per-shareholder ``<field>`` names match the Plan-D K-1 oracle's
``ScheduleK1Like`` input protocol where they overlap, so the two oracles
can be chained in integration tests.

### Numeric type

``float`` per project contract. Arithmetic is exact sum/subtract; no
rounding inside the oracle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


# ---------------------------------------------------------------------------
# Input dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EntityIdentity:
    """Form 1120-S header (boxes A-J on page 1).

    Fields captured here are those downstream oracles need; not every box
    is exposed (e.g., activity code, IRS center address are informational).
    """
    name: str
    ein: str
    # Accounting method governs some Schedule B answers. Kept here (not on
    # ScheduleBAnswers) because it may influence compute paths beyond Sch B.
    accounting_method: Literal["cash", "accrual", "other"]


@dataclass(frozen=True)
class GrossReceipts:
    """Form 1120-S Income section, lines 1a-6.

    Line 1c and line 3 and line 6 are computed; the rest are inputs.
    """
    gross_receipts_or_sales: float          # line 1a
    returns_and_allowances: float            # line 1b
    cost_of_goods_sold: float                # line 2 (from Form 1125-A; scope-out detail)
    net_gain_from_4797: float                # line 4 (§1231 net gain/loss)
    other_income: float                      # line 5


@dataclass(frozen=True)
class Deductions:
    """Form 1120-S Deductions section, lines 7-20.

    Line 21 is computed (sum of 7-20). All fields here are input amounts.
    """
    compensation_of_officers: float         # line 7 (from Form 1125-E; scope-out detail)
    salaries_and_wages: float                # line 8 (net of employment credits)
    repairs_and_maintenance: float           # line 9
    bad_debts: float                         # line 10
    rents: float                             # line 11
    taxes_and_licenses: float                # line 12
    interest_expense: float                  # line 13
    depreciation_not_on_1125a: float         # line 14 (Form 4562 depreciation not captured elsewhere)
    depletion: float                         # line 15 (oil/gas depletion NOT included per instructions)
    advertising: float                       # line 16
    pension_and_profit_sharing: float        # line 17
    employee_benefit_programs: float         # line 18
    energy_efficient_commercial_buildings_179d: float  # line 19 (attach Form 7205)
    other_deductions: float                  # line 20 (attach statement)


@dataclass(frozen=True)
class TaxAndPayments:
    """Form 1120-S Tax and Payments section.

    TY2025 line structure:
      23a  Excess net passive income or LIFO recapture tax (§1375/§1363(d))
      23b  Tax from Schedule D (Form 1120-S) — §1374 built-in gains
      23c  Add lines 23a + 23b
      24a  Prior-year overpayment credited + estimated tax payments
      24b  Tax deposited with Form 7004
      24c  Credit for federal tax paid on fuels (Form 4136)
      24d  Elective payment election amount from Form 3800 (§6417)
      24z  Add lines 24a-24d (total payments)
      25   Estimated tax penalty
      26   Amount owed
      27   Overpayment
      28a  Credited to next-year estimates
      28b  Refunded
      28c/d/e Direct-deposit info — scope-out (payment-mechanism strings)

    The oracle treats entity-level tax computation (§1375, §1374, §453A
    interest) as a SCOPE-OUT: caller supplies the pre-computed amounts
    directly. The oracle then performs the arithmetic to roll them forward
    to total tax, amount owed, and overpayment.
    """
    excess_net_passive_income_or_lifo_tax: float  # line 23a — CALLER-PROVIDED
    tax_from_schedule_d: float                     # line 23b — CALLER-PROVIDED
    prior_year_overpayment_and_estimates: float    # line 24a
    tax_deposited_with_7004: float                  # line 24b
    credit_for_federal_tax_paid_on_fuels: float    # line 24c
    elective_payment_election_from_form_3800: float  # line 24d (§6417)
    estimated_tax_penalty: float                    # line 25
    amount_credited_to_next_year_estimates: float  # portion of overpayment applied forward (line 28a)


@dataclass(frozen=True)
class ScheduleBAnswers:
    """Schedule B (Form 1120-S) — Other Information.

    Only questions that GATE downstream behavior or feed required
    disclosures are captured. Informational questions (business activity
    code, principal product) are stored as free-text strings and not
    validated here.

    Line numbers are 2025 Schedule B structure (VERIFY once ca-research
    confirms).
    """
    business_activity: str                  # line 2a — principal activity
    product_or_service: str                 # line 2b
    #
    # Line 3: Ownership of stock in any foreign or domestic corp.
    # Line 4: Ownership of ≥20% of any partnership or LLC interest.
    # (Both trigger disclosure schedules; oracle records the flag.)
    owns_stock_in_other_entity: bool                   # line 3
    owns_partnership_or_llc_interest_ge_20pct: bool    # line 4
    #
    # Line 9: total receipts < $250k AND total assets < $250k at year-end
    # → NOT required to complete Schedules L, M-1, M-2. If True, oracle
    # confirms scope-out alignment.
    total_receipts_and_assets_under_250k: bool
    #
    # Line 10b: §163(j) business interest expense limitation applies when
    # three-year average gross receipts exceed the §448(c) threshold. If
    # True, production must file Form 8990 and potentially limit line 13.
    # Oracle v1 does NOT apply §163(j); this flag is captured for the
    # harness to note a potential divergence.
    subject_to_163j_limitation: bool
    #
    # §448(c) gross receipts test — three-year average above the annually
    # indexed inflation-adjusted threshold triggers §163(j) and related
    # limits. Captured for disclosure, not applied internally.
    three_year_average_gross_receipts: float


@dataclass(frozen=True)
class Shareholder:
    """A single shareholder of the S corporation.

    Oracle requires CONSTANT ownership across the full tax year. Mid-year
    ownership changes (short-period allocation per Reg §1.1377-1(a)(2)(ii))
    are out of scope for v1; see ``_gate_scope``.
    """
    shareholder_id: str               # internal label, used in output dict keys
    name: str
    tin: str                          # SSN or EIN
    ownership_percentage: float       # 0.0 - 1.0 (not 0-100)
    is_us_resident: bool              # K-1 box — flag for downstream
    # Per-shareholder operational classification. Oracle does NOT determine
    # this — it's set by the shareholder's own involvement with the business.
    # Included here because the K-1 oracle's ``ScheduleK1Like`` protocol
    # requires it as input for passive classification.
    material_participation: bool


@dataclass(frozen=True)
class ScheduleKItems:
    """Entity-level separately-stated items that flow to Schedule K.

    OBI (Sch K line 1) is NOT a field here — it comes from main form
    line 21 automatically.

    Fields below mirror core Schedule K line numbering (2025):
      Line 2:  Net rental real estate income (loss)
      Line 3:  Other net rental income (loss)
      Line 4:  Interest income
      Line 5a: Ordinary dividends
      Line 5b: Qualified dividends (subset of 5a)
      Line 6:  Royalties
      Line 7:  Net short-term capital gain (loss)
      Line 8a: Net long-term capital gain (loss)
      Line 17V: QBI amount for §199A aggregation at shareholder level

    Collectibles gain (8b), unrecaptured §1250 gain (8c), §1231 gain
    (line 9), §179 deduction (line 11), credits, and foreign-activity
    items are SCOPE-OUT. Caller must not populate them; oracle gates on
    them being absent.
    """
    net_rental_real_estate_income: float   # line 2
    other_net_rental_income: float          # line 3
    interest_income: float                  # line 4
    ordinary_dividends: float               # line 5a
    qualified_dividends: float              # line 5b (subset of 5a)
    royalties: float                        # line 6
    net_short_term_capital_gain: float      # line 7
    net_long_term_capital_gain: float       # line 8a
    qbi_amount: float                       # line 17V


@dataclass(frozen=True)
class F1120SInput:
    """Top-level input dataclass for the 1120-S reference oracle."""
    entity: EntityIdentity
    gross: GrossReceipts
    deductions: Deductions
    tax: TaxAndPayments
    sch_b: ScheduleBAnswers
    sch_k: ScheduleKItems
    shareholders: tuple[Shareholder, ...]


# ---------------------------------------------------------------------------
# Scope gates
# ---------------------------------------------------------------------------
_OWNERSHIP_SUM_TOLERANCE = 1e-6


def _gate_scope(inp: F1120SInput) -> None:
    """Reject inputs the oracle does not model. Silent fallthrough is banned
    (iron law #2) — any out-of-scope item must raise.
    """
    if not inp.shareholders:
        raise ValueError("S corporation must have at least one shareholder.")

    total_ownership = sum(s.ownership_percentage for s in inp.shareholders)
    if abs(total_ownership - 1.0) > _OWNERSHIP_SUM_TOLERANCE:
        raise ValueError(
            f"Shareholder ownership percentages must sum to 1.0; "
            f"got {total_ownership}. Mid-year ownership changes and "
            f"short-period allocations are out of scope — see README."
        )

    ids = [s.shareholder_id for s in inp.shareholders]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Shareholder IDs must be unique; got {ids}.")


# ---------------------------------------------------------------------------
# Main form compute: lines 1-21
# ---------------------------------------------------------------------------
def _compute_main_form_income(g: GrossReceipts) -> dict[str, float]:
    """Lines 1a-6: Income."""
    # SOURCE: 2025 Form 1120-S instructions, Income section.
    line_1c = g.gross_receipts_or_sales - g.returns_and_allowances
    line_3 = line_1c - g.cost_of_goods_sold
    line_6 = line_3 + g.net_gain_from_4797 + g.other_income
    return {
        "f1120s_line_1a_gross_receipts": g.gross_receipts_or_sales,
        "f1120s_line_1b_returns_and_allowances": g.returns_and_allowances,
        "f1120s_line_1c_net_receipts": line_1c,
        "f1120s_line_2_cogs": g.cost_of_goods_sold,
        "f1120s_line_3_gross_profit": line_3,
        "f1120s_line_4_net_gain_from_4797": g.net_gain_from_4797,
        "f1120s_line_5_other_income": g.other_income,
        "f1120s_line_6_total_income": line_6,
    }


def _compute_main_form_deductions(d: Deductions) -> dict[str, float]:
    """Lines 7-21: Deductions."""
    # SOURCE: 2025 Form 1120-S instructions, Deductions section.
    line_21 = (
        d.compensation_of_officers
        + d.salaries_and_wages
        + d.repairs_and_maintenance
        + d.bad_debts
        + d.rents
        + d.taxes_and_licenses
        + d.interest_expense
        + d.depreciation_not_on_1125a
        + d.depletion
        + d.advertising
        + d.pension_and_profit_sharing
        + d.employee_benefit_programs
        + d.energy_efficient_commercial_buildings_179d
        + d.other_deductions
    )
    return {
        "f1120s_line_7_compensation_of_officers": d.compensation_of_officers,
        "f1120s_line_8_salaries_and_wages": d.salaries_and_wages,
        "f1120s_line_9_repairs_and_maintenance": d.repairs_and_maintenance,
        "f1120s_line_10_bad_debts": d.bad_debts,
        "f1120s_line_11_rents": d.rents,
        "f1120s_line_12_taxes_and_licenses": d.taxes_and_licenses,
        "f1120s_line_13_interest_expense": d.interest_expense,
        "f1120s_line_14_depreciation_not_on_1125a": d.depreciation_not_on_1125a,
        "f1120s_line_15_depletion": d.depletion,
        "f1120s_line_16_advertising": d.advertising,
        "f1120s_line_17_pension_and_profit_sharing": d.pension_and_profit_sharing,
        "f1120s_line_18_employee_benefit_programs": d.employee_benefit_programs,
        "f1120s_line_19_energy_efficient_commercial_buildings_179d":
            d.energy_efficient_commercial_buildings_179d,
        "f1120s_line_20_other_deductions": d.other_deductions,
        "f1120s_line_21_total_deductions": line_21,
    }


def _compute_main_form_obi(line_6: float, line_21: float) -> dict[str, float]:
    """Line 22: Ordinary business income (loss)."""
    # SOURCE: 2025 Form 1120-S instructions, line 22 — subtract line 21 from line 6.
    return {"f1120s_line_22_ordinary_business_income": line_6 - line_21}


def _compute_main_form_tax_and_payments(
    t: TaxAndPayments,
) -> dict[str, float]:
    """Lines 23-28: Tax and Payments.

    §1375 and §1374 tax computations are scope-out; caller provides the
    pre-computed amounts in t.excess_net_passive_income_or_lifo_tax and
    t.tax_from_schedule_d. Oracle performs the arithmetic rollup.
    """
    # SOURCE: 2025 Form 1120-S instructions, lines 23-28.
    line_23a = t.excess_net_passive_income_or_lifo_tax
    line_23b = t.tax_from_schedule_d
    line_23c = line_23a + line_23b

    line_24a = t.prior_year_overpayment_and_estimates
    line_24b = t.tax_deposited_with_7004
    line_24c = t.credit_for_federal_tax_paid_on_fuels
    line_24d = t.elective_payment_election_from_form_3800
    line_24z = line_24a + line_24b + line_24c + line_24d

    line_25 = t.estimated_tax_penalty

    # Balance due vs overpayment: compare line_24z against (line_23c + line_25).
    total_owed = line_23c + line_25
    if line_24z < total_owed:
        amount_owed = total_owed - line_24z
        overpayment = 0.0
    else:
        amount_owed = 0.0
        overpayment = line_24z - total_owed

    credited_forward = min(
        t.amount_credited_to_next_year_estimates, overpayment
    )
    refunded = overpayment - credited_forward

    return {
        "f1120s_line_23a_excess_net_passive_or_lifo_tax": line_23a,
        "f1120s_line_23b_tax_from_schedule_d": line_23b,
        "f1120s_line_23c_total_tax": line_23c,
        "f1120s_line_24a_prior_year_and_estimates": line_24a,
        "f1120s_line_24b_deposits_with_7004": line_24b,
        "f1120s_line_24c_fuel_tax_credit": line_24c,
        "f1120s_line_24d_elective_payment_election": line_24d,
        "f1120s_line_24z_total_payments": line_24z,
        "f1120s_line_25_estimated_tax_penalty": line_25,
        "f1120s_line_26_amount_owed": amount_owed,
        "f1120s_line_27_overpayment": overpayment,
        "f1120s_line_28a_credited_to_next_year": credited_forward,
        "f1120s_line_28b_refunded": refunded,
    }


# ---------------------------------------------------------------------------
# Schedule B: pass-through of gating answers
# ---------------------------------------------------------------------------
def _compute_schedule_b(
    b: ScheduleBAnswers,
    accounting_method: str,
) -> dict:
    """Emit Schedule B answers. The oracle does not VALIDATE the answers
    (e.g., it does not verify that an entity reporting <$250k receipts
    actually skipped L/M-1/M-2). It simply records what the caller asserted
    and exposes it for the harness to cross-check against production's
    reasoning.

    Line 10b tracks whether the §448(c) gross-receipts threshold is met
    (test uses the three-year-average value supplied by the caller;
    threshold itself is indexed annually — see ``three_year_average_gross_receipts``).
    Line 17 is reserved on the 2025 form; emitted as an explicit placeholder.
    """
    # SOURCE: 2025 Schedule B (Form 1120-S) form face.
    return {
        "sch_b_line_1_accounting_method": accounting_method,
        "sch_b_line_2a_business_activity": b.business_activity,
        "sch_b_line_2b_product_or_service": b.product_or_service,
        "sch_b_line_3_owns_stock_in_other_entity": b.owns_stock_in_other_entity,
        "sch_b_line_4_owns_partnership_or_llc_ge_20pct": b.owns_partnership_or_llc_interest_ge_20pct,
        "sch_b_line_9_total_receipts_and_assets_under_250k": b.total_receipts_and_assets_under_250k,
        "sch_b_line_10b_subject_to_163j_limitation": b.subject_to_163j_limitation,
        "sch_b_line_10b_3_year_avg_gross_receipts": b.three_year_average_gross_receipts,
        "sch_b_line_17_reserved": None,
    }


# ---------------------------------------------------------------------------
# Schedule K: entity-level totals
# ---------------------------------------------------------------------------
def _compute_schedule_k(
    k: ScheduleKItems,
    line_21_obi: float,
) -> dict[str, float]:
    """Schedule K — entity-level totals that will be allocated per-
    shareholder on K-1.

    Line 1 (OBI) is the main-form line 21 value carried over.
    """
    # SOURCE: 2025 Schedule K (Form 1120-S) line structure.
    return {
        "sch_k_line_1_ordinary_business_income": line_21_obi,
        "sch_k_line_2_net_rental_real_estate": k.net_rental_real_estate_income,
        "sch_k_line_3_other_net_rental": k.other_net_rental_income,
        "sch_k_line_4_interest_income": k.interest_income,
        "sch_k_line_5a_ordinary_dividends": k.ordinary_dividends,
        "sch_k_line_5b_qualified_dividends": k.qualified_dividends,
        "sch_k_line_6_royalties": k.royalties,
        "sch_k_line_7_net_short_term_capital_gain": k.net_short_term_capital_gain,
        "sch_k_line_8a_net_long_term_capital_gain": k.net_long_term_capital_gain,
        "sch_k_line_17v_qbi_amount": k.qbi_amount,
    }


# ---------------------------------------------------------------------------
# Schedule K-1: per-shareholder pro-rata allocation
# ---------------------------------------------------------------------------
def _compute_schedule_k1_per_shareholder(
    entity: EntityIdentity,
    sch_k: dict[str, float],
    shareholders: tuple[Shareholder, ...],
) -> dict:
    """Allocate Sch K items to each shareholder by ownership percentage.

    Output keys follow two parallel shapes:

    1. ``sch_k1_<id>_<line_semantic>``  — the literal K-1 box values as
       the form would emit them (ordinary_business_income, interest_income,
       etc.).
    2. ``sch_k1_<id>_schedule_k1_like``  — a dict matching the Plan-D K-1
       oracle's ``ScheduleK1Like`` input protocol, for the roundtrip
       integration test.

    The two shapes are redundant by design. Shape 1 is what PDF emission
    and tax-form review look at; shape 2 is what downstream oracles consume.
    """
    # SOURCE: 2025 Schedule K-1 (Form 1120-S) — per-shareholder allocation
    # is pro-rata by ownership percentage under §1366(a)(1) and §1377(a).
    # The short-period / "closing of the books" election per §1377(a)(2) /
    # Reg §1.1377-1(a)(2)(ii) is scope-gated; oracle assumes constant
    # ownership across the year.
    out: dict = {}
    for s in shareholders:
        p = s.ownership_percentage
        obi_sh = sch_k["sch_k_line_1_ordinary_business_income"] * p
        rre_sh = sch_k["sch_k_line_2_net_rental_real_estate"] * p
        orn_sh = sch_k["sch_k_line_3_other_net_rental"] * p
        int_sh = sch_k["sch_k_line_4_interest_income"] * p
        div_sh = sch_k["sch_k_line_5a_ordinary_dividends"] * p
        qdiv_sh = sch_k["sch_k_line_5b_qualified_dividends"] * p
        roy_sh = sch_k["sch_k_line_6_royalties"] * p
        st_sh = sch_k["sch_k_line_7_net_short_term_capital_gain"] * p
        lt_sh = sch_k["sch_k_line_8a_net_long_term_capital_gain"] * p
        qbi_sh = sch_k["sch_k_line_17v_qbi_amount"] * p

        prefix = f"sch_k1_{s.shareholder_id}"

        # Shape 1: literal K-1 line-by-line values.
        out[f"{prefix}_shareholder_name"] = s.name
        out[f"{prefix}_shareholder_tin"] = s.tin
        out[f"{prefix}_ownership_percentage"] = p
        out[f"{prefix}_is_us_resident"] = s.is_us_resident
        out[f"{prefix}_box_1_ordinary_business_income"] = obi_sh
        out[f"{prefix}_box_2_net_rental_real_estate"] = rre_sh
        out[f"{prefix}_box_3_other_net_rental"] = orn_sh
        out[f"{prefix}_box_4_interest_income"] = int_sh
        out[f"{prefix}_box_5a_ordinary_dividends"] = div_sh
        out[f"{prefix}_box_5b_qualified_dividends"] = qdiv_sh
        out[f"{prefix}_box_6_royalties"] = roy_sh
        out[f"{prefix}_box_7_net_short_term_capital_gain"] = st_sh
        out[f"{prefix}_box_8a_net_long_term_capital_gain"] = lt_sh
        out[f"{prefix}_box_17v_qbi_amount"] = qbi_sh

        # Shape 2: ScheduleK1Like-compatible dict for integration with the
        # Plan-D K-1 oracle (tests.oracles.k1_reference.ScheduleK1Like).
        # Field names match that protocol exactly.
        out[f"{prefix}_schedule_k1_like"] = {
            "entity_name": entity.name,
            "entity_ein": entity.ein,
            "entity_type": "s_corp",
            "material_participation": s.material_participation,
            "ordinary_business_income": obi_sh,
            "net_rental_real_estate": rre_sh,
            "other_net_rental": orn_sh,
            "interest_income": int_sh,
            "ordinary_dividends": div_sh,
            "qualified_dividends": qdiv_sh,
            "royalties": roy_sh,
            "net_short_term_capital_gain": st_sh,
            "net_long_term_capital_gain": lt_sh,
            "other_income": 0.0,  # scope-out; zero by construction
            "qbi_amount": qbi_sh,
            # prior_year_passive_loss_carryforward is shareholder-level
            # tax-history, not knowable from 1120-S. Downstream consumer
            # must supply it; oracle sets 0.0 as a default convention.
            "prior_year_passive_loss_carryforward": 0.0,
        }
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def compute_f1120s(inp: F1120SInput) -> dict:
    """Compute the full 1120-S return plus K-1s.

    Returns a flat dict keyed per the module docstring.
    """
    _gate_scope(inp)

    income = _compute_main_form_income(inp.gross)
    deductions = _compute_main_form_deductions(inp.deductions)
    obi = _compute_main_form_obi(
        income["f1120s_line_6_total_income"],
        deductions["f1120s_line_21_total_deductions"],
    )
    tax_and_payments = _compute_main_form_tax_and_payments(inp.tax)

    sch_b = _compute_schedule_b(inp.sch_b, inp.entity.accounting_method)
    sch_k = _compute_schedule_k(
        inp.sch_k,
        obi["f1120s_line_22_ordinary_business_income"],
    )
    k1s = _compute_schedule_k1_per_shareholder(
        inp.entity, sch_k, inp.shareholders
    )

    out: dict = {}
    out.update(income)
    out.update(deductions)
    out.update(obi)
    out.update(tax_and_payments)
    out.update(sch_b)
    out.update(sch_k)
    out.update(k1s)
    return out


__all__ = [
    "EntityIdentity",
    "GrossReceipts",
    "Deductions",
    "TaxAndPayments",
    "ScheduleBAnswers",
    "Shareholder",
    "ScheduleKItems",
    "F1120SInput",
    "compute_f1120s",
]
