"""The harness checks (spec §3.1): Value, Placement, Ink, Option groups, and
the emit's completeness. Each runs on what the REAL emit produced (a
``RecordedForm`` from the entry point's ``EmitRecord``), against an
already-authored declaration. Every check returns a list of ``Finding``s and
never raises; nothing is recomputed on the side.

Jurisdiction (ruled 2026-10-17): the runtime gate owns PRESENCE (a valued
declared line reaches the payload; ``gate.missing_lines``, which
``check_value`` reuses); the check-suite owns the PRINTED RESULT (what the
PDF holds, where it sits, its ink) and option-group EXCLUSIVITY. Both find
an option line's widget the same way: ``options.option_widgets``.
"""
import dataclasses
import functools
import traceback
from collections.abc import Mapping
from pathlib import Path

from pypdf import PdfReader

from tenforty.declarations import registry
from tenforty.declarations.model import DeclaredLine, FormDeclaration, expand
from tenforty.mappings.catalog import CATALOG
from tenforty.rounding import irs_round
from tenforty.verification import anchors as anchor_eval
from tenforty.verification.findings import Finding
from tenforty.verification.gate import final_payload, missing_lines
from tenforty.verification.options import option_widgets
from tenforty.verification.pixels import dark_pixels_in_rect
from tenforty.verification.record import EmitRecord, RecordedForm

# Ink thresholds, from the hand tests they generalize: a button needs at
# least MIN_INK_BUTTON dark pixels in its rect inset BUTTON_INSET
# (tests/test_ca_button_ink.py MIN_INK); text needs more than MIN_INK_TEXT
# with inset TEXT_INSET (CaSpouseDobPlacementTests). "No ink" is below the
# same threshold.
MIN_INK_BUTTON = 15
BUTTON_INSET = 2.0
MIN_INK_TEXT = 8
TEXT_INSET = 1.0
_OFF = ("", "/Off", "Off")

# The repeater-shape universe (census of every CATALOG mapping, 2021-2025;
# pinned 2026-10-17): the only non-empty repeater sections anywhere are Form
# 8949's pre-baked row lists, which FillSpec.flattened() fills flat. NO
# {template, max_slots} section exists, so template-repeater ROW checks are a
# pinned, named, EMPTY no-check zone (ruling 2026-10-17, option ii): the
# row-key convention is designed against the first real template-repeater
# form, and the census test failing is what forces it.
REPEATER_SHAPES = frozenset({
    ("f8949", "box_a_rows", "rows"),
    ("f8949", "box_b_rows", "rows"),
    ("f8949", "box_d_rows", "rows"),
    ("f8949", "box_e_rows", "rows"),
})


def _finding(decl: FormDeclaration, line: str, check: str,
             message: str) -> Finding:
    return Finding(scenario="", form="/".join(decl.form), year=decl.key,
                   line=line, check=check, message=message)


def _never_raises(check):
    """A check reports a problem it cannot evaluate as a finding; it never
    raises into the test that called it."""
    @functools.wraps(check)
    def guarded(rec, decl, *args, **kwargs):
        try:
            return check(rec, decl, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            return [_finding(
                decl, "", check.__name__.removeprefix("check_"),
                f"{check.__name__} could not run: {type(exc).__name__}: "
                f"{exc}\n{traceback.format_exc(limit=3)}")]
    return guarded


def _scalars(spec) -> Mapping[str, str]:
    return spec.mapping["scalars"] if spec.kind == "repeater" else spec.mapping


def _declared(decl: FormDeclaration, values: Mapping) -> list[DeclaredLine]:
    return [ln for ln in expand(decl, values) if ln.scope != "WORKBOOK"]


def _mapping_class_name(form: tuple[str, str]) -> str:
    entry = CATALOG.get(form)
    return entry.mapping_cls.__name__ if entry else "/".join(form)


def _full_name(widget) -> str:
    names, node = [], widget
    while node is not None:
        if "/T" in node:
            names.append(str(node["/T"]))
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ".".join(reversed(names))


def _widgets(pdf: Path) -> dict[str, list[tuple[int, list, str, list]]]:
    """field name -> [(page, rect, /AS, own /AP /N states)] per widget."""
    out: dict[str, list] = {}
    for pi, page in enumerate(PdfReader(str(pdf)).pages):
        for annot in page.get("/Annots") or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            ap = w.get("/AP", {}).get("/N")
            states = sorted(str(k) for k in ap.keys()) \
                if hasattr(ap, "keys") else []
            out.setdefault(_full_name(w), []).append(
                (pi, [float(v) for v in w["/Rect"]],
                 str(w.get("/AS") or "/Off"), states))
    return out


def _own_widget(widgets, field: str, on_state: str):
    """The widget of ``field`` whose own appearances include ``on_state``
    (a radio's kid; a checkbox's only widget)."""
    for w in widgets.get(field, []):
        if on_state in w[3]:
            return w
    return None


def _expected_text(ln: DeclaredLine, value) -> str:
    """The value rendered by ``kind`` (spec §3.1): amounts in whole dollars,
    IRS half-up, 0 printed as 0; everything else verbatim."""
    if ln.kind == "amount" and isinstance(value, (int, float)) \
            and not isinstance(value, bool):
        return str(irs_round(value))
    return str(value)


@_never_raises
def check_value(rec: RecordedForm, decl: FormDeclaration) -> list[Finding]:
    """Value (spec §3.1): a valued line prints its value; a line with nothing
    computed prints nothing. Presence is the gate's ``missing_lines`` (the
    same function production enforces); this adds what the PDF holds."""
    spec, values = rec.spec, rec.values
    findings: list[Finding] = []
    unprinted = set()
    lines = _declared(decl, values)
    for f in missing_lines(decl, values, final_payload(spec, values), spec):
        unprinted.add(f.line)
        ln = next(x for x in lines if x.line == f.line)
        field = _scalars(spec).get(ln.key)
        message = f.message
        if (field is not None and field in spec.blank_when_zero
                and values.get(ln.key) == 0):
            message += (f" Cause: {_mapping_class_name(rec.form)}'s "
                        f"blank_when_zero lists {field!r}, which erases the "
                        "computed 0 (the provenance rule prints a computed "
                        "zero).")
        findings.append(_finding(decl, f.line, "value", message))
    fields = PdfReader(str(rec.pdf_path)).get_fields() or {}
    widgets = None
    for ln in lines:
        if ln.line in unprinted:
            continue
        value = values.get(ln.key)
        if ln.selects is not None:
            if value is None or str(value) != ln.selects:
                continue  # exclusivity is check_option_groups'
            resolved = option_widgets(spec, ln.key, ln.selects)
            if len(resolved) != 1:
                continue  # the gate's finding above already names it
            widgets = widgets if widgets is not None else _widgets(rec.pdf_path)
            field, on = resolved[0]
            own = _own_widget(widgets, field, on)
            if own is None or own[2] != on:
                findings.append(_finding(
                    decl, ln.line, "value",
                    f"option line {ln.line} ({ln.key!r}={value!r}) should be "
                    f"ON as {on!r} in {field!r}; it is "
                    f"{own[2] if own else 'absent'!r}."))
            continue
        field_path = _scalars(spec).get(ln.key)
        if field_path is None or field_path not in fields:
            continue
        field = fields[field_path]
        stored = "" if field.get("/V") is None else str(field.get("/V"))
        if value is None:
            if stored not in _OFF:
                findings.append(_finding(
                    decl, ln.line, "value",
                    f"line {ln.line} ({ln.key!r}) has nothing computed but "
                    f"field {field_path!r} holds {stored!r}."))
            continue
        if field.get("/FT") == "/Btn":
            if (stored in _OFF) == bool(value):
                findings.append(_finding(
                    decl, ln.line, "value",
                    f"line {ln.line} ({ln.key!r}) is {value!r} but checkbox "
                    f"{field_path!r} is {stored or '/Off'!r}."))
            continue
        expected = _expected_text(ln, value)
        if stored != expected:
            findings.append(_finding(
                decl, ln.line, "value",
                f"line {ln.line} ({ln.key!r}) should print {expected!r}; "
                f"field {field_path!r} holds {stored!r}."))
    return findings


_PLACEMENT_CACHE: dict = {}


def check_placement(template: Path, decl: FormDeclaration,
                    spec) -> list[Finding]:
    """Placement (spec §3.3), on the blank template: each declared line's
    field sits where its anchor (explicit, or the default from its own
    label) says. Cached per (template, declaration, spec)."""
    cache_key = (str(template), decl.form, decl.key, id(decl), id(spec))
    if cache_key not in _PLACEMENT_CACHE:
        try:
            _PLACEMENT_CACHE[cache_key] = tuple(
                _placement(Path(template), decl, spec))
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            return [_finding(decl, "", "placement",
                             f"check_placement could not run: "
                             f"{type(exc).__name__}: {exc}")]
    return list(_PLACEMENT_CACHE[cache_key])


def _placement(template: Path, decl: FormDeclaration, spec) -> list[Finding]:
    has_tu = anchor_eval.template_has_tooltips(str(template))
    scalars = _scalars(spec)
    by_line = {ln.line: ln for ln in decl.lines}
    findings: list[Finding] = []
    for ln in expand(decl, {}):
        if ln.scope == "WORKBOOK":
            continue
        if ln.key == "":
            # A key-less line (unmodeled, or preprinted) has no mapped field
            # by definition. Placement checks mapping-declaration agreement,
            # which exists only for bound lines; a key-less line's nothing
            # state belongs to the ink side.
            continue
        if ln.selects is not None:
            resolved = option_widgets(spec, ln.key, ln.selects)
            field_path = resolved[0][0] if len(resolved) == 1 else None
        else:
            field_path = scalars.get(ln.key)
        if field_path is None:
            findings.append(_finding(
                decl, ln.line, "placement",
                f"line {ln.line} ({ln.key!r}) has no field to place."))
            continue
        anchor = ln.anchor or anchor_eval.default_anchor(ln, has_tu)
        other = None
        if isinstance(anchor, anchor_eval.NearField):
            other_line = by_line.get(anchor.other_line)
            other = scalars.get(other_line.key) if other_line else None
        result = anchor_eval.evaluate(anchor, field_path, template,
                                      other_field=other)
        if result is not None:
            findings.append(dataclasses.replace(
                result, form="/".join(decl.form), year=decl.key, line=ln.line,
                message=f"line {ln.line} ({ln.key!r}): {result.message}"))
    return findings


@_never_raises
def check_ink(rec: RecordedForm, decl: FormDeclaration) -> list[Finding]:
    """Ink (spec §3.1): a valued line puts dark pixels inside its own widget;
    a line with nothing computed puts none. Option lines: the selected line's
    widget is inked, every other option's widget is not."""
    spec, values = rec.spec, rec.values
    fields = PdfReader(str(rec.pdf_path)).get_fields() or {}
    widgets = _widgets(rec.pdf_path)
    cache: dict = {}
    findings: list[Finding] = []

    def ink(page, rect, inset):
        return dark_pixels_in_rect(rec.pdf_path, page, rect, inset=inset,
                                   _render_cache=cache)

    for ln in _declared(decl, values):
        value = values.get(ln.key)
        if ln.selects is not None:
            resolved = option_widgets(spec, ln.key, ln.selects)
            if len(resolved) != 1:
                continue
            field, on = resolved[0]
            own = _own_widget(widgets, field, on)
            if own is None:
                continue
            dark = ink(own[0], own[1], BUTTON_INSET)
            selected = value is not None and str(value) == ln.selects
            if selected and dark < MIN_INK_BUTTON:
                findings.append(_finding(
                    decl, ln.line, "ink",
                    f"option line {ln.line} is selected but its widget in "
                    f"{field!r} shows {dark} dark pixels (no visible mark)."))
            elif not selected and dark >= MIN_INK_BUTTON:
                findings.append(_finding(
                    decl, ln.line, "ink",
                    f"option line {ln.line} is not selected but its widget "
                    f"in {field!r} shows {dark} dark pixels (ink where "
                    "nothing is selected)."))
            continue
        field_path = _scalars(spec).get(ln.key)
        if field_path is None or field_path not in fields:
            continue
        button = fields[field_path].get("/FT") == "/Btn"
        for page, rect, _as, _states in widgets.get(field_path, [])[:1]:
            if button:
                dark = ink(page, rect, BUTTON_INSET)
                should = bool(value)
                visible = dark >= MIN_INK_BUTTON
            else:
                dark = ink(page, rect, TEXT_INSET)
                should = value is not None
                visible = dark > MIN_INK_TEXT
            if should and not visible:
                findings.append(_finding(
                    decl, ln.line, "ink",
                    f"line {ln.line} ({ln.key!r}) has a value but field "
                    f"{field_path!r} shows {dark} dark pixels (no visible "
                    "ink)."))
            elif not should and visible:
                findings.append(_finding(
                    decl, ln.line, "ink",
                    f"line {ln.line} ({ln.key!r}) has nothing computed but "
                    f"field {field_path!r} shows {dark} dark pixels (ink "
                    "where nothing is computed)."))
    return findings


@_never_raises
def check_option_groups(rec: RecordedForm,
                        decl: FormDeclaration) -> list[Finding]:
    """Option groups (ruling A2; exclusivity is the check-suite's, presence
    the gate's): among a group's widgets exactly one is ON when its key has
    a value (none when it has nothing), and the ON widget's /AS is one of
    that widget's own /AP /N states. Every option line must resolve to
    exactly one widget."""
    spec, values = rec.spec, rec.values
    widgets = _widgets(rec.pdf_path)
    groups: dict[str, list[DeclaredLine]] = {}
    for ln in _declared(decl, values):
        if ln.group is not None:
            groups.setdefault(ln.group, []).append(ln)
    findings: list[Finding] = []
    for group, lines in sorted(groups.items()):
        key = lines[0].key
        value = values.get(key)
        group_fields = []
        for ln in lines:
            resolved = option_widgets(spec, ln.key, ln.selects)
            if len(resolved) != 1:
                findings.append(_finding(
                    decl, ln.line, "option_group",
                    f"option line {ln.line} ({ln.key!r}={ln.selects!r}) "
                    f"resolves to {len(resolved)} widgets {resolved}."))
                continue
            if resolved[0][0] not in group_fields:
                group_fields.append(resolved[0][0])
        on = [(field, w[2], w[3]) for field in group_fields
              for w in widgets.get(field, []) if w[2] not in _OFF]
        expected = 0 if value is None else 1
        if len(on) != expected:
            findings.append(_finding(
                decl, group, "option_group",
                f"option group {group!r} ({key!r}={value!r}) has {len(on)} "
                f"widget(s) ON, expected {expected}: "
                f"{[(f, s) for f, s, _ in on]}"))
        for field, state, states in on:
            if state not in states:
                findings.append(_finding(
                    decl, group, "option_group",
                    f"option group {group!r}: a widget of {field!r} is ON as "
                    f"{state!r}, which is not one of its own /AP /N states "
                    f"{states}."))
    return findings


def check_repeater_rows(spec, decl: FormDeclaration) -> list[Finding]:
    """The pinned no-check zone, made loud: a declared form whose fill spec
    carries a {template, max_slots} repeater section gets a named finding,
    because no check reads those rows yet."""
    findings: list[Finding] = []
    if spec.kind != "repeater":
        return findings
    for section, shape in sorted(spec.mapping.get("repeaters", {}).items()):
        if isinstance(shape, Mapping) and "template" in shape:
            findings.append(_finding(
                decl, section, "repeater_rows",
                f"repeater section {section!r} is a template repeater: its "
                "rows have no row checks (pinned no-check zone). Design the "
                "row-key convention for this form before declaring it."))
    return findings


def check_unaccounted(emitted: Mapping[str, Path],
                      record: EmitRecord) -> list[Finding]:
    """Completeness of one emit, consuming NON_FILL_EMITTED and the fill
    census (duplicating neither): every emitted file is a recorded fill or a
    classified non-fill, and every recorded catalog form's mapping class is
    fully classified by ``fill_spec_for``."""
    from tenforty.verification.fill import fill_spec_for
    recorded = {Path(r.pdf_path) for r in record}
    findings: list[Finding] = []
    for key, path in sorted(emitted.items()):
        if Path(path) not in recorded and registry.non_fill_reason(key) is None:
            findings.append(Finding(
                scenario="", form=key, year="", line="", check="completeness",
                message=f"emitted {key!r} ({Path(path).name}) is neither a "
                        "recorded fill nor in NON_FILL_EMITTED."))
    for r in record:
        entry = CATALOG.get(r.form)
        if entry is None:
            continue
        try:
            fill_spec_for(entry.mapping_cls, r.key)
        except ValueError as exc:
            findings.append(Finding(
                scenario="", form="/".join(r.form), year=r.key, line="",
                check="completeness", message=str(exc)))
    return findings
