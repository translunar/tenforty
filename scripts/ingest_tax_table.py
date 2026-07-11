# scripts/ingest_tax_table.py
"""Parse a published IRS/FTB tax-table PDF into a CSV asset.

Output schema: lower,upper,single,mfj,mfs,hoh — one row per bin, lower
inclusive, upper exclusive, integer dollars. Federal source rows carry
four tax columns (Single, MFJ, MFS, HoH — QSS uses the MFJ column per
the table header). FTB source rows carry three (Single/MFS, MFJ/QSS,
HoH); they are expanded to the same four-column schema (mfs = the
single/MFS column) so one loader serves both jurisdictions.

Why coordinates, not `-layout` text: the real tables lay THREE side-by-side
table blocks per visual line, and `pdftotext -layout` renders the narrow
sub-$25 federal bins as vertically stacked fragments whose arrangement
differs from year to year (2024 stacks the [5,15)/[15,25) bins; 2025 stacks
the [0,5)/[5,15) bins). No whole-text regex can reassemble that reliably.
So we parse `pdftotext -bbox` word coordinates: cluster words into physical
rows by y, then walk each row left-to-right by x, greedily consuming clean
bin groups and skipping stray numbers (section labels like "1,000", the
"$100,000 or over" trailer, filing-status header digits). The EIC table and
the Tax Computation Worksheet are excluded at the page level.

The sanity checks are deliberately strict: full [0, ceiling) coverage with
no gaps or overlaps, per-column monotonicity, plausible magnitudes. A
garbled parse cannot produce a passing CSV. If sanity_check fails, the fix
is in parsing or the source PDF — never hand-edit the CSV.

Usage:
    python scripts/ingest_tax_table.py --jurisdiction federal --year 2025
    python scripts/ingest_tax_table.py --jurisdiction california --year 2024
"""
import argparse
import csv
import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_ASSETS = _REPO_ROOT / "assets" / "tax_tables"

# IRS and FTB tables both cover taxable income up to $100,000. (Federal bins
# are strictly "less than $100,000"; the FTB top bin is inclusive of exactly
# $100,000 — see normalize_california for how that maps to the same ceiling.)
CEILING = 100_000

# pdftotext -bbox emits one <word> per token with its bounding box.
_WORD_RE = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
    r'xMax="[\d.]+" yMax="[\d.]+">([^<]*)</word>'
)
# A numeric cell: optional leading '$' then digits/commas (e.g. "$1", "2,795").
# Anything with a stray '-', '.', '%' or letters (prose, worksheet math, the
# "$25,300-25,350" sample caption) is NOT a cell and is ignored.
_NUM_RE = re.compile(r"\$?([\d,]+)")

# Pages carrying these markers are NOT the Tax Table (the standalone Tax
# Computation Worksheet page lacks "Tax Table" and is excluded by the positive
# marker below; the "$100,000 or over — use the Tax Computation Worksheet"
# trailer sits ON the last tax page, so we must NOT exclude on that phrase).
_EXCLUDE_MARKERS = ("Earned Income Credit", "EIC")
_INCLUDE_MARKER = "Tax Table"

# A row's y-coordinates within this many points are one physical line. Real
# row pitch is ~7pt, so this cleanly separates rows while tolerating the tiny
# baseline jitter between side-by-side blocks.
_ROW_TOL = 3.0

# Plausible bin width in dollars. Federal bins run 5..50 wide, FTB 49/99 wide;
# this rejects the narrow (lower, upper) windows produced by header digits
# (e.g. "1 or 3 2 or 5 4" -> a candidate (1, 3)) during greedy resync.
_MIN_WIDTH = 5
_MAX_WIDTH = 200


def _to_int(token: str) -> int:
    return int(token.replace(",", ""))


def _numeric(text: str):
    """Return the integer value of a numeric cell token, else None."""
    m = _NUM_RE.fullmatch(text.strip())
    return int(m.group(1).replace(",", "")) if m else None


def _valid_bin(group: tuple) -> bool:
    """A (lower, upper, *taxes) group that looks like a real income bin."""
    lower, upper = group[0], group[1]
    if not (0 <= lower < upper <= CEILING):
        return False
    return _MIN_WIDTH <= upper - lower <= _MAX_WIDTH


def _cluster_rows(words):
    """Group (x, y, text) words into physical rows by y (within _ROW_TOL)."""
    rows = []
    current = []
    anchor = None
    for x, y, text in sorted(words, key=lambda w: (w[1], w[0])):
        if anchor is None or abs(y - anchor) <= _ROW_TOL:
            if anchor is None:
                anchor = y
            current.append((x, text))
        else:
            rows.append(current)
            current = [(x, text)]
            anchor = y
    if current:
        rows.append(current)
    return rows


def parse_rows(words, columns: int) -> list[tuple[int, ...]]:
    """Extract real bin rows from positioned words.

    `words` is an iterable of (x, y, text) tuples (one page of `pdftotext
    -bbox` output). Words are clustered into physical rows by y; within each
    row the numeric cells are read left-to-right and greedily grouped into
    `columns`-wide bins. A leading token that cannot start a valid bin (a
    section label, a trailer number, a header digit) is skipped and the walk
    resyncs — so noise glued onto a real row's line does not drop the row.
    """
    result: list[tuple[int, ...]] = []
    for row in _cluster_rows(words):
        values = [
            v for v in (_numeric(text) for _, text in sorted(row, key=lambda c: c[0]))
            if v is not None
        ]
        i, n = 0, len(values)
        while i + columns <= n:
            group = tuple(values[i:i + columns])
            if _valid_bin(group):
                result.append(group)
                i += columns
            else:
                i += 1
    return result


def normalize_california(raw_rows: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    """Map FTB (lower, upper_inclusive, col1, col2, col3) rows to the
    [lower, upper) four-column schema (single, mfj, mfs, hoh).

    Convention (settled):
    - Add 1 to every published (inclusive) upper so it becomes an exclusive
      upper: ($1–$50) -> [1, 51), ($6451–$6550) -> [6451, 6551). The top
      published bin is $99,951–$100,000 (income up to AND INCLUDING $100,000,
      unlike the federal strictly-"less-than" bins); its +1 would overshoot,
      so the maximum upper is clamped to CEILING, giving [99951, 100000) — the
      table's top exclusive upper IS the ceiling.
    - Extend the first bin's lower from 1 down to 0 (there is no published $0
      row) keeping that bin's published cells, so coverage starts at 0. Those
      cells MUST be $0 — a $0-income lookup must return $0 tax; a nonzero value
      means a misparse, so raise rather than fabricate.
    - FTB columns -> schema: single=col1, mfj=col2, mfs=col1 (CA MFS uses the
      single table), hoh=col3.
    """
    rows = sorted(set(raw_rows))
    out: list[tuple[int, ...]] = []
    for idx, (lower, upper, col1, col2, col3) in enumerate(rows):
        new_lower = 0 if idx == 0 else lower
        new_upper = min(upper + 1, CEILING)
        out.append((new_lower, new_upper, col1, col2, col1, col3))
    first = out[0]
    if not (first[2] == first[3] == first[4] == first[5] == 0):
        raise ValueError(
            f"California first bin has nonzero tax {first}; a $0-income "
            f"lookup must return $0 tax — refusing to fabricate"
        )
    return out


def sanity_check(rows: list[tuple[int, ...]], *, ceiling: int) -> None:
    if not rows:
        raise ValueError("No rows parsed")
    rows = sorted(set(rows))
    if rows[0][0] != 0:
        raise ValueError(f"First bin starts at {rows[0][0]}, expected 0")
    if rows[-1][1] != ceiling:
        raise ValueError(f"Last bin ends at {rows[-1][1]}, expected {ceiling}")
    for (a, b) in zip(rows, rows[1:]):
        if a[1] != b[0]:
            raise ValueError(f"Coverage break: bin ending {a[1]} followed by "
                             f"bin starting {b[0]}")
    n_tax_cols = len(rows[0]) - 2
    for col in range(2, 2 + n_tax_cols):
        taxes = [r[col] for r in rows]
        if any(t2 < t1 for t1, t2 in zip(taxes, taxes[1:])):
            raise ValueError(f"Tax column {col} not monotonic")
        # Column-aware magnitude floor (approved plan-defect fix). The
        # "single" column (index 2) is the largest and magnitude-stable
        # across jurisdictions (federal top ~$17k, CA top ~$5.8k), so it
        # keeps the 5%-of-ceiling floor. The other filing-status columns
        # (MFJ/MFS/HoH) are legitimately much lower under wide brackets —
        # California's MFJ/HoH top-bin taxes near $100k are genuinely sub-$5k
        # (CA 2024 MFJ $3,154, HoH $3,871) — so they use a 1%-of-ceiling
        # floor, still catching a zeroed/garbled column. The upper cap
        # catches merged-number garbles for every column.
        floor = ceiling * 0.05 if col == 2 else ceiling * 0.01
        if taxes[-1] > ceiling * 0.5 or taxes[-1] < floor:
            raise ValueError(f"Tax column {col} top value {taxes[-1]} "
                             f"implausible for ceiling {ceiling}")


def _pdftotext(pdf: Path) -> str:
    """Return pdftotext -bbox output (per-word bounding boxes as XML)."""
    return subprocess.run(
        ["pdftotext", "-bbox", str(pdf), "-"],
        check=True, capture_output=True, text=True,
    ).stdout


def _iter_tax_pages(bbox_html: str):
    """Yield the positioned words of each Tax Table page, one page at a time.

    Excludes the EIC Table and the standalone Tax Computation Worksheet page.
    Parsing per page (never merging pages) is essential: identical y values on
    different pages would otherwise cluster together and interleave.
    """
    for chunk in re.split(r"<page\b", bbox_html)[1:]:
        words = [(float(x), float(y), text)
                 for x, y, text in _WORD_RE.findall(chunk)]
        page_text = " ".join(w[2] for w in words)
        if any(mark in page_text for mark in _EXCLUDE_MARKERS):
            continue
        if _INCLUDE_MARKER not in page_text:
            continue
        yield words


def ingest(jurisdiction: str, year: int) -> Path:
    if jurisdiction == "federal":
        source = _REPO_ROOT / "pdfs" / "federal" / str(year) / "i1040tt.pdf"
        rows: list[tuple[int, ...]] = []
        for words in _iter_tax_pages(_pdftotext(source)):
            rows.extend(parse_rows(words, columns=6))
        normalized = sorted(set(rows))
    elif jurisdiction == "california":
        source = _REPO_ROOT / "pdfs" / "california" / str(year) / "tax_table.pdf"
        raw: list[tuple[int, ...]] = []
        for words in _iter_tax_pages(_pdftotext(source)):
            raw.extend(parse_rows(words, columns=5))
        normalized = sorted(set(normalize_california(raw)))
    else:
        raise ValueError(f"Unknown jurisdiction {jurisdiction!r}")

    sanity_check(normalized, ceiling=CEILING)

    out = _ASSETS / jurisdiction / f"{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["lower", "upper", "single", "mfj", "mfs", "hoh"])
        writer.writerows(normalized)
    print(f"Wrote {len(normalized)} bins to {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction", required=True,
                        choices=("federal", "california"))
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
    ingest(args.jurisdiction, args.year)


if __name__ == "__main__":
    main()
