"""Schedule 1 emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers the Schedule 1 line 8z cells no other row sets: one Form 1099-G
type (its caption in the 8z write-in), several types (the write-in reads
"See statement" and the statement attaches), and a Form 1099-G with no 8z
type (line 8z and 9 absent). Every scenario runs in every year 2021-2025.

Zero-lines audit rows ([R-ZL-5]): line 1 with a taxable state refund, the
same refund fully absorbed by the prior-year SALT cap (line 1 computes 0,
so Schedule 1 is not attached at all), and line 17 with a self-employed
health-insurance deduction on a single Schedule C.

All identities and amounts are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import (
    FilingStatus, Form1099G, Scenario, ScheduleCBusiness,
)
from tenforty.params.federal import load as load_params
from tests.fixtures.spine_battery import _battery_config, _w2, build_wages_only

YEARS = (2021, 2022, 2023, 2024, 2025)
PAYER = "Example State Agency"


def _with_1099_g(year, **amounts):
    base = build_wages_only(year, FilingStatus.SINGLE)
    return dataclasses.replace(
        base, form1099_g=[Form1099G(payer=PAYER, **amounts)])


def _one_8z_type(year):
    return _with_1099_g(year, taxable_grants=1_000.0)


def _every_8z_type(year):
    # All four line 8z types, so every caption prints on the statement.
    return _with_1099_g(year, rtaa_payments=500.0, taxable_grants=1_000.0,
                        agriculture_payments=750.0, market_gain=250.0)


def _no_8z_type(year):
    # Unemployment only (line 7): the 1099-G carries no line 8z type.
    return _with_1099_g(year, unemployment_compensation=2_000.0)


def _prior_year_refund(year, salt_paid):
    # A prior-year itemizer's state refund (Schedule 1 line 1). Itemized
    # deductions exceed the stated standard deduction by more than the
    # refund, so only the SALT-cap benefit limit can bind.
    base = build_wages_only(year, FilingStatus.SINGLE)
    config = dataclasses.replace(
        base.config, prior_year_itemized=True,
        prior_year_itemized_deduction_amount=20_000.0,
        prior_year_standard_deduction_amount=12_000.0,
        prior_year_salt_paid=salt_paid)
    return dataclasses.replace(
        base, config=config,
        form1099_g=[Form1099G(payer=PAYER, state_tax_refund=1_500.0,
                              state_tax_refund_tax_year=year - 1)])


def _prior_year_salt_cap(year):
    return float(load_params(year).for_status(
        FilingStatus.SINGLE).prior_year_salt_cap)


def _taxable_state_refund(year):
    # SALT paid under the prior-year cap: the whole refund raised the
    # deduction, so line 1 is the refund.
    return _prior_year_refund(year, 0.8 * _prior_year_salt_cap(year))


def _state_refund_absorbed_by_cap(year):
    # SALT paid over the cap by more than the refund: the capped deduction
    # is the same with or without the refund, so line 1 computes 0.
    return _prior_year_refund(year, _prior_year_salt_cap(year) + 2_000.0)


def _se_health_insurance(year):
    # Line 17 on its one lawful shape: a single Schedule C business, the
    # deduction under its earned-income limit.
    return Scenario(
        config=_battery_config(
            year, self_employed_health_insurance_deduction=4_000.0),
        w2s=[_w2(year, "Example Employer", 60_000.0, 8_000.0)],
        schedule_c_businesses=[ScheduleCBusiness(
            description="Example Map Studio", gross_receipts=45_000.0,
            supplies=1_000.0)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "one-8z-type": _one_8z_type,
    "every-8z-type": _every_8z_type,
    "no-8z-type": _no_8z_type,
    "taxable-state-refund": _taxable_state_refund,
    "state-refund-absorbed-by-cap": _state_refund_absorbed_by_cap,
    "se-health-insurance": _se_health_insurance,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
