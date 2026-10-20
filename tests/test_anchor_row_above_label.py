"""ROW_ABOVE_LABEL: a field anchored by a print-once phrase on the row
directly BELOW it (team-lead ruling, sch_e line 29b, 2026-10-19).

Schedule E's 29b row prints only a bare "b" and "Totals" (which prints four
times on page 2: rows 29a, 29b, 34a, 34b); the 29a row's "29a" prints twice
in 2022-2025 (line 30's text says "line 29a"). The row below 29b -- line 30
-- begins with "Add columns (h) and (k)", printed once per page every year.

Semantics (page y-up; rect/box = [x0, y0, x1, y1]):
- the phrase prints exactly once on the field's page; any other count is a
  refusal (never a geometric disambiguation);
- vertical abut: |field.y0 - phrase.y1| < ROW_PT;
- x-window: phrase.x0 - COLUMN_PT < field.x0 < phrase.x1.
"""
import unittest
from pathlib import Path

from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.verification import anchors as anchor_eval

REPO_ROOT = Path(__file__).resolve().parents[1]
_YEARS = (2021, 2022, 2023, 2024, 2025)
_P2 = "topmostSubform[0].Page2[0]."
_PHRASE = "Add columns (h) and (k)"
# Per year: the true 29b column-(g) box; the 29a-row box in the same column
# (2021: a shaded widget); the next column on the 29b row; line 34a's first
# box (same x-window as 29b, far below).
_BOXES = {
    2021: {"own": "f2_37", "29a_row": "R1", "next_column": "R4",
           "34a_row": "R6"},
    **{y: {"own": "f2_40", "29a_row": "f2_35", "next_column": "f2_41",
           "34a_row": "f2_60"} for y in (2022, 2023, 2024, 2025)},
}


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"


def _anchor(phrase=_PHRASE):
    return NearLabel(phrase, LabelRelation.ROW_ABOVE_LABEL)


class RowAboveLabelBoundaryTests(unittest.TestCase):
    """Both sides of every strict bound, on synthetic geometry."""

    BOX = (64.8, 444.6, 159.7, 455.1)  # the 2022-2025 phrase box
    TRUE = (93.6, 456.0, 186.4, 468.0)

    def _ok(self, rect):
        return anchor_eval._near_label(_anchor(), "F", rect, self.BOX) is None

    def _with(self, x0=None, y0=None):
        x = self.TRUE[0] if x0 is None else x0
        y = self.TRUE[1] if y0 is None else y0
        return (x, y, x + 92.8, y + 12.0)

    def test_the_true_box_qualifies(self):
        self.assertTrue(self._ok(self.TRUE))

    def test_vertical_bound_is_strict_on_both_sides(self):
        top, eps = self.BOX[3], 0.01
        self.assertTrue(self._ok(self._with(y0=top + anchor_eval.ROW_PT - eps)))
        self.assertFalse(self._ok(self._with(y0=top + anchor_eval.ROW_PT)))
        self.assertTrue(self._ok(self._with(y0=top - anchor_eval.ROW_PT + eps)))
        self.assertFalse(self._ok(self._with(y0=top - anchor_eval.ROW_PT)))

    def test_x_window_left_slack_is_column_pt_strict(self):
        left, eps = self.BOX[0] - anchor_eval.COLUMN_PT, 0.01
        self.assertTrue(self._ok(self._with(x0=left + eps)))
        self.assertFalse(self._ok(self._with(x0=left)))

    def test_x_window_right_edge_is_the_phrase_end_strict(self):
        right, eps = self.BOX[2], 0.01
        self.assertTrue(self._ok(self._with(x0=right - eps)))
        self.assertFalse(self._ok(self._with(x0=right)))


class RowAboveLabelTemplateTests(unittest.TestCase):
    """Schedule E 29b on the official templates: placed, and every
    neighbouring box refused."""

    def _evaluate(self, year, which, phrase=_PHRASE):
        return anchor_eval.evaluate(
            _anchor(phrase), _P2 + _BOXES[year][which] + "[0]",
            _template(year))

    def test_the_phrase_prints_exactly_once(self):
        for year in _YEARS:
            words = anchor_eval._page_words(str(_template(year)), 1)
            with self.subTest(year=year):
                self.assertEqual(
                    len(anchor_eval._phrase_boxes(words, _PHRASE)), 1)

    def test_29b_is_placed(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertIsNone(self._evaluate(year, "own"))

    def test_neighbouring_boxes_are_refused(self):
        for year in _YEARS:
            for which in ("29a_row", "next_column", "34a_row"):
                with self.subTest(year=year, box=which):
                    self.assertIsNotNone(self._evaluate(year, which))

    def test_a_repeated_phrase_refuses_loudly(self):
        # "Totals" prints 4x on page 2 and DOES sit left of the 29b box on
        # its own row: a _SIDE-style geometric resolution would accept it.
        # ROW_ABOVE_LABEL never disambiguates; several prints refuse.
        for year in _YEARS:
            with self.subTest(year=year):
                finding = self._evaluate(year, "own", phrase="Totals")
                self.assertIsNotNone(finding)
                self.assertIn("print exactly once", finding.message)

    def test_an_absent_phrase_refuses(self):
        finding = self._evaluate(2025, "own", phrase="Add columns (z)")
        self.assertIsNotNone(finding)
        self.assertIn("print exactly once", finding.message)


if __name__ == "__main__":
    unittest.main()
