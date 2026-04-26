"""Shared test configuration and helpers."""

import subprocess
import unittest
from pathlib import Path

from tenforty.models import Scenario, TaxReturnConfig, W2

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")


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


def plan_d_attestation_defaults() -> dict[str, bool]:
    """Return a dict of all attestation fields pre-set for a K-1-capable
    and S-corp-capable in-memory test scenario.

    Three fields default to True because they affirm the common test posture:
    unlimited at-risk amounts, basis tracked externally, and no K-1 credits.
    The other fields stay False because their compute-time gates fire only
    when the scenario's K-1s or lots actually carry the triggering field
    value — an all-False default is safe and conservative. Tests that need
    a different value for one of the three True fields should override it
    explicitly on `scenario.config`. The 7 1120-S fields are likewise safe
    at False because their compute gates require `s.s_corp_return` to be
    non-None."""
    return {
        "has_foreign_accounts": False,
        "acknowledges_sch_a_sales_tax_unsupported": False,
        "acknowledges_qbi_below_threshold": False,
        "acknowledges_unlimited_at_risk": True,
        "basis_tracked_externally": True,
        "acknowledges_no_partnership_se_earnings": False,
        "acknowledges_no_section_1231_gain": False,
        "acknowledges_no_more_than_four_k1s": False,
        "acknowledges_no_k1_credits": True,
        "acknowledges_no_section_179": False,
        "acknowledges_no_estate_trust_k1": False,
        "prior_year_itemized": False,
        "acknowledges_no_wash_sale_adjustments": False,
        "acknowledges_no_other_basis_adjustments": False,
        "acknowledges_no_28_rate_gain": False,
        "acknowledges_no_unrecaptured_section_1250": False,
        "acknowledges_no_1120s_schedule_l_needed": False,
        "acknowledges_no_1120s_schedule_m_needed": False,
        "acknowledges_constant_shareholder_ownership": False,
        "acknowledges_no_section_1375_tax": False,
        "acknowledges_no_section_1374_tax": False,
        "acknowledges_cogs_aggregate_only": False,
        "acknowledges_officer_comp_aggregate_only": False,
        "acknowledges_no_elective_payment_election": False,
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
            **plan_d_attestation_defaults(),
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
