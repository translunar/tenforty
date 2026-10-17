"""The one accessor for emit declarations (spec §2.1).

Each declared form module registers its ``FormDeclaration`` per key here.
``for_form`` raises ``LookupError`` for an undeclared form-key, so a caller
can never mistake "not declared" for "declares nothing".
"""
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
