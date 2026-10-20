"""Schedule B emit battery (emit-verification protocol step 6): scenario
INPUTS only. The harness compares every emit against the real computation,
so no expected value is written here.

Covers the payer rows the single-payer batteries never fill: one scenario
fills every interest and dividend row the year's paper prints (14 interest
rows; 16 dividend rows in 2021, 15 from 2022). Every scenario runs in every
year 2021-2025.

All identities and amounts are fully synthetic.
"""
import dataclasses
from collections.abc import Callable

from tenforty.mappings.pdf_sch_b import dividend_max_rows, interest_max_rows
from tenforty.models import FilingStatus, Form1099DIV, Form1099INT, Scenario
from tests.fixtures.spine_battery import build_wages_only

YEARS = (2021, 2022, 2023, 2024, 2025)


def _full_grid(year):
    # Distinct whole-dollar amounts per row; each total is over $1,500.
    base = build_wages_only(year, FilingStatus.SINGLE)
    return dataclasses.replace(
        base,
        form1099_int=[
            Form1099INT(payer=f"Example Bank {i}", interest=100.0 + i)
            for i in range(1, interest_max_rows(year) + 1)],
        form1099_div=[
            Form1099DIV(payer=f"Example Fund {i}",
                        ordinary_dividends=200.0 + i)
            for i in range(1, dividend_max_rows(year) + 1)])


SCENARIOS: dict[str, Callable[[int], Scenario]] = {
    "full-payer-grid": _full_grid,
}


def build(name: str, year: int) -> Scenario:
    return SCENARIOS[name](year)
