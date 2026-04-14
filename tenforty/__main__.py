"""CLI entry point: python -m tenforty scenario.yaml"""

import argparse
import sys
from pathlib import Path
from typing import TextIO

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round
from tenforty.scenario import load_scenario


GENERIC_OUTPUT_KEYS = [
    "wages", "interest_income", "dividend_income", "agi", "total_income",
    "taxable_income", "total_tax", "federal_withheld", "total_payments",
    "overpaid", "sche_line26", "sche_line41", "schd_line16",
]


def print_results(results: dict, stream: TextIO = sys.stdout) -> None:
    """Print federal return results to stream.

    Splits into two sections:
    - Federal Return Results: the generic line items, hidden when zero.
    - Deduction Analysis: standard, Schedule A, and applied deduction —
      always printed even when zero, so the user sees which path won.
    """
    print("=== Federal Return Results ===", file=stream)
    for key in GENERIC_OUTPUT_KEYS:
        val = results.get(key)
        if val is not None and val != 0:
            print(f"  {key:25s} ${irs_round(float(val)):>12,}", file=stream)

    print("", file=stream)
    print("=== Deduction Analysis ===", file=stream)
    std = irs_round(float(results.get("standard_deduction") or 0))
    sch_a = irs_round(float(results.get("schedule_a_total") or 0))
    applied = irs_round(float(results.get("total_deductions") or 0))
    print(f"  {'standard_deduction':25s} ${std:>12,}", file=stream)
    print(f"  {'schedule_a_total':25s} ${sch_a:>12,}", file=stream)
    label = _which_applied(std, sch_a, applied)
    print(f"  {'total_deductions':25s} ${applied:>12,}   ({label})", file=stream)


def _which_applied(standard: float, schedule_a: float, applied: float) -> str:
    """Derive the human-readable 'which was applied' label.

    Returns 'standard applied', 'itemized applied', or 'indeterminate'
    (when neither amount matches the applied total within a dollar;
    should not happen in practice but avoids a misleading label).
    """
    if abs(applied - standard) < 1 and standard >= schedule_a:
        return "standard applied"
    if abs(applied - schedule_a) < 1 and schedule_a >= standard:
        return "itemized applied"
    return "indeterminate"


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tenforty",
        description="Compute a federal tax return from a scenario YAML file.",
    )
    parser.add_argument("scenario", type=Path, help="Path to your tax scenario YAML file")
    parser.add_argument(
        "--spreadsheets-dir",
        type=Path,
        default=Path("spreadsheets"),
        metavar="DIR",
        help="Path to spreadsheets directory (default: ./spreadsheets)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="DIR",
        help="When set, fill and emit 1040 and 4868 PDFs to this directory",
    )

    args = parser.parse_args()
    scenario_path = args.scenario.expanduser()

    try:
        scenario = load_scenario(scenario_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    orchestrator = ReturnOrchestrator(
        spreadsheets_dir=args.spreadsheets_dir,
        work_dir=Path("/tmp/tenforty_work"),
    )

    print(f"Computing {scenario.config.year} federal return ({scenario.config.filing_status})...")
    results = orchestrator.compute_federal(scenario)

    print()
    print_results(results)

    if args.output_dir is not None:
        emitted = orchestrator.emit_pdfs(scenario, results, args.output_dir)
        print()
        print("=== Emitted PDFs ===")
        for form, path in emitted.items():
            print(f"  {form:4s}  -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
