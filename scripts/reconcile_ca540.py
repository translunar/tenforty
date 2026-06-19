"""Reconcile a recomputed CA 540 against a filed return's line values.

Non-gating amendment-review tool. The filed-return values come from an
EXTERNAL YAML passed by path — never committed (it contains real figures).
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def reconcile(recomputed: dict, filed: dict, keys) -> list[dict]:
    """Diff recomputed and filed-return values for specified keys.

    Args:
        recomputed: Dict of recomputed 2024 CA line values
        filed: Dict of filed-return CA line values
        keys: Tuple or list of keys to compare

    Returns:
        List of dicts with keys: key, recomputed, filed, delta, flag
        flag is "match" or "recompute-differs"
    """
    report = []
    for key in keys:
        rc, fl = recomputed.get(key), filed.get(key)
        delta = (rc or 0) - (fl or 0)
        report.append({
            "key": key,
            "recomputed": rc,
            "filed": fl,
            "delta": delta,
            "flag": "match" if delta == 0 else "recompute-differs"
        })
    return report


def main():
    """CLI: load external filed-return values file and print reconciliation report."""
    parser = argparse.ArgumentParser(
        description="Reconcile 2024 recomputed CA 540 against filed-return values"
    )
    parser.add_argument(
        "filed_path",
        type=Path,
        help="Path to external filed-return YAML file (never committed)"
    )
    parser.add_argument(
        "--recomputed",
        type=json.loads,
        help="JSON dict of recomputed 2024 CA values"
    )
    parser.add_argument(
        "--keys",
        type=lambda s: tuple(s.split(",")),
        help="Comma-separated keys to compare"
    )

    args = parser.parse_args()

    # Load filed-return values from external file
    with open(args.filed_path) as f:
        filed = yaml.safe_load(f)

    if not isinstance(filed, dict):
        print(f"Error: filed-return file must contain a YAML dict", file=sys.stderr)
        sys.exit(1)

    if args.recomputed is None or args.keys is None:
        print("Error: --recomputed and --keys required", file=sys.stderr)
        sys.exit(1)

    # Run reconciliation
    report = reconcile(args.recomputed, filed, args.keys)

    # Print report
    for row in report:
        print(f"{row['key']}: recomputed={row['recomputed']}, filed={row['filed']}, "
              f"delta={row['delta']}, flag={row['flag']}")


if __name__ == "__main__":
    main()
