"""Shared fixtures for Sub-plan 3 / California 540 tests.

Non-test helper module. The leading underscore prevents pytest from
collecting it as a test file. Tests across SP3 tasks T16-T19 import from
here instead of from each other to avoid test-to-test import dependencies.

The smoke scenario here is intentionally minimal — a CA-resident single
filer with all 40+ load-time attestations declared. Future SP3 tasks
(T17 `run_full_california_return`) will reuse this same scenario, so
per-task variants should compose on top of `_make_ca_v1_smoke_scenario`
rather than duplicating the attestation block.
"""

import tempfile
from pathlib import Path

from tenforty.models import (
    CA540Return,
    FilingStatus,
    Scenario,
    TaxReturnConfig,
)
from tests.helpers import CA_SCOPE_OUT_FIELDS, scope_out_attestation_defaults


def _make_ca_v1_smoke_scenario() -> Scenario:
    """Build a minimal CA-resident Scenario for SP3 smoke tests.

    Single filing status, year=2025, all load-time attestations declared
    (via `scope_out_attestation_defaults`). The CA-specific scope-out
    attestations are flipped True so the load-time CA gates pass; the
    federal scope-outs that aren't relevant to CA pipeline emit stay at
    their helper defaults.
    """
    attestations = scope_out_attestation_defaults()
    # Flip every CA-specific scope-out to True so the v1 single-filer
    # smoke scenario passes the load-time CA gates (no NOL carryover,
    # no depreciation divergence, no IRA basis divergence, etc.).
    for ca_key in CA_SCOPE_OUT_FIELDS:
        attestations[ca_key] = True
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01",
            state="CA",
            first_name="Smoke",
            last_name="Test",
            ssn="000-00-0000",
            address="1 Example Ave",
            address_city="Los Angeles",
            address_state="CA",
            address_zip="90001",
            **attestations,
        ),
        ca540=CA540Return(),
    )


def _write_ca_yaml(ca_yaml_dict: dict, tmp_dir: Path | None = None) -> Path:
    """Materialize a CA YAML dict to a tempfile and return its Path.

    Mirrors the on-disk format that T18's CLI will consume:
    top-level `ca540:` block + optional `federal_context:` sibling.
    """
    import yaml
    if tmp_dir is None:
        tmp_dir = Path(tempfile.mkdtemp())
    path = tmp_dir / "scenario.ca.yaml"
    path.write_text(yaml.safe_dump(ca_yaml_dict))
    return path
