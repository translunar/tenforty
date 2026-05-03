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
    """Importer return value: typed lists per Sch CA vs. Sch D 540 routing."""
    sch_ca: list[CASchCAAdjustment] = field(default_factory=list)
    sch_d_540: list[CASchD540Adjustment] = field(default_factory=list)


def import_fods_divergences(fods_path: Path) -> FodsDivergences:
    doc = parse(str(fods_path))
    tables = doc.getElementsByTagNameNS(_TABLE_NS, "table")
    if not tables:
        return FodsDivergences()
    raise NotImplementedError("non-empty .fods parsing not yet implemented")
