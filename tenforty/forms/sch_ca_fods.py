"""Importer for the CA Schedule CA + Schedule D 540 divergence .fods worksheet.

Reads an OpenDocument Flat XML Spreadsheet and emits, per tab, either a
``CASchCAAdjustment`` (Schedule CA Part I/II tabs) or a ``CASchD540Adjustment``
(Schedule D 540 tabs) per non-zero per-direction column total. The .fods file
itself is the per-row audit trail; the importer collapses each tab to its
two formula-driven column totals.

Parses via ``xml.dom.minidom``. ``odf.opendocument.load`` only reads zipped
ODS — flat XML FODS raises BadZipFile.

Tab layout (rows are 1-indexed for documentation; minidom returns them in
document order):
  Row 1: free-form sheet header — "... — Part I §B 7 — ..." or
         "... — Sch D 540 — ..."
  Row 2: cell A = subtractions total =SUM(B5:B10000)
         cell B = additions total    =SUM(C5:C10000)
  Row 3+: column headers + data (ignored by the importer)
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.dom.minidom import Element, parse

from tenforty.models import (
    CASchCAAdjustment,
    CASchD540Adjustment,
    DivergenceDirection,
    DivergenceSource,
)


_OFFICE_NS = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"

_SCH_D_540_LABEL = "Sch D 540"


@dataclass
class FodsDivergences:
    """Importer return value: per-routing-target divergence lists.

    The .fods worksheet groups Pub 1001 divergences across two distinct
    downstream targets. ``sch_ca`` carries Schedule CA (540) Part I/II
    line-level adjustments (additions and subtractions to federal AGI
    components); these are routed by the generic Schedule CA kernel.
    ``sch_d_540`` carries Schedule D (540) capital-gains divergences
    (§1202 QSBS, §1045 rollover, §1400Z, pre-1987 inherited basis,
    Peace Corps PR, etc.); these are surfaced for visibility only until
    California Schedule D (540) user-divergence compute support ships."""

    sch_ca: list[CASchCAAdjustment] = field(default_factory=list)
    sch_d_540: list[CASchD540Adjustment] = field(default_factory=list)


def import_fods_divergences(fods_path: Path) -> FodsDivergences:
    # str() coercion is required: xml.dom.minidom.parse expects a path-as-string
    # or a file-like object; passing a Path raises AttributeError because
    # minidom calls .read() on non-str inputs.
    doc = parse(str(fods_path))
    out = FodsDivergences()
    for table in doc.getElementsByTagNameNS(_TABLE_NS, "table"):
        _route_tab(table, out)
    return out


def _route_tab(table: Element, out: FodsDivergences) -> None:
    rows = table.getElementsByTagNameNS(_TABLE_NS, "table-row")
    if len(rows) < 2:
        return
    label = _row_label(rows[0])
    if not label:
        return
    sub_total, add_total = _row_totals(rows[1])
    if label == _SCH_D_540_LABEL:
        if sub_total:
            out.sch_d_540.append(_make_sch_d_540(DivergenceDirection.SUBTRACTION, sub_total, label))
        if add_total:
            out.sch_d_540.append(_make_sch_d_540(DivergenceDirection.ADDITION, add_total, label))
        return
    if sub_total:
        out.sch_ca.append(_make_sch_ca(label, DivergenceDirection.SUBTRACTION, sub_total))
    if add_total:
        out.sch_ca.append(_make_sch_ca(label, DivergenceDirection.ADDITION, add_total))


def _row_label(row: Element) -> str:
    cells = row.getElementsByTagNameNS(_TABLE_NS, "table-cell")
    if not cells:
        return ""
    text = _cell_text(cells[0])
    # Header text is "... — <routing-label> — ..."; pick the first em-dash
    # segment that matches one of the routing patterns.
    for segment in (s.strip() for s in text.split("—")):
        if segment.startswith("Part ") or segment == _SCH_D_540_LABEL:
            return segment
    return ""


def _row_totals(row: Element) -> tuple[float, float]:
    cells = row.getElementsByTagNameNS(_TABLE_NS, "table-cell")
    sub = _cell_value(cells[0]) if len(cells) > 0 else 0.0
    add = _cell_value(cells[1]) if len(cells) > 1 else 0.0
    return sub, add


def _cell_text(cell: Element) -> str:
    parts = cell.getElementsByTagNameNS(_TEXT_NS, "p")
    out: list[str] = []
    for p in parts:
        for child in p.childNodes:
            if child.nodeType == child.TEXT_NODE:
                out.append(child.data)
    return "".join(out)


def _cell_value(cell: Element) -> float:
    raw = cell.getAttributeNS(_OFFICE_NS, "value")
    if not raw:
        return 0.0
    return float(raw)


def _make_sch_ca(
    label: str, direction: DivergenceDirection, amount: float,
) -> CASchCAAdjustment:
    return CASchCAAdjustment(
        source=DivergenceSource.WORKSHEET,
        sch_ca_line=label,
        direction=direction,
        amount=amount,
        description=f"Worksheet sum from .fods tab '{label}'",
    )


def _make_sch_d_540(
    direction: DivergenceDirection, amount: float, label: str,
) -> CASchD540Adjustment:
    return CASchD540Adjustment(
        source=DivergenceSource.WORKSHEET,
        direction=direction,
        amount=amount,
        description=f"Worksheet sum from .fods tab '{label}'",
    )
