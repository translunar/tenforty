"""Schedule SE emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Adds the year sch_c_battery does not cover (2021), and the reachable half of
line 4c's $400 boundary: a return under $400 of net SE earnings files NO
Schedule SE (the manifest row's form set pins the non-emission).

The at-wage-base row ("wage-base-day-job", every year 2021-2025): on that
branch line 8a says "skip lines 8b through 10", so 8d, 9 and 10 print
nothing (sch-se-skip-branch-blanks). It is the one scenario here that runs
in every year (SCENARIO_YEARS); the others run in 2021 only.

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


# Line 8a's skip branch (sch-se-skip-branch-blanks): W-2 Social Security
# wages exactly AT the year's wage base -- the inclusive edge of "If $<base>
# or more, skip lines 8b through 10" -- so 8d, 9 and 10 print nothing. The
# amounts are each year's printed line 8a figure. A small Schedule C keeps
# taxable income under Form 8995's simplified-method limit and wages plus
# SE earnings under Form 8959's threshold.
_WAGE_BASE = {2021: 142_800.0, 2022: 147_000.0, 2023: 160_200.0,
              2024: 168_600.0, 2025: 176_100.0}


def _wage_base_day_job(year):
    return _build(year, [ScheduleCBusiness(
        description="Example Weekend Framing", gross_receipts=8_000.0,
        supplies=500.0)],
        w2s=[_w2("Example Employer", _WAGE_BASE[year])])


# Years a scenario runs in, where they differ from YEARS.
SCENARIO_YEARS: dict[str, tuple[int, ...]] = {
    "wage-base-day-job": (2021, 2022, 2023, 2024, 2025),
}


def years_for(name: str) -> tuple[int, ...]:
    return SCENARIO_YEARS.get(name, YEARS)


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "sole-trade": _sole_trade,
    "day-job-plus-sideline": _day_job_plus_sideline,
    "under-400-sideline": _under_400_sideline,
    "wage-base-day-job": _wage_base_day_job,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
