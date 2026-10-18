"""Static validation of a declaration against its official inventory.

``validate(decl)`` reports every structural problem as a ``Finding``
(``scenario=""``, since no scenario is involved). It reads the official
inventory for the declaration's own form and key (spec §2.1: every year is
checked against that year's own inventory), never tenforty's mappings.

Checks (check name in brackets):
- [inventory] every non-repeat ``(section, line)`` is a printed line of that
  key's inventory;
- [group] ``selects`` implies ``group``, and every line of a group binds
  the same key (ruling A2: one key, one value per option line);
- [single_state] ``single_state`` carries a non-empty reason;
- [not_printed] every not-printed reason starts with a known tag; an
  ``other-year:`` reason (a key whose printed line exists only in another
  year's layout) is accepted only when another year of the same form
  (``siblings``) binds that key, so the claim cannot go silently false;
- [duplicate] no ``(section, line)`` is declared twice;
- [inventory_exemption] a line's ``inventory_exemption`` (a ruled paper line
  the inventory cannot print, e.g. Schedule C Part V's unlabeled grid rows)
  carries a reason and is still absent from the inventory: once a
  regenerated inventory prints the line, the exemption is stale.

``exemptions_in_force(decl)`` enumerates every exemption a declaration
carries, so they never accumulate silently.
"""
from collections import Counter
from collections.abc import Iterable

from tenforty.declarations import inventory
from tenforty.declarations.model import FormDeclaration
from tenforty.verification.findings import Finding

OTHER_YEAR_TAG = "other-year:"
NOT_PRINTED_TAGS = ("intermediate:", "presentation-only:", "diagnostic:",
                    OTHER_YEAR_TAG)


def validate(decl: FormDeclaration,
             siblings: Iterable[FormDeclaration] = ()) -> list[Finding]:
    """``siblings``: the same module's declarations for other keys, against
    which ``other-year:`` not-printed entries are verified."""
    jurisdiction, form = decl.form
    where = f"{jurisdiction}/{form}"
    findings: list[Finding] = []

    def finding(line: str, check: str, message: str) -> None:
        findings.append(Finding(scenario="", form=where, year=decl.key,
                                line=line, check=check, message=message))

    printed = {(ln.section, ln.label)
               for ln in inventory.load(form, decl.key).lines}
    for ln in decl.lines:
        if ln.inventory_exemption is not None:
            if not ln.inventory_exemption.strip():
                finding(ln.line, "inventory_exemption",
                        f"line {ln.line!r} carries an inventory_exemption "
                        "without a reason.")
            elif ln.line_id in printed:
                finding(ln.line, "inventory_exemption",
                        f"{where} {decl.key} line {ln.line!r} in section "
                        f"{ln.section!r} is exempt from the inventory, but "
                        "the inventory now prints it: the exemption is stale "
                        f"({ln.inventory_exemption})")
            continue
        if ln.repeat is None and ln.line_id not in printed:
            finding(ln.line, "inventory",
                    f"{where} {decl.key} declares line {ln.line!r} in section "
                    f"{ln.section!r}, which the official form's inventory "
                    "does not print.")

    group_keys: dict[str, set[str]] = {}
    for ln in decl.lines:
        if ln.selects is not None and ln.group is None:
            finding(ln.line, "group",
                    f"line {ln.line!r} sets `selects` without a `group`.")
        if ln.group is not None:
            group_keys.setdefault(ln.group, set()).add(ln.key)
    for group, keys in sorted(group_keys.items()):
        if len(keys) > 1:
            finding(group, "group",
                    f"option group {group!r} binds several keys "
                    f"{sorted(keys)}; every line of a group shares one key.")

    for ln in decl.lines:
        if ln.single_state is not None and not (
                ln.single_state_reason or "").strip():
            finding(ln.line, "single_state",
                    f"line {ln.line!r} is single_state={ln.single_state!r} "
                    "without a reason.")

    bound_elsewhere = {ln.key for other in siblings
                       if other.form == decl.form and other.key != decl.key
                       for ln in other.lines if ln.key}
    for key, reason in sorted(decl.not_printed.items()):
        if not reason.startswith(NOT_PRINTED_TAGS):
            finding(key, "not_printed",
                    f"not-printed key {key!r} reason {reason!r} must start "
                    f"with one of {', '.join(NOT_PRINTED_TAGS)}")
        elif reason.startswith(OTHER_YEAR_TAG) and key not in bound_elsewhere:
            finding(key, "not_printed",
                    f"not-printed key {key!r} is tagged {OTHER_YEAR_TAG!r} "
                    f"but is bound in no other year of {where} among the "
                    "siblings supplied: the claim is unverified or stale "
                    f"({reason})")

    counts = Counter(ln.line_id for ln in decl.lines)
    for (section, line), n in sorted(counts.items()):
        if n > 1:
            finding(line, "duplicate",
                    f"line {line!r} in section {section!r} is declared {n} "
                    "times.")
    return findings


def exemptions_in_force(decl: FormDeclaration) -> list[tuple[tuple[str, str], str]]:
    """Every ``(section, line)`` the declaration exempts from the inventory,
    with its reason, in declaration order. Each is also excluded from
    placement (``checks.check_placement``) until the check-suite can locate
    it; its value and ink checks still run."""
    return [(ln.line_id, ln.inventory_exemption) for ln in decl.lines
            if ln.inventory_exemption is not None]
