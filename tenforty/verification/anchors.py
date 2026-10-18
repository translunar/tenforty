"""Anchor EVALUATION (spec §3.3): prove a mapped field really is the printed
line a declaration says it is. The anchor data types live in
``tenforty.declarations.anchors``; this module reads the blank template.

- ``Tooltip(pattern)``: the field's own ``/TU`` (or nearest ancestor's)
  matches the regex. Default for templates with tooltips (California).
- ``RowLabel(token)``: the marker probe. Every text field is stamped with its
  own leaf name, the page is rendered with ``pdftotext -layout``, and the
  field's row must carry the line token. Default for templates without
  tooltips (federal). ``row_line_tokens`` is the probe lifted verbatim from
  ``tests/test_mapping_line_identity.py``.
- ``NearLabel(phrase, relation)``: relative to a phrase printed EXACTLY ONCE
  on the field's page (``pdftotext -bbox``); twice is an ambiguity finding,
  except for RIGHT_OF / LEFT_OF, where exactly one occurrence on the field's
  row within LABEL_GAP_PT of the field's labelled side resolves it.
- ``NearField(other_line, relation)``: relative to another declared line's
  field.

Tolerances are the spec's (``ROW_PT``, ``COLUMN_PT``, ``NEXT_ROW_PT``,
``LABEL_GAP_PT``, ``WRAP_PT``). ``evaluate`` returns a ``Finding`` (check
``placement``) or ``None``; the caller fills in scenario/form/year/line.
"""
import functools
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

from tenforty.declarations.anchors import (
    COLUMN_PT,
    LABEL_GAP_PT,
    NEXT_ROW_PT,
    ROW_PT,
    WRAP_PT,
    Anchor,
    FieldRelation,
    LabelRelation,
    NearField,
    NearLabel,
    RowLabel,
    Tooltip,
)
from tenforty.declarations.model import DeclaredLine
from tenforty.filing.pdf import stamp_field_names
from tenforty.verification.findings import Finding
from tenforty.verification.pixels import widget_rect


def leaf(path: str) -> str:
    return path.split(".")[-1].replace("[0]", "")


def row_line_tokens(template: Path) -> dict[str, set[str]]:
    """leaf field name -> set of IRS-line tokens on that field's text row.

    Fills every text field with its own leaf name, renders, and for each
    rendered row collects the field markers and the line-number-shaped
    tokens (e.g. '16', '35a', '8z') sharing that row. Robust to total-line
    rows whose prose references other line numbers: the row still contains
    its own line label, so membership (not position) is the assertion.

    Lifted from tests/test_mapping_line_identity.py; the field-name stamping
    write moved to filing.pdf.stamp_field_names (ruling 2026-10-17: the
    field-write primitive lives in exactly one module)."""
    stamped = stamp_field_names(template)
    try:
        txt = subprocess.run(
            ["pdftotext", "-layout", str(stamped), "-"],
            capture_output=True, text=True,
        ).stdout
    finally:
        stamped.unlink(missing_ok=True)
    line_tok = re.compile(r"^\(?(\d{1,2}[a-z]?)$")
    mark = re.compile(r"\b(f[12]_\d{1,2})\b")
    out: dict[str, set[str]] = {}
    for row in txt.splitlines():
        toks = row.split()
        labels = {m.group(1) for t in toks for m in [line_tok.match(t)] if m}
        marks = {m.group(1) for t in toks for m in [mark.search(t)] if m}
        for leaf_name in marks:
            out.setdefault(leaf_name, set()).update(labels)
    return out


@functools.lru_cache(maxsize=64)
def _row_tokens_cached(template: str) -> dict[str, set[str]]:
    return row_line_tokens(Path(template))


@functools.lru_cache(maxsize=64)
def _fields(template: str) -> dict:
    return PdfReader(template).get_fields() or {}


@functools.lru_cache(maxsize=16)
def template_has_tooltips(template: str) -> bool:
    """True when the template's text fields carry /TU tooltips (every
    California template does; no federal one does)."""
    text = [f for f in _fields(template).values() if f.get("/FT") == "/Tx"]
    return bool(text) and sum(1 for f in text if f.get("/TU")) >= 0.9 * len(text)


def label_pattern(label: str) -> str:
    """Regex for a printed line label inside a tooltip, as a whole token:
    "12a" matches "Line 12 a." and "Line 12a"; "8" never matches "Line 18"."""
    m = re.fullmatch(r"(\d+)([a-z]*)", label)
    if m is None:
        return r"(?<![0-9A-Za-z])" + re.escape(label) + r"(?![0-9A-Za-z])"
    num, letters = m.groups()
    return (r"\bLine\s+" + num + (r"\s*" + letters if letters else "")
            + r"(?![0-9A-Za-z])")


def default_anchor(line: DeclaredLine, template_has_tooltips: bool) -> Anchor:
    """The anchor a declared line gets when it names none (spec §3.3)."""
    if template_has_tooltips:
        return Tooltip(label_pattern(line.line))
    return RowLabel(line.line)


def _tooltip(field) -> str:
    node = field
    while node is not None:
        tu = node.get("/TU")
        if tu:
            return str(tu)
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ""


@functools.lru_cache(maxsize=64)
def _page_words(template: str, page: int):
    xml = subprocess.run(
        ["pdftotext", "-bbox", "-f", str(page + 1), "-l", str(page + 1),
         template, "-"], check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(xml)
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    pg = root.find(".//x:page", ns)
    height = float(pg.get("height"))
    return tuple(((w.text or ""), float(w.get("xMin")),
                  height - float(w.get("yMax")), float(w.get("xMax")),
                  height - float(w.get("yMin")))
                 for w in pg.findall("x:word", ns))


def _phrase_boxes(words, phrase: str) -> list[tuple[float, float, float, float]]:
    """Bounding boxes of every occurrence of ``phrase`` (a word sequence)."""
    want = phrase.split()
    n = len(want)
    texts = [w[0] for w in words]
    boxes = []
    for i in range(len(texts) - n + 1):
        if texts[i:i + n] == want:
            span = words[i:i + n]
            boxes.append((min(w[1] for w in span), min(w[2] for w in span),
                          max(w[3] for w in span), max(w[4] for w in span)))
    return boxes


def _finding(message: str) -> Finding:
    return Finding(scenario="", form="", year="", line="", check="placement",
                   message=message)


def evaluate(anchor: Anchor, field_path: str, template: Path, *,
             other_field: str | None = None) -> Finding | None:
    """``None`` when ``field_path`` sits where ``anchor`` says, else a
    placement ``Finding`` saying why."""
    template = str(template)
    if isinstance(anchor, Tooltip):
        field = _fields(template).get(field_path)
        if field is None:
            return _finding(f"field {field_path!r} is not on the template")
        tu = _tooltip(field)
        if re.search(anchor.pattern, tu):
            return None
        return _finding(f"field {field_path!r} tooltip {tu[:80]!r} does not "
                        f"match {anchor.pattern!r}")
    if isinstance(anchor, RowLabel):
        tokens = _row_tokens_cached(template).get(leaf(field_path), set())
        if anchor.token in tokens:
            return None
        return _finding(f"field {field_path!r} prints on a row with line "
                        f"tokens {sorted(tokens)}, not {anchor.token!r}")
    if isinstance(anchor, NearLabel):
        page, rect = widget_rect(template, field_path)
        boxes = _phrase_boxes(_page_words(template, page), anchor.phrase)
        if len(boxes) > 1 and anchor.relation in _SIDE:
            # A label that also prints elsewhere (Schedule C Part II's "8"
            # in the left margin; line G's "Yes", also on rows I and J): it
            # resolves to the ONE occurrence that labels this field -- on
            # its row, on the relation's side of it, within LABEL_GAP_PT.
            # None or several still refuse (fail-closed).
            qualifies, side = _SIDE[anchor.relation]
            labelling = [box for box in boxes if qualifies(rect, box)]
            if len(labelling) == 1:
                return _near_label(anchor, field_path, rect, labelling[0])
            return _finding(f"phrase {anchor.phrase!r} prints {len(boxes)} "
                            f"times on page {page + 1} and "
                            f"{len(labelling)} occurrences sit within "
                            f"LABEL_GAP_PT {side} of field {field_path!r}; "
                            "exactly one must (ambiguous)")
        if len(boxes) != 1:
            return _finding(f"phrase {anchor.phrase!r} prints {len(boxes)} "
                            f"times on page {page + 1}; an anchor phrase must "
                            "print exactly once (ambiguous)")
        return _near_label(anchor, field_path, rect, boxes[0])
    if isinstance(anchor, NearField):
        if other_field is None:
            return _finding(f"NearField({anchor.other_line!r}): that line "
                            "has no mapped field to anchor against")
        page, rect = widget_rect(template, field_path)
        other_page, other = widget_rect(template, other_field)
        if page != other_page:
            return _finding(f"field {field_path!r} is not on the page of "
                            f"line {anchor.other_line!r}'s field")
        return _near_field(anchor, field_path, rect, other)
    raise TypeError(f"unknown anchor type {type(anchor).__name__}")


def _overlaps_row(rect, box) -> bool:
    return min(rect[3], box[3]) - max(rect[1], box[1]) > 0 or (
        abs(rect[1] - box[1]) < ROW_PT)


def _labels(rect, box) -> bool:
    """Whether the printed token ``box`` labels the field ``rect``: on its
    row, ending at most LABEL_GAP_PT before the field begins (with the
    ROW_PT tolerance RIGHT_OF allows for a token that runs a hair past the
    field's edge)."""
    return (_overlaps_row(rect, box)
            and -ROW_PT <= rect[0] - box[2] <= LABEL_GAP_PT)


def _labels_from_right(rect, box) -> bool:
    """Whether the printed token ``box`` labels the field ``rect`` from its
    right (a checkbox before its caption): on its row, beginning at most
    LABEL_GAP_PT after the field ends (with the ROW_PT tolerance LEFT_OF
    allows)."""
    return (_overlaps_row(rect, box)
            and -ROW_PT <= box[0] - rect[2] <= LABEL_GAP_PT)


# Relations whose repeated phrase resolves by geometry -> (qualifier, the
# side of the field the qualifying occurrence sits on).
_SIDE = {
    LabelRelation.RIGHT_OF: (_labels, "left"),
    LabelRelation.LEFT_OF: (_labels_from_right, "right"),
}


def _near_label(anchor: NearLabel, field_path, rect, box) -> Finding | None:
    rel = anchor.relation
    if rel is LabelRelation.ON_ROW:
        ok = _overlaps_row(rect, box)
    elif rel is LabelRelation.RIGHT_OF:
        ok = _overlaps_row(rect, box) and rect[0] >= box[2] - ROW_PT
    elif rel is LabelRelation.LEFT_OF:
        ok = (_overlaps_row(rect, box) and rect[2] <= box[0] + ROW_PT
              and box[0] - rect[2] <= LABEL_GAP_PT)
    elif rel is LabelRelation.AFTER_WRAPPED:
        ok = 0 <= box[1] - rect[3] <= WRAP_PT or _overlaps_row(rect, box)
    else:
        raise TypeError(f"unknown label relation {rel}")
    if ok:
        return None
    return _finding(f"field {field_path!r} at {[round(v, 1) for v in rect]} "
                    f"is not {rel.value} {anchor.phrase!r} at "
                    f"{[round(v, 1) for v in box]}")


def _near_field(anchor: NearField, field_path, rect, other) -> Finding | None:
    rel = anchor.relation
    if rel is FieldRelation.SAME_ROW_RIGHT_OF:
        ok = abs(rect[1] - other[1]) < ROW_PT and rect[0] > other[2]
    elif rel is FieldRelation.NEXT_ROW_BELOW:
        ok = (abs(rect[0] - other[0]) < COLUMN_PT
              and 0 <= other[1] - rect[3] < NEXT_ROW_PT)
    else:
        raise TypeError(f"unknown field relation {rel}")
    if ok:
        return None
    return _finding(f"field {field_path!r} is not {rel.value} line "
                    f"{anchor.other_line!r}'s field")
