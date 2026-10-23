"""Cross-check: every zero-child cell of each ingested EIC Table against the
attested params (childless-EITC spec §5.3; ruling R-T1). The table is the
production method; this proves the ingested table and the independently
attested params describe the same credit.

Construction rule (ruling R-T1): "observed construction, exhaustively
verified TY2025 (both statuses + all child columns); no published
construction rule exists in Rev. Proc. 2024-40 / i1040gi / Pub. 596."
  expected(bin) = round half-up of the §32 formula at the bin's midpoint,
  the credit capped at the published max credit — EXCEPT the one bin that
  contains eic_earned_income_amount, which prints the published max credit.
The exception is keyed off that params field, never off whichever bin
mismatches, so it cannot absorb an ingest error. A mismatch anywhere else is
a red routed to team-lead, not a new exception.

Adjudicated divergences (ruling R-S8-9): IRC §32(f) — the credit is
determined under the Secretary's tables — so where the print departs from
R-T1 the print governs, pinned as a FROZEN per-year list (PINNED_DIVERGENCES),
each bin exactly $1 from R-T1 with its sign written out (R-S8-18).
(An unrounded max-credit base explains 2023 but not 2024/2025: a model
only.)

A footnoted bin is split in the CSV only for its marked column: every other
column printed one value for the whole $50 bin, so it is checked at the
printed bin's midpoint.
"""
import math
import unittest
from collections import defaultdict

from tenforty.eic_table import load_table
from tenforty.params.federal import load as load_params

YEARS = (2022, 2023, 2024, 2025)
COLUMNS = {"single_0": "single", "mfj_0": "married_filing_jointly"}


def _formula(params, status: str, amount: float) -> float:
    credit = min(params.eic_credit_pct * amount, params.eic_max_credit)
    over = max(0.0, amount - params.eic_phaseout_threshold[status])
    return max(0.0, credit - params.eic_phaseout_pct * over)


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _printed_bins(rows, column: str):
    """(lower, upper, printed value) per bin as the column printed it:
    split rows rejoin unless this column is the one the footnote split."""
    groups = defaultdict(list)
    for lo, hi, cells in rows:
        groups[lo // 50].append((lo, hi, cells[column]))
    for parts in groups.values():
        if len({v for _, _, v in parts}) == 1:
            yield parts[0][0], parts[-1][1], parts[0][2]
        else:
            yield from parts


def _expected(params, status: str, lo: int, hi: int) -> int:
    """R-T1 for one printed bin."""
    if lo <= params.eic_earned_income_amount < hi:
        return params.eic_max_credit
    return _half_up(_formula(params, status, (lo + hi) / 2))


def mismatches(year: int) -> list[tuple]:
    params = load_params(year)
    out = []
    for column, status in COLUMNS.items():
        for lo, hi, printed in _printed_bins(load_table(year), column):
            expected = _expected(params, status, lo, hi)
            if printed != expected:
                out.append((year, column, lo, hi, printed, expected))
    return out


# Ruling R-S8-9: year -> (column, bin lower bound, printed credit) for every
# bin where the published table prints $1 below R-T1. Written out from the
# adjudicated ingest; NEVER recomputed (a re-ingest shift must go red).
PINNED_DIVERGENCES: dict[int, frozenset[tuple[str, int, int, int]]] = {
    # (column, bin lower bound, printed credit, printed - R-T1), delta in
    # exactly {-1, +1} (ruling R-S8-18).
    2022: frozenset({
        # [9,150, 9,200) straddles the 9,160 threshold; the print holds the
        # max there (a model only).
        ("single_0", 9150, 560, +1), ("single_0", 11050, 413, -1),
        ("single_0", 13050, 260, -1), ("single_0", 15050, 107, -1),
    }),
    2023: frozenset({
        # single_0: 38 bins
        ("single_0", 9950, 586, -1), ("single_0", 10250, 563, -1),
        ("single_0", 10500, 544, -1), ("single_0", 10550, 540, -1),
        ("single_0", 10800, 521, -1), ("single_0", 11100, 498, -1),
        ("single_0", 11350, 479, -1), ("single_0", 11400, 475, -1),
        ("single_0", 11650, 456, -1), ("single_0", 11700, 452, -1),
        ("single_0", 11950, 433, -1), ("single_0", 12250, 410, -1),
        ("single_0", 12500, 391, -1), ("single_0", 12550, 387, -1),
        ("single_0", 12800, 368, -1), ("single_0", 13100, 345, -1),
        ("single_0", 13350, 326, -1), ("single_0", 13400, 322, -1),
        ("single_0", 13650, 303, -1), ("single_0", 13700, 299, -1),
        ("single_0", 13950, 280, -1), ("single_0", 14250, 257, -1),
        ("single_0", 14500, 238, -1), ("single_0", 14550, 234, -1),
        ("single_0", 14800, 215, -1), ("single_0", 15100, 192, -1),
        ("single_0", 15350, 173, -1), ("single_0", 15400, 169, -1),
        ("single_0", 15650, 150, -1), ("single_0", 15700, 146, -1),
        ("single_0", 15950, 127, -1), ("single_0", 16250, 104, -1),
        ("single_0", 16500, 85, -1), ("single_0", 16550, 81, -1),
        ("single_0", 16800, 62, -1), ("single_0", 17100, 39, -1),
        ("single_0", 17350, 20, -1), ("single_0", 17400, 16, -1),
        # mfj_0: 35 bins
        ("mfj_0", 16650, 576, -1), ("mfj_0", 16900, 557, -1),
        ("mfj_0", 16950, 553, -1), ("mfj_0", 17200, 534, -1),
        ("mfj_0", 17500, 511, -1), ("mfj_0", 17750, 492, -1),
        ("mfj_0", 17800, 488, -1), ("mfj_0", 18050, 469, -1),
        ("mfj_0", 18350, 446, -1), ("mfj_0", 18650, 423, -1),
        ("mfj_0", 18900, 404, -1), ("mfj_0", 18950, 400, -1),
        ("mfj_0", 19200, 381, -1), ("mfj_0", 19500, 358, -1),
        ("mfj_0", 19750, 339, -1), ("mfj_0", 19800, 335, -1),
        ("mfj_0", 20050, 316, -1), ("mfj_0", 20350, 293, -1),
        ("mfj_0", 20650, 270, -1), ("mfj_0", 20900, 251, -1),
        ("mfj_0", 20950, 247, -1), ("mfj_0", 21200, 228, -1),
        ("mfj_0", 21500, 205, -1), ("mfj_0", 21750, 186, -1),
        ("mfj_0", 21800, 182, -1), ("mfj_0", 22050, 163, -1),
        ("mfj_0", 22350, 140, -1), ("mfj_0", 22650, 117, -1),
        ("mfj_0", 22900, 98, -1), ("mfj_0", 22950, 94, -1),
        ("mfj_0", 23200, 75, -1), ("mfj_0", 23500, 52, -1),
        ("mfj_0", 23750, 33, -1), ("mfj_0", 23800, 29, -1),
        ("mfj_0", 24050, 10, -1),
    }),
}


class EicTableCrosscheckTests(unittest.TestCase):

    def test_every_zero_child_cell_matches_the_attested_params(self):
        # Exactly the adjudicated bins mismatch (none outside 2023): a bin
        # entering or leaving the list is a red routed to team-lead.
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    {(c, lo, printed, printed - expected)
                     for _, c, lo, _, printed, expected in mismatches(year)},
                    PINNED_DIVERGENCES.get(year, frozenset()))

    def test_each_pinned_bin_prints_one_off_the_rule(self):
        # Both sides exact: the printed value literally, and R-T1 + delta
        # from the attested params, delta exactly -1 or +1 (R-S8-18) — a
        # moved print, a moved param or a new pattern all fire.
        for year, pinned in sorted(PINNED_DIVERGENCES.items()):
            params = load_params(year)
            for column, lo, printed, delta in sorted(pinned):
                bins = {b_lo: (b_hi, value) for b_lo, b_hi, value in
                        _printed_bins(load_table(year), column)}
                with self.subTest(year=year, column=column, lower=lo):
                    self.assertIn(delta, (-1, 1))
                    hi, value = bins[lo]
                    self.assertEqual(value, printed)
                    self.assertEqual(printed, _expected(
                        params, COLUMNS[column], lo, hi) + delta)

    def test_the_exception_is_exactly_one_bin_per_column(self):
        # The earned-income-amount bin is the ONLY place the rule departs
        # from the midpoint formula; it must exist once per column.
        for year in YEARS:
            params = load_params(year)
            for column in COLUMNS:
                with self.subTest(year=year, column=column):
                    holding = [lo for lo, hi, _ in
                               _printed_bins(load_table(year), column)
                               if lo <= params.eic_earned_income_amount < hi]
                    self.assertEqual(len(holding), 1)

    def test_every_ingested_year_is_crosschecked(self):
        from pathlib import Path
        assets = Path(__file__).resolve().parent.parent / "assets" / "eic_tables"
        self.assertEqual({int(p.stem) for p in assets.glob("*.csv")},
                         set(YEARS))
