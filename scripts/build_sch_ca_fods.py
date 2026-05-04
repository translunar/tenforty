"""Generate the Schedule CA divergence .fods template from the catalog.

Reads spreadsheets/california/<year>/sch_ca_divergences-<year>.catalog.yaml
and writes spreadsheets/california/<year>/sch_ca_input_worksheet.fods.
Run once at template-authoring time and on annual Pub 1001 refresh.
"""

import argparse
import sys
from itertools import groupby
from pathlib import Path

import yaml
from odf.opendocument import OpenDocumentSpreadsheet
from odf.table import Table, TableCell, TableRow
from odf.text import P


_TAB_NAME_TRANS = str.maketrans({"§": "", " ": "_", "/": "_", ":": "_"})


def _sanitize_tab_name(sch_ca_line: str) -> str:
    return sch_ca_line.translate(_TAB_NAME_TRANS).replace("__", "_").strip("_")


def _common_first(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (not r.get("common", False), r.get("description", "")))


def _build_tab(sch_ca_line: str, rows: list[dict]) -> Table:
    section_title = rows[0].get("section_title", "")
    table = Table(name=_sanitize_tab_name(sch_ca_line))

    header_text = f"Schedule CA (540) — {sch_ca_line} — {section_title}"
    table.addElement(_text_row(header_text))

    table.addElement(_totals_row())

    table.addElement(_text_row("Description", "Subtractions", "Additions", "Pub 1001 ref"))

    table.addElement(TableRow())  # blank separator

    for row in _common_first(rows):
        table.addElement(_data_row(row))

    return table


def _text_row(*texts: str) -> TableRow:
    row = TableRow()
    for t in texts:
        cell = TableCell(valuetype="string")
        cell.addElement(P(text=t))
        row.addElement(cell)
    return row


def _totals_row() -> TableRow:
    row = TableRow()
    for col in ("B", "C"):
        cell = TableCell(valuetype="float", value="0",
                         formula=f"of:=SUM({col}5:{col}10000)")
        cell.addElement(P(text="0"))
        row.addElement(cell)
    return row


def _data_row(row: dict) -> TableRow:
    out = TableRow()
    desc = TableCell(valuetype="string")
    desc.addElement(P(text=row["description"]))
    out.addElement(desc)

    direction = row["direction"]
    sub_active = direction in ("Sub", "Both")
    add_active = direction in ("Add", "Both")
    out.addElement(_amount_cell(active=sub_active))
    out.addElement(_amount_cell(active=add_active))

    pub_ref = TableCell(valuetype="string")
    pub_ref.addElement(P(text=f"p.{row['pub1001_page']}"))
    out.addElement(pub_ref)

    return out


def _amount_cell(active: bool) -> TableCell:
    cell = TableCell(valuetype="float", value="0")
    cell.addElement(P(text="" if active else "—"))
    return cell


def build_template(catalog_path: Path) -> OpenDocumentSpreadsheet:
    catalog = yaml.safe_load(catalog_path.read_text())
    catalog.sort(key=lambda r: r["sch_ca_line"])

    doc = OpenDocumentSpreadsheet()
    for sch_ca_line, group in groupby(catalog, key=lambda r: r["sch_ca_line"]):
        doc.spreadsheet.addElement(_build_tab(sch_ca_line, list(group)))
    return doc


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    doc = build_template(args.catalog)
    # odfpy's save() produces packaged ODS (zip). xml() produces flat XML
    # (.fods). Write the flat XML bytes directly to the output path.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(doc.xml())
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
