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


def crosscheck(decl: FormDeclaration, stylesheet_lines,
               discrepancies=None) -> list[Finding]:
    """Findings for every declared line that disagrees with the stylesheet.

    ``discrepancies`` (``discrepancies_in_force``: ``(section, line)`` ->
    reason, for this year) are the declaration module's documented witness
    discrepancies. A documented line's findings are suppressed; a documented
    line with no finding is itself a finding (stale: the stylesheet in fact
    agrees), so the record can neither hide an undocumented disagreement nor
    outlive the one it documents."""
    where = "/".join(decl.form)
    findings = []
    disagreeing: set[tuple[str, str]] = set()
    documented = dict(discrepancies or {})

    def finding(line: str, message: str) -> None:
        if line_id in documented:
            disagreeing.add(line_id)
            return
        findings.append(Finding(scenario="", form=where, year=decl.key,
                                line=line, check="stylesheet",
                                message=message))

    for ln in expand(decl, {}):
        if ln.repeat is not None:
            continue
        line_id = ln.line_id
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
    for (section, line), reason in sorted(documented.items()):
        if (section, line) not in disagreeing:
            findings.append(Finding(
                scenario="", form=where, year=decl.key, line=line,
                check="stylesheet",
                message=(f"{where} {decl.key}: documented witness "
                         f"discrepancy for line {line!r} (section "
                         f"{section!r}) is stale: the stylesheet agrees with "
                         f"the declaration, or no such line is declared "
                         f"({reason})")))
    return findings


def discrepancies_in_force(module, year: int) -> dict[tuple[str, str], str]:
    """A declaration module's documented witness discrepancies for ``year``
    (``WITNESS_DISCREPANCIES``: ``(section, line)`` -> ``(years, reason)``),
    as ``(section, line)`` -> reason. A module without the record has none."""
    record = getattr(module, "WITNESS_DISCREPANCIES", {})
    return {line_id: reason for line_id, (years, reason) in record.items()
            if year in years}


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
