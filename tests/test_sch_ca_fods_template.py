import unittest
from pathlib import Path
from xml.dom.minidom import Element, parse

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = REPO_ROOT / "spreadsheets" / "california" / "2025" / "sch_ca_input_worksheet.fods"

_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"


def _row_text(row: Element) -> str:
    cells = row.getElementsByTagNameNS(_TABLE_NS, "table-cell")
    if not cells:
        return ""
    parts = cells[0].getElementsByTagNameNS(_TEXT_NS, "p")
    out = []
    for p in parts:
        for child in p.childNodes:
            if child.nodeType == child.TEXT_NODE:
                out.append(child.data)
    return "".join(out)


class TemplateShapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = parse(str(TEMPLATE_PATH))
        cls.tables = cls.doc.getElementsByTagNameNS(_TABLE_NS, "table")

    def test_template_has_at_least_one_tab(self):
        self.assertGreater(len(self.tables), 0)

    def test_every_tab_has_human_label_in_row_1(self):
        for table in self.tables:
            with self.subTest(name=table.getAttributeNS(_TABLE_NS, "name")):
                rows = table.getElementsByTagNameNS(_TABLE_NS, "table-row")
                self.assertGreaterEqual(len(rows), 3)
                text = _row_text(rows[0])
                self.assertTrue(
                    "Part " in text or "Sch D 540" in text,
                    f"row 1 must name a Sch CA Part or Sch D 540: {text!r}",
                )

    def test_every_tab_has_two_total_cells_in_row_2(self):
        for table in self.tables:
            with self.subTest(name=table.getAttributeNS(_TABLE_NS, "name")):
                rows = table.getElementsByTagNameNS(_TABLE_NS, "table-row")
                cells = rows[1].getElementsByTagNameNS(_TABLE_NS, "table-cell")
                self.assertGreaterEqual(len(cells), 2)
                for c in cells[:2]:
                    formula = c.getAttributeNS(_TABLE_NS, "formula") or ""
                    self.assertTrue(
                        formula.startswith("of:=SUM("),
                        f"row 2 totals must use =SUM(): {formula!r}",
                    )

    def test_no_auto_derived_only_lines(self):
        # Lines with mixed manual + auto-derived items (e.g., Part I §B 7 has
        # UI auto-derived AND manual Pub 1001 items) ARE allowed — auto-derive
        # runs at compute time independently of the .fods. This test guards
        # against accidentally adding a tab whose only admitted divergences
        # are kernel-derived. Currently no Sch CA line is purely auto-derived,
        # so the forbidden set is empty.
        forbidden_labels: set[str] = set()
        for table in self.tables:
            text = _row_text(table.getElementsByTagNameNS(_TABLE_NS, "table-row")[0])
            for label in forbidden_labels:
                self.assertNotIn(label, text)
