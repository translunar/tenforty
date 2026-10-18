"""Schedule C emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers the declared Schedule C cells sch_c_battery and emit_battery_sch_se
leave uncovered: 2021, the Part II lines no other row sets (insurance,
utilities, depreciation, other expenses with their Part V row and line 48),
line B's business code, a loss (box 32a), and a business with no line A
description. Every scenario runs in every year 2021-2025.

All identities and amounts are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.models import Scenario, ScheduleCBusiness
from tests.fixtures.sch_c_battery import _build, _w2

YEARS = (2021, 2022, 2023, 2024, 2025)


def _every_expense_line(year):
    # Every modeled Part II category except supplies (line 22's nothing
    # state); stated-mode depreciation for line 13.
    return _build(year, [ScheduleCBusiness(
        description="Example Cartography Studio", business_code="541990",
        gross_receipts=90_000.0, advertising=500.0, insurance=1_200.0,
        legal_professional=800.0, office_expense=300.0, rent_lease=6_000.0,
        taxes_licenses=250.0, travel=900.0, deductible_meals=400.0,
        utilities=1_100.0, wages=12_000.0, other_expenses=700.0,
        other_expenses_description="Software subscriptions",
        depreciation=1_500.0,
        acknowledges_depreciation_stated_outside_macrs=True)])


def _at_risk_loss(year):
    # Expenses exceed receipts: line 32 is answered, box 32a.
    scenario = _build(year, [ScheduleCBusiness(
        description="Example Pottery Kiln", gross_receipts=10_000.0,
        supplies=15_000.0)],
        w2s=[_w2("Example Employer", 60_000.0)])
    scenario.config = dataclasses.replace(
        scenario.config, acknowledges_sch_c_all_investment_at_risk=True)
    return scenario


def _unnamed_business(year):
    # Line A blank: no description is given. The W-2 keeps the return on
    # the native path (no-W-2 returns route to the workbook).
    return _build(year, [ScheduleCBusiness(
        gross_receipts=20_000.0, supplies=500.0)],
        w2s=[_w2("Example Employer", 60_000.0)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "every-expense-line": _every_expense_line,
    "at-risk-loss": _at_risk_loss,
    "unnamed-business": _unnamed_business,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
