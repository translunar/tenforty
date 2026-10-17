"""Official line inventories, machine-extracted from the pinned templates.

For each form and tax year (or revision), the printed line labels with
their text, page, Part/section and position, taken ONLY from the tax
authority's own artifact (spec 2026-10-17 emit-verification harness §4.1):

* Federal templates carry no tooltips, so their lines come from the printed
  page: ``pdftotext -bbox-layout`` words, line-number tokens in the page's
  label columns, the same-row text to the right of each label, and the
  ``Part <roman>`` headings the label sits under.
* California templates carry ``/TU`` tooltips reading "Line 12. ..."; lines
  come from those, and any printed label whose widgets carry only a generic
  tooltip is taken from the printed page the federal way.

Lines are keyed by ``(page, section, label)``: a label that recurs under
two Parts (or Questions) is two lines, never merged. This module never
reads tenforty's own mappings, computations or orchestrator; that is the
independence rule (pinned by NoMappingImportTests).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import statistics
import subprocess
from pathlib import Path
from xml.etree import ElementTree

from pypdf import PdfReader

INVENTORY_DIR = Path(__file__).parent / "inventories"
REPO_ROOT = Path(__file__).resolve().parents[2]

_XHTML = "{http://www.w3.org/1999/xhtml}"
# A printed line number: 1-3 digits, no leading zero (so a cents column's
# "00" is not a line), optionally a lowercase sub-letter ("4a").
_NUMBER = re.compile(r"^[1-9]\d{0,2}[a-z]?$")
# A sub-line marker printed on its own beside the number column: a letter,
# or a lowercase roman row numeral (f8995 rows 1i-1v).
_SUBLINE = re.compile(r"^(?:[a-z]|ii|iii|iv|vi|vii|viii)$")
_ROMAN = re.compile(r"^[IVX]+$")
_LEADER = re.compile(r"^[.\s]+$")
_SAME_ROW = 2.5        # pt: words whose tops differ by less share a row
_LABEL_GAP = 8.0       # pt: a label has no word ending within this to its left
_COMPOSITE_GAP = 6.0   # pt: "1" + "a" printed as two words form "1a"
_SUBLINE_REACH = 10.0  # pt: a sub-letter sits this far right of the numbers
_COLUMN_GAP = 8.0      # pt: label x-positions closer than this share a column
_BOX_REPEAT = 14.0     # pt: a line-number box repeats its row's label
_FULL_HEIGHT = 0.8     # a label at least this fraction of the median height
                       # (footnote markers are smaller)


@dataclasses.dataclass(frozen=True)
class InventoryLine:
    page: int
    section: str
    label: str
    text: str
    bbox: tuple[float, float, float, float]

    @property
    def key(self) -> tuple[int, str, str]:
        return line_key(self.page, self.section, self.label)


def line_key(page: int, section: str, label: str) -> tuple[int, str, str]:
    """The one identity of a printed line, shared by both extractors: a
    label that recurs under two sections is two lines (Review Focus 1)."""
    return (page, section, label)


@dataclasses.dataclass(frozen=True)
class Inventory:
    source_sha256: str
    lines: tuple[InventoryLine, ...]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- federal: the printed page ---------------------------------------------

def _page_words(pdf: Path) -> list[list[tuple[float, float, float, float, str]]]:
    out = subprocess.run(
        ["pdftotext", "-bbox-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True).stdout
    root = ElementTree.fromstring(re.sub(r"<!DOCTYPE[^>]*>", "", out))
    return [[(float(w.get("xMin")), float(w.get("yMin")),
              float(w.get("xMax")), float(w.get("yMax")), w.text or "")
             for w in page.iter(_XHTML + "word")]
            for page in root.iter(_XHTML + "page")]


def _columns(xs: list[float]) -> list[tuple[float, float]]:
    """Clusters of label x-positions (two or more labels each)."""
    groups: list[list[float]] = []
    for x in sorted(xs):
        if groups and x - groups[-1][-1] <= _COLUMN_GAP:
            groups[-1].append(x)
        else:
            groups.append([x])
    return [(g[0] - 1, g[-1] + 1) for g in groups if len(g) >= 2]


def _number_of(label: str) -> int:
    return int(re.match(r"^\d+", label).group(0))


def extract_federal(pdf: Path) -> tuple[InventoryLine, ...]:
    """Every printed line label of a template, from its printed pages."""
    lines: list[InventoryLine] = []
    section = ""
    for page_no, words in enumerate(_page_words(pdf), 1):
        def row(w):
            return [v for v in words
                    if v is not w and abs(v[1] - w[1]) < _SAME_ROW]

        def left_clear(w):
            return not any(v[2] > w[0] - _LABEL_GAP and v[0] < w[0]
                           for v in row(w))

        def right_neighbour(w):
            right = sorted(v for v in row(w) if v[0] >= w[2] - 0.5)
            return right[0] if right else None

        numbers = [w for w in words if _NUMBER.match(w[4]) and left_clear(w)]
        if not numbers:
            continue
        median_height = statistics.median(w[3] - w[1] for w in numbers)

        def full_height(w):
            return (w[3] - w[1]) >= _FULL_HEIGHT * median_height

        numbers = [w for w in numbers if full_height(w)]
        columns = _columns([w[0] for w in numbers])

        def column_of(w):
            return next(((lo, hi) for lo, hi in columns if lo <= w[0] <= hi),
                        None)

        events = []
        for w in words:
            if w[4] == "Part" and left_clear(w):
                # A heading starts its row; "go to Part III" is a reference.
                nxt = right_neighbour(w)
                if nxt and _ROMAN.match(nxt[4]) and nxt[0] - w[2] < _LABEL_GAP:
                    # A heading printed on its first line's row precedes it.
                    events.append((w[1] - 3, 0, "part", f"Part {nxt[4]}", w))
            elif w in numbers and column_of(w):
                events.append((w[1], 1, "number", w[4], w))
            elif (_SUBLINE.match(w[4]) and full_height(w) and left_clear(w)
                  and any(lo <= w[0] <= hi + _SUBLINE_REACH
                          for lo, hi in columns)):
                events.append((w[1], 1, "subline", w[4], w))
        events.sort(key=lambda e: (e[0], e[1], e[4][0]))

        # A label column counts up within a Part. A column whose numbers fall
        # back inside one Part is a table's values (e.g. Form 4562's
        # recovery periods, "25 yrs.", "39 yrs."), not line labels.
        sequences: dict = {}
        current = section
        for _, _, kind, value, w in events:
            if kind == "part":
                current = value
            elif kind == "number":
                sequences.setdefault((column_of(w), current), []).append(
                    _number_of(value))
        not_labels = {col for (col, _), seq in sequences.items()
                      if any(b < a for a, b in zip(seq, seq[1:]))}
        events = [e for e in events
                  if not (e[2] == "number" and column_of(e[4]) in not_labels)]

        last_number = None
        for _, _, kind, value, w in events:
            if kind == "part":
                section = value
                continue
            consumed = {id(w)}
            if kind == "number":
                label = value
                last_number = str(_number_of(value))
                nxt = right_neighbour(w)
                if (nxt and not value[-1].isalpha() and _SUBLINE.match(nxt[4])
                        and nxt[0] - w[2] < _COMPOSITE_GAP):
                    label = value + nxt[4]
                    consumed.add(id(nxt))
            else:
                if last_number is None:
                    continue
                label = last_number + value
            if line_key(page_no, section, label) in {o.key for o in lines}:
                continue
            # A line-number box repeats its row's label (same line).
            if any(o.page == page_no and o.label == label
                   and abs(o.bbox[1] - w[1]) < _BOX_REPEAT for o in lines):
                continue
            stop = min([lo for lo, _ in columns if lo > w[2] + 2] + [1e9])
            text = " ".join(
                v[4] for v in sorted(row(w) + [w])
                if w[2] < v[0] < stop and id(v) not in consumed
                and not _LEADER.match(v[4])).strip()
            lines.append(InventoryLine(page_no, section, label, text,
                                       tuple(round(c, 2) for c in w[:4])))
    return tuple(lines)


# --- California: the templates' own tooltips --------------------------------

# "Line 12. ...", "Line 1 h. ...", "Line 3 . ...", "Line 8 A. ...", with an
# optional section prefix: "Part 1 . ", "Question A. ", "Schedule Q
# Question A. ", "Section B. ".
_TOOLTIP = re.compile(
    r"^(?:(?P<section>(?:Schedule \w+ )?(?:Part|Question|Section) \w+)\s*\.\s*)?"
    r"Line (?P<number>[1-9]\d{0,2})\s?(?P<sub>[a-zA-Z]{1,2})?\s*\.?\s*"
    r"(?P<text>.*)$", re.S)


def _tooltip(annotation) -> str | None:
    node = annotation
    while node is not None:
        if node.get("/TU") is not None:
            return str(node["/TU"])
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def extract_california(pdf: Path) -> tuple[InventoryLine, ...]:
    """Lines from the FTB template's /TU tooltips; a printed label whose
    widgets carry only generic tooltips comes from the printed page."""
    lines: list[InventoryLine] = []
    seen: set[tuple[int, str, str]] = set()
    reader = PdfReader(str(pdf))
    for page_no, page in enumerate(reader.pages, 1):
        height = float(page.mediabox.height)
        for ref in page.get("/Annots") or []:
            annotation = ref.get_object()
            tip = _tooltip(annotation)
            if tip is None:
                continue
            m = _TOOLTIP.match(" ".join(tip.split()))
            if not m:
                continue
            section = m.group("section") or ""
            section = re.sub(r"^Part (\d+)$", lambda p: f"Part {p.group(1)}",
                             section)
            label = m.group("number") + (m.group("sub") or "")
            key = line_key(page_no, section, label)
            if key in seen:
                continue
            seen.add(key)
            x0, y0, x1, y1 = (float(c) for c in annotation["/Rect"])
            # Top-left origin, like pdftotext.
            bbox = (round(x0, 2), round(height - y1, 2),
                    round(x1, 2), round(height - y0, 2))
            lines.append(InventoryLine(page_no, section, label,
                                       m.group("text").strip(), bbox))
    for line in extract_federal(pdf):
        if not any(o.page == line.page and o.label == line.label
                   for o in lines):
            lines.append(line)
    return tuple(lines)


# --- storage -----------------------------------------------------------------

def _sorted(lines) -> tuple[InventoryLine, ...]:
    return tuple(sorted(lines, key=lambda l: (l.page, l.bbox[1], l.bbox[0],
                                              l.section, l.label)))


def extract(jurisdiction: str, pdf: Path) -> tuple[InventoryLine, ...]:
    if jurisdiction == "federal":
        return extract_federal(pdf)
    if jurisdiction == "california":
        return extract_california(pdf)
    raise ValueError(f"unknown jurisdiction {jurisdiction!r}")


def to_json(form: str, key: int | str, jurisdiction: str, source: Path,
            lines) -> str:
    return json.dumps({
        "form": form,
        "key": key,
        "jurisdiction": jurisdiction,
        "source": Path(source).resolve().relative_to(REPO_ROOT).as_posix(),
        "source_sha256": sha256_of(source),
        "lines": [dataclasses.asdict(l) for l in _sorted(lines)],
    }, indent=1, ensure_ascii=False) + "\n"


def write(form: str, key: int | str, jurisdiction: str, source: Path) -> Path:
    """Extract one template's inventory and write it (reviewed data: a
    re-extraction that changes anything shows as a diff)."""
    path = inventory_path(form, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(form, key, jurisdiction, source,
                            extract(jurisdiction, source)))
    return path


def refresh() -> list[Path]:
    """Re-extract every committed inventory from the template it records."""
    written = []
    for path in sorted(INVENTORY_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        written.append(write(data["form"], data["key"], data["jurisdiction"],
                             REPO_ROOT / data["source"]))
    return written


def inventory_path(form: str, key: int | str) -> Path:
    return INVENTORY_DIR / f"{form}_{key}.json"


def load(form: str, key: int | str) -> Inventory:
    data = json.loads(inventory_path(form, key).read_text())
    return Inventory(
        source_sha256=data["source_sha256"],
        lines=tuple(InventoryLine(
            page=l["page"], section=l["section"], label=l["label"],
            text=l["text"], bbox=tuple(l["bbox"])) for l in data["lines"]))
