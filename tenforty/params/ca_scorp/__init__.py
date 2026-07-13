# tenforty/params/ca_scorp/__init__.py
"""Per-year California S-corporation (Form 100S) tax parameters.

Year-agnostic Form 100S logic reads everything from CAScorpParams; there
are no `if year ==` branches in the math. Adding a year = adding one yNNNN
module and declaring the year in tenforty/years.py (CA_SCORP_YEARS).

Every value here is dual-transcribed and attested from official FTB
primary sources (Form 100S booklet / R&TC); see the matching
tests/params_attestations/ca_scorp_yNNNN.py records and the layer-1
attestation gate in tests/test_params_attestation.py. NO field has a
default: a schema addition forces every year red until it is re-attested.
"""
import importlib
from dataclasses import dataclass

from tenforty import years as year_manifest


@dataclass(frozen=True)
class CAScorpParams:
    year: int
    # Form 100S franchise tax rate on net income for S corporations.
    franchise_tax_rate: float
    # Annual minimum franchise tax (applies even in loss years).
    minimum_franchise_tax: int
    # Whether a corporation's FIRST taxable year is exempt from the
    # minimum (measured tax still applies). Statutory rule, attested.
    first_year_minimum_tax_exempt: bool
    # Whether estimated payments are required for the family (informational
    # for diagnostics; Form 100-ES generation is out of scope).
    estimated_payment_required: bool


def load(year: int) -> CAScorpParams:
    if year not in year_manifest.CA_SCORP_YEARS:
        raise NotImplementedError(
            f"CA S-corp params: year {year} not in "
            f"{year_manifest.describe(year_manifest.CA_SCORP_YEARS)}")
    mod = importlib.import_module(f"tenforty.params.ca_scorp.y{year}")
    return mod.PARAMS
