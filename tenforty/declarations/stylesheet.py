"""Extraction of the IRS MeF stylesheets (emit-verification harness spec §5).

The IRS renders an e-filed return as the printed form with XSL stylesheets
(``manifest.PACKAGES``). Each printed line is a block: a left label box
("10"), a description box ("Qualified business income deduction before the
income limitation ..."), and one or more ``TargetNode`` parameters naming the
e-file element(s) whose value prints there. ``extract`` reads those blocks
as ``StylesheetLine`` records; ``load`` reads the committed extraction for one
form-year (``stylesheets/<form>_<year>.json``), written by
``write_extractions`` from the hash-pinned packages.

Extraction is a single pass over the parsed XSL in document order:

- A **label box** opens a record. Label boxes are the left number/letter
  boxes, ``sty[IRS<form>]LNLeft(Num|Ltr)Box<variant>`` (``LABEL_CLASS``); the
  right-hand number box repeats the label beside the amount and never opens a
  record. An empty label box is a layout spacer on a continuation row: it
  opens nothing, so what follows stays with the line it continues.
- The first **description box** after the label (the Desc family:
  ``styLNDesc``, ``styLnDesc``, ``sty1040Desc``, ``sty1040XLongDesc``,
  ``styIRS4562LNDesc``, ...; ``DESC_CLASS``) gives the record's text, with
  dot leaders and whitespace normalized.
- Every ``TargetNode`` ``select`` before the next label box is appended to
  the record's elements, in document order (a line can carry several: an
  amount and a checkbox, or two columns). The stylesheet's own form-data
  variable (``$FormData``, ``$IRS4562Data``, ...; the top-level parameter
  whose select is ``$RtnDoc/IRS<form>``) is stripped; any other source
  (``$RtnHdrData/...`` for the return header, a repeating row's node) is kept
  verbatim so its provenance stays visible.
- A Part heading (``styPartName``) sets the ``page_section`` of the lines
  under it, so a label printed twice on a form ("1" in Part I and Part II)
  stays two records.
"""
import hashlib
import html.entities
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from tenforty.declarations.stylesheets import manifest

_XSL = "{http://www.w3.org/1999/XSL/Transform}"
_DIR = Path(__file__).parent / "stylesheets"

LABEL_CLASS = re.compile(r"^sty(?:IRS\w+?)?LNLeft(?:Num|Ltr)Box\w*$")
DESC_CLASS = re.compile(
    r"^(?:sty(?:IRS\w+?)?L[Nn]Desc|sty1040X?(?:Long)?Desc)$")
# What a printed line label looks like: "1", "10a", "b", "A.", "(a)", "6c(1)".
# A label-class box holding anything else is a description the IRS styled
# with a label class (2025 Schedule B line 4), not a label.
LABEL_SHAPE = re.compile(r"^\(?[0-9]{0,3}[A-Za-z]{0,2}\)?(?:\([0-9a-z]{1,3}\))?\.?$")
_PART_NAME_CLASS = re.compile(r"(?i)partname$")
_DOT_LEADER_CLASS = re.compile(r"DotLn")
# Boxes whose printed content is a line number or a value, never line text.
_NOT_TEXT_CLASS = re.compile(r"^sty\w*LN(?:Right\w*Box|Amount\w*Box|CtrNumBox)\w*$")
_DOT_RUN = re.compile(r"(?:\s*\.){2,}")
_XML_BUILTIN = frozenset({"amp", "lt", "gt", "quot", "apos"})


@dataclass(frozen=True)
class StylesheetLine:
    label: str
    text: str
    elements: tuple[str, ...]
    page_section: str


# Form-specific label shapes (team-lead ruling 2026-10-17). Schedule K-1
# (Form 1120-S) prints a box grid: an `IRS1120SScheduleK1_itemLabel` box ("1"),
# an unclassed div with the line text ("Ordinary business income (loss)"),
# then the amount box carrying the TargetNode. The generic pass reads it once
# the item-label class counts as a label; the text comes from the
# following-sibling fallback.
FORM_LABEL_CLASS: dict[str, re.Pattern] = {
    "IRS1120SScheduleK1": re.compile(r"^IRS1120SScheduleK1_itemLabel$"),
}


def is_label_class(cls: str, form_xsl: str | None = None) -> bool:
    form_specific = FORM_LABEL_CLASS.get(form_xsl or "")
    return bool(LABEL_CLASS.match(cls)
                or (form_specific is not None and form_specific.match(cls)))


def _classes(el: ET.Element) -> list[str]:
    return (el.get("class") or "").split()


def _prepare(xsl_text: str) -> str:
    """Drop the DOCTYPE and resolve HTML named entities (the stylesheets use
    &nbsp; and friends, declared in an internal DTD or not at all)."""
    text = re.sub(r"<!DOCTYPE[^\[>]*(?:\[.*?\])?\s*>", "", xsl_text, flags=re.S)

    def entity(m: re.Match) -> str:
        name = m.group(1)
        if name in _XML_BUILTIN:
            return m.group(0)
        code = html.entities.name2codepoint.get(name)
        return chr(code) if code is not None else " "
    return re.sub(r"&([A-Za-z][A-Za-z0-9]*);", entity, text)


def _normalize(text: str) -> str:
    text = _DOT_RUN.sub(" ", text.replace(" ", " "))
    return " ".join(text.split()).strip()


def _visible_text(el: ET.Element) -> str:
    """Printed text of a box: its text nodes and xsl:text, minus dot-leader
    spans and every other XSL instruction (they produce values, not words)."""
    parts: list[str] = []

    def walk(node: ET.Element) -> None:
        tag = node.tag if isinstance(node.tag, str) else ""
        xsl_instruction = tag.startswith(_XSL) and tag != f"{_XSL}text"
        # Nested dot leaders, number boxes and amount boxes carry no words.
        not_words = node is not el and any(
            _DOT_LEADER_CLASS.search(c) or _NOT_TEXT_CLASS.match(c)
            for c in _classes(node))
        skip = xsl_instruction or not_words
        if not skip:
            parts.append(node.text or "")
            for child in node:
                walk(child)
                parts.append(child.tail or "")
    walk(el)
    return _normalize(" ".join(parts))


def _following_sibling_text(el: ET.Element, parent_of: dict,
                            form_xsl: str | None = None) -> str:
    """Text of the label's first following sibling that prints words: the
    line text on forms whose description box is not of the Desc family
    (Schedule C's styGenericDiv cell, Form 3115's unclassed div). When the
    label sits alone in a table cell (Form 4562 lines 31-36) the next cell
    holds the text, so the search climbs one level."""
    node = el
    for _level in range(2):  # the label's siblings, then its parent's
        parent = parent_of.get(node)
        if parent is None:
            return ""
        siblings = list(parent)
        for sib in siblings[siblings.index(node) + 1:]:
            if any(is_label_class(c, form_xsl) for c in _classes(sib)):
                return ""
            text = _visible_text(sib)
            if text:
                return text
        node = parent
    return ""


def _data_variable(root: ET.Element, form_xsl: str | None) -> str:
    """Name of the stylesheet's own form-data parameter: the top-level
    xsl:param/xsl:variable selecting ``$RtnDoc/<form_xsl>`` (or, without a
    form name, the first one selecting ``$RtnDoc/...``). ``FormData`` when
    none is declared (an excerpt)."""
    for child in root:
        if child.tag not in (f"{_XSL}param", f"{_XSL}variable"):
            continue
        select = (child.get("select") or "").strip()
        if (select == f"$RtnDoc/{form_xsl}" if form_xsl
                else select.startswith("$RtnDoc/")):
            return child.get("name")
    return "FormData"


def extract(xsl_text: str, form_xsl: str | None = None
            ) -> tuple[StylesheetLine, ...]:
    """Line blocks of one stylesheet, in document order (module docstring).
    ``form_xsl`` ("IRS4562") names the form so its data variable is found
    exactly."""
    root = ET.fromstring(_prepare(xsl_text))
    prefix = f"${_data_variable(root, form_xsl)}/"
    parent_of = {child: parent for parent in root.iter() for child in parent}
    lines: list[StylesheetLine] = []
    section = ""
    label: str | None = None
    text: str | None = None
    fallback = ""
    elements: list[str] = []
    label_section = ""

    def close() -> None:
        if label is not None:
            lines.append(StylesheetLine(
                label, text if text is not None else fallback,
                tuple(dict.fromkeys(elements)), label_section))

    for el in root.iter():
        classes = _classes(el)
        if any(_PART_NAME_CLASS.search(c) for c in classes):
            section = _visible_text(el)
        if any(is_label_class(c, form_xsl) for c in classes):
            new_label = _visible_text(el)
            if new_label and not LABEL_SHAPE.match(new_label):
                if label is not None and text is None:
                    text = new_label
                continue
            if new_label:
                close()
                label, text, elements, label_section = (
                    new_label, None, [], section)
                fallback = _following_sibling_text(el, parent_of, form_xsl)
            continue
        if label is None:
            continue
        if text is None and any(DESC_CLASS.match(c) for c in classes):
            text = _visible_text(el)
        if (el.tag == f"{_XSL}with-param"
                and el.get("name") == "TargetNode" and el.get("select")):
            select = el.get("select").strip()
            elements.append(select[len(prefix):]
                            if select.startswith(prefix) else select)
    close()
    return tuple(lines)


def class_census(xsl_text: str, form_xsl: str | None = None
                 ) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """(label classes, description classes) the stylesheet actually uses,
    sorted: recorded beside each extraction so the recognised class lists
    are pinned against the real packages, not against a sample."""
    root = ET.fromstring(_prepare(xsl_text))
    labels, descs = set(), set()
    for el in root.iter():
        for c in _classes(el):
            if is_label_class(c, form_xsl):
                labels.add(c)
            if DESC_CLASS.match(c):
                descs.add(c)
    return tuple(sorted(labels)), tuple(sorted(descs))


def load_census(form: str, year: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The committed class census for one form-year (``class_census``)."""
    data = json.loads(_json_path(form, year).read_text())
    return tuple(data["label_classes"]), tuple(data["desc_classes"])


def _json_path(form: str, year: int) -> Path:
    return _DIR / f"{form}_{year}.json"


def load(form: str, year: int) -> tuple[StylesheetLine, ...]:
    """The committed extraction for one form-year (``write_extractions``)."""
    data = json.loads(_json_path(form, year).read_text())
    return tuple(StylesheetLine(d["label"], d["text"], tuple(d["elements"]),
                                d["page_section"]) for d in data["lines"])


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_extractions(cache: Path, check: bool = False) -> list[Path]:
    """Extract every XSL_NAME form for every pinned year from the cached
    packages (``cache/<year>/stylesheets.zip``) into the committed JSON
    files. Refuses a package whose sha256 differs from its pin. With
    ``check``, writes nothing and returns the committed files whose content
    differs from a fresh extraction (empty = the commit is current)."""
    written = []
    for year, package in sorted(manifest.PACKAGES.items()):
        zip_path = cache / str(year) / "stylesheets.zip"
        digest = _sha256(zip_path)
        if digest != package.sha256:
            raise ValueError(
                f"TY{year} package {zip_path} has sha256 {digest}, not the "
                f"pinned {package.sha256}; re-fetch it, never substitute.")
        with zipfile.ZipFile(zip_path) as z:
            for form, xsl in sorted(manifest.XSL_NAME.items()):
                member = f"{manifest.stylesheet_dir(year)}/{xsl}.xsl"
                xsl_text = z.read(member).decode("utf-8")
                lines = extract(xsl_text, form_xsl=xsl)
                label_classes, desc_classes = class_census(xsl_text, xsl)
                payload = {
                    "label_classes": list(label_classes),
                    "desc_classes": list(desc_classes),
                    "form": form, "year": year, "xsl": member,
                    "package": package.url, "package_sha256": package.sha256,
                    "lines": [dict(asdict(ln), elements=list(ln.elements))
                              for ln in lines],
                }
                out = _json_path(form, year)
                rendered = json.dumps(payload, indent=1, sort_keys=True,
                                      ensure_ascii=False) + "\n"
                if check:
                    if not out.exists() or out.read_text() != rendered:
                        written.append(out)
                    continue
                out.write_text(rendered)
                written.append(out)
    return written
