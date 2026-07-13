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
    return {
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
        "f100s_amount_owed": irs_round(max(delta, 0.0)),
        "f100s_overpayment": irs_round(max(-delta, 0.0)),
    }
