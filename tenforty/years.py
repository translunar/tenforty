# tenforty/years.py
"""Single source of truth for which tax years tenforty supports.

Every other statement of year support — params load() gates, PDF mapping
year keys, error messages, test parameterizations — is checked against
(or derived from) this module. Declaring a year here without completing
its data pack is caught by the completeness gate; completing a pack
without declaring the year here leaves it unreachable. No silent
half-support in either direction.

This module must import nothing from tenforty — every params/mappings
module gates on it, so any import here risks a cycle.
"""
from collections.abc import Iterable

# Full federal pipeline: native spine compute + PDF emit.
FEDERAL_YEARS: tuple[int, ...] = (2024, 2025)

# Full California pipeline: 540 compute + PDF emit + divergence catalog.
CALIFORNIA_YEARS: tuple[int, ...] = (2024, 2025)

# CA 540 math only — validated against FTB-published worked examples
# (see tests/test_ca540_compute.py oracles), but no PDF mappings, emit
# path, or divergence catalog. A year leaves this tier by completing
# its pack and moving to CALIFORNIA_YEARS.
CALIFORNIA_COMPUTE_ONLY_YEARS: tuple[int, ...] = (2021, 2022, 2023)

# Years with a third-party XLS workbook registered at
# spreadsheets/federal/<year>/1040.xlsx. Optional per year: the workbook
# is an acceptance oracle and the out-of-spine-scope fallback, not a
# requirement for support.
WORKBOOK_YEARS: tuple[int, ...] = (2024, 2025)

# Form sets per jurisdiction — the second dimension of the support grid.
# Names match the mappings/pdf_<name>.py module basenames.
FEDERAL_FORMS: tuple[str, ...] = (
    "1040", "sch_1", "sch_a", "sch_b", "sch_d", "sch_e",
    "4562", "4868", "8959", "f8582", "f8949", "f8995",
    "f1120s", "f1120s_k1",
)
CALIFORNIA_FORMS: tuple[str, ...] = ("f540", "sch_ca", "sch_d_540")


def describe(years: Iterable[int]) -> str:
    """Render a year set for error messages: '2021, 2024, 2025'."""
    return ", ".join(str(y) for y in sorted(years))
