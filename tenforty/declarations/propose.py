"""Binding proposals: which compute key prints on which official line
(emit-verification harness spec §4.2).

Machines propose; agents confirm. Three passes over one form-year:

1. **Naming.** A key shaped ``<prefix>_line_<n>[_words]`` proposes printed
   line ``n``.
2. **Auto-confirmation.** A naming proposal binds with no agent review only
   when the official artifacts agree with it:
   * federal: the IRS stylesheet prints line ``n`` with text matching the
     inventory's (token-set Jaccard >= 0.6), and the key's own words name
     that line (containment >= 0.5, the seam guard);
   * California: the inventory line ``n`` was read from the FTB tooltip
     (``source == "tooltip"``, never the printed-page fallback) and the
     key's words name it.
   Anything else becomes an exception for agent review: ``seam`` (the key's
   number names a line its words don't describe, e.g. f8995's
   ``f8995_line_3_component``, printed on line 5), ``disagree`` (the
   artifacts or the passes disagree) or ``no-proposal``.
3. **Description ranking.** Every inventory line no key names gets the
   output keys ranked against its text; the top five are candidates. This
   pass NEVER binds.

Inputs are only the official inventories and stylesheets and the
computation's output key NAMES: never tenforty's mappings, computations or
orchestrator (the independence rule).
"""
from __future__ import annotations

import dataclasses
import json
import re
from typing import Literal, Sequence

from tenforty.declarations import inventory, stylesheet
from tenforty.declarations.inventory import InventoryLine

# Each form's compute-key prefix, recorded from the computation's output key
# list (names only). A form with no entry has no naming pass: all of its
# lines go to ranking.
KEY_PREFIX: dict[str, str] = {
    "f8995": "f8995",
}

STYLESHEET_AGREEMENT = 0.6   # Jaccard, stylesheet text vs inventory text
# Containment of the key's words in the line's words (the seam guard).
# PROVISIONAL: set at 0.5 when the rule was ruled in (2026-10-17) from the
# f8995 worked examples (line_15_qbi_deduction 1.0, line_3_component 0.0);
# the Schedule C pilot's recalibration may move it.
KEY_AGREEMENT = 0.5
# An acronym match ("agi" = adjusted gross income) needs a key word of at
# least this many characters; two-letter matches are likelier spurious.
ACRONYM_FLOOR = 3
CANDIDATES = 5

@dataclasses.dataclass(frozen=True)
class Binding:
    section: str
    line: str
    key: str
    evidence: str


@dataclasses.dataclass(frozen=True)
class Exception_:
    section: str
    line: str
    reason: Literal["no-proposal", "disagree", "seam"]
    candidates: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class Proposals:
    auto_confirmed: tuple[Binding, ...]
    exceptions: tuple[Exception_, ...]


# --- words ---------------------------------------------------------------

_DOT_LEADERS = re.compile(r"(?:\s*\.){2,}")


def words(text: str) -> list[str]:
    """Lower-case words, punctuation and dot leaders stripped, stop-words
    kept (spec §4.2)."""
    text = _DOT_LEADERS.sub(" ", text.lower())
    return re.findall(r"[a-z0-9]+", text)


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if (a or b) else 0.0


def camel_words(element: str) -> list[str]:
    """``QualifiedBusinessIncomeDedAmt`` -> qualified, business, income,
    ded, amt; ``SSTWagesRRTCompAmt`` -> sst, wages, rrt, comp, amt."""
    name = element.split("/")[-1].lstrip("@$")
    return [w.lower() for w in re.findall(r"[A-Z]+(?![a-z])|[A-Z][a-z]*|\d+",
                                          name)]


def key_words(key: str, prefix: str | None) -> list[str]:
    """The key's descriptive words: without its form prefix and line
    number."""
    rest = key
    if prefix and rest.startswith(prefix + "_"):
        rest = rest[len(prefix) + 1:]
    rest = re.sub(r"^line_?\d+[a-z]?(?:_|$)", "", rest)
    return [w for w in rest.split("_") if w]


def containment(key: Sequence[str], line: Sequence[str]) -> float:
    """Share of the key's words the line names: literally, or as the
    initials of consecutive line words ("qbi" = qualified business income,
    "agi" = adjusted gross income)."""
    if not key:
        return 0.0
    line = list(line)
    present = set(line)
    initials = {"".join(w[0] for w in line[i:j])
                for i in range(len(line))
                for j in range(i + 2, min(i + 6, len(line)) + 1)}
    return sum(1 for w in key if w in present or (
        len(w) >= ACRONYM_FLOOR and w in initials)) / len(key)


# --- the official lines ----------------------------------------------------

def line_ref(line) -> str:
    """A printed line as "label", or "section:label" inside a section."""
    return f"{line.section}:{line.label}" if line.section else line.label


def _number(label: str) -> str | None:
    m = re.match(r"^(\d+)", label)
    return m.group(1) if m else None


def stylesheet_lines(form: str, year: int
                     ) -> dict[tuple[str, str], stylesheet.StylesheetLine]:
    """The year's stylesheet lines by (section, full label): a sub-line the
    stylesheet prints as a bare letter ("1a", "b", "c") carries the last
    number ("1b", "1c")."""
    out: dict[tuple[str, str], stylesheet.StylesheetLine] = {}
    last = None
    for line in stylesheet.load(form, year):
        label = line.label.strip("().")
        if _number(label):
            last = _number(label)
        elif re.fullmatch(r"[a-z]", label) and last:
            label = last + label
        else:
            continue
        out.setdefault((line.page_section, label), line)
    return out


def _stylesheet_line(styles, inv_line: InventoryLine):
    hit = styles.get((inv_line.section, inv_line.label))
    if hit is None:
        matches = [s for (sec, lab), s in styles.items()
                   if lab == inv_line.label]
        hit = matches[0] if len(matches) == 1 else None
    return hit


def stylesheet_agreement(styles, inv_line: InventoryLine) -> float:
    """Jaccard of the stylesheet's text for the line against the
    inventory's (0.0 when the stylesheet does not print the line)."""
    hit = _stylesheet_line(styles, inv_line)
    if hit is None:
        return 0.0
    return jaccard(set(words(hit.text)), set(words(inv_line.text)))


def is_split_row(inv_line: InventoryLine, lines) -> bool:
    """A printed-page row whose label lost its sub-letter to the text ("19"
    reading "a Alimony paid. 19a" beside the tooltip's own "19a")."""
    m = re.match(r"^([a-z])\s", inv_line.text)
    return bool(m) and any(
        o.page == inv_line.page and o.section == inv_line.section
        and o.label == inv_line.label + m.group(1) for o in lines)


def _line_words(inv_line: InventoryLine, styles) -> list[str]:
    out = words(inv_line.text)
    hit = _stylesheet_line(styles, inv_line) if styles else None
    if hit is not None:
        for element in hit.elements:
            out += camel_words(element)
    return out


def _evidence_element(hit, key: Sequence[str]) -> str:
    elements = [e for e in hit.elements if not e.startswith("$")]
    return max(reversed(elements),
               key=lambda e: containment(key, camel_words(e)))


# --- proposals -----------------------------------------------------------

def _rank(output_keys, prefix, line_words_: list[str]) -> tuple[str, ...]:
    target = set(line_words_)
    scored = []
    for key in output_keys:
        kw = key_words(key, prefix) or key.split("_")
        score = max(jaccard(set(kw), target), containment(kw, line_words_))
        scored.append((-score, key))
    return tuple(k for s, k in sorted(scored)[:CANDIDATES] if s < 0)


def propose(form: str, key: int | str, output_keys: Sequence[str]
            ) -> Proposals:
    inv = inventory.load(form, key)
    lines = inv.lines
    jurisdiction = json.loads(
        inventory.inventory_path(form, key).read_text())["jurisdiction"]
    styles = (stylesheet_lines(form, int(key))
              if jurisdiction == "federal" else {})
    prefix = KEY_PREFIX.get(form)
    naming = (re.compile(rf"^{re.escape(prefix)}_line_?(?P<n>\d+[a-z]?)(?:_|$)")
              if prefix else None)

    auto: list[Binding] = []
    exceptions: list[Exception_] = []
    claimed: dict[tuple[str, str], list[str]] = {}
    for k in sorted(output_keys):
        m = naming.match(k) if naming else None
        if not m:
            continue
        n = m.group("n")
        targets = [l for l in lines if l.label == n
                   and not is_split_row(l, lines)]
        kw = key_words(k, prefix)
        if len(targets) != 1:
            exceptions.append(Exception_(
                "", n, "disagree",
                tuple(line_ref(t) for t in targets) or (k,)))
            continue
        target = targets[0]
        claimed.setdefault((target.section, target.label), []).append(k)
        if containment(kw, _line_words(target, styles)) < KEY_AGREEMENT:
            ranked = sorted(
                (l for l in lines if not is_split_row(l, lines)),
                key=lambda l: -containment(kw, _line_words(l, styles)))
            exceptions.append(Exception_(
                target.section, target.label, "seam",
                tuple(line_ref(l) for l in ranked[:CANDIDATES]
                      if containment(kw, _line_words(l, styles)) > 0)
                + (k,)))
            continue
        if jurisdiction == "federal":
            hit = _stylesheet_line(styles, target)
            if hit is None or stylesheet_agreement(
                    styles, target) < STYLESHEET_AGREEMENT:
                exceptions.append(Exception_(
                    target.section, target.label, "disagree", (k,)))
                continue
            auto.append(Binding(
                target.section, target.label, k,
                f"naming+stylesheet:{_evidence_element(hit, kw)}"))
        elif target.source != "tooltip":
            # The FTB's tooltip must name the line itself; a line recovered
            # from the printed page is for an agent to confirm.
            exceptions.append(Exception_(
                target.section, target.label, "disagree", (k,)))
        else:
            auto.append(Binding(target.section, target.label, k,
                                "naming+tooltip"))
    # One key per line: two naming proposals for one line disagree.
    doubled = {line for line, keys in claimed.items() if len(keys) > 1}
    for line in doubled:
        auto = [b for b in auto if (b.section, b.line) != line]
        exceptions.append(Exception_(line[0], line[1], "disagree",
                                     tuple(sorted(claimed[line]))))
    named = set(claimed)
    for l in lines:
        if (l.section, l.label) in named or is_split_row(l, lines):
            continue
        exceptions.append(Exception_(
            l.section, l.label, "no-proposal",
            _rank(output_keys, prefix, _line_words(l, styles))))
    return Proposals(tuple(auto), tuple(exceptions))
