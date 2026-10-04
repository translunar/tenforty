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


def template_fields(pdf_path) -> dict[str, dict]:
    """{field_name: {"ft": "/Tx"|"/Btn"|..., "tu": tooltip, "value": str|None}}
    for every terminal field of ``pdf_path`` (pypdf's field tree)."""
    out = {}
    for name, f in PdfReader(str(pdf_path)).get_fields().items():
        value = f.get("/V")
        out[name] = {
            "ft": f.get("/FT"),
            "tu": str(f.get("/TU") or ""),
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
