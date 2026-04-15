"""IRS Pub 946 MACRS depreciation tables (hand-keyed, verbatim).

Year-stable: these percentages are statutory (IRC §168) and have not
changed since promulgation. Encoded as literals so the set is
reviewable against the source PDF cell-by-cell. Algorithmic
regeneration + diff lives in forms.depreciation.table_generator
(run under @pytest.mark.oracle).

Every cell below was transcribed from the 2025 edition of IRS Pub 946
Appendix A (Tables A-1 page 71, A-6 page 73, A-7a page 74). The
generator is a cross-check against gross keying bugs; Pub 946 is the
sole source of truth when they disagree.

Scope: v1 covers recovery classes used by 2025 scenarios.

  - TABLE_A_1: GDS, 200%-DB, half-year convention
      (3, 5, 7, 10, 15, 20-year)
  - TABLE_A_6: GDS, straight-line, mid-month
      (27.5-year residential rental)
  - TABLE_A_7a: GDS, straight-line, mid-month
      (39-year nonresidential real property)

Tables A-2 / A-3 (150%-DB, SL alt), A-4 / A-5 (mid-quarter 200%-DB),
A-8..A-20 (ADS, nonres pre-5/13/1993, etc.) are NOT encoded in v1;
add them when a scenario needs them. `_lookup_percentage` in macrs.py
raises NotImplementedError for conventions not represented here.
"""

# --- TABLE A-1: half-year convention, 200%-DB (3/5/7/10) or 150%-DB (15/20) ---
# Shape: {recovery_class: {recovery_year: decimal_percentage}}
# Lookup: TABLE_A_1[cls][year]
# Iterate:  TABLE_A_1["5-year"].items()  / sum(TABLE_A_1["5-year"].values())
#
# 3/5/7/10/15-year are published to 4 decimal places (percent/100).
# 20-year is published to 3 decimal places of percent, i.e. 5 decimals
# of the percent/100 fraction — so it's encoded with 5-place precision
# to preserve Pub 946's 4.462/4.461 alternation exactly.
TABLE_A_1: dict[str, dict[int, float]] = {
    "3-year": {
        1: 0.3333,
        2: 0.4445,
        3: 0.1481,
        4: 0.0741,
    },
    "5-year": {
        1: 0.2000,
        2: 0.3200,
        3: 0.1920,
        4: 0.1152,
        5: 0.1152,
        6: 0.0576,
    },
    "7-year": {
        1: 0.1429,
        2: 0.2449,
        3: 0.1749,
        4: 0.1249,
        5: 0.0893,
        6: 0.0892,
        7: 0.0893,
        8: 0.0446,
    },
    "10-year": {
        1: 0.1000,
        2: 0.1800,
        3: 0.1440,
        4: 0.1152,
        5: 0.0922,
        6: 0.0737,
        7: 0.0655,
        8: 0.0655,
        9: 0.0656,
        10: 0.0655,
        11: 0.0328,
    },
    "15-year": {
        1: 0.0500,
        2: 0.0950,
        3: 0.0855,
        4: 0.0770,
        5: 0.0693,
        6: 0.0623,
        7: 0.0590,
        8: 0.0590,
        9: 0.0591,
        10: 0.0590,
        11: 0.0591,
        12: 0.0590,
        13: 0.0591,
        14: 0.0590,
        15: 0.0591,
        16: 0.0295,
    },
    "20-year": {
        # Pub 946 alternates 4.462 / 4.461 in years 9-20 so the column
        # sums to exactly 100.000%. Preserved verbatim below.
        1: 0.03750,
        2: 0.07219,
        3: 0.06677,
        4: 0.06177,
        5: 0.05713,
        6: 0.05285,
        7: 0.04888,
        8: 0.04522,
        9: 0.04462,
        10: 0.04461,
        11: 0.04462,
        12: 0.04461,
        13: 0.04462,
        14: 0.04461,
        15: 0.04462,
        16: 0.04461,
        17: 0.04462,
        18: 0.04461,
        19: 0.04462,
        20: 0.04461,
        21: 0.02231,
    },
}

# --- TABLE A-6: residential rental real property (27.5-year, mid-month, SL) ---
# Shape: {recovery_class: {recovery_year: {month_placed_in_service: decimal}}}
# Lookup: TABLE_A_6[cls][year][month]
#
# Pub 946 publishes this table such that depreciation for property
# placed in months 1-6 terminates in year 28 (year 29 row is blank);
# for months 7-12 it terminates in year 29. Middle years (2-27) use
# 3.636 for some rows and 3.637 for others in an alternating pattern
# so each column sums to exactly 100.000%.

# Year 1 — month vector from Pub 946 Table A-6 row 1.
_A6_YEAR1 = [
    0.03485, 0.03182, 0.02879, 0.02576, 0.02273, 0.01970,
    0.01667, 0.01364, 0.01061, 0.00758, 0.00455, 0.00152,
]
# Year 28 — months 1-6 terminate with partials; months 7-12 get the
# final full-rate year.
_A6_YEAR28 = [
    0.01970, 0.02273, 0.02576, 0.02879, 0.03182, 0.03485,
    0.03636, 0.03636, 0.03636, 0.03636, 0.03636, 0.03636,
]
# Year 29 — blank for months 1-6 (already terminated in year 28);
# months 7-12 get the final-year partials (Pub 946 Table A-6 row 29).
_A6_YEAR29 = [
    0.00000, 0.00000, 0.00000, 0.00000, 0.00000, 0.00000,
    0.00152, 0.00455, 0.00758, 0.01061, 0.01364, 0.01667,
]


def _build_table_a_6() -> dict[str, dict[int, dict[int, float]]]:
    """Expand the compact Pub 946 Table A-6 into a full year × month grid.

    Years 2-9 are 3.636 flat. Years 10-27 alternate by parity —
    even rows (10, 12, 14, ...) use 3.637 for months 1-6 and 3.636 for
    months 7-12; odd rows (11, 13, ...) flip that pattern. This is the
    column-balancing IRS uses so each month column sums to 100.000%.
    """
    out: dict[int, dict[int, float]] = {}
    out[1] = {m: _A6_YEAR1[m - 1] for m in range(1, 13)}
    for year in range(2, 10):
        out[year] = {m: 0.03636 for m in range(1, 13)}
    for year in range(10, 28):
        if year % 2 == 0:
            mo_1_6, mo_7_12 = 0.03637, 0.03636
        else:
            mo_1_6, mo_7_12 = 0.03636, 0.03637
        out[year] = {
            m: (mo_1_6 if m <= 6 else mo_7_12) for m in range(1, 13)
        }
    out[28] = {m: _A6_YEAR28[m - 1] for m in range(1, 13)}
    out[29] = {m: _A6_YEAR29[m - 1] for m in range(1, 13)}
    return {"27.5-year": out}


TABLE_A_6: dict[str, dict[int, dict[int, float]]] = _build_table_a_6()

# --- TABLE A-7a: nonresidential real property (39-year, mid-month, SL) ---
# Shape: {recovery_class: {recovery_year: {month_placed_in_service: decimal}}}
#
# Simpler than A-6: year 1 partial, 38 full middle years at 2.564,
# year 40 complementary partial. Columns sum to 100.000%.
_A7a_YEAR1 = [
    0.02461, 0.02247, 0.02033, 0.01819, 0.01605, 0.01391,
    0.01177, 0.00963, 0.00749, 0.00535, 0.00321, 0.00107,
]
_A7a_YEAR40 = [
    0.00107, 0.00321, 0.00535, 0.00749, 0.00963, 0.01177,
    0.01391, 0.01605, 0.01819, 0.02033, 0.02247, 0.02461,
]


def _build_table_a_7a() -> dict[str, dict[int, dict[int, float]]]:
    out: dict[int, dict[int, float]] = {}
    out[1] = {m: _A7a_YEAR1[m - 1] for m in range(1, 13)}
    for year in range(2, 40):
        out[year] = {m: 0.02564 for m in range(1, 13)}
    out[40] = {m: _A7a_YEAR40[m - 1] for m in range(1, 13)}
    return {"39-year": out}


TABLE_A_7a: dict[str, dict[int, dict[int, float]]] = _build_table_a_7a()
