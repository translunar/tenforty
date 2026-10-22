# tenforty/eic_table.py
"""Published Earned Income Credit (EIC) Table lookup — the production
method for the credit amount (childless-EITC spec §5.3, ruling Q5: the
table is the method, the params formula is the cross-check).

A filer reads the credit off the table for the amount the EIC Worksheet
says to look up (earned income, and AGI where the worksheet directs). The
CSV assets are ingested from the official booklet with provenance by
scripts/ingest_eic_table.py and cross-validated against the attested params
by tests/test_eic_table_crosscheck.py.
"""
import csv
import functools
from bisect import bisect_right
from pathlib import Path

from tenforty.models import FilingStatus

_ASSETS = Path(__file__).parent.parent / "assets" / "eic_tables"

# The table's Single column is headed "Single, head of household, or
# qualifying surviving spouse"; its other column "Married filing jointly".
_COLUMN_BY_STATUS: dict[FilingStatus, str] = {
    FilingStatus.SINGLE: "single",
    FilingStatus.HEAD_OF_HOUSEHOLD: "single",
    FilingStatus.QUALIFYING_WIDOW: "single",
    FilingStatus.MARRIED_FILING_JOINTLY: "mfj",
}


@functools.cache
def load_table(year: int) -> tuple[tuple[int, int, dict[str, int]], ...]:
    path = _ASSETS / f"{year}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No EIC-table asset for {year} at {path}; run "
            f"scripts/ingest_eic_table.py --year {year}")
    with open(path, newline="") as fh:
        return tuple(
            (int(row.pop("lower")), int(row.pop("upper")),
             {k: int(v) for k, v in row.items()})
            for row in csv.DictReader(fh))


def eic_from_table(amount: float, year: int, filing_status: FilingStatus,
                   children: int = 0) -> int:
    """The credit the year's EIC Table prints for ``amount``. At or above
    the table's top an amount reads the last bin, which the ingest sanity
    check pins to 0 in every column (each has run out there). An amount
    below the first bin is not a table lookup: the caller decides (no
    earned income → no credit)."""
    if filing_status not in _COLUMN_BY_STATUS:
        raise ValueError(f"the EIC Table has no column for {filing_status}")
    if not 0 <= children <= 3:
        raise ValueError(f"children must be 0-3 (3 = three or more); "
                         f"got {children}")
    rows = load_table(year)
    if amount < rows[0][0]:
        raise ValueError(f"the {year} EIC Table starts at {rows[0][0]}; "
                         f"got {amount}")
    idx = bisect_right([r[0] for r in rows], amount) - 1
    return rows[idx][2][f"{_COLUMN_BY_STATUS[filing_status]}_{children}"]
