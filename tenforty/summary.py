"""Results snapshots and the one-page columnar cover sheet.

Two public entry points, both pure additions the CALLER invokes after a
compute/emit run — nothing in the orchestrator knows this module exists:

``write_results_snapshot(results, path, *, year, label, ...)``
    Serializes the FULL results dict to JSON with provenance metadata. A full
    dump, deliberately, never a curated subset: the cover's row vocabulary can
    grow later without re-running any return whose snapshot was already taken.

``compose_cover(columns, out_pdf, *, extra_rows=None)``
    Renders ONE page — a single table, one column per snapshot — the "client
    tax summary" that sits on top of a return. No prose.

WHAT A SNAPSHOT'S ``results`` IS. One FLAT dict. The orchestrator returns the
federal results, the California results and the amendment-form values as
separate dicts; their key families are prefix-disjoint (``f540_*`` /
``sch_ca_*`` / ``sch_d_540_*`` for California, ``f1040x_*`` and
``schedule_x_*`` for the amendment forms), so a caller who wants the state
block or the amendment rows merges them into the one dict it snapshots:
``{**federal_results, **ca_results, **f1040x_values, **schedule_x_values}``.

ROW VOCABULARY -> RESULTS KEYS. The vocabulary is fixed and mirrors Form 1040,
not any particular filer. Where several keys are listed, the FIRST one present
with a non-None value wins; the later ones exist because the two federal
compute paths (native spine, XLSX workbook) and the leaf schedule computes
name the same line differently.

  Income
    Wages                         ``wages``                          (1040 line 1a/1z)
    Interest                      ``taxable_interest`` | ``interest_income``     (2b)
    Dividends                     ``ordinary_dividends`` | ``dividend_income``   (3b)
    Capital gain/loss (Sch D)     ``capital_gain_loss``                          (7)
                                  — the section-1211-CAPPED transfer to the
                                  1040, not the uncapped ``schd_line16``, so
                                  the income rows foot to Total income.
    Business income (Sch C)       ``sch_1_line_3_business_income``
                                  | ``sch_c_line_31_net_profit_total``  (Sch 1 line 3)
    Rentals, royalties &          ``sch_1_line_5_rental_re_royalty``    (Sch 1 line 5)
      pass-throughs (Sch E)       — Sch E Part I line 26 + Part II line 41.
    Retirement/Social Security    ``ira_taxable`` + ``pensions_taxable``
                                  + ``social_security_taxable``      (4b + 5b + 6b)
                                  — sum of whichever are present; these are
                                  the names Schedule CA already reads off the
                                  federal results. No federal compute path
                                  produces them today, so the row is dormant.
    Unemployment/other income     ``sch_1_line_10`` − Sch 1 line 3 − Sch 1 line 5
                                  — the RESIDUAL of "additional income" (Sch 1
                                  lines 1, 4, 6, 7, 8z), so the income rows
                                  foot to Total income by construction. When
                                  line 10 (or line 3 / line 5) is missing it
                                  falls back to the sum of whichever of
                                  ``sch_1_line_1_taxable_refunds``,
                                  ``sch_1_line_4_other_gains``,
                                  ``sch_1_line_6_farm_income``,
                                  ``sch_1_line_7_unemployment``,
                                  ``sch_1_line_8z_other_income`` are present.
  Computation
    Total income                  ``total_income``                               (9)
    Adjustments                   ``adjustments`` | ``sch_1_line_26``
                                  | ``sch_1_line_26_total_adjustments``         (10)
    AGI                           ``agi``                                       (11)
    Deduction                     ``total_deductions`` | ``applied_deduction``  (12)
                                  — ``total_deductions`` first because it is
                                  line 12(c): in 2021 it carries the line-12b
                                  non-itemizer charitable amount, which
                                  ``applied_deduction`` does not, and it is
                                  the figure AGI − deduction − QBI foots with.
                                  Tagged "itemized" when ``schedule_a_total``
                                  is positive and >= ``standard_deduction``
                                  (the spine's own tie rule), else "std".
    QBI deduction                 ``qbi_deduction`` | ``_qbi_deduction_1040``   (13)
    Taxable income                ``taxable_income``                            (15)
  Tax
    Income tax                    ``total_tax``                                 (16)
                                  — on BOTH compute paths ``total_tax`` is
                                  1040 LINE 16, income tax only. It is never
                                  read here as a liability.
    Other taxes (Sch 2)           ``schedule2_tax`` + ``other_taxes``       (17 + 23)
                                  — Schedule 2 Part I plus Part II. BOTH keys
                                  are required: the workbook path harvests no
                                  line 23, and printing Part I alone under
                                  this label would be a partial total.
    Credits                       ``total_credits``                             (21)
                                  — nonrefundable credits. Refundable credits
                                  (net premium tax credit) are in Payments,
                                  where the 1040 itself puts them.
    Total tax                     ``tax_liability_line24``                      (24)
                                  | ``tax_after_credits`` + ``other_taxes``
                                  — the workbook path harvests line 24
                                  directly; the native spine publishes no
                                  line-24 key but does publish lines 22 and
                                  23, whose sum is line 24 (it is the same
                                  composition the spine settles against).
    Payments                      ``total_payments``                            (33)
    BOTTOM LINE                   refund: ``overpaid``                          (34)
                                  owe:    ``amount_owed``                       (37)
                                  — the two keys the spine derives from
                                  payments − line 24. The workbook path
                                  harvests ``overpaid`` only, so when
                                  ``amount_owed`` is absent the owed side is
                                  derived as ``tax_liability_line24`` −
                                  ``total_payments``. With neither available
                                  the cell is ABSENT, never "0".
  California (printed when any column carries Form 540 results)
    CA AGI                        ``f540_ca_agi``                          (540 line 17)
    CA taxable                    ``f540_taxable_income``                       (19)
    CA tax                        ``f540_ca_tax``                               (31)
                                  — tax BEFORE credits; line 48 is not a
                                  published key.
    CA bottom line                ``f540_total_liability``
                                  — a SIGNED net (tax − credits + additions −
                                  payments): positive is owed, negative is a
                                  refund.
  Amendment (printed when any column carries amendment-form values)
    1040-X bottom line            owe:    ``f1040x_line20_amount_owed`` | ``f1040x_line20``
                                  refund: ``f1040x_line21`` | ``f1040x_line22_refund``
                                          | ``f1040x_line22``
    Schedule X bottom line        owe:    ``schedule_x_line7_amount_owed`` | ``schedule_x_line7``
                                  refund: ``schedule_x_line9`` | ``schedule_x_line11_refund``
                                          | ``schedule_x_line11``
  Notes
    Caller-supplied ``extra_rows``: ``{row_label: {column_index: short_string}}``.

PRINTING RULES. A row prints only if at least one column holds a NONZERO value
for it (zero-collapse). The bottom-line rows (BOTTOM LINE, CA bottom line,
1040-X bottom line, Schedule X bottom line) are EXEMPT: an exactly-even bottom
line prints "0", and the row is dropped only when no column carries one at
all. In a row that prints, a column whose snapshot lacks the
value shows an em dash and a column whose value is a real zero shows "0" — the
two are different facts. Amounts are whole dollars with thousands separators,
right-aligned; a negative is parenthesized. A bottom line prints as
"refund N" or "owe N". The page never overflows: a table too wide or too tall
for one page raises ``CoverOverflowError`` and writes nothing.
"""
from __future__ import annotations

import datetime
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Mapping

from tenforty.rounding import irs_round

__all__ = [
    "SNAPSHOT_SCHEMA",
    "CoverOverflowError",
    "write_results_snapshot",
    "load_results_snapshot",
    "cover_table",
    "compose_cover",
]

SNAPSHOT_SCHEMA = "tenforty.results-snapshot/1"

# A caller-supplied extra-row value is a terse tag ("closed 4/26"), never a
# sentence. The cap is what makes that a checked rule rather than a hope.
MAX_EXTRA_CHARS = 24

DASH = "—"


class CoverOverflowError(ValueError):
    """The cover table does not fit on one page; nothing was written."""


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

# Result keys never written to a snapshot, by suffix: bank routing and
# account numbers (the California results carry the direct deposit numbers on
# their way to Form 540 line 116). A snapshot is a review artifact that gets
# kept and compared; it has no use for them. Matching by suffix covers any
# such key added later, at any depth of the results.
SNAPSHOT_REDACTED_KEY_SUFFIXES: tuple[str, ...] = (
    "_routing_number", "_account_number")


def _without_redacted_keys(value):
    """``value`` with every mapping key ending in a redacted suffix dropped,
    recursively through mappings, lists and tuples. Returns ``value`` itself
    (never a copy) when it holds nothing to drop, so an unaffected snapshot
    serializes exactly as before."""
    if isinstance(value, Mapping):
        kept = {
            key: _without_redacted_keys(item) for key, item in value.items()
            if not (isinstance(key, str)
                    and key.endswith(SNAPSHOT_REDACTED_KEY_SUFFIXES))}
        unchanged = len(kept) == len(value) and all(
            kept[key] is value[key] for key in kept)
        return value if unchanged else kept
    if isinstance(value, (list, tuple)):
        items = [_without_redacted_keys(item) for item in value]
        if all(new is old for new, old in zip(items, value)):
            return value
        return type(value)(items) if isinstance(value, tuple) else items
    return value


def write_results_snapshot(
    results: Mapping,
    path,
    *,
    year: int,
    label: str,
    scenario_path=None,
    emitted=None,
) -> Path:
    """Write the full ``results`` dict plus provenance metadata as JSON.

    ``label`` is the free-form column label the cover prints ("K-1",
    "Sch C"). ``scenario_path``, when given, is recorded together with the
    file's sha256 so a snapshot can be tied to the exact scenario it was
    computed from. ``emitted`` is the emit step's ``{form name: pdf path}``
    mapping (or any iterable of form names); only the names are kept.
    Values JSON cannot represent (paths, dates, decimals, enums) are written
    as their ``str()``.

    Keys ending in `SNAPSHOT_REDACTED_KEY_SUFFIXES` (bank routing and
    account numbers) are left out, at any depth. ``results`` itself is not
    modified.
    """
    path = Path(path)
    scenario = None
    if scenario_path is not None:
        scenario_path = Path(scenario_path)
        scenario = {
            "path": str(scenario_path),
            "sha256": hashlib.sha256(scenario_path.read_bytes()).hexdigest(),
        }
    snapshot = {
        "schema": SNAPSHOT_SCHEMA,
        "year": year,
        "label": label,
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"),
        "scenario": scenario,
        "emitted": sorted(str(name) for name in (emitted or ())),
        "results": dict(_without_redacted_keys(results)),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, indent=2, default=str) + "\n")
    return path


def load_results_snapshot(path) -> dict:
    """Read a snapshot written by ``write_results_snapshot``."""
    snapshot = json.loads(Path(path).read_text())
    return _validated(snapshot, origin=str(path))


def _validated(snapshot, origin: str) -> dict:
    if (
        not isinstance(snapshot, Mapping)
        or snapshot.get("schema") != SNAPSHOT_SCHEMA
        or not isinstance(snapshot.get("results"), Mapping)
        or "year" not in snapshot
        or "label" not in snapshot
    ):
        raise ValueError(
            f"{origin} is not a tenforty results snapshot (expected schema "
            f"{SNAPSHOT_SCHEMA!r} with year, label and results); write one "
            "with write_results_snapshot."
        )
    return dict(snapshot)


def _load_column(column, index: int) -> dict:
    if isinstance(column, Mapping):
        return _validated(column, origin=f"columns[{index}]")
    return load_results_snapshot(column)


# ---------------------------------------------------------------------------
# Cells
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _Cell:
    text: str
    zero: bool = False
    tone: str = "plain"   # plain | negative | refund | owe | note


def _num(results: Mapping, *keys: str) -> float | None:
    """The first of ``keys`` present with a numeric value, else None.

    A key holding None counts as not present (both compute paths use None for
    "this line did not apply"). Numeric strings are accepted so a Decimal that
    went through the snapshot's ``str()`` coercion still reads as money.
    """
    for key in keys:
        value = results.get(key)
        if value is None or isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                continue
    return None


def _fmt(amount: float) -> str:
    whole = irs_round(amount)
    return f"({-whole:,})" if whole < 0 else f"{whole:,}"


def _money(amount: float | None, tag: str | None = None) -> _Cell | None:
    if amount is None:
        return None
    whole = irs_round(amount)
    text = _fmt(whole)
    if tag:
        text = f"{tag} {text}"
    return _Cell(text, zero=(whole == 0),
                 tone="negative" if whole < 0 else "plain")


def _settlement(owe: float | None, refund: float | None) -> _Cell | None:
    """A bottom line from its two mutually exclusive sides."""
    if refund is not None and irs_round(refund) > 0:
        return _Cell(f"refund {_fmt(refund)}", tone="refund")
    if owe is not None and irs_round(owe) > 0:
        return _Cell(f"owe {_fmt(owe)}", tone="owe")
    if owe is None or refund is None:
        # One side unknown and the other not positive: we cannot say the
        # return is even, so say nothing.
        return None
    return _Cell("0", zero=True)


def _key(*keys: str) -> Callable[[Mapping], _Cell | None]:
    return lambda r: _money(_num(r, *keys))


def _sum_present(*keys: str) -> Callable[[Mapping], _Cell | None]:
    def cell(r: Mapping) -> _Cell | None:
        values = [v for v in (_num(r, k) for k in keys) if v is not None]
        return _money(sum(values)) if values else None
    return cell


def _sum_required(*keys: str) -> Callable[[Mapping], _Cell | None]:
    def cell(r: Mapping) -> _Cell | None:
        values = [_num(r, k) for k in keys]
        if any(v is None for v in values):
            return None
        return _money(sum(values))
    return cell


def _other_income(r: Mapping) -> _Cell | None:
    line_10 = _num(r, "sch_1_line_10", "sch_1_line_10_total_additional_income")
    line_3 = _num(r, "sch_1_line_3_business_income")
    line_5 = _num(r, "sch_1_line_5_rental_re_royalty")
    if None not in (line_10, line_3, line_5):
        return _money(line_10 - line_3 - line_5)
    return _sum_present(
        "sch_1_line_1_taxable_refunds", "sch_1_line_4_other_gains",
        "sch_1_line_6_farm_income", "sch_1_line_7_unemployment",
        "sch_1_line_8z_other_income",
    )(r)


def _deduction(r: Mapping) -> _Cell | None:
    amount = _num(r, "total_deductions", "applied_deduction")
    if amount is None:
        return None
    itemized = _num(r, "schedule_a_total") or 0
    standard = _num(r, "standard_deduction") or 0
    tag = "itemized" if itemized > 0 and itemized >= standard else "std"
    return _money(amount, tag=tag)


def _total_tax_amount(r: Mapping) -> float | None:
    line_24 = _num(r, "tax_liability_line24")
    if line_24 is not None:
        return line_24
    line_22 = _num(r, "tax_after_credits")
    line_23 = _num(r, "other_taxes")
    if line_22 is None or line_23 is None:
        return None
    return line_22 + line_23


def _federal_bottom_line(r: Mapping) -> _Cell | None:
    refund = _num(r, "overpaid")
    owe = _num(r, "amount_owed")
    if owe is None:
        line_24 = _num(r, "tax_liability_line24")
        payments = _num(r, "total_payments")
        if line_24 is not None and payments is not None:
            owe = max(0.0, line_24 - payments)
            if refund is None:
                refund = max(0.0, payments - line_24)
    return _settlement(owe, refund)


def _ca_bottom_line(r: Mapping) -> _Cell | None:
    net = _num(r, "f540_total_liability")
    if net is None:
        return None
    return _settlement(max(0.0, net), max(0.0, -net))


def _f1040x_bottom_line(r: Mapping) -> _Cell | None:
    return _settlement(
        _num(r, "f1040x_line20_amount_owed", "f1040x_line20"),
        _num(r, "f1040x_line21", "f1040x_line22_refund", "f1040x_line22"),
    )


def _schedule_x_bottom_line(r: Mapping) -> _Cell | None:
    return _settlement(
        _num(r, "schedule_x_line7_amount_owed", "schedule_x_line7"),
        _num(r, "schedule_x_line9", "schedule_x_line11_refund",
             "schedule_x_line11"),
    )


# (section, row label, cell function, emphasized). Emphasized == a
# bottom-line row: drawn bold on a band AND exempt from zero-collapse.
_VOCABULARY: tuple[tuple[str, str, Callable[[Mapping], _Cell | None], bool], ...] = (
    ("Income", "Wages", _key("wages"), False),
    ("Income", "Interest", _key("taxable_interest", "interest_income"), False),
    ("Income", "Dividends",
     _key("ordinary_dividends", "dividend_income"), False),
    ("Income", "Capital gain/loss (Sch D)", _key("capital_gain_loss"), False),
    ("Income", "Business income (Sch C)",
     _key("sch_1_line_3_business_income", "sch_c_line_31_net_profit_total"),
     False),
    ("Income", "Rentals, royalties & pass-throughs (Sch E)",
     _key("sch_1_line_5_rental_re_royalty"), False),
    ("Income", "Retirement/Social Security",
     _sum_present("ira_taxable", "pensions_taxable",
                  "social_security_taxable"), False),
    ("Income", "Unemployment/other income", _other_income, False),
    ("Computation", "Total income", _key("total_income"), False),
    ("Computation", "Adjustments",
     _key("adjustments", "sch_1_line_26", "sch_1_line_26_total_adjustments"),
     False),
    ("Computation", "AGI", _key("agi"), False),
    ("Computation", "Deduction", _deduction, False),
    ("Computation", "QBI deduction",
     _key("qbi_deduction", "_qbi_deduction_1040"), False),
    ("Computation", "Taxable income", _key("taxable_income"), False),
    ("Tax", "Income tax", _key("total_tax"), False),
    ("Tax", "Other taxes (Sch 2)",
     _sum_required("schedule2_tax", "other_taxes"), False),
    ("Tax", "Credits", _key("total_credits"), False),
    ("Tax", "Total tax", lambda r: _money(_total_tax_amount(r)), False),
    ("Tax", "Payments", _key("total_payments"), False),
    ("Tax", "BOTTOM LINE", _federal_bottom_line, True),
    ("California", "CA AGI", _key("f540_ca_agi"), False),
    ("California", "CA taxable", _key("f540_taxable_income"), False),
    ("California", "CA tax", _key("f540_ca_tax"), False),
    ("California", "CA bottom line", _ca_bottom_line, True),
    ("Amendment", "1040-X bottom line", _f1040x_bottom_line, True),
    ("Amendment", "Schedule X bottom line", _schedule_x_bottom_line, True),
)

_NOTES_SECTION = "Notes"


@dataclass(frozen=True)
class _Row:
    section: str
    label: str
    cells: tuple[_Cell | None, ...]
    emphasized: bool = False


def _extra_rows(extra_rows: Mapping | None, n_columns: int) -> list[_Row]:
    rows = []
    for label, by_column in (extra_rows or {}).items():
        cells: list[_Cell | None] = [None] * n_columns
        for raw_index, value in by_column.items():
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                index = -1
            if not 0 <= index < n_columns:
                raise ValueError(
                    f"extra row {label!r}: column index {raw_index!r} is out "
                    f"of range for {n_columns} column(s)."
                )
            if (not isinstance(value, str) or not value.strip()
                    or "\n" in value or len(value) > MAX_EXTRA_CHARS):
                raise ValueError(
                    f"extra row {label!r}, column {index}: value {value!r} "
                    f"must be a short single-line string of at most "
                    f"{MAX_EXTRA_CHARS} characters — a tag, not a sentence."
                )
            cells[index] = _Cell(value, tone="note")
        rows.append(_Row(_NOTES_SECTION, str(label), tuple(cells)))
    return rows


def _layout(columns: list[dict], extra_rows: Mapping | None) -> list[_Row]:
    """The rows that print, in order, after zero-collapse."""
    rows = []
    for section, label, cell_fn, emphasized in _VOCABULARY:
        cells = tuple(cell_fn(c["results"]) for c in columns)
        # A bottom-line row (the emphasized ones) prints whenever any column
        # HAS one, even an exactly-even "0": nothing due and nothing refunded
        # is the headline fact of a return, not noise. Every other row needs
        # a nonzero value somewhere.
        if any(cell is not None and (emphasized or not cell.zero)
               for cell in cells):
            rows.append(_Row(section, label, cells, emphasized))
    rows.extend(
        row for row in _extra_rows(extra_rows, len(columns))
        if any(cell is not None for cell in row.cells)
    )
    return rows


def _header(columns: list[dict]) -> list[str]:
    return [""] + [f"TY{c['year']} · {c['label']}" for c in columns]


def _cell_text(cell: _Cell | None) -> str:
    return DASH if cell is None else cell.text


def _load_columns(columns: Iterable) -> list[dict]:
    loaded = [_load_column(c, i) for i, c in enumerate(columns)]
    if not loaded:
        raise ValueError("compose_cover needs at least one snapshot column.")
    return loaded


def cover_table(columns: Iterable, *, extra_rows: Mapping | None = None
                ) -> list[list[str]]:
    """The cover as text: a header row, then one row per PRINTED vocabulary
    row (label first, one cell per column). Section headings are a rendering
    detail and are not included. This is exactly what ``compose_cover``
    draws."""
    loaded = _load_columns(columns)
    return [_header(loaded)] + [
        [row.label] + [_cell_text(cell) for cell in row.cells]
        for row in _layout(loaded, extra_rows)
    ]


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

_FONT = "Helvetica"
_BOLD = "Helvetica-Bold"
_SIZE = 9
_SECTION_SIZE = 7
_PAD_X = 6
_PAD_Y = 2.5


def compose_cover(columns: Iterable, out_pdf, *,
                  extra_rows: Mapping | None = None) -> Path:
    """Render the cover — one table on ONE US-Letter page — to ``out_pdf``.

    ``columns`` is a list of snapshot paths and/or already-loaded snapshot
    dicts, printed left to right. ``extra_rows`` is
    ``{row_label: {column_index: short_string}}``. Raises
    ``CoverOverflowError`` (and writes nothing) if the table cannot fit.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Table, TableStyle

    out_pdf = Path(out_pdf)
    loaded = _load_columns(columns)
    rows = _layout(loaded, extra_rows)
    n = len(loaded)

    ink = colors.HexColor("#1a1a1a")
    muted = colors.HexColor("#8a8a8a")
    rule = colors.HexColor("#c8c8c8")
    red = colors.HexColor("#b3261e")
    green = colors.HexColor("#1b6e3c")
    band = colors.HexColor("#f1f1f1")

    data: list[list[str]] = [_header(loaded)]
    style: list[tuple] = [
        ("FONT", (0, 0), (-1, -1), _FONT, _SIZE),
        ("TEXTCOLOR", (0, 0), (-1, -1), ink),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), _PAD_X),
        ("RIGHTPADDING", (0, 0), (-1, -1), _PAD_X),
        ("TOPPADDING", (0, 0), (-1, -1), _PAD_Y),
        ("BOTTOMPADDING", (0, 0), (-1, -1), _PAD_Y),
        ("FONT", (0, 0), (-1, 0), _BOLD, _SIZE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, ink),
    ]
    # Width each column needs, measured in the font its widest cell uses.
    needed = [0.0] * (n + 1)

    def measure(col: int, text: str, font: str, size: float) -> None:
        needed[col] = max(needed[col], stringWidth(text, font, size))

    for col, text in enumerate(data[0]):
        measure(col, text, _BOLD, _SIZE)

    section = None
    for row in rows:
        if row.section != section:
            section = row.section
            r = len(data)
            data.append([section.upper()] + [""] * n)
            style += [
                ("FONT", (0, r), (-1, r), _BOLD, _SECTION_SIZE),
                ("TEXTCOLOR", (0, r), (-1, r), muted),
                ("TOPPADDING", (0, r), (-1, r), 7),
                ("LINEBELOW", (0, r), (-1, r), 0.4, rule),
            ]
            measure(0, section.upper(), _BOLD, _SECTION_SIZE)
        r = len(data)
        data.append([row.label] + [_cell_text(cell) for cell in row.cells])
        row_font = _BOLD if row.emphasized else _FONT
        if row.emphasized:
            style += [
                ("FONT", (0, r), (-1, r), _BOLD, _SIZE),
                ("BACKGROUND", (0, r), (-1, r), band),
            ]
        measure(0, row.label, row_font, _SIZE)
        for i, cell in enumerate(row.cells):
            col = i + 1
            measure(col, _cell_text(cell), row_font, _SIZE)
            if cell is None:
                style.append(("TEXTCOLOR", (col, r), (col, r), muted))
            elif cell.tone == "negative":
                style.append(("TEXTCOLOR", (col, r), (col, r), red))
            elif cell.tone == "refund":
                style.append(("TEXTCOLOR", (col, r), (col, r), green))
            elif cell.tone == "note":
                style.append(("FONT", (col, r), (col, r),
                              "Helvetica-Oblique", _SIZE))
                measure(col, cell.text, "Helvetica-Oblique", _SIZE)

    page_w, page_h = letter
    margin = 36
    avail_w, avail_h = page_w - 2 * margin, page_h - 2 * margin

    widths = [w + 2 * _PAD_X + 1 for w in needed]
    if sum(widths) > avail_w:
        raise CoverOverflowError(
            f"The cover must fit on one page, and {n} column(s) need "
            f"{sum(widths):.0f}pt of width where the page has {avail_w:.0f}pt. "
            "Compose fewer columns per cover (or shorten the column labels)."
        )
    # Equal-width value columns read better; use them whenever they fit.
    value_w = max(widths[1:])
    if widths[0] + n * value_w <= avail_w:
        widths = [widths[0]] + [value_w] * n

    table = Table(data, colWidths=widths)
    table.setStyle(TableStyle(style))
    _, height = table.wrap(avail_w, avail_h)
    if height > avail_h:
        raise CoverOverflowError(
            f"The cover must fit on one page, and {len(data)} table row(s) "
            f"need {height:.0f}pt of height where the page has "
            f"{avail_h:.0f}pt. Pass fewer extra rows."
        )

    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    canvas = Canvas(str(out_pdf), pagesize=letter, invariant=1)
    canvas.setTitle("Tax summary")
    table.drawOn(canvas, margin, page_h - margin - height)
    canvas.showPage()
    canvas.save()
    return out_pdf
