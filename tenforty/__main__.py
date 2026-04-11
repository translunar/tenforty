"""CLI entry point: python -m tenforty scenario.yaml"""

import sys
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario


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
    print("=== Federal Return Results ===")
    for key in ["wages", "interest_income", "dividend_income", "agi", "total_income",
                "standard_deduction", "total_deductions", "taxable_income",
                "total_tax", "federal_withheld", "total_payments", "overpaid",
                "sche_line26", "sche_line41", "schd_line16"]:
        val = results.get(key)
        if val is not None and val != 0:
            print(f"  {key:25s} ${float(val):>12,.0f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
