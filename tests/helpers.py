"""Shared test configuration and helpers."""

import subprocess
import unittest
from pathlib import Path

from tenforty.attestations import _CA_ATTESTATIONS
from tenforty.models import Scenario, TaxReturnConfig, W2
from tenforty.attestations import _ATTESTATIONS

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")

# Set of CA scope-out attestation field names, derived from the registry.
# Single source of truth for tests that need to iterate every CA scope-out
# (e.g. setting them all True in a smoke scenario). Tests that need to
# verify the registry's coverage against an EXPECTED list keep their own
# literal to avoid a tautology — see tests/test_attestations_ca.py.
CA_SCOPE_OUT_FIELDS: frozenset[str] = frozenset(a.field for a in _CA_ATTESTATIONS)


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = unittest.skipUnless(
    libreoffice_available(), "LibreOffice not installed",
)

needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


# Test fixtures affirm three attestations as True because they match the
# common in-memory scenario posture: unlimited at-risk amounts, basis
# tracked externally, no K-1 credits. Every other registered attestation
# defaults to False. To change the default for an attestation that
# already exists, edit this set; new attestations default to False
# automatically.
_TEST_POSTURE_AFFIRMED: frozenset[str] = frozenset({
    "acknowledges_unlimited_at_risk",
    "basis_tracked_externally",
    "acknowledges_no_k1_credits",
})


def scope_out_attestation_defaults() -> dict[str, bool]:
    """Return safe-default values for every registered scope-out attestation.

    Auto-derived from `tenforty.attestations._ATTESTATIONS` so that adding
    a new attestation to the registry requires zero fixture-helper edits
    when it should default False (the conservative case). Three fields
    default to True because they affirm the common test posture; see
    `_TEST_POSTURE_AFFIRMED`. Tests that need a different value for any
    field should override it explicitly on `scenario.config`."""
    return {
        attestation.field: attestation.field in _TEST_POSTURE_AFFIRMED
        for attestation in _ATTESTATIONS
    }


def make_simple_scenario() -> Scenario:
    """Create a simple single-filer scenario for tests that need a Scenario instance.

    Sets all load-time scope-out attestations to False so
    in-memory fixtures mirror the load-time contract enforced on YAML fixtures.
    Also sets `prior_year_itemized=False` (factual) to mean last year took the
    standard deduction, so 1099-G state-refund tax-benefit-rule short-circuits.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
            **scope_out_attestation_defaults(),
        ),
        w2s=[
            W2(
                employer="Acme Corp",
                wages=100000,
                federal_tax_withheld=15000,
                ss_wages=100000,
                ss_tax_withheld=6200,
                medicare_wages=100000,
                medicare_tax_withheld=1450,
            ),
        ],
    )


def make_k1_scenario() -> Scenario:
    """Variant of make_simple_scenario whose config passes the K-1 gates.
    Use in compute tests where the K-1 itself is the subject, not the gate."""
    s = make_simple_scenario()
    for name in (
        "acknowledges_qbi_below_threshold",
        "acknowledges_unlimited_at_risk",
        "basis_tracked_externally",
        "acknowledges_no_partnership_se_earnings",
        "acknowledges_no_section_1231_gain",
        "acknowledges_no_more_than_four_k1s",
        "acknowledges_no_k1_credits",
        "acknowledges_no_section_179",
        "acknowledges_no_estate_trust_k1",
    ):
        setattr(s.config, name, True)
    return s
