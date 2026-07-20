"""CLI entry point: ``python -m tenforty {federal,ca} ...``.

Backward-compat: ``python -m tenforty <yaml>`` (no subcommand) is still
accepted and routed to the ``federal`` subcommand. See ``_route_argv``.
"""

import argparse
import sys
from pathlib import Path
from typing import TextIO

from tenforty import pdf_packet
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round
from tenforty.scenario import load_scenario


GENERIC_OUTPUT_KEYS = [
    "wages", "interest_income", "dividend_income", "agi", "total_income",
    "taxable_income", "total_tax", "federal_withheld", "total_payments",
    "overpaid", "sche_line26", "sche_line41", "schd_line16",
]

_SUBCOMMANDS = ("federal", "ca")


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


def _assemble_packets_and_prune(
    emitted: dict, output_dir: Path, year: int
) -> tuple[dict, list[Path]]:
    """Assemble combined packet(s) from loose emitted PDFs, then remove the
    loose form files that went into a packet (combined-only).

    Files claimed by no packet are retained: the standalone Form 4868
    (a separate filing) and any defensively-unclassified key. Returns
    ``(combined, retained)`` where ``combined`` maps packet name → packet PDF
    path and ``retained`` lists the loose files kept on disk.
    """
    combined = pdf_packet.assemble_all(emitted, output_dir, year)
    retained: list[Path] = []
    for key, path in emitted.items():
        if pdf_packet.classify_key(key) in (None, "standalone"):
            retained.append(path)
        else:
            path.unlink(missing_ok=True)
    return combined, retained


def _print_packets(combined: dict, retained: list[Path]) -> None:
    print()
    print("=== Assembled return packet(s) ===")
    for name, path in combined.items():
        print(f"  {name:20s} -> {path}")
    if retained:
        print()
        print("=== Standalone files (filed separately) ===")
        for path in retained:
            print(f"  {path}")


def _route_argv(argv: list[str]) -> list[str]:
    """Backward-compat router: insert ``federal`` when bare YAML is given.

    Pre-processes ``sys.argv``-shape lists so legacy ``python -m tenforty
    foo.yaml`` invocations continue to work. Rules:
    - ``len(argv) < 2``: leave alone (argparse will show usage).
    - ``argv[1].startswith("-")``: leave alone (top-level flag like --help).
    - ``argv[1]`` already a known subcommand: leave alone.
    - Otherwise: insert ``"federal"`` at index 1.
    """
    if len(argv) < 2:
        return list(argv)
    first = argv[1]
    if first.startswith("-") or first in _SUBCOMMANDS:
        return list(argv)
    return [argv[0], "federal", *argv[1:]]


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="python -m tenforty",
        description=(
            "Compute a federal or California tax return from scenario YAML "
            "files. Use one of the subcommands below."
        ),
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    p_fed = subparsers.add_parser(
        "federal",
        help="Compute a federal return from a scenario YAML",
    )
    p_fed.add_argument(
        "scenario", type=Path,
        help="Path to your tax scenario YAML file",
    )
    p_fed.add_argument(
        "--spreadsheets-dir", type=Path, default=Path("spreadsheets"),
        metavar="DIR",
        help="Path to spreadsheets directory (default: ./spreadsheets)",
    )
    p_fed.add_argument(
        "--output-dir", type=Path, default=None, metavar="DIR",
        help="When set, fill and emit 1040 and 4868 PDFs to this directory",
    )

    p_ca = subparsers.add_parser(
        "ca",
        help="Compute a California 540 return from federal + CA YAMLs",
    )
    p_ca.add_argument(
        "federal_scenario", type=Path,
        help="Path to the federal scenario YAML file",
    )
    p_ca.add_argument(
        "ca_scenario", type=Path, nargs="?", default=None,
        help=(
            "Path to the CA scenario YAML file. If omitted, defaults to "
            "<federal>.ca.yaml next to the federal YAML."
        ),
    )
    p_ca.add_argument(
        "--spreadsheets-dir", type=Path, default=Path("spreadsheets"),
        metavar="DIR",
        help="Path to spreadsheets directory (default: ./spreadsheets)",
    )
    p_ca.add_argument(
        "--output-dir", type=Path, required=True, metavar="DIR",
        help="Directory to write the CA-state PDFs to (required)",
    )

    return parser


def _run_federal(args: argparse.Namespace) -> int:
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
    if args.output_dir is not None:
        results, emitted = orchestrator.run_full_return(scenario, args.output_dir)
    else:
        results = orchestrator.compute_federal(scenario)
        emitted = None

    print()
    print_results(results)

    if emitted is not None:
        combined, retained = _assemble_packets_and_prune(
            emitted, args.output_dir, scenario.config.year)
        _print_packets(combined, retained)

    return 0


def _run_ca(args: argparse.Namespace) -> int:
    federal_yaml = args.federal_scenario
    if args.ca_scenario is not None:
        ca_yaml = args.ca_scenario
    else:
        ca_yaml = federal_yaml.with_suffix(".ca.yaml")
        if not ca_yaml.exists():
            print(
                f"CA YAML not found at inferred path {ca_yaml}. "
                f"Pass it explicitly: tenforty ca {federal_yaml} "
                f"/path/to/alternate.yaml",
                file=sys.stderr,
            )
            return 1

    try:
        scenario = load_scenario(federal_yaml.expanduser())
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    orchestrator = ReturnOrchestrator(
        spreadsheets_dir=args.spreadsheets_dir,
        work_dir=Path("/tmp/tenforty_work"),
    )

    print(f"Computing {scenario.config.year} California 540 return ({scenario.config.filing_status})...")
    _ca_results, emitted = orchestrator.run_full_california_return(
        scenario=scenario,
        ca_yaml_path=ca_yaml,
        output_dir=args.output_dir,
        federal_yaml_path=federal_yaml,
    )

    combined, retained = _assemble_packets_and_prune(
        emitted, args.output_dir, scenario.config.year)
    _print_packets(combined, retained)
    return 0


def main() -> int:
    sys.argv = _route_argv(sys.argv)
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand == "federal":
        return _run_federal(args)
    if args.subcommand == "ca":
        return _run_ca(args)
    # subparsers(required=True) prevents this branch; keep an explicit
    # fall-through for static analysers.
    parser.error(f"Unknown subcommand: {args.subcommand!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
