# scripts/diff_pdf_fields.py
"""Diff two blank PDFs' field inventories (fully-qualified names + types).

Year-port triage: `identical` means the new year's template kept the old
field tree, so the mapping may inherit mechanically (the fields-on-template
gate then re-verifies every path against the new PDF). Any added/removed/
retyped field blocks inheritance for this form — re-probe with
scripts/probe_pdf_fields.py and read the rendered markers.

Limitation, by design: a field that KEPT its name but MOVED on the page is
invisible here; the probe step is the authority on positions.

Usage:
    python scripts/diff_pdf_fields.py --old pdfs/federal/2024/f1040sa.pdf \
        --new pdfs/federal/2025/f1040sa.pdf
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class FieldDiff:
    identical: bool
    added: tuple[str, ...]
    removed: tuple[str, ...]
    retyped: tuple[str, ...]


def inventory(pdf: Path) -> dict[str, str]:
    fields = PdfReader(pdf).get_fields() or {}
    return {name: str(field.get("/FT", "?")) for name, field in fields.items()}


def diff(old: dict[str, str], new: dict[str, str]) -> FieldDiff:
    added = tuple(sorted(set(new) - set(old)))
    removed = tuple(sorted(set(old) - set(new)))
    retyped = tuple(sorted(
        name for name in set(old) & set(new) if old[name] != new[name]))
    return FieldDiff(
        identical=not (added or removed or retyped),
        added=added, removed=removed, retyped=retyped,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    args = parser.parse_args()
    result = diff(inventory(args.old), inventory(args.new))
    if result.identical:
        print(f"IDENTICAL: {args.new.name} field inventory matches "
              f"{args.old.name} — mapping may inherit")
        sys.exit(0)
    for label, names in (("added", result.added), ("removed", result.removed),
                         ("retyped", result.retyped)):
        for name in names:
            print(f"{label:8} {name}")
    print(f"CHANGED: {len(result.added)} added, {len(result.removed)} "
          f"removed, {len(result.retyped)} retyped — re-probe this form")
    sys.exit(1)


if __name__ == "__main__":
    main()
