"""Schedule SE emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Adds the year sch_c_battery does not cover (2021), and the reachable half of
line 4c's $400 boundary: a return under $400 of net SE earnings files NO
Schedule SE (the manifest row's form set pins the non-emission).

Not here yet: an at-or-above-wage-base row. On that branch line 8a says
"skip lines 8b through 10", so 8d, 9 and 10 print nothing; that row arrives
with the sch-se-skip-branch-blanks lane, whose fix makes their nothing
state reachable.

All identities and amounts are fully synthetic.
"""
from collections.abc import Callable

from tenforty.models import Form1099INT, Scenario, ScheduleCBusiness
from tests.fixtures.sch_c_battery import _build, _w2

YEARS = (2021,)


def _sole_trade(year):
    return _build(year, [ScheduleCBusiness(
        description="Example Bookbinding", gross_receipts=48_000.0,
        supplies=900.0, office_expense=400.0)])


def _day_job_plus_sideline(year):
    # W-2 social security wages below the wage base: line 8a carries a
    # value and line 9 a remainder.
    return _build(year, [ScheduleCBusiness(
        description="Example Tutoring", gross_receipts=30_000.0,
        supplies=600.0)],
        w2s=[_w2("Example Employer", 60_000.0)])


def _under_400_sideline(year):
    # Net SE earnings under $400 (line 4c stop): no Schedule SE is filed.
    # Taxable interest keeps a no-W-2 filer clear of the EIC routing gate.
    scenario = _build(year, [ScheduleCBusiness(
        description="Example Seedlings", gross_receipts=1_000.0,
        supplies=700.0)])
    scenario.form1099_int = [
        Form1099INT(payer="Example Bank", interest=30_000.00)]
    return scenario


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "sole-trade": _sole_trade,
    "day-job-plus-sideline": _day_job_plus_sideline,
    "under-400-sideline": _under_400_sideline,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
