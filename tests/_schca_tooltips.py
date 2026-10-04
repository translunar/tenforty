"""Parse Schedule CA (540) widget tooltips into (line token, column).

Tooltips are the template's own statement of what each cell is, so they are the
ground truth used to verify (and generate) the line/column -> field mapping.
Only Part I numeric cells carry "Column A/B/C" in the tooltip.
"""

import re

from pypdf import PdfReader

_COL = re.compile(r"Column ([ABC])\b")
_LINE_CAP = re.compile(r"Line\s+(\d{1,2})\s?([a-z]\d?)?\s?\.")
_LETTERED = re.compile(r"(?:^|[\s.])(\d{1,2})\s([a-z]\d?)\.\s")


def _inherited(widget, key):
    node = widget
    while node is not None:
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def parse_tooltip(tu: str):
    """Return (token, col) or None. token like '1a', '8z', '9b1', '12', '26'."""
    col = _COL.search(tu)
    if not col:
        return None
    head = tu[: col.start()]
    cands = []
    for rx in (_LINE_CAP, _LETTERED):
        for m in rx.finditer(head):
            cands.append((m.group(1), (m.group(2) or "")))
    if not cands:
        return None
    # most specific (a lettered suffix) wins; else the last "Line N" mention
    lettered = [c for c in cands if c[1]]
    num, letter = (lettered[-1] if lettered else cands[-1])
    return f"{num}{letter}", col.group(1)


def part_i_cells(pdf_path):
    """[(page_index, y_top, field_name, token, col)] for Part I numeric cells,
    in reading order (page, then top-to-bottom)."""
    out = []
    reader = PdfReader(str(pdf_path))
    for pi, page in enumerate(reader.pages):
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            tu = str(_inherited(w, "/TU") or "")
            parsed = parse_tooltip(tu)
            if parsed is None:
                continue
            out.append((pi, -float(w["/Rect"][3]), str(_inherited(w, "/T")), parsed[0], parsed[1]))
    out.sort()
    return out


# Section A prints the federal line with its 1040 sub-letter (2b, 3b, 4b, 6b, 7a);
# the compute keys name the bare line.
_SEC_A_FEDERAL_SUFFIX = {"2b": "2", "3b": "3", "4b": "4", "6b": "6", "7a": "7"}


def part_i_sectioned(pdf_path):
    """[(section, token, col, field_name)] for the Part I numeric cells, with
    section in {'A','B','C','T'} ('T' = lines 9a/10/25/26/27 totals, 9b NOL rows
    stay in 'B'). Part I ends where Part II (itemized deductions) begins.
    Section A -> B is the first time a token other than '7' follows the '7' rows."""
    reader = PdfReader(str(pdf_path))
    rows = []
    for pi, page in enumerate(reader.pages):
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            rows.append((pi, -float(w["/Rect"][3]), -float(w["/Rect"][0]),
                         str(_inherited(w, "/T")), str(_inherited(w, "/TU") or "")))
    rows.sort()
    out, section, seen7 = [], "A", False
    for pi, y, x, name, tu in rows:
        low = tu.lower()
        if "part two" in low or "medical and dental" in low:
            break
        parsed = parse_tooltip(tu)
        if parsed is None:
            continue
        token, col = parsed
        if "total other income" in low:
            token = "9a"
        elif section == "A" and token in _SEC_A_FEDERAL_SUFFIX:
            token = _SEC_A_FEDERAL_SUFFIX[token]
        digits = int("".join(ch for ch in token if ch.isdigit()))
        if token in ("9a", "10", "25", "26", "27"):
            sec = "T"
        elif digits in range(11, 25) and token not in ("25",):
            sec = "C"
        else:
            if section == "A" and seen7 and token != "7":
                section = "B"
            if token == "7":
                seen7 = True
            sec = section
            if token.startswith("8") or token.startswith("9b"):
                sec = "B"
        out.append((sec, token, col, name))
    return out
