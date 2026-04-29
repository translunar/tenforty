"""California Form 540 main-form compute helpers.

Year-parameterized lookups for the standard deduction and the
basic exemption credit (un-phased-out). Year-specific constants
live in tenforty/constants/california_y{year}.py modules and are
loaded dynamically.

The exemption credit returned here is the un-phased-out lookup;
the AGI phaseout (when federal AGI exceeds the per-year threshold)
is gated in T11's final-liability compute, not here.
"""

import importlib

from tenforty.models import FilingStatus


def _load_ca_constants(year: int):
    try:
        return importlib.import_module(f"tenforty.constants.california_y{year}")
    except ImportError as e:
        raise NotImplementedError(
            f"CA Form 540 not implemented for tax year {year} "
            f"(tenforty v1 supports tax years 2021-2025)."
        ) from e


def compute_standard_deduction(year: int, filing_status: FilingStatus) -> int:
    constants = _load_ca_constants(year)
    return constants.STANDARD_DEDUCTION[filing_status]


def compute_exemption_credit(year: int, filing_status: FilingStatus) -> int:
    constants = _load_ca_constants(year)
    return constants.EXEMPTION_CREDIT[filing_status]
