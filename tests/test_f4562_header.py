"""Form 4562 header: which box the name, the activity and the SSN print in.

The header row has three boxes, left to right:

  Name(s) shown on return | Business or activity to which this form relates
  | Identifying number

The 2022-2025 mappings sent the SSN to the MIDDLE box, so it printed under
"Business or activity to which this form relates" and the identifying-number
box stayed empty. (2021 was already right.)

Every field path here is a literal, anchored to each year's blank template
by `TemplateAnchorTests` -- never read from mappings/pdf_4562.py.
"""

import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.models import DepreciableAsset, RentalProperty
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, SPREADSHEETS_DIR, make_simple_scenario

YEARS = (2021, 2022, 2023, 2024, 2025)

NAME_BOX = {
    2021: "topmostSubform[0].Page1[0].f1_1[0]",
    2022: "topmostSubform[0].Page1[0].f1_1[0]",
    2023: "topmostSubform[0].Page1[0].f1_1[0]",
    2024: "topmostSubform[0].Page1[0].f1_1[0]",
    2025: "topmostSubform[0].Page1[0].f1_1[0]",
}
ACTIVITY_BOX = {
    2021: "topmostSubform[0].Page1[0].f1_2[0]",
    2022: "topmostSubform[0].Page1[0].f1_2[0]",
    2023: "topmostSubform[0].Page1[0].f1_2[0]",
    2024: "topmostSubform[0].Page1[0].f1_2[0]",
    2025: "topmostSubform[0].Page1[0].f1_2[0]",
}
IDENTIFYING_NUMBER_BOX = {
    2021: "topmostSubform[0].Page1[0].f1_3[0]",
    2022: "topmostSubform[0].Page1[0].f1_3[0]",
    2023: "topmostSubform[0].Page1[0].f1_3[0]",
    2024: "topmostSubform[0].Page1[0].f1_3[0]",
    2025: "topmostSubform[0].Page1[0].f1_3[0]",
}

HEADER_LABELS = [
    "Name(s) shown on return",
    "Business or activity to which this form relates",
    "Identifying number",
]

FILER_NAME = "Test Filer"
FILER_SSN = "000-00-0000"


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f4562.pdf"


def _page_1_widgets(year: int) -> list[dict]:
    """Every widget on page 1 of the blank template: full name, rect and
    /MaxLen."""
    page = PdfReader(str(_template(year))).pages[0]
    widgets = []
    for annotation in page.get("/Annots", []):
        annotation = annotation.get_object()
        if annotation.get("/Subtype") != "/Widget":
            continue
        names, node = [], annotation
        while node is not None:
            if "/T" in node:
                names.append(node["/T"])
            node = node.get("/Parent")
            node = node.get_object() if node is not None else None
        left, bottom, right, top = (float(v) for v in annotation["/Rect"])
        widgets.append({
            "name": ".".join(reversed(names)), "left": left, "right": right,
            "bottom": bottom, "top": top,
            "max_len": annotation.get("/MaxLen")})
    return widgets


def _header_text_fragments(year: int) -> list[tuple[str, float, float]]:
    """``(text, x, y)`` for every text fragment on page 1, in the order the
    page prints them."""
    fragments = []

    def visit(text, cm, tm, _font_dict, _font_size):
        if text.strip():
            fragments.append((text.strip(), tm[4] + cm[4], tm[5] + cm[5]))

    PdfReader(str(_template(year))).pages[0].extract_text(visitor_text=visit)
    return fragments


def _header_row_widgets(
        year: int, first_label: str = HEADER_LABELS[0]) -> list[dict]:
    """The widgets on the row directly under the "Name(s) shown on return"
    label, left to right."""
    label = [(x, y) for text, x, y in _header_text_fragments(year)
             if text == first_label]
    if len(label) != 1:
        raise AssertionError(
            f"expected one {first_label!r} label on the {year} form; "
            f"found {label}")
    _x, label_y = label[0]
    row = [w for w in _page_1_widgets(year)
           if 0 <= label_y - w["top"] <= 6]
    return sorted(row, key=lambda w: w["left"])


class TemplateAnchorTests(unittest.TestCase):
    """What each blank template itself says the three header boxes are."""

    def test_the_three_labels_print_in_this_order(self):
        """The labels are consecutive fragments, in left-to-right order."""
        for year in YEARS:
            with self.subTest(year=year):
                texts = [t for t, _x, _y in _header_text_fragments(year)]
                self.assertIn(HEADER_LABELS[0], texts)
                start = texts.index(HEADER_LABELS[0])
                self.assertEqual(texts[start:start + 3], HEADER_LABELS)

    def test_the_header_row_is_three_boxes_and_they_are_the_literals(self):
        for year in YEARS:
            with self.subTest(year=year):
                row = _header_row_widgets(year)
                self.assertEqual(
                    [w["name"] for w in row],
                    [NAME_BOX[year], ACTIVITY_BOX[year],
                     IDENTIFYING_NUMBER_BOX[year]])
                # Side by side, not overlapping: left-to-right order is the
                # label order.
                for left_box, right_box in zip(row, row[1:]):
                    self.assertLessEqual(
                        left_box["right"], right_box["left"] + 1)

    def test_only_the_identifying_number_box_is_limited_to_an_ssns_length(
            self):
        """An independent reading: the box meant for the identifying number
        is the one the template caps at 11 characters (NNN-NN-NNNN)."""
        for year in YEARS:
            with self.subTest(year=year):
                by_name = {w["name"]: w for w in _header_row_widgets(year)}
                self.assertEqual(
                    by_name[IDENTIFYING_NUMBER_BOX[year]]["max_len"], 11)
                self.assertIsNone(by_name[ACTIVITY_BOX[year]]["max_len"])
                self.assertIsNone(by_name[NAME_BOX[year]]["max_len"])

    def test_a_missing_label_is_a_failure_not_a_pass(self):
        """The row probe raises when its label is not found."""
        for year in YEARS:
            with self.subTest(year=year):
                with self.assertRaisesRegex(AssertionError, "expected one"):
                    _header_row_widgets(year, first_label="No such label")


class MappingTests(unittest.TestCase):
    def test_ssn_maps_to_the_identifying_number_box(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    Pdf4562.get_mapping(year)["scalars"]["taxpayer_ssn"],
                    IDENTIFYING_NUMBER_BOX[year])

    def test_name_maps_to_the_name_box(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    Pdf4562.get_mapping(year)["scalars"]["taxpayer_name"],
                    NAME_BOX[year])


def _read(pdf_path, field_path) -> str:
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "").strip()


def _roof(year: int) -> DepreciableAsset:
    return DepreciableAsset(
        description="Roof", date_placed_in_service=date(year, 3, 10),
        basis=30_000.0, recovery_class="27.5-year")


def _rental(year: int, address: str = "100 Example Street") -> RentalProperty:
    return RentalProperty(
        address=address, property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=[_roof(year)])


def _scenario(year: int, rentals=None, businesses=()):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, first_name="Test", last_name="Filer",
        ssn=FILER_SSN, acknowledges_no_source_documents=True)
    return dataclasses.replace(
        base, config=config,
        rental_properties=[_rental(year)] if rentals is None else rentals,
        schedule_c_businesses=list(businesses),
        acknowledges_no_listed_property=True)


class _EmitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self._n = 0

    def _emit_4562(self, scenario) -> Path:
        self._n += 1
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.tmp / f"work{self._n}")
        results = orchestrator.compute_federal(scenario)
        emitted = orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out{self._n}")
        return emitted["f4562"]


class EmittedHeaderTests(_EmitCase):
    def test_ssn_prints_in_the_identifying_number_box_and_nowhere_else(self):
        for year in YEARS:
            with self.subTest(year=year):
                form = self._emit_4562(_scenario(year))
                self.assertEqual(
                    _read(form, IDENTIFYING_NUMBER_BOX[year]), FILER_SSN)
                self.assertEqual(_read(form, NAME_BOX[year]), FILER_NAME)
                self.assertNotIn(
                    FILER_SSN, _read(form, ACTIVITY_BOX[year]))
                carrying_ssn = [
                    name for name, field in
                    (PdfReader(str(form)).get_fields() or {}).items()
                    if FILER_SSN in str(field.get("/V") or "")]
                self.assertEqual(
                    carrying_ssn, [IDENTIFYING_NUMBER_BOX[year]])


if __name__ == "__main__":
    unittest.main()
