"""California Form 100S — S corporation franchise tax.

Compute lives here; emit now exists too (``tenforty/mappings/pdf_f100s.py``,
``orchestrator._emit_ca_scorp_pdfs_internal``, and the public
``run_full_california_scorp_return``).

v1 scope (see spec §1): 100% CA apportionment (gated at load), no Sch L/M-2
analogues, penalties/interest out of scope. CA net income starts from the
federal 1120-S ordinary business income (upstream), plus the explicit
state-tax addback and depreciation adjustment inputs.
"""
from tenforty.params import ca_scorp
from tenforty.rounding import irs_round


# Schedule F compute key -> federal 1120-S compute key (page 1 line mirror).
_SCHEDULE_F_FROM_FEDERAL: dict[str, str] = {
    "f100s_sch_f_gross_receipts": "f1120s_gross_receipts",              # 1a
    "f100s_sch_f_returns_allowances": "f1120s_returns_and_allowances",  # 1b
    "f100s_sch_f_net_receipts": "f1120s_net_receipts",                  # 1c
    "f100s_sch_f_cogs": "f1120s_cost_of_goods_sold",                    # 2
    "f100s_sch_f_gross_profit": "f1120s_gross_profit",                  # 3
    "f100s_sch_f_net_gain_loss": "f1120s_net_gain_loss_4797",           # 4
    "f100s_sch_f_other_income": "f1120s_other_income",                  # 5
    "f100s_sch_f_total_income": "f1120s_total_income",                  # 6
    "f100s_sch_f_officer_comp": "f1120s_compensation_of_officers",      # 7
    "f100s_sch_f_salaries_wages": "f1120s_salaries_wages",              # 8
    "f100s_sch_f_repairs": "f1120s_repairs_maintenance",                # 9
    "f100s_sch_f_bad_debts": "f1120s_bad_debts",                        # 10
    "f100s_sch_f_rents": "f1120s_rents",                                # 11
    "f100s_sch_f_taxes": "f1120s_taxes_licenses",                       # 12
    "f100s_sch_f_interest": "f1120s_interest",                          # 13
    "f100s_sch_f_depreciation_balance": "f1120s_depreciation",          # 14c
    "f100s_sch_f_depletion": "f1120s_depletion",                        # 15
    "f100s_sch_f_advertising": "f1120s_advertising",                    # 16
    "f100s_sch_f_pension": "f1120s_pension_profit_sharing",             # 17
    "f100s_sch_f_employee_benefits": "f1120s_employee_benefits",        # 18
    "f100s_sch_f_other_deductions": "f1120s_other_deductions",          # 20
    "f100s_sch_f_total_deductions": "f1120s_total_deductions",          # 21
    "f100s_sch_f_ordinary_income": "f1120s_ordinary_business_income",   # 22
}


def compute(scenario, upstream) -> dict:
    r = scenario.s_corp_return
    ca = r.ca
    p = ca_scorp.load(scenario.config.year)
    fed = upstream["f1120s"]

    federal_income = fed["f1120s_ordinary_business_income"]
    net_income = (federal_income
                  + ca.state_tax_deducted_federally
                  + ca.depreciation_adjustment)

    # Form 100S is a two-stage whole-dollar computation: Side 2 line 20 (net
    # income) is entered in whole dollars FIRST, then line 21 tax = 1.5% x the
    # whole-dollar line 20, rounded. Round net income before applying the rate.
    net_income_line = irs_round(net_income)
    measured = (irs_round(net_income_line * p.franchise_tax_rate)
                if net_income_line > 0 else 0)
    floor_applies = not (ca.first_year and p.first_year_minimum_tax_exempt)
    if floor_applies and measured < p.minimum_franchise_tax:
        tax, minimum_applies = p.minimum_franchise_tax, True
    else:
        tax, minimum_applies = measured, False

    total_payments = (irs_round(ca.estimated_tax_payments)
                      + irs_round(ca.prior_year_overpayment_applied))
    delta = tax - total_payments
    amount_owed = irs_round(max(delta, 0.0))
    overpayment = irs_round(max(-delta, 0.0))
    out = {
        "f100s_federal_ordinary_income": irs_round(federal_income),
        "f100s_state_tax_addback": irs_round(ca.state_tax_deducted_federally),
        "f100s_depreciation_adjustment": irs_round(ca.depreciation_adjustment),
        "f100s_net_income_for_tax": net_income_line,
        "f100s_measured_tax": measured,
        "f100s_minimum_tax_applies": minimum_applies,
        "f100s_franchise_tax": irs_round(tax),
        # v1 pass-through totals so the emitted form is internally consistent
        # with L40/L41: with no credits (L22-25), no other taxes (L27-29), and
        # no use tax (L37), the arithmetic collapses to L26=L30=L21 (the tax)
        # and L38=L36 (total payments).
        "f100s_total_tax": irs_round(tax),                       # Side 2 L26
        "f100s_total_tax_after_other_taxes": irs_round(tax),     # Side 2 L30
        "f100s_estimated_tax_payments": irs_round(ca.estimated_tax_payments),
        "f100s_prior_year_overpayment_applied":
            irs_round(ca.prior_year_overpayment_applied),
        "f100s_total_payments": total_payments,
        "f100s_payments_balance": total_payments,                # Side 2 L38
        "f100s_amount_owed": amount_owed,
        "f100s_overpayment": overpayment,
        # Printed totals (v1: no state deductions on Side 2 lines 9-12, no
        # Schedule R apportionment, no L16-L19 deductions), so Side 1 L8 = Side
        # 2 L14 = L15 = the whole-dollar net income that L20 and the tax use.
        "f100s_total_additions": net_income_line,                # Side 1 L8
        "f100s_total_state_deductions": 0,                       # Side 2 L13
        "f100s_net_income_after_adjustments": net_income_line,   # Side 2 L14
        "f100s_net_income_for_state_purposes": net_income_line,  # Side 2 L15
    }
    # Side 6 Schedule K, line 1 and the line 19 reconciliation total (v1: the
    # only pro-rata item is ordinary business income). (b) federal, (d) CA law
    # (= the whole-dollar net income the tax uses), (c) the adjustment, defined
    # as d - b so the row foots on the page ("Combine column (b) and column
    # (c)"). Line 19 = line 1 here (no other Schedule K items to combine).
    k_federal = irs_round(federal_income)
    k_adjustment = net_income_line - k_federal
    for line in ("line1", "line19"):
        out[f"f100s_sch_k_{line}_federal"] = k_federal
        out[f"f100s_sch_k_{line}_ca_adjustment"] = k_adjustment
        out[f"f100s_sch_k_{line}_ca_total"] = net_income_line
    # Side 4 Schedule F mirrors federal 1120-S page 1: every line is the federal
    # compute's own figure passed through (never recomputed here), so line 22
    # equals Side 1 line 1 by construction. Schedule F lines 14a/14b and 19a/19b
    # have no scenario source and are not emitted.
    # (Present only when the upstream federal dict carries the line: the full
    # federal compute always does; narrow unit-test upstreams may not.)
    for sch_f_key, fed_key in _SCHEDULE_F_FROM_FEDERAL.items():
        if fed_key in fed:
            out[sch_f_key] = irs_round(fed[fed_key])
    # Side 2 L45 = L39 + L40 + L42 + L44a - L41 (L39 use tax, L42 credited
    # forward and L44a penalties are out of v1 scope = 0). A negative result
    # (an overpayment) is NOT emitted: no FTB instruction in the repo says how a
    # negative line 45 is entered, so the cell stays blank (refund = L41-L43).
    if amount_owed - overpayment >= 0:
        out["f100s_total_amount_due"] = amount_owed - overpayment
    return out
