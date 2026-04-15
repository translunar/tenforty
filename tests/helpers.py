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


def make_simple_scenario() -> Scenario:
    """Create a simple single-filer scenario for tests that need a Scenario instance.

    Sets both Plan B scope-out attestations (`has_foreign_accounts`,
    `acknowledges_form_8949_unsupported`) to False so in-memory fixtures mirror
    the load-time contract enforced on YAML fixtures.
    """
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
            has_foreign_accounts=False,
            acknowledges_form_8949_unsupported=False,
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
