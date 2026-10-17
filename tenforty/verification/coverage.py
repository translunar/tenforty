"""Coverage is measured, not assumed (spec §3.4).

A coverage cell is (form, year, declared line, observed output state), the
state being ``value`` (zero included) or ``nothing``. Every declared line of
every declared form-year needs both states produced by some battery
scenario, except:

- a ``single_state`` line needs only its one state (its reason says why);
- a ``scope="WORKBOOK"`` line is listed as ``WORKBOOK-SCOPED: owned by the
  e2e tests until the workbook retires`` and never counts as uncovered.

Cells are OBSERVED states: coverage proves the paper matched the output in
both states, never that the output was right (boundary 1).
"""
import dataclasses
from collections.abc import Iterable, Mapping

from tenforty.declarations import registry
from tenforty.declarations.model import FormDeclaration, expand
from tenforty.verification.record import RecordedForm

STATES = ("value", "nothing")
WORKBOOK_LABEL = ("WORKBOOK-SCOPED: owned by the e2e tests until the "
                  "workbook retires")

Cell = tuple[tuple[str, str], int | str, str, str]  # form, key, line, state


@dataclasses.dataclass(frozen=True)
class CoverageReport:
    covered: Mapping[Cell, tuple[str, ...]]      # cell -> scenarios
    uncovered: tuple[Cell, ...]                  # red
    workbook_scoped: tuple[Cell, ...]            # listed, never red

    def render(self) -> str:
        out = ["# coverage: cell -> scenarios (spec §3.4)"]
        for cell, scenarios in sorted(self.covered.items(), key=str):
            out.append(f"{_cell(cell)}  <- {', '.join(sorted(scenarios))}")
        out.append("# uncovered (red)")
        out += [f"UNCOVERED {_cell(c)}" for c in self.uncovered]
        out.append("# workbook-scoped (listed, never red)")
        out += [f"{WORKBOOK_LABEL}  {_cell(c)}" for c in self.workbook_scoped]
        return "\n".join(out) + "\n"


def _cell(cell: Cell) -> str:
    form, key, line, state = cell
    return f"{'/'.join(form)} {key} line {line} [{state}]"


def _required(decl: FormDeclaration, values_seen: Iterable[Mapping]
              ) -> tuple[set[Cell], set[Cell]]:
    """(required cells, workbook-scoped cells) for one declaration. Repeat
    lines contribute one line per index any record produced."""
    lines = {}
    for values in values_seen:
        for ln in expand(decl, values):
            lines[ln.line] = ln
    for ln in expand(decl, {}):
        lines.setdefault(ln.line, ln)
    required, workbook = set(), set()
    for ln in lines.values():
        states = (ln.single_state,) if ln.single_state else STATES
        for state in states:
            cell = (decl.form, decl.key, ln.line, state)
            (workbook if ln.scope == "WORKBOOK" else required).add(cell)
    return required, workbook


def coverage_cells(records: Iterable[tuple[str, RecordedForm]],
                   declarations: Iterable[FormDeclaration] | None = None
                   ) -> CoverageReport:
    """Coverage over ``(scenario name, RecordedForm)`` pairs from real
    emits. ``declarations`` defaults to every registered declaration, so a
    declared form no scenario emits shows every cell uncovered."""
    records = list(records)
    decls = {(d.form, d.key): d for d in (
        declarations if declarations is not None else
        (registry.for_form(f, k) for f, k in registry.declared_forms()))}
    covered: dict[Cell, set[str]] = {}
    seen: dict[tuple, list[Mapping]] = {}
    for scenario, rec in records:
        decl = decls.get((rec.form, rec.key))
        if decl is None:
            continue
        seen.setdefault((rec.form, rec.key), []).append(rec.values)
        for ln in expand(decl, rec.values):
            state = "nothing" if rec.values.get(ln.key) is None else "value"
            covered.setdefault((decl.form, decl.key, ln.line, state),
                               set()).add(scenario)
    uncovered, workbook = set(), set()
    for fk, decl in decls.items():
        req, wb = _required(decl, seen.get(fk, []))
        uncovered |= req - set(covered)
        workbook |= wb
    return CoverageReport(
        covered={c: tuple(sorted(s)) for c, s in covered.items()},
        uncovered=tuple(sorted(uncovered, key=str)),
        workbook_scoped=tuple(sorted(workbook, key=str)))
