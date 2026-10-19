# scripts/harness_manifest.py
"""Regenerate (or --check) tests/fixtures/harness_emit_manifest.json: for
every BATTERIES scenario, its routing, refusal, or exact filled-form set on
the real emit path (tenforty.verification.emit_manifest).

A manifest diff is a behaviour change. Regenerating prints the per-row diff;
paste it, with an explanation of every row, into the commit or report.

Usage:
    python scripts/harness_manifest.py            # rewrite, print the diff
    python scripts/harness_manifest.py --check    # exit 1 if stale
"""
import argparse
import sys
from pathlib import Path

# The batteries are test data (tests/fixtures): run from anywhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tenforty.verification import emit_manifest  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    new = emit_manifest.build_manifest()
    try:
        old = emit_manifest.load_manifest()
    except FileNotFoundError:
        old = {}
    changes = emit_manifest.diff(old, new)
    for line in changes:
        print(line)
    if args.check:
        print("manifest current" if not changes
              else f"manifest STALE: {len(changes)} row(s) differ")
        return 1 if changes else 0
    emit_manifest.write_manifest(new)
    print(f"wrote {len(new)} rows; {len(changes)} changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
