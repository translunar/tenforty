"""IRS Pub 946 MACRS depreciation tables (hand-keyed, verbatim).

Year-stable: these percentages are statutory (IRC §168) and have not
changed since promulgation. Encoded as literals so the set is
reviewable against the source PDF cell-by-cell. Algorithmic
regeneration + diff lives in forms.depreciation.table_generator
(run under @pytest.mark.oracle).

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

# --- TABLE A-1: half-year convention, 200%-DB switching to SL ---
# Shape: {recovery_class: {recovery_year: decimal_percentage}}
# Lookup: TABLE_A_1[cls][year]
# Iterate:  TABLE_A_1["5-year"].items()  / sum(TABLE_A_1["5-year"].values())
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
        1: 0.0375,
        2: 0.0722,
        3: 0.0668,
        4: 0.0618,
        5: 0.0571,
        6: 0.0528,
        7: 0.0489,
        8: 0.0452,
        9: 0.0447,
        10: 0.0447,
        11: 0.0446,
        12: 0.0446,
        13: 0.0446,
        14: 0.0446,
        15: 0.0446,
        16: 0.0446,
        17: 0.0446,
        18: 0.0446,
        19: 0.0446,
        20: 0.0446,
        21: 0.0223,
    },
}

# --- TABLE A-6: residential rental real property (27.5-year, mid-month, SL) ---
# Shape: {recovery_class: {recovery_year: {month_placed_in_service: decimal}}}
# Lookup: TABLE_A_6[cls][year][month]
# Year 1 percentages (month 1..12, from Pub 946):
_A6_YEAR1 = [
    0.03485, 0.03182, 0.02879, 0.02576, 0.02273, 0.01970,
    0.01667, 0.01364, 0.01061, 0.00758, 0.00455, 0.00152,
]
# Year 29 percentages (the final partial year; mirror of year 1):
_A6_YEAR29 = [
    0.01970, 0.02273, 0.02576, 0.02879, 0.03182, 0.03485,
    # Months 7..12 use year 28 continuation at 3.636% — per Pub 946.
    0.00000, 0.00000, 0.00000, 0.00000, 0.00000, 0.00000,
]


def _build_table_a_6() -> dict[str, dict[int, dict[int, float]]]:
    out: dict[int, dict[int, float]] = {}
    out[1] = {m: _A6_YEAR1[m - 1] for m in range(1, 13)}
    for year in range(2, 29):
        out[year] = {m: 0.03636 for m in range(1, 13)}
    out[29] = {m: _A6_YEAR29[m - 1] for m in range(1, 13)}
    return {"27.5-year": out}


TABLE_A_6: dict[str, dict[int, dict[int, float]]] = _build_table_a_6()

# --- TABLE A-7a: nonresidential real property (39-year, mid-month, SL) ---
# Shape: {recovery_class: {recovery_year: {month_placed_in_service: decimal}}}
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
