"""Algorithmic MACRS table generator (Pub 946 formulas).

Produces the same {key: pct} dicts as forms.depreciation.tables but
derived from first principles. An oracle test
(tests/test_depreciation_table_generator.py) diffs every cell against
the hand-keyed literals, so a bug in either source is caught.

Methods implemented:
  - 200%-declining-balance switching to straight-line, half-year
    convention (TABLE A-1)
  - Straight-line, mid-month convention, 27.5-year (TABLE A-6)
  - Straight-line, mid-month convention, 39-year (TABLE A-7a)

Not implemented: 150%-DB (A-2/A-3), mid-quarter (A-4/A-5), ADS.
"""

import math

from tenforty.rounding import round4, round5


# ---- TABLE A-1: 200%-DB switching to SL, half-year convention ----

_A1_CLASSES = {
    "3-year": 3,
    "5-year": 5,
    "7-year": 7,
    "10-year": 10,
    "15-year": 15,
    "20-year": 20,
}

# 200%-DB for 3/5/7/10-year; 150%-DB for 15/20-year (per §168(b)(2))
_A1_DB_FACTOR = {
    "3-year": 2.0,
    "5-year": 2.0,
    "7-year": 2.0,
    "10-year": 2.0,
    "15-year": 1.5,
    "20-year": 1.5,
}


def _half_year_schedule(recovery_period: int, db_factor: float) -> list[float]:
    """Generate N+1 years of half-year-convention MACRS percentages.

    Year 1 and year N+1 get a half-year of depreciation; years 2..N are
    full years. Each year uses max(DB rate, SL-on-remaining-basis), and
    when SL-on-remaining >= DB, we switch to SL for the rest of the
    recovery period. Returns a list of length recovery_period+1.
    """
    percentages = [0.0] * (recovery_period + 1)
    remaining = 1.0
    db_rate = db_factor / recovery_period
    for year in range(1, recovery_period + 2):
        periods_this_year = 0.5 if year == 1 or year == recovery_period + 1 else 1.0
        halves_used_after = (2 * year - 1) if year <= recovery_period else 2 * recovery_period
        halves_remaining_before_this_year = 2 * recovery_period - (halves_used_after - (2 * periods_this_year))
        sl_rate_this_year = (remaining / halves_remaining_before_this_year) * (2 * periods_this_year)
        db_rate_this_year = remaining * db_rate * periods_this_year
        rate_this_year = max(db_rate_this_year, sl_rate_this_year)
        rate_this_year = min(rate_this_year, remaining)
        percentages[year - 1] = rate_this_year
        remaining -= rate_this_year
    return percentages


def generate_table_a_1() -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for cls, period in _A1_CLASSES.items():
        schedule = _half_year_schedule(period, _A1_DB_FACTOR[cls])
        rows: dict[int, float] = {}
        for i, pct in enumerate(schedule, start=1):
            if pct > 0:
                rows[i] = round4(pct)
        out[cls] = rows
    return out


# ---- TABLE A-6 / A-7a: mid-month SL ----

def _mid_month_schedule(recovery_period: float, month_placed: int) -> list[float]:
    """Generate recovery_period+1 years of mid-month SL depreciation.

    Mid-month: asset is treated as placed in service on the 15th of the
    month. In year 1, allowable months = 12 - month_placed + 0.5.
    Straight-line rate = 1 / recovery_period per year. Allowance per
    year = (allowable_months / 12) * rate * remaining basis.
    """
    rate = 1.0 / recovery_period
    first_year_months = 12 - month_placed + 0.5
    first_pct = rate * (first_year_months / 12.0)
    years: list[float] = [first_pct]
    remaining = 1.0 - first_pct
    total_rows = int(math.ceil(recovery_period)) + 1
    for _ in range(2, total_rows):
        yr_pct = min(rate, remaining)
        years.append(yr_pct)
        remaining -= yr_pct
    years.append(max(0.0, remaining))
    return years


def generate_table_a_6() -> dict[str, dict[int, dict[int, float]]]:
    years: dict[int, dict[int, float]] = {}
    for month in range(1, 13):
        schedule = _mid_month_schedule(27.5, month)
        for i, pct in enumerate(schedule, start=1):
            years.setdefault(i, {})[month] = round5(pct)
    return {"27.5-year": years}


def generate_table_a_7a() -> dict[str, dict[int, dict[int, float]]]:
    years: dict[int, dict[int, float]] = {}
    for month in range(1, 13):
        schedule = _mid_month_schedule(39.0, month)
        for i, pct in enumerate(schedule, start=1):
            years.setdefault(i, {})[month] = round5(pct)
    return {"39-year": years}
