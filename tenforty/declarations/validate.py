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
- [not_printed] every not-printed reason starts with a known tag;
- [duplicate] no ``(section, line)`` is declared twice.
"""
from collections import Counter

from tenforty.declarations import inventory
from tenforty.declarations.model import FormDeclaration
from tenforty.verification.findings import Finding

NOT_PRINTED_TAGS = ("intermediate:", "presentation-only:", "diagnostic:")


def validate(decl: FormDeclaration) -> list[Finding]:
    jurisdiction, form = decl.form
    where = f"{jurisdiction}/{form}"
    findings: list[Finding] = []

    def finding(line: str, check: str, message: str) -> None:
        findings.append(Finding(scenario="", form=where, year=decl.key,
                                line=line, check=check, message=message))

    printed = {(ln.section, ln.label)
               for ln in inventory.load(form, decl.key).lines}
    for ln in decl.lines:
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

    for key, reason in sorted(decl.not_printed.items()):
        if not reason.startswith(NOT_PRINTED_TAGS):
            finding(key, "not_printed",
                    f"not-printed key {key!r} reason {reason!r} must start "
                    f"with one of {', '.join(NOT_PRINTED_TAGS)}")

    counts = Counter(ln.line_id for ln in decl.lines)
    for (section, line), n in sorted(counts.items()):
        if n > 1:
            finding(line, "duplicate",
                    f"line {line!r} in section {section!r} is declared {n} "
                    "times.")
    return findings
