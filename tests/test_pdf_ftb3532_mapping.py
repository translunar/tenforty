# tests/test_pdf_ftb3532_mapping.py
"""FTB 3532 (Head of Household Filing Status Schedule) template mapping,
every year 2021-2025.

Field identity is proved against EACH year's own template, never a
neighbour's:

- text cells by the widget's own ``/TU`` tooltip (the FTB templates carry
  ``/TU``, unlike the IRS ones);
- Part I / Part II selections by geometry: the widget the mapping turns ON
  sits on the row of its printed ``1a``..``1f`` / ``2a``..``2e`` label
  (``pdftotext -bbox``) and on no other label's row;
- the 3a/3b Yes/No answers by geometry: the widget the mapping turns ON for
  True is immediately left of the printed "Yes", and for False immediately
  left of "No" (spec section 5.2's provisional "/0 = Yes" reading is settled
  here, by placement, not by state order);
- ink: a filled value reads back as ``/V`` and puts dark pixels in its rect.

All values are synthetic.
"""
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_ftb3532 import REQUIRED_TEXT_KEYS, PdfFtb3532
from tests._pdf_pixels import checked_widgets, dark_pixels_in_rect, widget_rect
from tests.helpers import REPO_ROOT

YEARS = (2021, 2022, 2023, 2024, 2025)

MARITAL_LABEL = {
    "unmarried": "1a",
    "surviving_spouse": "1b",
    "marriage_annulled": "1c",
    "divorced_or_legally_separated": "1d",
    "married_lived_apart_all_year": "1e",
    "married_lived_together_part_of_year": "1f",
}
RELATIONSHIP_LABEL = {
    "child_or_stepchild": "2a",
    "grandchild_sibling_niece_or_nephew": "2b",
    "eligible_foster_child": "2c",
    "parent_or_stepparent": "2d",
    "other_relative": "2e",
}

# compute key -> (fragments the /TU must contain, fragments it must not)
TEXT_LABELS = {
    "ftb3532_header_name": (("Name", "shown on tax return"), ()),
    "ftb3532_header_ssn": (("Social Security",), ("Line 3",)),
    "ftb3532_period_1_from": (("beginning FROM",), ("Second",)),
    "ftb3532_period_1_to": (("ending TO",), ("Second",)),
    "ftb3532_period_2_from": (("Second beginning",), ()),
    "ftb3532_period_2_to": (("Second ending",), ()),
    "ftb3532_qp_first_name": (("Line 3", "First Name"), ()),
    "ftb3532_qp_last_name": (("Line 3", "Last Name"), ()),
    "ftb3532_qp_ssn": (("Line 3", "Social Security"), ()),
    "ftb3532_qp_dob": (("Line 3", "Date of birth"), ()),
    "ftb3532_line_4_gross_income": (("Line 4", "gross income"), ()),
    "ftb3532_line_5_days": (("Line 5", "Number of days"), ()),
}

# Answered on every branch of the form (header, line 3, lines 4 and 5).
ALWAYS_ANSWERED_TEXT_KEYS = (
    "ftb3532_header_name", "ftb3532_header_ssn",
    "ftb3532_qp_first_name", "ftb3532_qp_last_name",
    "ftb3532_qp_ssn", "ftb3532_qp_dob",
    "ftb3532_line_4_gross_income", "ftb3532_line_5_days",
)

TEXT_VALUES = {
    "ftb3532_header_name": "Example Filer",
    "ftb3532_header_ssn": "000000001",
    "ftb3532_period_1_from": "01/01/2024",
    "ftb3532_period_1_to": "02/15/2024",
    "ftb3532_period_2_from": "03/01/2024",
    "ftb3532_period_2_to": "04/30/2024",
    "ftb3532_qp_first_name": "Example",
    "ftb3532_qp_last_name": "Child",
    "ftb3532_qp_ssn": "000000005",
    "ftb3532_qp_dob": "03/07/2014",
    "ftb3532_line_4_gross_income": 1200,
    "ftb3532_line_5_days": 365,
}


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "california" / str(year) / "ftb3532.pdf"


def _words(pdf: Path) -> list[tuple[str, float, float, float, float]]:
    """Page-1 words as (text, x0, y0, x1, y1) in PDF points (origin bottom-left)."""
    xml = subprocess.run(
        ["pdftotext", "-bbox", "-f", "1", "-l", "1", str(pdf), "-"],
        check=True, capture_output=True, text=True).stdout
    root = ET.fromstring(xml)
    ns = {"x": "http://www.w3.org/1999/xhtml"}
    page = root.find(".//x:page", ns)
    height = float(page.get("height"))
    return [((w.text or ""), float(w.get("xMin")), height - float(w.get("yMax")),
             float(w.get("xMax")), height - float(w.get("yMin")))
            for w in page.findall("x:word", ns)]


def _label_rows(pdf: Path, labels) -> dict[str, tuple[float, float]]:
    """{label: (y0, y1)} for each label word, which must print exactly once."""
    rows: dict[str, list] = {}
    for text, _x0, y0, _x1, y1 in _words(pdf):
        if text in labels:
            rows.setdefault(text, []).append((y0, y1))
    for label in labels:
        assert len(rows.get(label, [])) == 1, (pdf, label, rows.get(label))
    return {label: boxes[0] for label, boxes in rows.items()}


def _v_overlap(rect, row) -> float:
    return min(rect[3], row[1]) - max(rect[1], row[0])


def _resolve(year: int, values: dict) -> dict[str, str]:
    return PdfFiller.resolve_fields(
        PdfFtb3532.get_mapping(year), values,
        derivations=PdfFtb3532.get_derivations(year),
        checkbox_states=PdfFtb3532.get_checkbox_states(year))


def _fill(year: int, values: dict, out: Path) -> Path:
    return PdfFiller().fill(
        template_path=_template(year), output_path=out,
        field_mapping=PdfFtb3532.get_mapping(year), values=values,
        derivations=PdfFtb3532.get_derivations(year),
        checkbox_states=PdfFtb3532.get_checkbox_states(year))


def _on_widgets(year: int, payload: dict[str, str]) -> list[tuple[str, str, list]]:
    """(field, state, rect) for each button cell the payload turns ON."""
    on = []
    for field, state in payload.items():
        if state.startswith("/") and state != "/Off":
            _page, rect = widget_rect(_template(year), field, on_state=state)
            on.append((field, state, rect))
    return on


class Ftb3532LabelIdentityTests(unittest.TestCase):
    """Every mapped text cell IS the template's widget for that line, per its
    own /TU, in every year."""

    def test_text_keys_map_to_widgets_with_matching_tooltips(self):
        for year in YEARS:
            mapping = PdfFtb3532.get_mapping(year)
            fields = PdfReader(str(_template(year))).get_fields()
            self.assertEqual(set(mapping), set(TEXT_LABELS), year)
            for key, (must, must_not) in TEXT_LABELS.items():
                with self.subTest(year=year, key=key):
                    field = fields[mapping[key]]
                    self.assertEqual(field.get("/FT"), "/Tx")
                    tu = str(field.get("/TU", ""))
                    for frag in must:
                        self.assertIn(frag, tu)
                    for frag in must_not:
                        self.assertNotIn(frag, tu)

    def test_each_text_key_has_its_own_widget(self):
        for year in YEARS:
            with self.subTest(year=year):
                paths = list(PdfFtb3532.get_mapping(year).values())
                self.assertEqual(len(paths), len(TEXT_LABELS))
                self.assertEqual(len(paths), len(set(paths)))

    def test_required_text_keys_are_the_always_answered_lines(self):
        # Header x2, line 3 x4, lines 4 and 5: answered on every branch.
        # The 1f periods are branch-only, so they are not in this set.
        self.assertEqual(set(REQUIRED_TEXT_KEYS), set(ALWAYS_ANSWERED_TEXT_KEYS))
        for year in YEARS:
            with self.subTest(year=year):
                self.assertLessEqual(set(REQUIRED_TEXT_KEYS),
                                     set(PdfFtb3532.get_mapping(year)))


class Ftb3532OptionGeometryTests(unittest.TestCase):
    """The widget each enum value turns ON sits on its printed label's row
    (and no other label's), and the 3a/3b True/False widgets sit immediately
    left of the printed Yes/No."""

    def _assert_on_label_row(self, year, values, labels, expected):
        payload = _resolve(year, values)
        rows = _label_rows(_template(year), labels.values())
        on = [w for w in _on_widgets(year, payload)
              if any(_v_overlap(w[2], r) > 0 for r in rows.values())]
        self.assertEqual(len(on), 1, on)
        _field, _state, rect = on[0]
        hits = sorted(lab for lab, r in rows.items() if _v_overlap(rect, r) > 0)
        self.assertEqual(hits, [expected])

    def test_part_one_selection_sits_on_its_label_row(self):
        for year in YEARS:
            for status, label in MARITAL_LABEL.items():
                with self.subTest(year=year, status=status):
                    self._assert_on_label_row(
                        year, {"ftb3532_marital_status": status},
                        MARITAL_LABEL, label)

    def test_part_two_selection_sits_on_its_label_row(self):
        for year in YEARS:
            for rel, label in RELATIONSHIP_LABEL.items():
                with self.subTest(year=year, relationship=rel):
                    self._assert_on_label_row(
                        year, {"ftb3532_relationship": rel},
                        RELATIONSHIP_LABEL, label)

    def _word_right_of(self, words, rect) -> tuple[str, float]:
        """The nearest word on the widget's row whose left edge is at or right
        of the widget's right edge, and the gap to it."""
        cands = [(x0 - rect[2], text) for text, x0, y0, _x1, y1 in words
                 if x0 >= rect[2] - 0.5 and _v_overlap(rect, (y0, y1)) > 0]
        gap, text = min(cands)
        return text, gap

    def test_yes_no_answers_sit_left_of_their_printed_words(self):
        for year in YEARS:
            words = _words(_template(year))
            fields = PdfReader(str(_template(year))).get_fields()
            for key, line in (("ftb3532_line_3a", "Line 3a"),
                              ("ftb3532_line_3b", "Line 3b")):
                fields_for_key = set()
                for answer, word in ((True, "Yes"), (False, "No")):
                    with self.subTest(year=year, key=key, answer=answer):
                        payload = _resolve(year, {key: answer})
                        on = _on_widgets(year, payload)
                        self.assertEqual(len(on), 1, on)
                        field, _state, rect = on[0]
                        fields_for_key.add(field)
                        self.assertIn(line, str(fields[field].get("/TU", "")))
                        text, gap = self._word_right_of(words, rect)
                        self.assertEqual(text, word)
                        self.assertLess(gap, 12)
                with self.subTest(year=year, key=key, check="one group"):
                    self.assertEqual(len(fields_for_key), 1)

    def test_3a_and_3b_are_different_groups_on_different_rows(self):
        for year in YEARS:
            with self.subTest(year=year):
                a = _on_widgets(year, _resolve(year, {"ftb3532_line_3a": True}))
                b = _on_widgets(year, _resolve(year, {"ftb3532_line_3b": True}))
                self.assertNotEqual(a[0][0], b[0][0])
                # 3a prints above 3b.
                self.assertGreater(a[0][2][1], b[0][2][3])


class Ftb3532ExactlyOneOnTests(unittest.TestCase):
    """After a real fill, exactly one widget per part is ON (with visible ink)
    and every other button on the page is /Off — the 2021-2024 checkbox sets
    and the 2025 radio groups alike."""

    def test_exactly_one_widget_per_part_is_on_after_fill(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            marital_rows = _label_rows(_template(year), MARITAL_LABEL.values())
            rel_rows = _label_rows(_template(year), RELATIONSHIP_LABEL.values())
            cases = [(m, "child_or_stepchild") for m in MARITAL_LABEL]
            cases += [("unmarried", r) for r in RELATIONSHIP_LABEL]
            for status, rel in cases:
                with self.subTest(year=year, status=status, relationship=rel):
                    out = _fill(year, {"ftb3532_marital_status": status,
                                       "ftb3532_relationship": rel},
                                tmp / f"f3532_{year}_{status}_{rel}.pdf")
                    on = list(checked_widgets(out))
                    self.assertEqual(len(on), 2, on)
                    part1 = [w for w in on if any(
                        _v_overlap(w[2], r) > 0 for r in marital_rows.values())]
                    part2 = [w for w in on if any(
                        _v_overlap(w[2], r) > 0 for r in rel_rows.values())]
                    self.assertEqual(len(part1), 1)
                    self.assertEqual(len(part2), 1)
                    self.assertGreater(_v_overlap(
                        part1[0][2], marital_rows[MARITAL_LABEL[status]]), 0)
                    self.assertGreater(_v_overlap(
                        part2[0][2], rel_rows[RELATIONSHIP_LABEL[rel]]), 0)
                    for page, _name, rect, _state in on:
                        self.assertGreater(
                            dark_pixels_in_rect(out, page, rect, inset=2.0), 8)

    def test_unknown_enum_value_refuses_rather_than_leaving_part_blank(self):
        for year in YEARS:
            for key in ("ftb3532_marital_status", "ftb3532_relationship"):
                with self.subTest(year=year, key=key):
                    with self.assertRaises(ValueError):
                        _resolve(year, {key: "not_a_member"})


class Ftb3532InkTests(unittest.TestCase):
    """Every text key, filled with a synthetic value, reads back as /V and
    prints ink inside its own widget."""

    def test_every_text_key_reads_back_and_prints_ink(self):
        tmp = Path(tempfile.mkdtemp())
        for year in YEARS:
            mapping = PdfFtb3532.get_mapping(year)
            out = _fill(year, dict(TEXT_VALUES), tmp / f"f3532_{year}_ink.pdf")
            read = {n: str(f.get("/V") or "")
                    for n, f in PdfReader(str(out)).get_fields().items()}
            for key, value in TEXT_VALUES.items():
                with self.subTest(year=year, key=key):
                    self.assertEqual(read[mapping[key]], str(value))
                    page, rect = widget_rect(out, mapping[key])
                    self.assertGreater(
                        dark_pixels_in_rect(out, page, rect, inset=1.0), 8)


class Ftb3532Under19Tests(unittest.TestCase):
    """Under 19 the form says "go to line 4": with no 3a/3b keys the mapping
    writes nothing to either radio, and after a fill both stay /Off."""

    def test_absent_3a_3b_keys_leave_both_radios_off(self):
        tmp = Path(tempfile.mkdtemp())
        values = dict(TEXT_VALUES, ftb3532_marital_status="unmarried",
                      ftb3532_relationship="child_or_stepchild")
        words = _words(_template(2021))
        yes_no_rows = [(y0, y1) for t, _x0, y0, _x1, y1 in words
                       if t in ("Yes", "No")]
        self.assertEqual(len(yes_no_rows), 4)
        for year in YEARS:
            with self.subTest(year=year):
                payload = _resolve(year, values)
                on = _on_widgets(year, payload)
                self.assertEqual(len(on), 2, on)  # Part I + Part II only
                out = _fill(year, values, tmp / f"f3532_{year}_u19.pdf")
                filled = list(checked_widgets(out))
                self.assertEqual(len(filled), 2, filled)
                for _p, _n, rect, _s in filled:
                    for row in yes_no_rows:
                        self.assertLessEqual(_v_overlap(rect, row), 0)

    def test_present_3a_3b_keys_turn_one_widget_on_each(self):
        for year in YEARS:
            with self.subTest(year=year):
                payload = _resolve(year, {"ftb3532_line_3a": True,
                                          "ftb3532_line_3b": False})
                self.assertEqual(len(_on_widgets(year, payload)), 2)


class Ftb3532RequiredFieldsTests(unittest.TestCase):
    """required_pdf_fields is branch-aware and fail-closed: the 3a/3b answers
    are required whenever the DOB puts the qualifying person at 19+ in the
    tax year (the form's own skip rule), the first period whenever Part I is
    1f, and a complete payload always covers the required set."""

    def _base(self, year: int, **over) -> dict:
        values = {k: v for k, v in TEXT_VALUES.items()
                  if not k.startswith("ftb3532_period_")}
        values.update(ftb3532_marital_status="unmarried",
                      ftb3532_relationship="child_or_stepchild",
                      ftb3532_qp_dob=f"03/07/{year - 10}")
        values.update(over)
        return values

    def _radio_fields(self, year, key) -> set[str]:
        return {f for f, _s, _r in _on_widgets(
            year, _resolve(year, {key: True}))}

    def test_complete_under_19_payload_covers_the_required_set(self):
        for year in YEARS:
            with self.subTest(year=year):
                values = self._base(year)
                required = PdfFtb3532.required_pdf_fields(values, year)
                mapping = PdfFtb3532.get_mapping(year)
                self.assertLessEqual(
                    {mapping[k] for k in REQUIRED_TEXT_KEYS}, required)
                # One Part I and one Part II cell are required as well.
                on = _on_widgets(year, _resolve(year, values))
                self.assertLessEqual({f for f, _s, _r in on}, required)
                self.assertEqual(len(on), 2)
                self.assertLessEqual(required, set(_resolve(year, values)))
                for key in ("ftb3532_line_3a", "ftb3532_line_3b"):
                    self.assertFalse(required & self._radio_fields(year, key))

    def test_19_or_older_requires_both_answers(self):
        for year in YEARS:
            with self.subTest(year=year):
                values = self._base(year, ftb3532_qp_dob=f"03/07/{year - 19}")
                required = PdfFtb3532.required_pdf_fields(values, year)
                for key in ("ftb3532_line_3a", "ftb3532_line_3b"):
                    self.assertLessEqual(self._radio_fields(year, key), required)
                self.assertFalse(required <= set(_resolve(year, values)))
                values.update(ftb3532_line_3a=True, ftb3532_line_3b=False)
                self.assertLessEqual(required, set(_resolve(year, values)))

    def test_18_does_not_require_answers(self):
        for year in YEARS:
            with self.subTest(year=year):
                values = self._base(year, ftb3532_qp_dob=f"12/31/{year - 18}")
                required = PdfFtb3532.required_pdf_fields(values, year)
                self.assertIn(PdfFtb3532.get_mapping(year)["ftb3532_qp_dob"],
                              required)
                self.assertLessEqual(required, set(_resolve(year, values)))

    def test_lived_together_requires_the_first_period(self):
        for year in YEARS:
            with self.subTest(year=year):
                mapping = PdfFtb3532.get_mapping(year)
                values = self._base(
                    year,
                    ftb3532_marital_status="married_lived_together_part_of_year")
                required = PdfFtb3532.required_pdf_fields(values, year)
                self.assertIn(mapping["ftb3532_period_1_from"], required)
                self.assertIn(mapping["ftb3532_period_1_to"], required)
                self.assertNotIn(mapping["ftb3532_period_2_from"], required)
                values.update(ftb3532_period_2_from="03/01/2020")
                required = PdfFtb3532.required_pdf_fields(values, year)
                self.assertIn(mapping["ftb3532_period_2_to"], required)

    def test_dropping_a_required_key_leaves_its_field_missing(self):
        for year in YEARS:
            for key in ALWAYS_ANSWERED_TEXT_KEYS:
                with self.subTest(year=year, key=key):
                    values = self._base(year)
                    del values[key]
                    required = PdfFtb3532.required_pdf_fields(values, year)
                    missing = required - set(_resolve(year, values))
                    self.assertIn(PdfFtb3532.get_mapping(year)[key], missing)

    def test_missing_part_selection_leaves_part_fields_missing(self):
        for year in YEARS:
            for key in ("ftb3532_marital_status", "ftb3532_relationship"):
                with self.subTest(year=year, key=key):
                    values = self._base(year)
                    del values[key]
                    required = PdfFtb3532.required_pdf_fields(values, year)
                    self.assertTrue(required - set(_resolve(year, values)))
