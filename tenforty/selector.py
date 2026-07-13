"""Changed-forms selector for federal paper amendments (spec §4).

Federal paper amendments attach ONLY the forms that changed or are new.
Selection is machine-derived by comparing two already-built per-form
emit-payload dict-sets (the as-filed run vs. the corrected run). These are
pure dict comparisons: no I/O, no scenario execution, no PDF rendering.

Caveat (spec §4): selection compares tenforty-vs-tenforty runs, so a form
the FILED return included erroneously (that tenforty never emits) cannot be
selected here. That class, along with dropped forms, is surfaced in the
packet manifest, which defers to the preparer.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChangedForm:
    """A federal form selected for the amendment attachment subset.

    ``reason`` is ``"changed"`` when the form exists in both runs but at least
    one mapped payload value differs, and ``"new"`` when the form is present in
    the corrected run and absent from the as-filed run.
    """

    form: str
    reason: Literal["changed", "new"]


def changed_forms(
    filed_payloads: dict[str, dict],
    corrected_payloads: dict[str, dict],
) -> list[ChangedForm]:
    """Return the federal forms to attach to the amendment, sorted by name.

    For each form present in ``corrected_payloads``:

    - absent from ``filed_payloads`` -> ``ChangedForm(form, "new")``;
    - present but any mapped value differs -> ``ChangedForm(form, "changed")``;
    - present and identical -> NOT selected.

    Forms present only in ``filed_payloads`` (dropped by the corrected run) are
    NOT selected here; see :func:`dropped_forms`.
    """
    selected: list[ChangedForm] = []
    for form in sorted(corrected_payloads):
        if form not in filed_payloads:
            selected.append(ChangedForm(form, "new"))
        elif corrected_payloads[form] != filed_payloads[form]:
            selected.append(ChangedForm(form, "changed"))
    return selected


def dropped_forms(
    filed_payloads: dict[str, dict],
    corrected_payloads: dict[str, dict],
) -> list[str]:
    """Return form names present in the filed run but absent from corrected.

    These forms are correctly excluded from the attach list, but must not be
    silent: the packet manifest lists them as "no longer applies -- not
    attached; preparer notes in explanation" (parallel to the §4
    erroneous-inclusion caveat). Sorted by name for determinism.
    """
    return sorted(form for form in filed_payloads if form not in corrected_payloads)
