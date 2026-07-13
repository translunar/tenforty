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
FEDERAL_YEARS: tuple[int, ...] = (2022, 2023, 2024, 2025)

# Federal spine math only — native 1040 compute, validated against the Layer-2
# tax-table oracle and air-gapped attested params, but NO PDF mappings, emit
# path, or workbook requirement. Mirrors CALIFORNIA_COMPUTE_ONLY_YEARS: a year
# leaves this tier by completing its PDF pack and moving to FEDERAL_YEARS.
# Backfilled to enable filed-return reconciliation for a prior year.
FEDERAL_COMPUTE_ONLY_YEARS: tuple[int, ...] = (2021,)

# Full California pipeline: 540 compute + PDF emit + divergence catalog.
CALIFORNIA_YEARS: tuple[int, ...] = (2023, 2024, 2025)

# CA 540 math only — validated against FTB-published worked examples
# (see tests/test_ca540_compute.py oracles), but no PDF mappings, emit
# path, or divergence catalog. A year leaves this tier by completing
# its pack and moving to CALIFORNIA_YEARS.
CALIFORNIA_COMPUTE_ONLY_YEARS: tuple[int, ...] = (2021, 2022)

# Years with a third-party XLS workbook registered at
# spreadsheets/federal/<year>/1040.xlsx. Optional per year: the workbook
# is an acceptance oracle and the out-of-spine-scope fallback, not a
# requirement for support. A COMPUTE-ONLY federal year may still carry a
# workbook as a BONUS oracle (e.g. 2021, wired as a bounded partial — its
# vendor workbook omits the Form 8582 tab, so that key group is declared in
# F1040.WORKBOOK_KEY_EXCLUSIONS and surfaced as explicit parity skips).
WORKBOOK_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)

# Form sets per jurisdiction — the second dimension of the support grid.
# Names match the mappings/pdf_<name>.py module basenames.
FEDERAL_FORMS: tuple[str, ...] = (
    "1040", "sch_1", "sch_a", "sch_b", "sch_d", "sch_e",
    "4562", "4868", "8959", "f8582", "f8949", "f8995",
)

# Compute-only federal form set: the individual-return family, EXCLUDING the
# S-corp forms (f1120s, f1120s_k1). The S-corp packet workstream owns all
# S-corp support via its own SCORP_FEDERAL_YEARS tier, so a compute-only year's
# gate must not demand S-corp coverage (the two workstreams would collide on
# the same grid cell). Derived from FEDERAL_FORMS so it auto-collapses back to
# the full set once the S-corp SCORP_FORMS split lands on that workstream.
FEDERAL_COMPUTE_ONLY_FORMS: tuple[str, ...] = tuple(
    f for f in FEDERAL_FORMS if f not in ("f1120s", "f1120s_k1")
)

CALIFORNIA_FORMS: tuple[str, ...] = ("f540", "sch_ca", "sch_d_540")

# S-corporation form family. Decoupled from FEDERAL_YEARS: the S-corp
# return has its own year support (backfill reaches 2021 without touching
# the individual-return tiers). See docs/specs/2026-07-12-s-corp-packet-design.md §4-5.
SCORP_FEDERAL_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)
SCORP_FORMS: tuple[str, ...] = ("f1120s", "f1120s_k1")

# California S-corp family: Form 100S compute and emit (emit has landed —
# PdfF100S/PdfF100SK1 + _emit_ca_scorp_pdfs_internal, exposed via public
# run_full_california_scorp_return; the completeness gate tracks pack contents).
CA_SCORP_YEARS: tuple[int, ...] = (2021, 2022, 2023, 2024, 2025)
CA_SCORP_FORMS: tuple[str, ...] = ("f100s", "f100s_k1")


def describe(years: Iterable[int]) -> str:
    """Render a year set for error messages: '2021, 2024, 2025'."""
    return ", ".join(str(y) for y in sorted(years))
