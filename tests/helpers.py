"""Shared test configuration and helpers."""

import os
import subprocess
import unittest
from pathlib import Path

import pytest

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


def needs_libreoffice(obj):
    """Mark a test class or method as requiring LibreOffice (the oracle tier).

    SINGLE source of the LibreOffice dependency. It stamps two things at one
    site so they can NEVER drift apart:
      1. pytest.mark.oracle  — so `-m "not oracle"` deselects it and the fast
         (native) suite never launches soffice on LO-equipped machines.
      2. unittest.skipUnless(libreoffice_available()) — skips when LO is absent.
    A LibreOffice-dependent test therefore cannot exist without being oracle-tier.
    Enforced by tests/test_oracle_marker_guard.py.
    """
    obj = pytest.mark.oracle(obj)
    obj = unittest.skipUnless(libreoffice_available(), "LibreOffice not installed")(obj)
    return obj

needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


def set_oracle_sanction(item) -> None:
    """Set/clear the runtime soffice sanction env from an item's oracle marker.

    Deterministic every test: oracle-marked -> set, unmarked -> cleared. Because it
    clears on unmarked items, an oracle test followed by an unmarked test (test-order
    randomization) leaves the sanction CLEARED — no stale leak.
    """
    if item.get_closest_marker("oracle") is not None:
        os.environ["TENFORTY_ORACLE_SANCTIONED"] = "1"
    else:
        os.environ.pop("TENFORTY_ORACLE_SANCTIONED", None)


# Test fixtures affirm five attestations as True because they match the
# common in-memory scenario posture: unlimited at-risk amounts, basis
# tracked externally, no K-1 credits, no prior-year capital-loss
# carryforward, no federal AMT. Every other registered attestation defaults
# to False. To change the default for an attestation that already exists,
# edit this set; new attestations default to False automatically.
#
# THE FIVE ARE NOT AFFIRMED ON THE SAME GROUNDS. Read each entry's own
# comment before citing one as precedent for another.
_TEST_POSTURE_AFFIRMED: frozenset[str] = frozenset({
    "acknowledges_unlimited_at_risk",
    "basis_tracked_externally",
    "acknowledges_no_k1_credits",
    # Every synthetic test scenario is built from scratch with no
    # prior-year history, so it genuinely HAS no capital-loss carryover
    # under IRC §1212(b): affirming this is scenario-faithful, not a
    # convenience default. Tests that want the refusal set it False
    # explicitly on scenario.config.
    "acknowledges_no_capital_loss_carryforward",
    # (a) THE BASIS IS TEST INTENT, and it is deliberately NOT the basis the
    #     carryforward entry above uses. That one affirms a FACT about the
    #     fixtures — a scenario built from scratch genuinely has no prior-year
    #     history. The parallel sentence here, "synthetic fixtures genuinely
    #     have no AMT", is a TAX-LAW claim about which modeled inputs can
    #     produce AMT, and that is exactly the derivation nobody has done (see
    #     the registry entry in attestations._ALWAYS_TAIL). So the basis is the
    #     weaker, checkable one: these fixtures were not CONSTRUCTED to
    #     represent AMT-bearing filers. That is verifiable by reading them.
    # (b) THIS IS NOT A CLAIM THAT AMT CANNOT ARISE from fixture data. It is a
    #     statement about what the fixtures were written to exercise, nothing
    #     more.
    # (c) Ticket (q) — "can any modeled input construct an AMT-positive
    #     scenario?" — is what would force revisiting this default. If (q)
    #     concludes that some fixture can owe AMT, this entry is wrong and the
    #     fixtures, not just this line, need revisiting.
    # (d) ANY FUTURE TEST THAT EXERCISES THE AMT REFUSAL must set the field
    #     False EXPLICITLY at its point of use, with an `assertFalse`
    #     precondition proving it took effect. Never reach the gate through
    #     this affirming default: a refusal test that depends on the default
    #     is testing nothing it names, and would silently stop exercising the
    #     refusal the day the default flips.
    # Why not leave it undecided: both defaults encode a claim. Defaulting
    # False would say "these fixtures may owe AMT" — unfalsifiable on the same
    # evidence — AND, because the gate's trigger is `_always`, it would fire
    # the refusal on every fixture in the suite, making everything downstream
    # untestable and reading as breakage rather than as posture.
    "acknowledges_no_federal_amt",
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
