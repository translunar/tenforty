"""Names-only output key list for a form (emit-verification harness §4.2).

Usage:
    python scripts/harness_output_keys.py --form sch_se --out keys/sch_se.txt

Emits every native, non-refusing BATTERIES row whose manifest form set
includes the form, unions the ``RecordedForm.values`` key names for that
form across all copies and years, and writes them sorted, one per line.
Names only: no values are written anywhere.
"""
import argparse
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tenforty.verification.batteries import BATTERIES  # noqa: E402
from tenforty.verification import emit_manifest  # noqa: E402


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--form", required=True,
                        help="catalog form name, e.g. sch_se")
    parser.add_argument("--jurisdiction", default="federal")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    manifest = emit_manifest.load_manifest()
    target = (args.jurisdiction, args.form)
    label = f"{args.jurisdiction}/{args.form}"
    names: set[str] = set()
    rows = 0
    with tempfile.TemporaryDirectory() as tmp:
        for battery in BATTERIES:
            for name, year, build in battery.scenarios():
                rid = emit_manifest.row_id(battery.name, name, year)
                row = manifest[rid]
                if row["routing"] != "native" or row["refusal"]:
                    continue
                if not any(lbl.split("#")[0] == label
                           for lbl in row["forms"]):
                    continue
                out = Path(tmp) / f"row{rows}"
                result = emit_manifest.emit(battery, build(), out)
                recs = [r for r in result.record if r.form == target]
                if not recs:
                    raise SystemExit(
                        f"{rid}: manifest lists {label} but the record "
                        f"has no such form")
                for rec in recs:
                    names.update(rec.values.keys())
                rows += 1
    if not rows:
        raise SystemExit(f"no native, non-refusing row emits {label}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(sorted(names)) + "\n")
    print(f"{label}: {rows} rows, {len(names)} key names -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
