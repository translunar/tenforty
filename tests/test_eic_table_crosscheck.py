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

A footnoted bin is split in the CSV only for its marked column: every other
column printed one value for the whole $50 bin, so it is checked at the
printed bin's midpoint.
"""
import math
import unittest
from collections import defaultdict

from tenforty.eic_table import load_table
from tenforty.params.federal import load as load_params

YEARS = (2025,)
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


def mismatches(year: int) -> list[tuple]:
    params = load_params(year)
    out = []
    for column, status in COLUMNS.items():
        for lo, hi, printed in _printed_bins(load_table(year), column):
            if lo <= params.eic_earned_income_amount < hi:
                expected = params.eic_max_credit
            else:
                expected = _half_up(_formula(params, status, (lo + hi) / 2))
            if printed != expected:
                out.append((year, column, lo, hi, printed, expected))
    return out


class EicTableCrosscheckTests(unittest.TestCase):

    def test_every_zero_child_cell_matches_the_attested_params(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(mismatches(year), [])

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
