"""The one accessor for emit declarations (spec §2.1).

Each declared form module registers its ``FormDeclaration`` per key here.
``for_form`` raises ``LookupError`` for an undeclared form-key, so a caller
can never mistake "not declared" for "declares nothing".
"""
import re
from collections.abc import Mapping

from tenforty.declarations.model import FormDeclaration

FormKey = tuple[tuple[str, str], int | str]

_DECLARATIONS: dict[FormKey, FormDeclaration] = {}

# A declared form-key's lines still being authored (spec §10 D2): form-key ->
# the lines not yet declared. May be non-empty on a lane branch; MUST be
# empty to merge (pinned by RegistryTests).
WORK_IN_PROGRESS: Mapping[FormKey, tuple[str, ...]] = {}


def register(decl: FormDeclaration) -> FormDeclaration:
    """Add a declaration; a second declaration for one form-key refuses."""
    form_key = (decl.form, decl.key)
    if form_key in _DECLARATIONS:
        raise ValueError(f"{decl.form} {decl.key} is already declared.")
    _DECLARATIONS[form_key] = decl
    return decl


def for_form(form: tuple[str, str], key: int | str) -> FormDeclaration:
    try:
        return _DECLARATIONS[(form, key)]
    except KeyError:
        raise LookupError(
            f"{form} {key} has no emit declaration (it is on the pending "
            "list).") from None


def declared_forms() -> frozenset[FormKey]:
    return frozenset(_DECLARATIONS)


# Emitted keys that are NOT form fills, each with its reason (ruling
# 2026-10-17). An entry is an exact key, or a pattern whose only variable part
# is an explicit "{i}" (a 1-based copy number), matched against the WHOLE key.
# Every emitted key is either a recorded fill (EmitRecord) or matches here;
# EveryEntryPointCarriesRecordTests fails closed on anything else. Reviewed
# like WORK_IN_PROGRESS.
NON_FILL_EMITTED: Mapping[str, str] = {
    "1120s_k1_qbi_stmt_{i}":
        "Section 199A Statement A per shareholder: a generated statement "
        "page (reportlab), not a form fill",
    "1120s_other_deductions_stmt":
        "Form 1120-S line 19 other-deductions statement: a generated "
        "statement page, not a form fill",
    "f100s_other_deductions_stmt":
        "Form 100S other-deductions statement: a generated statement page, "
        "not a form fill",
    "f3115_asset_stmt":
        "Form 3115 Schedule E asset statement: a generated statement page, "
        "not a form fill",
    "f3115_duplicate_copy":
        "Form 3115 duplicate copy to sign: a packet concatenation of the "
        "already-filled, recorded Form 3115 and its statement",
    "depreciation_audit":
        "the depreciation audit workbook (.xlsx), not a PDF form",
    "sch_1_8z_stmt":
        "Schedule 1 line 8z statement (two or more Form 1099-G types): a "
        "generated statement page (reportlab), not a form fill",
}


def _non_fill_pattern(entry: str) -> re.Pattern:
    return re.compile(re.escape(entry).replace(re.escape("{i}"), r"[1-9]\d*"))


_NON_FILL_PATTERNS = {entry: _non_fill_pattern(entry)
                      for entry in NON_FILL_EMITTED}


def non_fill_reason(key: str) -> str | None:
    """The reason ``key`` is an emitted non-fill, or None."""
    for entry, pattern in _NON_FILL_PATTERNS.items():
        if pattern.fullmatch(key):
            return NON_FILL_EMITTED[entry]
    return None


# Populate the registry: ``forms`` imports each graduated form's declaration
# module, and each calls ``register`` above at import time. This import must
# stay at the bottom, after ``register`` is defined, to break the cycle.
from tenforty.declarations import forms  # noqa: E402,F401
