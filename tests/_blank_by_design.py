"""Enumerate every fillable cell of an emitted form and classify the blanks.

The completeness standard for a CA form: every fillable cell on the template is
EITHER filled in the emitted PDF OR matched by a documented blank-by-design
rule. A rule is ``(regex_on_tooltip, reason)``. Tests built on this module
assert (a) no unfilled cell is unclassified, and (b) no rule is dead (matches
no unfilled cell in any checked year), so the list cannot silently rot.
"""

import re
from collections.abc import Iterable, Sequence

from pypdf import PdfReader


def _qualified_name(widget) -> str:
    parts, node = [], widget
    while node is not None:
        if "/T" in node:
            parts.append(str(node["/T"]))
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return ".".join(reversed(parts))


def part_two_fields(pdf_path) -> set[str]:
    """Names of every field at or after the start of Schedule CA Part Two
    (itemized-deduction adjustments) in reading order; empty for other forms."""
    rows = []
    for pi, page in enumerate(PdfReader(str(pdf_path)).pages):
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            if w.get("/Subtype") != "/Widget":
                continue
            node, tu = w, None
            while node is not None and tu is None:
                tu = node.get("/TU")
                parent = node.get("/Parent")
                node = parent.get_object() if parent is not None else None
            rows.append((pi, -float(w["/Rect"][3]), _qualified_name(w), str(tu or "")))
    rows.sort()
    for i, (_, _, _, tu) in enumerate(rows):
        low = tu.lower()
        if "part two" in low or "medical and dental" in low:
            return {name for _, _, name, _ in rows[i:]}
    return set()


def template_fields(pdf_path) -> dict[str, dict]:
    """{field_name: {"ft": "/Tx"|"/Btn"|..., "tu": tooltip, "value": str|None}}
    for every terminal field of ``pdf_path`` (pypdf's field tree). Tooltips of
    Schedule CA Part Two cells are prefixed ``[Part II] `` so a rule can name them."""
    part2 = part_two_fields(pdf_path)
    out = {}
    for name, f in PdfReader(str(pdf_path)).get_fields().items():
        value = f.get("/V")
        tu = str(f.get("/TU") or "")
        out[name] = {
            "ft": f.get("/FT"),
            "tu": ("[Part II] " + tu) if name in part2 else tu,
            "value": None if value in (None, "", "/Off") else str(value),
        }
    return out


def unfilled(pdf_path) -> dict[str, dict]:
    return {n: i for n, i in template_fields(pdf_path).items() if i["value"] is None}


def classify(unfilled_fields: dict[str, dict],
             rules: Sequence[tuple[str, str]]) -> tuple[list[str], set[int]]:
    """Return (unclassified field names, indices of rules that matched)."""
    compiled = [re.compile(pat, re.IGNORECASE | re.DOTALL) for pat, _ in rules]
    unclassified, used = [], set()
    for name, info in unfilled_fields.items():
        for i, rx in enumerate(compiled):
            if rx.search(info["tu"]):
                used.add(i)
                break
        else:
            unclassified.append(f"{name}: {info['tu'][:90]}")
    return unclassified, used
