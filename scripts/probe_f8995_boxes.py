"""Derive, from the printed IRS Form 8995 template itself, which printed line
number each PDF widget field sits on.

This is an EVIDENCE probe, not a documentation restatement. It never reads
`tenforty/mappings/pdf_f8995.py` and never assumes a field's ordinal (the `NN`
in `f1_NN`) tells you its printed line. The only inputs are:

  1. Each `/Widget` annotation's `/Rect` (from the AcroForm field tree, walked
     via `pdfs/federal/{year}/f8995.pdf` directly), and its fully-qualified
     field name (joining `/T` at each `/Parent` level).
  2. The page's own rendered text, extracted with coordinates via
     `page.extract_text(visitor_text=...)`, filtered to left-margin
     (x < 70) tokens that are either a bare line number ("1".."17") or one of
     the roman-numeral row markers ("i".."v") printed next to the five rows
     of the line-1 table.

A field is bound to the nearest qualifying label whose baseline sits above
the field's `/Rect` bottom (`lly`), within 20pt. That threshold and the
observed ~2.5pt / ~13.8pt gap pattern are described in the task-1 brief
(single-line captions put the box 2.5pt below the caption baseline; wrapped
captions put it ~13.8pt below the caption's FIRST baseline, because the box
aligns to the dot-leader continuation row). The irregularity between those
two gap sizes is a property of the form's layout, not evidence of anything
having shifted — do not read a shift into it.

Row markers ("i".."v") are not full printed IRS line numbers by themselves;
they are composed with the nearest numeric line label above THEM (which is
always "1" on this form, but the script does not hardcode that — it derives
it the same way it derives everything else) to produce a label like "1i".

CAPTION EXTRACTION
------------------
A caption is the text printed on the SAME baseline as the bound label
(within 0.6pt), at x >= the label's own x, excluding:

  - the label span itself (excluded by object identity, NOT by position —
    the caption very often renders at the *exact same x* as its line
    number, e.g. 2021 line 4 has both label and caption at x=45.40, so an
    `x > label_x` test silently drops the real caption); and
  - right-hand glyphs at x > 380 that contain no letters — these are the
    line-number reprints and box ornaments beside the entry boxes, which
    an `x > label_x` test would otherwise pick up as a bogus one-character
    "caption" (that is how "4", "5", "10" ended up in this column before).

Trailing dot leaders are stripped. The caption's indentation is
YEAR-DEPENDENT (line 12's caption is at x=40.39 in 2021–2022 but x=64.80 in
2023–2025), which is why the rule keys off the label's own x rather than
any fixed column.

Fields bound to a row marker ("1i".."1v") have no caption on their own
baseline — the line-1 table's captions are its COLUMN HEADERS. For those,
the caption is the header text whose x falls within that field's own
`/Rect` x-range, so the column is derived from the field's geometry rather
than assumed. This is a real caption, not a fallback.

Usage:
    .venv/bin/python scripts/probe_f8995_boxes.py
    .venv/bin/python scripts/probe_f8995_boxes.py --years 2025
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

REPO_ROOT = Path(__file__).resolve().parent.parent
YEARS = (2021, 2022, 2023, 2024, 2025)
NEAR_THRESHOLD_PT = 20.0
LEFT_MARGIN_X = 70.0
ROMAN_ROW_MARKERS = ("i", "ii", "iii", "iv", "v")
NUMERIC_LABEL_RE = re.compile(r"^\d{1,2}$")

# Baseline tolerance for "same printed row". Captions on a hanging indent sit
# up to ~0.2pt off their label's baseline (2021 line 2: label y=433.54,
# caption y=433.34), so an exact match is too strict.
BASELINE_TOL_PT = 0.6
# x beyond which a letter-free glyph is an entry-box ornament (the reprinted
# line number, the "( )" negative-wrapper, the "▶" arrow), not caption text.
ENTRY_BOX_X = 380.0
DOT_LEADER_RE = re.compile(r"[\s.]*\.\s*\.[\s.]*$")
CAPTION_MAX_CHARS = 96


@dataclass
class TextLabel:
    y: float
    x: float
    text: str


@dataclass
class FieldWidget:
    name: str
    rect: tuple[float, float, float, float]  # (llx, lly, urx, ury)

    @property
    def bottom(self) -> float:
        return self.rect[1]


def _fq_name(field_obj) -> str:
    """Fully-qualified field name: join /T at each /Parent level with '.'."""
    parts: list[str] = []
    cur = field_obj
    seen = 0
    while cur is not None and seen < 20:
        t = cur.get("/T")
        if t is not None:
            parts.append(str(t))
        parent = cur.get("/Parent")
        cur = parent.get_object() if parent is not None else None
        seen += 1
    return ".".join(reversed(parts))


def extract_widgets(reader: PdfReader) -> list[FieldWidget]:
    """All /Widget annotations on page 1, with fully-qualified names and rects.

    Only text (/FT == /Tx) fields are kept — this form has no checkboxes to
    bind to a line.
    """
    page = reader.pages[0]
    annots_ref = page.get("/Annots")
    annots = annots_ref.get_object() if annots_ref is not None else []
    widgets: list[FieldWidget] = []
    for a in annots:
        obj = a.get_object()
        if obj.get("/Subtype") != "/Widget":
            continue
        ft = obj.get("/FT")
        if ft is None:
            parent = obj.get("/Parent")
            if parent is not None:
                ft = parent.get_object().get("/FT")
        if ft != "/Tx":
            continue
        rect = obj.get("/Rect")
        if rect is None:
            continue
        widgets.append(
            FieldWidget(
                name=_fq_name(obj),
                rect=tuple(float(v) for v in rect),
            )
        )
    return widgets


def extract_text_labels(reader: PdfReader) -> list[TextLabel]:
    """All non-blank text spans on page 1, with their (x, y) baseline."""
    page = reader.pages[0]
    items: list[TextLabel] = []

    def visitor(text, cm, tm, font_dict, font_size):
        if not text or not text.strip():
            return
        items.append(TextLabel(y=tm[5], x=tm[4], text=text))

    page.extract_text(visitor_text=visitor)
    return items


def classify_left_margin_labels(
    labels: list[TextLabel],
) -> tuple[list[TextLabel], list[TextLabel]]:
    """Split left-margin text into (numeric line labels, roman row markers).

    Filters to x in (0, LEFT_MARGIN_X) to exclude both the y=0/x=0 artifacts
    pypdf emits for some annotation appearance streams (no real position) and
    body text that happens to start near the left margin but isn't a label.
    A label must be *exactly* a bare 1- or 2-digit number, or exactly one of
    "i".."v" — this excludes prose like "filing separately; ..." even though
    it also starts at x < 70.
    """
    numeric: list[TextLabel] = []
    roman: list[TextLabel] = []
    for lbl in labels:
        if not (0 < lbl.x < LEFT_MARGIN_X):
            continue
        stripped = lbl.text.strip()
        if NUMERIC_LABEL_RE.fullmatch(stripped):
            numeric.append(lbl)
        elif stripped in ROMAN_ROW_MARKERS:
            roman.append(lbl)
    return numeric, roman


def nearest_above(y: float, candidates: list[TextLabel], max_gap: float | None = None):
    """The candidate label with smallest (candidate.y - y) subject to
    candidate.y >= y (i.e. the nearest label ABOVE y), optionally capped at
    max_gap. Returns None if no candidate qualifies.
    """
    best = None
    best_gap = None
    for c in candidates:
        gap = c.y - y
        if gap < -0.01:  # candidate is below y; not eligible
            continue
        if max_gap is not None and gap > max_gap:
            continue
        if best_gap is None or gap < best_gap:
            best = c
            best_gap = gap
    return best, best_gap


def caption_excerpt(label: TextLabel, labels: list[TextLabel]) -> str:
    """The caption printed on the same baseline as `label`.

    See the module docstring's CAPTION EXTRACTION section for why this uses
    `x >= label.x` with identity-based exclusion of the label itself, rather
    than a strict `x > label.x`: on this form a line's caption routinely
    renders at the *exact same x* as its own line-number glyph, and the
    indentation is year-dependent.
    """
    parts = []
    for other in labels:
        if other is label:
            continue  # the label itself, excluded by identity not position
        if abs(other.y - label.y) >= BASELINE_TOL_PT:
            continue
        if other.x < label.x - 0.01:
            continue
        stripped = other.text.strip()
        # Entry-box ornaments: reprinted line numbers, "( )", "▶".
        if other.x > ENTRY_BOX_X and not re.search(r"[A-Za-z]", stripped):
            continue
        parts.append(other)
    parts.sort(key=lambda p: p.x)
    text = " ".join("".join(p.text for p in parts).split())
    text = DOT_LEADER_RE.sub("", text).strip()
    return text[:CAPTION_MAX_CHARS]


def column_header_caption(
    field: FieldWidget,
    numeric_labels: list[TextLabel],
    roman_labels: list[TextLabel],
    all_labels: list[TextLabel],
) -> str:
    """For a line-1 table cell, the column header sitting above its column.

    The header block is the text between the topmost row marker and just
    above the line-1 label's baseline. The column is chosen by which header
    spans fall inside THIS field's own /Rect x-range — derived from the
    field's geometry, never from a hardcoded column boundary.
    """
    if not roman_labels or not numeric_labels:
        return ""
    top_roman_y = max(lbl.y for lbl in roman_labels)
    # The numeric label heading this table (nearest numeric label above the
    # topmost row marker) — derived, not assumed to be "1".
    heading, _ = nearest_above(top_roman_y, numeric_labels, None)
    if heading is None:
        return ""
    llx, _, urx, _ = field.rect
    header_spans = [
        lbl
        for lbl in all_labels
        if top_roman_y < lbl.y <= heading.y + 6.0
        and lbl.x >= LEFT_MARGIN_X
        and llx <= lbl.x < urx
    ]
    header_spans.sort(key=lambda lbl: (-lbl.y, lbl.x))
    text = " ".join("".join(lbl.text for lbl in header_spans).split())
    return text[:CAPTION_MAX_CHARS]


def bind_field(
    field: FieldWidget,
    numeric_labels: list[TextLabel],
    roman_labels: list[TextLabel],
    all_labels: list[TextLabel],
) -> tuple[str | None, str]:
    """Bind one field to a printed line, returning (bound_line, caption).

    Considers both numeric line labels and roman row markers as candidates;
    whichever sits nearer (and within NEAR_THRESHOLD_PT) above the field's
    /Rect bottom wins. A roman marker is composed with the nearest numeric
    label above ITSELF (e.g. "1i"), derived the same geometric way — never
    hardcoded.
    """
    num_hit, num_gap = nearest_above(field.bottom, numeric_labels, NEAR_THRESHOLD_PT)
    rom_hit, rom_gap = nearest_above(field.bottom, roman_labels, NEAR_THRESHOLD_PT)

    if num_hit is None and rom_hit is None:
        return None, ""

    if rom_hit is not None and (num_hit is None or rom_gap < num_gap):
        # Bound to a row marker: compose with the numeric line above it.
        parent_num, _ = nearest_above(rom_hit.y, numeric_labels, None)
        line = f"{parent_num.text.strip()}{rom_hit.text.strip()}" if parent_num else rom_hit.text.strip()
        # A row marker has no caption on its own baseline; the table's
        # captions are its column headers.
        cap = column_header_caption(field, numeric_labels, roman_labels, all_labels)
        return line, cap

    line = num_hit.text.strip()
    cap = caption_excerpt(num_hit, all_labels)
    return line, cap


def probe_year(year: int) -> list[dict]:
    pdf_path = REPO_ROOT / "pdfs" / "federal" / str(year) / "f8995.pdf"
    reader = PdfReader(pdf_path)
    widgets = extract_widgets(reader)
    all_labels = extract_text_labels(reader)
    numeric_labels, roman_labels = classify_left_margin_labels(all_labels)

    rows = []
    for w in sorted(widgets, key=lambda f: -f.bottom):
        line, cap = bind_field(w, numeric_labels, roman_labels, all_labels)
        rows.append(
            {
                "field": w.name.rsplit(".", 1)[-1],
                "full_path": w.name,
                "rect": w.rect,
                "line": line,
                "caption": cap,
            }
        )
    return rows


def render_markdown(results: dict[int, list[dict]]) -> str:
    lines = [
        "# Form 8995 field → printed-line correspondence",
        "",
        "Generated by `scripts/probe_f8995_boxes.py`. Each row binds a PDF",
        "widget field to the nearest printed IRS line label ABOVE its",
        "`/Rect` bottom (within 20pt), derived entirely from the template's",
        "own text and widget geometry — never from",
        "`tenforty/mappings/pdf_f8995.py`. See the script docstring and",
        "`.superpowers/sdd/2026-08-19-f8995-box-mapping/task-1-brief.md` for",
        "the method and its rationale.",
        "",
        "`Bound line` is blank for fields that bind to no printed-line label",
        "within 20pt (the header identification fields).",
        "",
        "## How the `Caption excerpt` column is derived",
        "",
        "Stated so a reader can tell apart the distinct reasons a cell may be",
        "blank — they are not interchangeable:",
        "",
        "- For a field bound to a **numeric line**, the caption is the text on",
        "  that line label's own baseline (within 0.6pt) at `x >= the label's",
        "  x`, excluding the label span itself (by identity, since a caption",
        "  often renders at the *exact same x* as its line number) and",
        "  excluding letter-free glyphs at `x > 380` (the reprinted line",
        "  number and box ornaments beside the entry boxes). Trailing dot",
        "  leaders are stripped; the text is truncated to 96 characters.",
        "- For a field bound to a **line-1 table row** (`1i`–`1v`), no caption",
        "  exists on the row's own baseline — the table's captions are its",
        "  **column headers**. The caption shown is the header text whose x",
        "  falls inside that field's own `/Rect` x-range, so the column is",
        "  derived from the field's geometry.",
        "- In this table, as generated for 2021–2025, **every blank caption is",
        "  a field that binds to no printed line**, so no caption lookup was",
        "  attempted for it — blank does NOT mean the field has no caption on",
        "  the form. (Checked across all five years: the set of blank-caption",
        "  rows and the set of line-unbound rows are the same two rows in each",
        "  year. This is an observed property of these five templates, not a",
        "  guarantee about templates not yet examined.) **Both of those fields",
        "  do have printed captions**, and for opposite reasons the table does",
        "  not show them:",
        "    - `f1_1` (`f1_01` in 2025) is captioned **`Name(s) shown on",
        "      return`**, printed at x=36.00, y=687.60 (2021–2022) / y=687.97",
        "      (2023–2025) — within 20pt of the field's `/Rect` bottom, so it",
        "      is geometrically recoverable; it simply is not a line caption",
        "      and is out of scope for a line-correspondence table.",
        "    - `f1_2` (`f1_02` in 2025) is captioned **`Your taxpayer",
        "      identification number`**, which appears in every year's text",
        "      stream ONLY at the degenerate coordinates x=0.00, y=0.00 (the",
        "      same unpositioned-artifact class as the `(a)` glyph noted",
        "      below), with no positioned occurrence near the box. That",
        "      caption is real but **not geometrically recoverable**.",
        "  Those two blanks therefore mean different things: one was never",
        "  looked up, the other could not be found. Neither means \"this field",
        "  has no caption.\"",
        "",
        "Caption indentation is **year-dependent** (line 12's caption is at",
        "x=40.39 in 2021–2022 but x=64.80 in 2023–2025), which is why the rule",
        "keys off each label's own x rather than any fixed column.",
        "",
        "Note: the literal `(a)` column-header glyph carries no usable text",
        "position in these templates (pypdf reports it at x=0, y=0), so column",
        "(a)'s caption below reads as its header words without the `(a)`",
        "prefix that `(b)` and `(c)` retain. That is a property of the",
        "template's text encoding, not a truncation.",
        "",
    ]
    for year in sorted(results):
        lines.append(f"## {year}")
        lines.append("")
        lines.append("| Field | Full path | /Rect | Bound line | Caption excerpt |")
        lines.append("|---|---|---|---|---|")
        for row in results[year]:
            rect = ", ".join(f"{v:.2f}" for v in row["rect"])
            line = row["line"] if row["line"] is not None else ""
            caption = row["caption"].replace("|", "\\|")
            lines.append(
                f"| `{row['field']}` | `{row['full_path']}` | {rect} | {line} | {caption} |"
            )
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--years",
        type=int,
        nargs="+",
        default=list(YEARS),
        help="Years to probe (default: 2021-2025)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "docs" / "coverage" / "f8995-box-correspondence.md",
        help="Output markdown path",
    )
    args = parser.parse_args()

    results = {year: probe_year(year) for year in args.years}
    markdown = render_markdown(results)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown)
    print(f"Wrote {args.output}")

    for year, rows in results.items():
        unbound = [r["field"] for r in rows if r["line"] is None]
        no_caption = [r["field"] for r in rows if not r["caption"]]
        print(
            f"{year}: {len(rows)} fields | {len(unbound)} unbound to a line: {unbound}"
            f" | {len(no_caption)} without a caption: {no_caption}"
        )


if __name__ == "__main__":
    main()
