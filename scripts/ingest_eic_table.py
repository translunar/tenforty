# scripts/ingest_eic_table.py
"""Parse a year's published Earned Income Credit (EIC) Table into a CSV asset
with provenance.

Source: the EIC Table pages of pdfs/federal/<year>/i1040tt.pdf (Publication
1040, "Tax and Earned Income Credit Tables" — the same booklet
ingest_tax_table.py reads; that script excludes these pages).

Output assets/eic_tables/<year>.csv: lower,upper,single_0..single_3,
mfj_0..mfj_3 — one row per bin, lower inclusive, upper exclusive, whole
dollars. The table's Single column also serves head of household and
qualifying surviving spouse (its own header). Every column is ingested; the
childless-EIC leg reads only the _0 columns.

Footnoted cells. The bin where a column's credit runs out prints a marker
(*, **, ***) instead of a number; a footnote on the same page splits that
bin: "at least $A but less than $B ... your credit is $C", and "$B or more
... you can't take the credit". The footnote names the child count but not
the filing status: the column is the cell that carries the marker. Such a
bin becomes two rows, [lower, B) and [B, upper), the marked column taking C
then 0 and every other column its printed value in both.

Why -layout text here (ingest_tax_table.py uses -bbox): the EIC table's bins
are uniform $50 rows, two side-by-side blocks of ten cells per printed line,
with no stacked narrow bins. The sanity checks are strict — contiguous
coverage from the first bin to the last, ten cells per block, every marker
resolved by exactly one footnote, each column rising, flat, then falling to
0 — so a garbled parse cannot produce a passing CSV. Never hand-edit the CSV.

Usage:
    python scripts/ingest_eic_table.py --year 2025
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_ASSETS = _REPO_ROOT / "assets" / "eic_tables"
COLUMNS = tuple(f"{status}_{n}" for status in ("single", "mfj")
                for n in range(4))
_CHILDREN = {"no": 0, "one": 1, "two": 2, "three": 3}
_TOKEN = re.compile(r"^(\d{1,3}(?:,\d{3})*|\*{1,3})$")
_FOOTNOTE = re.compile(
    r"(\*{1,3})\s*If the amount you are looking up from the worksheet is at "
    r"least \$([\d,]+) but less than \$([\d,]+), and you have (no|one|two|"
    r"three) qualifying child(?:ren)?\b.*?your credit is \$([\d,]+)\.\s*If "
    r"the amount you are looking up from the worksheet is \$([\d,]+) or more",
    re.S)


def _num(text: str) -> int:
    return int(text.replace(",", ""))


def _pages(source: Path) -> list[str]:
    out = subprocess.run(["pdftotext", "-layout", str(source), "-"],
                         check=True, capture_output=True, text=True).stdout
    pages = out.split("\f")
    return [p for p in pages if "Earned Income Credit (EIC)" in p
            and "This booklet only contains" not in p]


def parse_page(text: str) -> list[tuple[int, int, list]]:
    """Bins on one page, footnote markers resolved: (lower, upper, cells)
    where a split bin yields two entries."""
    footnotes = {}
    for m in _FOOTNOTE.finditer(re.sub(r"\s+", " ", text)):
        marker, at_least, less_than, kids, credit, or_more = m.groups()
        if less_than != or_more:
            raise ValueError(f"footnote {marker}: split points disagree "
                             f"({less_than} vs {or_more})")
        if marker in footnotes:
            raise ValueError(f"footnote {marker} appears twice on one page")
        footnotes[marker] = (_num(at_least), _num(less_than),
                             _CHILDREN[kids], _num(credit))
    bins, used = [], set()
    for line in text.splitlines():
        tokens = line.split()
        if not tokens or not all(_TOKEN.match(t) for t in tokens):
            continue
        if len(tokens) not in (10, 20):
            continue  # the page-1 worked example (6 cells), stray numbers
        for block in (tokens[:10], tokens[10:]):
            if not block:
                continue
            lower, upper = _num(block[0]), _num(block[1])
            cells = [c if c.startswith("*") else _num(c) for c in block[2:]]
            marked = [i for i, c in enumerate(cells) if isinstance(c, str)]
            if not marked:
                bins.append((lower, upper, cells))
                continue
            if len(marked) != 1:
                raise ValueError(f"bin {lower}: {len(marked)} markers")
            col, marker = marked[0], cells[marked[0]]
            if marker not in footnotes:
                raise ValueError(f"bin {lower}: marker {marker} unresolved")
            at_least, split, kids, credit = footnotes[marker]
            if at_least != lower or not lower < split < upper:
                raise ValueError(f"bin {lower}: footnote {marker} covers "
                                 f"[{at_least}, {split}), not this bin")
            if col % 4 != kids:
                raise ValueError(f"bin {lower}: marker {marker} sits in a "
                                 f"{col % 4}-child column, footnote says {kids}")
            used.add(marker)
            first = cells[:col] + [credit] + cells[col + 1:]
            second = cells[:col] + [0] + cells[col + 1:]
            bins += [(lower, split, first), (split, upper, second)]
    if used != set(footnotes):
        raise ValueError(f"footnotes never used: {set(footnotes) - used}")
    return bins


def sanity_check(rows: list[tuple[int, int, list]]) -> None:
    if not rows:
        raise ValueError("no bins parsed")
    for (lo, hi, _), (nlo, _, _) in zip(rows, rows[1:]):
        if not lo < hi or hi != nlo:
            raise ValueError(f"coverage break at [{lo}, {hi}) -> {nlo}")
    for col, name in enumerate(COLUMNS):
        series = [cells[col] for _, _, cells in rows]
        peak = series.index(max(series))
        rising, falling = series[:peak + 1], series[peak:]
        if any(b < a for a, b in zip(rising, rising[1:])):
            raise ValueError(f"{name}: not non-decreasing up to its peak")
        if any(b > a for a, b in zip(falling, falling[1:])):
            raise ValueError(f"{name}: not non-increasing after its peak")
        if series[-1] != 0:
            raise ValueError(f"{name}: last bin is not 0")


def source_pdf(year: int) -> Path:
    return _REPO_ROOT / "pdfs" / "federal" / str(year) / "i1040tt.pdf"


def rows_for(year: int) -> list[tuple[int, int, list]]:
    """The year's checked bins, parsed from the source (writes nothing)."""
    rows = []
    for text in _pages(source_pdf(year)):
        rows += parse_page(text)
    rows.sort(key=lambda r: r[0])
    sanity_check(rows)
    return rows


def ingest(year: int) -> tuple[Path, Path]:
    source = source_pdf(year)
    rows = rows_for(year)
    _ASSETS.mkdir(parents=True, exist_ok=True)
    out = _ASSETS / f"{year}.csv"
    with open(out, "w", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(("lower", "upper") + COLUMNS)
        writer.writerows((lo, hi, *cells) for lo, hi, cells in rows)
    cover = subprocess.run(["pdftotext", "-layout", "-f", "1", "-l", "1",
                            str(source), "-"], check=True,
                           capture_output=True, text=True).stdout
    # The cover stamp's title varies by edition ("Publication 1040 (2025)",
    # "Instructions for Form 1040 Tax Tables (2024)").
    stamp = re.search(r"(?:Publication 1040|Instructions for Form 1040 Tax "
                      r"Tables) \(\d{4}\)\s+Catalog Number \S+", cover)
    provenance = {
        "source": str(source.relative_to(_REPO_ROOT)),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "edition": stamp.group(0) if stamp else None,
        "csv_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "script": "scripts/ingest_eic_table.py",
    }
    prov = _ASSETS / f"{year}.provenance.json"
    prov.write_text(json.dumps(provenance, indent=1) + "\n")
    return out, prov


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    for path in ingest(parser.parse_args().year):
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
