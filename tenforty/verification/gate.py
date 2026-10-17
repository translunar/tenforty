"""The runtime gate (spec §8; rulings Q1-Q6, 2026-10-17).

``fill()`` calls ``check`` before a form's template is opened. For a DECLARED
form, every declared line whose key has a value in ``values`` must reach a
field in what is about to print:

1. the line's key resolves, through the spec's mapping (a repeater spec's
   scalars), to a field present in the final payload (``PdfFiller``'s
   resolution, then the ``blank_when_zero`` drop). A valued key that no
   field prints, a derivation-only line included, is a finding: the gate
   never reverse-engineers derivations (ruling Q3);
2. when that field is an aggregation cell, every constituent key is present
   and not ``None``; otherwise ``PdfFiller`` would print a partial sum.

Repeat lines are checked through the model's own ``expand`` (ruling Q4);
for an option group only the line its value selects must be present
(exclusivity is the check-suite's; Q5); ``scope="WORKBOOK"`` lines are
outside the harness (Q6). Any finding refuses with ``IncompleteEmitError``
listing every one, before anything is written; there is no
acknowledge-and-proceed.

A PENDING form (``pending.PENDING_DECLARATIONS``) passes untouched (D3). A
form neither declared nor pending refuses: an emitted form must be one or
the other (Q1).

``missing_lines`` is shared with the harness's Value check, so the test
proves exactly what production enforces.
"""
from collections.abc import Mapping

from tenforty.declarations import registry
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.filing.pdf import PdfFiller, apply_blank_when_zero
from tenforty.verification import pending
from tenforty.verification.findings import Finding


class IncompleteEmitError(ValueError):
    """An emit that would print a declared line blank (or incomplete)."""


def final_payload(spec, values: Mapping) -> dict[str, str]:
    """The ``{pdf field: text}`` about to print: PdfFiller's own resolution,
    then the ``blank_when_zero`` drop (the same helper ``PdfFiller.fill``
    uses)."""
    if spec.kind == "flat":
        payload = PdfFiller.resolve_fields(
            spec.mapping, values,
            aggregations=spec.aggregations or None,
            derivations=spec.derivations or None,
            checkbox_states=spec.checkbox_states or None,
            field_formats=spec.field_formats or None,
        )
    else:
        payload = PdfFiller._expand_repeaters(spec.mapping, values)
    return apply_blank_when_zero(payload, spec.blank_when_zero)


def _where(decl: FormDeclaration) -> str:
    return "/".join(decl.form)


def missing_lines(decl: FormDeclaration, values: Mapping,
                  final_payload: Mapping[str, str], spec) -> list[Finding]:
    """Every declared line that has a value but would not print (rule 1),
    or would print an incomplete aggregation (rule 2)."""
    where = _where(decl)
    mapping = spec.mapping["scalars"] if spec.kind == "repeater" else spec.mapping
    findings: list[Finding] = []

    def finding(ln, message: str) -> None:
        findings.append(Finding(
            scenario="", form=where, year=decl.key, line=ln.line,
            check="gate",
            message=(f"{where} {decl.key} line {ln.line} "
                     f"({ln.description!r}, key {ln.key!r}): {message}")))

    for ln in expand(decl, values):
        if ln.scope == "WORKBOOK":
            continue
        value = values.get(ln.key)
        if value is None:
            continue  # nothing computed: blank is correct
        if ln.selects is not None and str(value) != ln.selects:
            continue  # an option this value does not select
        field = mapping.get(ln.key)
        if field is None:
            finding(ln, "the computation produced a value, but no field of "
                        "this form's fill prints that key.")
            continue
        if field not in final_payload:
            finding(ln, f"the computation produced a value, but field "
                        f"{field!r} would print blank.")
            continue
        constituents = spec.aggregations.get(field)
        if constituents:
            absent = [k for k in constituents if values.get(k) is None]
            if absent:
                finding(ln, f"its total (field {field!r}) would print "
                            f"without {', '.join(absent)}: a partial sum.")
    return findings


def check(form: tuple[str, str], key: int | str, spec,
          values: Mapping) -> None:
    """Refuse (``IncompleteEmitError``) an emit of a declared form that
    would print a valued line blank or partial; pass a pending form; refuse
    a form neither declared nor pending."""
    if form in pending.PENDING_DECLARATIONS:
        return
    try:
        decl = registry.for_form(form, key)
    except LookupError:
        raise IncompleteEmitError(
            f"{'/'.join(form)} {key} is about to be filled, but it has no "
            "emit declaration and is not on PENDING_DECLARATIONS "
            "(tenforty/verification/pending.py). Every emitted form must be "
            "declared, or pending with a reason. Declare it, or add it to "
            "PENDING_DECLARATIONS.") from None
    findings = missing_lines(decl, values, final_payload(spec, values), spec)
    if findings:
        lines = "\n".join(f"  - {f.message}" for f in findings)
        raise IncompleteEmitError(
            f"{'/'.join(form)} {key} would print incomplete; refusing to "
            f"write it:\n{lines}\nCause: a value the computation produced "
            "does not reach the paper. Remedy: fix the form's mapping or "
            "fill spec so every declared line prints. There is no "
            "acknowledge-and-proceed.")
