"""The official stylesheet cross-check (spec §5.3), federal declarations.

Each declared line is diffed against the IRS MeF stylesheet's line for the
same printed label (``propose.stylesheet_lines``: by section and full label,
sub-letters carrying their number). Text agreement uses the binding
proposer's own scoring (``propose.words``/``jaccard`` against
``propose.STYLESHEET_AGREEMENT``): the provisional thresholds live in exactly
one place.

Failures: a declared label the stylesheet does not print; declared text
that materially differs; a declared ``mef_element`` the stylesheet does not
put on that line. Stylesheet amount lines no declaration names are
information only (``undeclared_amount_lines``), never failures.
"""
from types import SimpleNamespace

from tenforty.declarations import propose
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.verification.findings import Finding


def _hit(stylesheet_lines, section: str, label: str):
    return propose._stylesheet_line(
        stylesheet_lines, SimpleNamespace(section=section, label=label))


def crosscheck(decl: FormDeclaration, stylesheet_lines) -> list[Finding]:
    """Findings for every declared line that disagrees with the stylesheet."""
    where = "/".join(decl.form)
    findings = []

    def finding(line: str, message: str) -> None:
        findings.append(Finding(scenario="", form=where, year=decl.key,
                                line=line, check="stylesheet",
                                message=message))

    for ln in expand(decl, {}):
        if ln.repeat is not None:
            continue
        hit = _hit(stylesheet_lines, ln.section, ln.line)
        if hit is None:
            finding(ln.line, f"{where} {decl.key}: declared line {ln.line!r} "
                             f"(section {ln.section!r}) is not printed by the "
                             "official stylesheet.")
            continue
        agreement = propose.jaccard(set(propose.words(hit.text)),
                                    set(propose.words(ln.description)))
        if agreement < propose.STYLESHEET_AGREEMENT:
            finding(ln.line, f"{where} {decl.key} line {ln.line}: declared "
                             f"text {ln.description!r} differs from the "
                             f"stylesheet's {hit.text!r} (agreement "
                             f"{agreement:.2f} < "
                             f"{propose.STYLESHEET_AGREEMENT}).")
        if ln.mef_element and ln.mef_element not in hit.elements:
            finding(ln.line, f"{where} {decl.key} line {ln.line}: declared "
                             f"mef_element {ln.mef_element!r} is not among "
                             f"the stylesheet's {list(hit.elements)}.")
    return findings


def undeclared_amount_lines(decl: FormDeclaration,
                            stylesheet_lines) -> list[str]:
    """Stylesheet lines (with an element) no declared line names:
    information for the form-coverage report, never a failure."""
    declared = {(ln.section, ln.line) for ln in expand(decl, {})}
    labels = {ln.line for ln in expand(decl, {})}
    out = []
    for (section, label), line in sorted(stylesheet_lines.items()):
        if line.elements and (section, label) not in declared \
                and label not in labels:
            out.append(f"{'/'.join(decl.form)} {decl.key} {section}:{label} "
                       f"{line.text[:60]!r} {list(line.elements)}")
    return out
