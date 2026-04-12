"""CLI entry point: python -m tenforty scenario.yaml"""

import sys
from pathlib import Path
from typing import TextIO

from tenforty.orchestrator import ReturnOrchestrator
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
            print(f"  {key:25s} ${float(val):>12,.0f}", file=stream)

    print("", file=stream)
    print("=== Deduction Analysis ===", file=stream)
    std = float(results.get("standard_deduction") or 0)
    sch_a = float(results.get("schedule_a_total") or 0)
    applied = float(results.get("total_deductions") or 0)
    print(f"  {'standard_deduction':25s} ${std:>12,.0f}", file=stream)
    print(f"  {'schedule_a_total':25s} ${sch_a:>12,.0f}", file=stream)
    label = _which_applied(std, sch_a, applied)
    print(f"  {'total_deductions':25s} ${applied:>12,.0f}   ({label})", file=stream)


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
    if len(sys.argv) < 2:
        print("Usage: python -m tenforty <scenario.yaml> [spreadsheets_dir]")
        print()
        print("  scenario.yaml     Path to your tax scenario file")
        print("  spreadsheets_dir  Path to spreadsheets directory (default: ./spreadsheets)")
        return 1

    scenario_path = Path(sys.argv[1]).expanduser()
    spreadsheets_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("spreadsheets")

    try:
        scenario = load_scenario(scenario_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    orchestrator = ReturnOrchestrator(
        spreadsheets_dir=spreadsheets_dir,
        work_dir=Path("/tmp/tenforty_work"),
    )

    print(f"Computing {scenario.config.year} federal return ({scenario.config.filing_status})...")
    results = orchestrator.compute_federal(scenario)

    print()
    print_results(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
