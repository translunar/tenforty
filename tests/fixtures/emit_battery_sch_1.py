"""Schedule 1 emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers the Schedule 1 line 8z cells no other row sets: one Form 1099-G
type (its caption in the 8z write-in), several types (the write-in reads
"See statement" and the statement attaches), and a Form 1099-G with no 8z
type (line 8z and 9 absent). Every scenario runs in every year 2021-2025.

All identities and amounts are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import FilingStatus, Form1099G, Scenario
from tests.fixtures.spine_battery import build_wages_only

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


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "one-8z-type": _one_8z_type,
    "every-8z-type": _every_8z_type,
    "no-8z-type": _no_8z_type,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
