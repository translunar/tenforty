"""CLI entry point: ``python -m tenforty {federal,ca,scorp} ...``.

Backward-compat: ``python -m tenforty <yaml>`` (no subcommand) is still
accepted and routed to the ``federal`` subcommand. See ``_route_argv``.
"""

import argparse
import sys
from pathlib import Path
from typing import TextIO

import pypdf

from tenforty import pdf_packet
from tenforty.forms.depreciation.resolver import recon_groups
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round
from tenforty.scenario import load_scenario


GENERIC_OUTPUT_KEYS = [
    "wages", "interest_income", "dividend_income", "agi", "total_income",
    "taxable_income", "total_tax", "federal_withheld", "total_payments",
    "overpaid", "sche_line26", "sche_line41", "schd_line16",
]

_SUBCOMMANDS = ("federal", "ca", "scorp")


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

    _print_depreciation_recon(results, stream)


def _print_depreciation_recon(results: dict, stream: TextIO) -> None:
    """Printed whenever any activity is in asset mode: the engine's computed
    depreciation beside the figure the return uses. They differ only under a
    value-pinned override, which is flagged -- loud, never a silent mode."""
    groups = recon_groups(results)
    if not groups:
        return
    print("", file=stream)
    print("=== Depreciation Reconciliation ===", file=stream)
    for group in groups:
        engine = irs_round(float(group["engine_amount"]))
        used = irs_round(float(group["used_amount"]))
        flag = "   OVERRIDE" if group["mode"] == "assets-overridden" else ""
        print(f"  {group['activity']}", file=stream)
        print(f"    {'engine computed':23s} ${engine:>12,}", file=stream)
        print(f"    {'used on return':23s} ${used:>12,}{flag}", file=stream)
        if group.get("note"):
            print(f"    NOTE: {group['note']}", file=stream)


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
    emitted: dict, output_dir: Path, year: int,
    source_documents=(),
) -> tuple[dict, list[Path]]:
    """Assemble combined packet(s) from loose emitted PDFs, then remove the
    loose form files that went into a packet (combined-only).

    Files claimed by no packet are retained: the standalone Form 4868
    (a separate filing) and any defensively-unclassified key. Returns
    ``(combined, retained)`` where ``combined`` maps packet name → packet PDF
    path and ``retained`` lists the loose files kept on disk. Source
    documents are spliced in by pdf_packet; loose-file pruning only ever
    touches emitted form files.
    """
    combined = pdf_packet.assemble_all(
        emitted, output_dir, year, source_documents=source_documents)
    retained: list[Path] = []
    for key, path in emitted.items():
        if pdf_packet.classify_key(key) in (None, "standalone"):
            retained.append(path)
        else:
            path.unlink(missing_ok=True)
    return combined, retained


def _print_form_3115(output_dir: Path) -> None:
    """Point at the Form 3115 filing manifest when the run wrote one: it
    lists the statements the applicant must still attach and where the
    signed duplicate copy is filed."""
    manifests = sorted(output_dir.glob("f3115_filing_manifest_*.txt"))
    if not manifests:
        return
    print()
    print("=== Form 3115 ===")
    for manifest in manifests:
        print(f"  Read before filing: {manifest}")
    for copy in sorted(output_dir.glob("f3115_*_duplicate_copy_to_sign.pdf")):
        print(f"  Sign and file separately: {copy}")


def _print_packets(combined: dict, retained: list[Path],
                    source_documents=()) -> None:
    print()
    print("=== Assembled return packet(s) ===")
    for name, path in combined.items():
        print(f"  {name:20s} -> {path}")
    if retained:
        print()
        print("=== Standalone files (filed separately) ===")
        for path in retained:
            print(f"  {path}")
    if source_documents:
        print()
        print("=== Attached source documents ===")
        for doc in source_documents:
            pages = len(pypdf.PdfReader(str(doc.path)).pages)
            dests = ", ".join(
                name for name in doc.packets if name in combined)
            if dests:
                print(f"  {doc.path.name} ({doc.kind}, {pages} page(s)) "
                      f"-> {dests}")


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

    p_scorp = subparsers.add_parser(
        "scorp",
        help=("Emit the federal 1120-S + K-1s and, when the scenario has a "
              "CA block, the CA 100S + K-1s from an S-corp scenario YAML"),
    )
    p_scorp.add_argument(
        "scenario", type=Path,
        help="Path to the S-corp scenario YAML file",
    )
    p_scorp.add_argument(
        "--spreadsheets-dir", type=Path, default=Path("spreadsheets"),
        metavar="DIR",
        help="Path to spreadsheets directory (default: ./spreadsheets)",
    )
    p_scorp.add_argument(
        "--output-dir", type=Path, required=True, metavar="DIR",
        help="Directory to write the S-corp packet PDFs to (required)",
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
            emitted, args.output_dir, scenario.config.year,
            scenario.source_documents)
        _print_packets(combined, retained, scenario.source_documents)
        _print_form_3115(args.output_dir)

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
        emitted, args.output_dir, scenario.config.year,
        scenario.source_documents)
    _print_packets(combined, retained, scenario.source_documents)
    return 0


def _run_scorp(args: argparse.Namespace) -> int:
    try:
        scenario = load_scenario(args.scenario.expanduser())
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if scenario.s_corp_return is None:
        print(
            "Error: scenario has no s_corp_return block; nothing to emit. "
            "Use the federal or ca subcommand for personal returns.",
            file=sys.stderr,
        )
        return 1

    orchestrator = ReturnOrchestrator(
        spreadsheets_dir=args.spreadsheets_dir,
        work_dir=Path("/tmp/tenforty_work"),
    )

    year = scenario.config.year
    print(f"Computing {year} federal 1120-S return...")
    _corp_results, emitted = orchestrator.run_full_federal_scorp_return(
        scenario, args.output_dir)
    emitted = dict(emitted)

    if scenario.s_corp_return.ca is not None:
        print(f"Computing {year} California 100S return...")
        _ca_results, ca_emitted = orchestrator.run_full_california_scorp_return(
            scenario, args.output_dir)
        emitted.update(ca_emitted)

    combined, retained = _assemble_packets_and_prune(
        emitted, args.output_dir, year, scenario.source_documents)
    _print_packets(combined, retained, scenario.source_documents)
    return 0


def main() -> int:
    sys.argv = _route_argv(sys.argv)
    parser = _build_parser()
    args = parser.parse_args()

    if args.subcommand == "federal":
        return _run_federal(args)
    if args.subcommand == "ca":
        return _run_ca(args)
    if args.subcommand == "scorp":
        return _run_scorp(args)
    # subparsers(required=True) prevents this branch; keep an explicit
    # fall-through for static analysers.
    parser.error(f"Unknown subcommand: {args.subcommand!r}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
