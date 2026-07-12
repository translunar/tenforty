# scripts/fetch_year_assets.py
"""Download a tax year's blank-form PDFs + tax-table instructions from the
official IRS / FTB URL schemes into pdfs/<jurisdiction>/<year>/.

DOWNLOADS ARE A USER-APPROVED STEP. Agents must not run this without the
user's explicit go-ahead. Only irs.gov and ftb.ca.gov hosts are permitted;
every fetched file is validated (PDF magic bytes, >50KB) and the run hard-
stops on the first failure — a 404 HTML page must never land in pdfs/.

The IRS prior-year scheme is stable: irs.gov/pub/irs-prior/<stem>--<year>.pdf
(the federal tax-table stem is year-dependent — see _federal_tax_table_stem).
The FTB scheme is ftb.ca.gov/forms/<year>/<year>-<doc>.pdf. If the FTB
renames a document (they occasionally do), edit _CALIFORNIA_DOCS — the
validation guarantees a wrong guess fails loudly rather than corrupting
the year pack.

Usage:
    python scripts/fetch_year_assets.py --jurisdiction federal --year 2023
    python scripts/fetch_year_assets.py --jurisdiction california --year 2023 --dry-run
"""
import argparse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_PDFS = _REPO_ROOT / "pdfs"

# (IRS stem, destination filename). Stems per the irs-prior naming scheme.
_FEDERAL_DOCS: list[tuple[str, str]] = [
    ("f1040", "f1040.pdf"),
    ("f1040s1", "f1040s1.pdf"),
    ("f1040sa", "f1040sa.pdf"),
    ("f1040sb", "f1040sb.pdf"),
    ("f1040sd", "f1040sd.pdf"),
    ("f1040se", "f1040se.pdf"),
    ("f8949", "f8949.pdf"),
    ("f4562", "f4562.pdf"),
    ("f4868", "f4868.pdf"),
    ("f8582", "f8582.pdf"),
    ("f8959", "f8959.pdf"),
    ("f8995", "f8995.pdf"),
    ("f1120s", "f1120s.pdf"),
    # IRS source stem for Schedule K-1 (Form 1120-S) is "f1120ssk" for every
    # year; the repo's on-disk convention uses an underscore (f1120s_k1.pdf).
    ("f1120ssk", "f1120s_k1.pdf"),
]

# The federal tax table's IRS source stem is year-dependent: the standalone
# "i1040tt" document was discontinued after tax year 2024 and the Tax Table
# folded into "p1040". The on-disk destination stays i1040tt.pdf for every
# year — a stable role-name that the ingester and year packs rely on — so
# only the URL stem moves, not the filename.
_FEDERAL_TAX_TABLE_DEST = "i1040tt.pdf"


def _federal_tax_table_stem(year: int) -> str:
    return "i1040tt" if year <= 2024 else "p1040"


# (FTB doc suffix, destination filename).
_CALIFORNIA_DOCS: list[tuple[str, str]] = [
    ("540", "f540.pdf"),
    ("540-schedule-ca", "sch_ca.pdf"),
    ("540-schedule-d", "sch_d_540.pdf"),
    ("540-taxtable", "tax_table.pdf"),      # Layer-2 oracle source
    ("540-tax-rate-schedules", "tax_rate_schedules.pdf"),
]

_ALLOWED_HOSTS = ("https://www.irs.gov/", "https://www.ftb.ca.gov/")


@dataclass(frozen=True)
class Download:
    url: str
    dest: Path


def build_download_plan(jurisdiction: str, year: int) -> list[Download]:
    if jurisdiction == "federal":
        docs = _FEDERAL_DOCS + [
            (_federal_tax_table_stem(year), _FEDERAL_TAX_TABLE_DEST)]
        return [
            Download(
                url=f"https://www.irs.gov/pub/irs-prior/{stem}--{year}.pdf",
                dest=_PDFS / "federal" / str(year) / dest_name,
            )
            for stem, dest_name in docs
        ]
    if jurisdiction == "california":
        return [
            Download(
                url=f"https://www.ftb.ca.gov/forms/{year}/{year}-{doc}.pdf",
                dest=_PDFS / "california" / str(year) / dest_name,
            )
            for doc, dest_name in _CALIFORNIA_DOCS
        ]
    raise ValueError(f"Unknown jurisdiction {jurisdiction!r} "
                     f"(expected 'federal' or 'california')")


def validate_pdf(path: Path) -> None:
    data = path.read_bytes()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{path}: not a PDF (magic bytes {data[:8]!r}) — "
                         f"likely a 404/HTML page; check the URL scheme")
    if len(data) < 50_000:
        raise ValueError(f"{path}: only {len(data)} bytes — too small to be "
                         f"a real IRS/FTB form; check the URL scheme")


def fetch(plan: list[Download], *, dry_run: bool) -> None:
    for item in plan:
        if not item.url.startswith(_ALLOWED_HOSTS):
            raise ValueError(f"Refusing non-official host: {item.url}")
        if dry_run:
            print(f"DRY RUN  {item.url}  ->  {item.dest}")
            continue
        if item.dest.exists():
            print(f"exists   {item.dest} (skipping)")
            continue
        item.dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"fetching {item.url}")
        urllib.request.urlretrieve(item.url, item.dest)  # noqa: S310 — hosts allowlisted above
        validate_pdf(item.dest)
        print(f"ok       {item.dest}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction", required=True,
                        choices=("federal", "california"))
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    fetch(build_download_plan(args.jurisdiction, args.year), dry_run=args.dry_run)


if __name__ == "__main__":
    main()
