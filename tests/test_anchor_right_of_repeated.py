"""A RIGHT_OF anchor whose label token prints more than once (team-lead
ruling, bucket (b), sch_c declaration lane).

Schedule C Part II's two-field rows anchor each bound field to its printed
box label ("8", "17", "18", "26"), a lone token that also prints in the left
margin of the same row (and, for "8", inside line 28's text). Measured on
all five templates, exactly one occurrence sits on the bound field's row
within LABEL_GAP_PT left of it (gaps 6.4-8.6 pt); every other occurrence is
144 pt or more from any field on its row.

The evaluator resolves such a phrase to the ONE occurrence that qualifies by
geometry -- on the field's row, left of it, the gap from the token's right
edge to the field's left edge within LABEL_GAP_PT -- and refuses, as before,
when none or several qualify. Only RIGHT_OF does this; every other relation,
and every phrase that prints once, is unchanged.
"""
import unittest
import unittest.mock
from pathlib import Path

from tenforty.declarations.anchors import LabelRelation, NearLabel
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.verification import anchors as anchor_eval

REPO_ROOT = Path(__file__).resolve().parents[1]
_YEARS = (2021, 2022, 2023, 2024, 2025)
# The repeated box-label token -> the key whose field it labels, and the
# years its row holds two fields (line 26: 2021-2022 only).
_TWO_FIELD_ROWS = {
    "8": ("sch_c_expense_advertising", _YEARS),
    "17": ("sch_c_expense_legal_professional", _YEARS),
    "18": ("sch_c_expense_office_expense", _YEARS),
    "26": ("sch_c_expense_wages", (2021, 2022)),
}


def _template(year):
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040sc.pdf"


def _field(year, key):
    return PdfSchC.get_mapping(year)[key]


class RepeatedRightOfLabelTests(unittest.TestCase):
    def test_the_tokens_print_more_than_once(self):
        # The premise: without geometry these phrases are ambiguous.
        for token, (_, years) in _TWO_FIELD_ROWS.items():
            for year in years:
                words = anchor_eval._page_words(str(_template(year)), 0)
                with self.subTest(token=token, year=year):
                    self.assertGreater(
                        len(anchor_eval._phrase_boxes(words, token)), 1)

    def test_each_box_label_locates_its_field(self):
        for token, (key, years) in _TWO_FIELD_ROWS.items():
            for year in years:
                with self.subTest(token=token, year=year):
                    self.assertIsNone(anchor_eval.evaluate(
                        NearLabel(token, LabelRelation.RIGHT_OF),
                        _field(year, key), _template(year)))

    def test_a_repeated_label_beside_no_field_still_refuses(self):
        # No "8" sits within LABEL_GAP_PT left of line 17's field: zero
        # occurrences qualify, so the anchor is ambiguous, as before.
        finding = anchor_eval.evaluate(
            NearLabel("8", LabelRelation.RIGHT_OF),
            _field(2021, "sch_c_expense_legal_professional"), _template(2021))
        self.assertIsNotNone(finding)
        self.assertIn("ambiguous", finding.message)

    def test_other_relations_still_require_exactly_one_print(self):
        for relation in (LabelRelation.LEFT_OF, LabelRelation.ON_ROW,
                         LabelRelation.AFTER_WRAPPED):
            with self.subTest(relation=relation):
                finding = anchor_eval.evaluate(
                    NearLabel("8", relation),
                    _field(2021, "sch_c_expense_advertising"), _template(2021))
                self.assertIsNotNone(finding)
                self.assertIn("ambiguous", finding.message)

    def test_two_qualifying_occurrences_still_refuse(self):
        # Fail-closed: geometry must pick exactly one. Two "8"s both within
        # LABEL_GAP_PT left of the field, on its row -> ambiguous.
        words = (("8", 160.0, 100.0, 165.0, 110.0),
                 ("8", 170.0, 100.0, 175.0, 110.0))
        with unittest.mock.patch.object(
                anchor_eval, "_page_words", lambda template, page: words), \
                unittest.mock.patch.object(
                    anchor_eval, "widget_rect",
                    lambda template, field: (0, (180.0, 100.0, 280.0, 110.0))):
            finding = anchor_eval.evaluate(
                NearLabel("8", LabelRelation.RIGHT_OF), "synthetic.field",
                Path("synthetic.pdf"))
        self.assertIsNotNone(finding)
        self.assertIn("ambiguous", finding.message)


class SinglePrintPhrasesAreUnchangedTests(unittest.TestCase):
    """A phrase that prints once takes the evaluator's original path."""

    def test_a_single_print_label_locates_its_field(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertIsNone(anchor_eval.evaluate(
                    NearLabel("24b", LabelRelation.RIGHT_OF),
                    _field(year, "sch_c_expense_deductible_meals"),
                    _template(year)))

    def test_a_single_print_label_beside_another_field_fails_on_geometry(self):
        # Not an ambiguity: the one "24b" is not left of line 8's field.
        finding = anchor_eval.evaluate(
            NearLabel("24b", LabelRelation.RIGHT_OF),
            _field(2021, "sch_c_expense_advertising"), _template(2021))
        self.assertIsNotNone(finding)
        self.assertNotIn("ambiguous", finding.message)
        self.assertIn("is not right_of", finding.message)


if __name__ == "__main__":
    unittest.main()
