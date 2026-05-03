"""Importer for the CA Schedule CA divergence .fods worksheet.

Reads an OpenDocument Flat XML Spreadsheet and emits, per tab, either a
``CASchCAAdjustment`` (Sch CA Part I/II tabs) or a ``CASchD540Adjustment``
(Sch D 540 tabs) per non-zero per-direction column total. The .fods file
itself is the per-row audit trail; the importer collapses each tab to its
two formula-driven column totals.

FODS parsing uses ``xml.dom.minidom`` directly (not ``odf.opendocument.load``,
which only handles zipped ODS).
"""

from dataclasses import dataclass, field
from pathlib import Path
from xml.dom.minidom import parse

from tenforty.models import (
    CASchCAAdjustment,
    CASchD540Adjustment,
    DivergenceDirection,
    DivergenceSource,
)


_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"


@dataclass
class FodsDivergences:
    """Importer return value: per-routing-target divergence lists.

    The .fods worksheet groups Pub 1001 divergences across two distinct
    downstream targets. ``sch_ca`` carries Schedule CA (540) Part I/II
    line-level adjustments (additions and subtractions to federal AGI
    components); these are routed by the SP3 generic Sch CA kernel.
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
    tables = doc.getElementsByTagNameNS(_TABLE_NS, "table")
    if not tables:
        return FodsDivergences()
    raise NotImplementedError("non-empty .fods parsing not yet implemented")
