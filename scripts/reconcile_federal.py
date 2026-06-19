"""2024 filed-return reconciliation report.

Diffs a recomputed 2024 result against an external prior-filing values file.
Produces a triaged report: per line, recomputed vs prior-filing, delta, and flag.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def reconcile(recomputed: dict, prior: dict, keys) -> list[dict]:
    """Diff recomputed and prior-filing values for specified keys.

    Args:
        recomputed: Dict of recomputed 2024 line values
        prior: Dict of prior-filing line values
        keys: Tuple or list of keys to compare

    Returns:
        List of dicts with keys: key, recomputed, prior, delta, flag
        flag is "match" or "recompute-differs"
    """
    report = []
    for key in keys:
        rc, pr = recomputed.get(key), prior.get(key)
        delta = (rc or 0) - (pr or 0)
        report.append({
            "key": key,
            "recomputed": rc,
            "prior": pr,
            "delta": delta,
            "flag": "match" if delta == 0 else "recompute-differs"
        })
    return report


def main():
    """CLI: load external expected-values file and print reconciliation report."""
    parser = argparse.ArgumentParser(
        description="Reconcile 2024 recomputed return against prior-filing values"
    )
    parser.add_argument(
        "prior_filing_path",
        type=Path,
        help="Path to external prior-filing YAML file (never committed)"
    )
    parser.add_argument(
        "--recomputed",
        type=json.loads,
        help="JSON dict of recomputed 2024 values"
    )
    parser.add_argument(
        "--keys",
        type=lambda s: tuple(s.split(",")),
        help="Comma-separated keys to compare"
    )

    args = parser.parse_args()

    # Load prior-filing values from external file
    with open(args.prior_filing_path) as f:
        prior = yaml.safe_load(f)

    if not isinstance(prior, dict):
        print(f"Error: prior-filing file must contain a YAML dict", file=sys.stderr)
        sys.exit(1)

    if args.recomputed is None or args.keys is None:
        print("Error: --recomputed and --keys required", file=sys.stderr)
        sys.exit(1)

    # Run reconciliation
    report = reconcile(args.recomputed, prior, args.keys)

    # Print report
    for row in report:
        print(f"{row['key']}: recomputed={row['recomputed']}, prior={row['prior']}, "
              f"delta={row['delta']}, flag={row['flag']}")


if __name__ == "__main__":
    main()
