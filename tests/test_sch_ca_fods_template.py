import unittest
from pathlib import Path
from xml.dom.minidom import Element, parse

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE_PATH = REPO_ROOT / "spreadsheets" / "california" / "2025" / "sch_ca_input_worksheet.fods"
TEMPLATE_PATH_2024 = REPO_ROOT / "spreadsheets" / "california" / "2024" / "sch_ca_input_worksheet.fods"

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


def _assert_template_shape(test_case: unittest.TestCase, tables) -> None:
    """Assert structural invariants that every generated .fods worksheet must satisfy."""
    test_case.assertGreater(len(tables), 0, "worksheet must have at least one tab")

    for table in tables:
        tab_name = table.getAttributeNS(_TABLE_NS, "name")
        with test_case.subTest(tab=tab_name):
            rows = table.getElementsByTagNameNS(_TABLE_NS, "table-row")
            test_case.assertGreaterEqual(
                len(rows), 3,
                f"tab {tab_name!r} must have at least 3 rows",
            )

            # Row 1: human-readable label naming a Sch CA Part or Sch D 540
            text = _row_text(rows[0])
            test_case.assertTrue(
                "Part " in text or "Sch D 540" in text,
                f"tab {tab_name!r} row 1 must name a Sch CA Part or Sch D 540: {text!r}",
            )

            # Row 2: two =SUM() total cells
            cells = rows[1].getElementsByTagNameNS(_TABLE_NS, "table-cell")
            test_case.assertGreaterEqual(
                len(cells), 2,
                f"tab {tab_name!r} row 2 must have at least 2 cells",
            )
            for c in cells[:2]:
                formula = c.getAttributeNS(_TABLE_NS, "formula") or ""
                test_case.assertTrue(
                    formula.startswith("of:=SUM("),
                    f"tab {tab_name!r} row 2 totals must use =SUM(): {formula!r}",
                )

            # No auto-derived-only lines (forbidden set is currently empty)
            forbidden_labels: set[str] = set()
            for label in forbidden_labels:
                test_case.assertNotIn(label, text)


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


class TemplateShapeTests2024(unittest.TestCase):
    """Structural shape checks for the TY2024 Schedule CA divergence worksheet.

    The 2024 worksheet is generated from a verbatim row-copy of the 2025 catalog
    (header comment updated to TY2024 only); the Sch CA line structure is
    identical between years. These tests assert the same structural invariants
    as TemplateShapeTests — not byte-equality, only shape.
    """

    @classmethod
    def setUpClass(cls):
        cls.doc = parse(str(TEMPLATE_PATH_2024))
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
        forbidden_labels: set[str] = set()
        for table in self.tables:
            text = _row_text(table.getElementsByTagNameNS(_TABLE_NS, "table-row")[0])
            for label in forbidden_labels:
                self.assertNotIn(label, text)

    def test_same_tab_count_as_2025(self):
        """2024 catalog is a verbatim row copy of 2025 — tab count must be equal."""
        doc_2025 = parse(str(TEMPLATE_PATH))
        tables_2025 = doc_2025.getElementsByTagNameNS(_TABLE_NS, "table")
        self.assertEqual(
            len(self.tables),
            len(tables_2025),
            "2024 and 2025 worksheets should have the same number of tabs "
            f"(2024: {len(self.tables)}, 2025: {len(tables_2025)})",
        )
