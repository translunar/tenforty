"""Computed but not printed (spec §2.3; ruling A4).

Within one scenario's packet, every compute key the DECLARED forms were
filled from is either bound by some declared line (of any form in the
packet) or listed in some declaration's ``not_printed`` with a reason. A
key in neither place is undeclared: a new compute key nobody wired to paper.

The universe is the union of the ``EmitRecord.values`` keys of the packet's
declared forms (ruling A4: packet scope; there is no ``cross-form:`` tag).
Pending forms are outside it: the harness is inactive for them (D3).
"""
import re
from collections.abc import Iterable

from tenforty.declarations import registry
from tenforty.declarations.model import FormDeclaration
from tenforty.verification.findings import Finding
from tenforty.verification.record import RecordedForm


def _key_patterns(decls: Iterable[FormDeclaration]) -> list[re.Pattern]:
    patterns = []
    for decl in decls:
        for ln in decl.lines:
            if ln.repeat is not None:
                placeholder = "{" + ln.repeat.index_name + "}"
                regex = re.escape(ln.key).replace(
                    re.escape(placeholder), r"[A-Za-z0-9]+")
            else:
                regex = re.escape(ln.key)
            patterns.append(re.compile(regex))
        patterns += [re.compile(re.escape(k)) for k in decl.not_printed]
    return patterns


def undeclared_keys(records: Iterable[RecordedForm], scenario: str = ""
                    ) -> list[Finding]:
    """Undeclared keys of ONE scenario's packet (``records``)."""
    declared = {}
    universe: dict[str, RecordedForm] = {}
    for rec in records:
        try:
            decl = registry.for_form(rec.form, rec.key)
        except LookupError:
            continue  # pending: outside the harness (D3)
        declared[(rec.form, rec.key)] = decl
        for key in rec.values:
            universe.setdefault(key, rec)
    patterns = _key_patterns(declared.values())
    findings = []
    for key, rec in sorted(universe.items()):
        if any(p.fullmatch(key) for p in patterns):
            continue
        findings.append(Finding(
            scenario=scenario, form="/".join(rec.form), year=rec.key,
            line="", check="undeclared",
            message=f"compute key {key!r} (filled into {'/'.join(rec.form)} "
                    f"{rec.key}) is neither bound by a declared line nor "
                    "listed in any declaration's not_printed."))
    return findings
