"""Write binding proposals for form-years (emit-verification harness §4.2).

Usage:
    python scripts/harness_propose.py --form f8995 --keys 2021 2022 \\
        --output-keys keys/f8995.txt --out <dir>

Reads the form's committed line inventories and stylesheets and a
names-only output key list (one compute-key name per line), and writes
``<out>/proposals/<form>_<key>.json`` per key, printing a summary: total
lines, auto-confirmed, exceptions by reason.
"""
import argparse
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tenforty.declarations import inventory, propose  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--form", required=True)
    parser.add_argument("--keys", nargs="+", required=True,
                        help="tax years, or revisions for revision-keyed forms")
    parser.add_argument("--output-keys", type=Path, required=True,
                        help="names-only text file, one compute key per line")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    names = sorted({line.strip() for line in
                    args.output_keys.read_text().splitlines() if line.strip()})
    out_dir = args.out / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)
    for raw in args.keys:
        key = int(raw) if raw.isdigit() else raw
        result = propose.propose(args.form, key, names)
        path = out_dir / f"{args.form}_{key}.json"
        path.write_text(json.dumps({
            "form": args.form, "key": key, "output_keys": names,
            "auto_confirmed": [dataclasses.asdict(b)
                               for b in result.auto_confirmed],
            "exceptions": [dataclasses.asdict(e) for e in result.exceptions],
        }, indent=1) + "\n")
        reasons = Counter(e.reason for e in result.exceptions)
        total = len(inventory.load(args.form, key).lines)
        print(f"{args.form} {key}: {total} lines, "
              f"{len(result.auto_confirmed)} auto-confirmed, exceptions "
              + ", ".join(f"{r}={reasons.get(r, 0)}"
                          for r in ("seam", "disagree", "no-proposal")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
