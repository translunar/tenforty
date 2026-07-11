# tenforty/tax_table.py
"""Published tax-table lookup (Layer-2 oracle asset, and — below $100k —
the federal production tax method).

The Form 1040 instructions direct filers with taxable income under
$100,000 to use the Tax Table, not the rate schedule; the two differ by a
few dollars because each table bin carries the tax at the bin midpoint.
tax_from_table reproduces exactly what a filer reads off the published
page. The CSV assets are ingested from the official PDFs by
scripts/ingest_tax_table.py and cross-validated against the params rate
schedules by tests/test_tax_table_oracle.py.
"""
import csv
import functools
from bisect import bisect_right
from pathlib import Path

from tenforty.models import FilingStatus

_ASSETS = Path(__file__).parent.parent / "assets" / "tax_tables"

# The published tables cover taxable income strictly below this.
TABLE_CEILING = 100_000

_COLUMN_BY_STATUS: dict[FilingStatus, str] = {
    FilingStatus.SINGLE: "single",
    FilingStatus.MARRIED_JOINTLY: "mfj",
    # The table's MFJ column is headed "Married filing jointly (or
    # Qualifying surviving spouse)".
    FilingStatus.QUALIFYING_WIDOW: "mfj",
    FilingStatus.MARRIED_SEPARATELY: "mfs",
    FilingStatus.HEAD_OF_HOUSEHOLD: "hoh",
}


@functools.cache
def load_table(jurisdiction: str, year: int) -> tuple[tuple[int, int, dict[str, int]], ...]:
    path = _ASSETS / jurisdiction / f"{year}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No {jurisdiction} tax-table asset for {year} at {path}; "
            f"run scripts/ingest_tax_table.py (see the add-tax-year runbook)")
    rows: list[tuple[int, int, dict[str, int]]] = []
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            rows.append((
                int(row["lower"]), int(row["upper"]),
                {k: int(row[k]) for k in ("single", "mfj", "mfs", "hoh")},
            ))
    return tuple(rows)


def tax_from_table(taxable_income: float, year: int,
                   filing_status: FilingStatus) -> int:
    if not 0 <= taxable_income < TABLE_CEILING:
        raise ValueError(
            f"Tax Table covers $0-{TABLE_CEILING:,}; got {taxable_income} — "
            f"use the rate schedule (tax_from_schedule) at or above")
    rows = load_table("federal", year)
    lowers = [r[0] for r in rows]
    idx = bisect_right(lowers, taxable_income) - 1
    lower, upper, taxes = rows[idx]
    return taxes[_COLUMN_BY_STATUS[filing_status]]
