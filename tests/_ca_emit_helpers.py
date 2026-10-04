"""Shared CA-emit helpers for the form-completeness / checkbox-ink tests.

Non-test module (leading underscore). Emits a synthetic CA-resident return
for any supported year and filing status and returns the compute results and
the filled PDF paths, so presentation tests can inspect real emitted forms.
"""

import dataclasses
import tempfile
from pathlib import Path

from tenforty.models import FilingStatus, W2
from tenforty.orchestrator import ReturnOrchestrator
from tests._ca_fixtures import _make_ca_withholding_scenario, _write_ca_yaml

REPO_ROOT = Path(__file__).parent.parent
CA_YEARS = (2021, 2022, 2023, 2024, 2025)


def make_ca_scenario(year: int, filing_status: FilingStatus = FilingStatus.SINGLE,
                     *, dependents: tuple[str, ...] = (), w2s: list | None = None,
                     state_tax_withheld: float = 4_000.0):
    base = _make_ca_withholding_scenario(state_tax_withheld)
    config = dataclasses.replace(
        base.config, year=year, filing_status=filing_status,
        dependents=list(dependents), county="Synthetic County",
        middle_initial="Q", address_is_principal_residence=True,
    )
    kwargs = {"config": config, "ca540": None}
    if w2s is not None:
        kwargs["w2s"] = w2s
    return dataclasses.replace(base, **kwargs)


def emit_ca(scenario, out_dir: Path | None = None):
    """Run the CA pipeline; returns (ca_results, {basename: Path})."""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.mkdtemp())
    ca_yaml = _write_ca_yaml(
        {"ca540": {"estimated_payments": 0.0, "use_tax": 0.0}}, tmp_dir=out_dir)
    orch = ReturnOrchestrator(
        spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=out_dir / "work")
    return orch.run_full_california_return(
        scenario=scenario, ca_yaml_path=ca_yaml, output_dir=out_dir)
