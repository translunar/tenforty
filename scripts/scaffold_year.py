# scripts/scaffold_year.py
"""Scaffold a new tax year's pack skeleton: params stub + attestation stub.

Both stubs are FAIL-CLOSED. The params stub raises at import, so
params.load(), the batteries, and the completeness gate all stay red until
real cited values replace it. The attestation stub is all-None, so the
dual-transcription gate stays red until an air-gapped transcriber fills
it. The scaffolder deliberately does NOT edit tenforty/years.py — declaring
a year in the manifest is a human decision made when the pack is real.

Usage:
    python scripts/scaffold_year.py --jurisdiction federal --year 2023
"""
import argparse
from pathlib import Path

_FIELDS = {
    "federal": (
        "year", "standard_deduction", "ordinary_brackets",
        "qdcgt_breakpoints", "addl_medicare_threshold", "ss_wage_base",
        "qbi_threshold", "salt_cap_starting", "salt_phaseout_threshold",
        "salt_phaseout_rate", "salt_cap_floor", "medical_agi_floor_pct",
        "prior_year_salt_cap", "eic_income_ceiling",
    ),
    "california": (
        "year", "standard_deduction", "exemption_credit",
        "dependent_exemption_amount", "agi_phaseout_threshold",
        "rate_schedule", "renter_credit_agi_threshold",
        "renter_credit_amount",
    ),
}

_PARAMS_STUB = '''\
"""UNFILLED SCAFFOLD for {jurisdiction} tax year {year}.

Replace this raise with PARAMS = {cls}(...) carrying officially cited
values (see docs/runbooks/add-tax-year.md, dual-transcription step).
Fields required: {fields}.
"""
raise NotImplementedError(
    "{jurisdiction} {year} params are scaffolded but unfilled — "
    "see docs/runbooks/add-tax-year.md"
)
'''

_ATTESTATION_STUB = '''\
"""UNFILLED attestation scaffold for {jurisdiction} tax year {year}.

To be completed by an AIR-GAPPED transcriber (must not read
tenforty/params/*/y20*.py or tests asserting values) from official
publications, one citation comment per value.
"""
SOURCES: tuple[str, ...] = ()

ATTESTED: dict[str, object] = {{
{entries}
}}
'''


def scaffold(root: Path, jurisdiction: str, year: int) -> list[Path]:
    if jurisdiction not in _FIELDS:
        raise ValueError(f"Unknown jurisdiction {jurisdiction!r}")
    cls = "FederalParams" if jurisdiction == "federal" else "CaliforniaParams"
    params_path = (root / "tenforty" / "params" / jurisdiction
                   / f"y{year}.py")
    attestation_path = (root / "tests" / "params_attestations"
                        / f"{jurisdiction}_y{year}.py")
    for path in (params_path, attestation_path):
        if path.exists():
            raise FileExistsError(f"{path} already exists — refusing to "
                                  f"overwrite; delete it first if you mean it")
        path.parent.mkdir(parents=True, exist_ok=True)

    fields = _FIELDS[jurisdiction]
    params_path.write_text(_PARAMS_STUB.format(
        jurisdiction=jurisdiction, year=year, cls=cls,
        fields=", ".join(fields)))
    entries = "\n".join(
        f'    "{name}": None,  # TODO: cite official source' for name in fields)
    attestation_path.write_text(_ATTESTATION_STUB.format(
        jurisdiction=jurisdiction, year=year, entries=entries))
    return [params_path, attestation_path]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jurisdiction", required=True,
                        choices=("federal", "california"))
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).parent.parent)
    args = parser.parse_args()
    for path in scaffold(args.root, args.jurisdiction, args.year):
        print(f"created {path}")
    print("Next: docs/runbooks/add-tax-year.md — fetch assets, "
          "dual-transcribe params, ingest the tax table, diff/probe "
          "mappings, then declare the year in tenforty/years.py.")


if __name__ == "__main__":
    main()
