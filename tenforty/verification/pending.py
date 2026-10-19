"""Forms not yet under the harness (spec §10 D3).

Until a form is declared, the runtime gate is inactive for it and it emits
exactly as before. Every entry carries its reason; the list starts as every
form ``fill()`` can be called with and must be empty when the harness program
finishes. ``PendingRegistryTests`` pins it exact in both directions: every
fillable form is pending or declared, and no pending entry is stale.
"""
from collections.abc import Mapping

from tenforty.mappings.catalog import CATALOG

_REASON = "DECLARATION PENDING: harness v0.2.1 burn-down"

# Every form identity fill() is called with: the catalog forms, plus the
# amendment forms (1040-X, Schedule X) and the revision-keyed Form 3115.
_FILLABLE_FORMS = (
    *sorted(CATALOG),
    ("federal", "f1040x"),
    ("california", "schedule_x"),
    ("federal", "f3115"),
)

# Graduated forms: declared, registered in tenforty.declarations.forms, and
# under the runtime gate. A form leaves the pending list only here, in the
# same commit that registers it.
_GRADUATED = frozenset({
    ("federal", "sch_se"),
    ("federal", "sch_c"),
    ("federal", "sch_2"),
    ("federal", "sch_1"),
})

PENDING_DECLARATIONS: Mapping[tuple[str, str], str] = {
    form: _REASON for form in _FILLABLE_FORMS if form not in _GRADUATED
}


def registry_problems() -> list[str]:
    """The registry's standing invariants, read live: no form both declared
    and pending (D3), and no declared form-key with work still in progress
    (D2: WORK_IN_PROGRESS must be empty to merge)."""
    from tenforty.declarations import registry
    problems = []
    declared = {form for form, _key in registry.declared_forms()}
    for form in sorted(declared & set(PENDING_DECLARATIONS)):
        problems.append(f"{'/'.join(form)} is both declared and pending")
    for form_key, lines in sorted(registry.WORK_IN_PROGRESS.items(), key=str):
        problems.append(f"{form_key} has work in progress: {list(lines)}")
    return problems
