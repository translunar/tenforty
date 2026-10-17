"""The emit declaration types (spec §2.1; rulings A2, A5, single_state).

A ``FormDeclaration`` lists, for one form and one tax year (or revision),
the printed lines tenforty's computation is responsible for. Each
``DeclaredLine`` binds a printed label to the compute key whose value prints
there. Declarations are written from the official form's own line list
(the inventory, ``tenforty.declarations.inventory``), never from tenforty's
mappings.

A printed line's identity is ``(section, line)``: a label that recurs under
two Parts ("1" in Part I and Part II) is two lines.

Years are diffs, not copies: ``derive`` builds a year from a base year with
explicit ``add``/``drop``/``relabel``/``rebind`` changes, and every year is
validated against its own inventory (``validate``).
"""
import dataclasses
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

from tenforty.declarations.anchors import Anchor

LineId = tuple[str, str]  # (section, line)


@dataclass(frozen=True)
class Repeat:
    """A templated line printed once per row or column (ruling A5).

    ``index_name`` is the placeholder in ``line`` and ``key`` ("i" for
    numbered rows, "col" for lettered columns). Exactly one of ``values``
    (explicit indices, e.g. Schedule E's columns "a", "b", "c") or ``max``
    (rows 1..max, expanded only for the rows the computation produced) is
    set."""
    index_name: str
    values: tuple[str, ...] | None = None
    max: int | None = None

    def __post_init__(self) -> None:
        if (self.values is None) == (self.max is None):
            raise ValueError(
                f"Repeat({self.index_name!r}) needs exactly one of `values` "
                "(explicit indices) or `max` (rows 1..max).")


@dataclass(frozen=True)
class DeclaredLine:
    line: str                              # official printed label; may contain "{i}"/"{col}" when repeat is set
    description: str                       # official line text from the inventory
    key: str                               # compute key; may contain "{i}"/"{col}" when repeat is set (A5)
    kind: Literal["amount", "text", "date", "checkbox", "ssn"]
    section: str = ""                      # Part/section heading, matching InventoryLine.section
    anchor: Anchor | None = None
    mef_element: str | None = None
    scope: Literal["NATIVE", "WORKBOOK"] = "NATIVE"
    group: str | None = None               # A2: option group name
    selects: str | None = None             # A2: key value that turns THIS line ON
    repeat: Repeat | None = None           # A5
    single_state: Literal["value", "nothing"] | None = None
    single_state_reason: str | None = None

    @property
    def line_id(self) -> LineId:
        return (self.section, self.line)


@dataclass(frozen=True)
class FormDeclaration:
    form: tuple[str, str]
    key: int | str                         # tax year, or revision for revision-keyed forms
    lines: tuple[DeclaredLine, ...]
    not_printed: Mapping[str, str]         # key -> reason; tags: intermediate:, presentation-only:, diagnostic:


def _require(ids: Iterable[LineId], present: set[LineId], what: str,
             base: FormDeclaration) -> None:
    missing = [i for i in ids if i not in present]
    if missing:
        raise KeyError(
            f"derive({base.form}, from {base.key}): cannot {what} "
            f"{missing}; the base declares no such (section, line).")


def derive(base: FormDeclaration, key: int | str, *,
           add: Iterable[DeclaredLine] = (),
           drop: Iterable[LineId] = (),
           relabel: Mapping[LineId, str] | None = None,
           rebind: Mapping[LineId, str] | None = None) -> FormDeclaration:
    """The declaration for ``key`` as explicit changes to ``base``.

    ``drop`` removes ``(section, line)`` lines; ``relabel`` gives a line a
    new printed label; ``rebind`` gives it a new compute key; ``add``
    appends new lines. Naming a line the base does not declare raises
    ``KeyError``: a stale diff fails loudly instead of silently doing
    nothing. ``not_printed`` carries over unchanged."""
    relabel = dict(relabel or {})
    rebind = dict(rebind or {})
    drop = tuple(drop)
    present = {ln.line_id for ln in base.lines}
    _require(drop, present, "drop", base)
    _require(relabel, present, "relabel", base)
    _require(rebind, present, "rebind", base)
    dropped = set(drop)
    lines = []
    for ln in base.lines:
        if ln.line_id in dropped:
            continue
        changes = {}
        if ln.line_id in relabel:
            changes["line"] = relabel[ln.line_id]
        if ln.line_id in rebind:
            changes["key"] = rebind[ln.line_id]
        lines.append(dataclasses.replace(ln, **changes) if changes else ln)
    lines.extend(add)
    return FormDeclaration(form=base.form, key=key, lines=tuple(lines),
                           not_printed=dict(base.not_printed))


def _substitute(ln: DeclaredLine, index: str) -> DeclaredLine:
    placeholder = "{" + ln.repeat.index_name + "}"
    return dataclasses.replace(
        ln, line=ln.line.replace(placeholder, index),
        key=ln.key.replace(placeholder, index), repeat=None)


def expand(decl: FormDeclaration, values: Mapping[str, object]
           ) -> tuple[DeclaredLine, ...]:
    """The declaration's lines with every repeat template substituted, in
    declaration order. ``Repeat.values`` expand to one line per value;
    ``Repeat.max`` expands to the rows 1..max whose key is present in
    ``values`` (the computation's output), so a return with three rows
    declares three lines, not ``max``."""
    out: list[DeclaredLine] = []
    for ln in decl.lines:
        rep = ln.repeat
        if rep is None:
            out.append(ln)
        elif rep.values is not None:
            out.extend(_substitute(ln, v) for v in rep.values)
        else:
            placeholder = "{" + rep.index_name + "}"
            out.extend(
                _substitute(ln, str(i)) for i in range(1, rep.max + 1)
                if ln.key.replace(placeholder, str(i)) in values)
    return tuple(out)
