"""Form 4562 in a mid-stream placement year: line 17 vs line 19, and line 22.

Two defects this module pins shut:

1. Prior-year assets printed on line 19. Section B (line 19) is headed
   "Assets Placed in Service During {year} Tax Year"; line 17 reads "MACRS
   deductions for assets placed in service in tax years beginning before
   {year}". The form used to bucket EVERY asset on the return into its line
   19 class row, so a building placed years ago printed as a current
   placement, under the earliest in-service date and with the bases summed.
   Line 17 was never filled.

2. Line 22 on the wrong widget, 2022-2024. Those years' mapping sent the
   total to a page 2 widget that sits on line 25 (special depreciation
   allowance for listed property). The printed line 22 is on page 1.

Every field path here is a literal, anchored to the blank template by
`TemplateAnchorTests` (printed line number AND the words printed beside the
widget) -- never read from mappings/pdf_4562.py.

Figures (hand-derived from Pub 946 Table A-6, 27.5-year, mid-month, and
Table A-1, 5-year, half-year):
  building, 200,000, placed June 2019 -> recovery years 3..7 in 2021..2025,
      3.636% each: 7,272
  roof, 30,000, placed March of the return year -> year 1, month 3,
      2.879%: 864 (863.70)
  equipment, 10,000, placed the year before the return year -> year 2,
      32.00%: 3,200
"""

import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.forms import f4562
from tenforty.forms.depreciation.resolver import (
    reconstruct_prior_depreciation, resolve,
)
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.models import DepreciableAsset, RentalProperty
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, SPREADSHEETS_DIR, make_simple_scenario
from tests.test_f4562_emit_gate import (
    _left_margin_line_numbers, _line_number_of, _page_widgets,
)

YEARS = (2021, 2022, 2023, 2024, 2025)

LINE_17 = {
    2021: "topmostSubform[0].Page1[0].f1_25[0]",
    2022: "topmostSubform[0].Page1[0].f1_25[0]",
    2023: "topmostSubform[0].Page1[0].f1_25[0]",
    2024: "topmostSubform[0].Page1[0].f1_25[0]",
    2025: "topmostSubform[0].Page1[0].f1_25[0]",
}
LINE_22 = {
    2021: "topmostSubform[0].Page1[0].f1_108[0]",
    2022: "topmostSubform[0].Page1[0].f1_108[0]",
    2023: "topmostSubform[0].Page1[0].f1_108[0]",
    2024: "topmostSubform[0].Page1[0].f1_108[0]",
    2025: "topmostSubform[0].Page2[0].f2_2[0]",
}
# Where the 2022-2024 mapping used to send line 22: the line 25 box.
LINE_25_2022_TO_2024 = "topmostSubform[0].Page2[0].f2_1[0]"
# The residential-rental (27.5-year) Section B row: (b) date, (c) basis,
# (g) deduction.
_SB = "topmostSubform[0].Page1[0].SectionBTable[0]"
RESIDENTIAL_ROW = {
    **{year: {
        "date": f"{_SB}.Line19h_1[0].f1_61[0]",
        "basis": f"{_SB}.Line19h_1[0].f1_62[0]",
        "deduction": f"{_SB}.Line19h_1[0].f1_66[0]",
    } for year in (2021, 2022, 2023, 2024)},
    2025: {
        "date": f"{_SB}.Line19i_1[0].f1_74[0]",
        "basis": f"{_SB}.Line19i_1[0].f1_75[0]",
        "deduction": f"{_SB}.Line19i_1[0].f1_79[0]",
    },
}
SCH_E_LINE_18_PROPERTY_A = (
    "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]")

BUILDING_AMOUNT = 7_272
ROOF_AMOUNT = 864
EQUIPMENT_AMOUNT = 3_200


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f4562.pdf"


def _old_building(year: int) -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Rental building", date_placed_in_service=date(2019, 6, 1),
        basis=200_000.0, recovery_class="27.5-year")
    asset.prior_depreciation = float(
        reconstruct_prior_depreciation(asset, year))
    return asset


def _new_roof(year: int) -> DepreciableAsset:
    return DepreciableAsset(
        description="Roof", date_placed_in_service=date(year, 3, 10),
        basis=30_000.0, recovery_class="27.5-year")


def _last_years_equipment(year: int) -> DepreciableAsset:
    asset = DepreciableAsset(
        description="Equipment", date_placed_in_service=date(year - 1, 5, 1),
        basis=10_000.0, recovery_class="5-year",
        no_bonus_or_section_179_history=True)
    asset.prior_depreciation = float(
        reconstruct_prior_depreciation(asset, year))
    return asset


def _rental(*assets) -> RentalProperty:
    return RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        depreciable_assets=list(assets))


def _scenario(year: int, *assets):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, first_name="Test", last_name="Filer",
        ssn="000-00-0000", acknowledges_no_source_documents=True)
    return dataclasses.replace(
        base, config=config, rental_properties=[_rental(*assets)],
        acknowledges_no_listed_property=True)


class PriorAssetsGoOnLine17Tests(unittest.TestCase):
    def test_prior_building_is_line_17_and_the_roof_alone_is_line_19(self):
        for year in YEARS:
            with self.subTest(year=year):
                s = _scenario(year, _old_building(year), _new_roof(year))
                r = f4562.compute(s, upstream={})
                self.assertEqual(r["f4562_line_17"], BUILDING_AMOUNT)
                self.assertEqual(
                    r["f4562_line_19i_date_placed_in_service"],
                    f"03/{year}")
                self.assertEqual(r["f4562_line_19i_basis"], 30_000)
                self.assertEqual(r["f4562_line_19i_deduction"], ROOF_AMOUNT)
                rows = r["f4562_part_iii_section_b_rows"]
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["basis"], 30_000.0)
                self.assertEqual(
                    rows[0]["date_placed_in_service"], date(year, 3, 10))
                self.assertEqual(
                    r["f4562_line_22_total_depreciation"],
                    BUILDING_AMOUNT + ROOF_AMOUNT)

    def test_a_class_with_only_prior_assets_gets_no_line_19_row(self):
        for year in YEARS:
            with self.subTest(year=year):
                s = _scenario(
                    year, _last_years_equipment(year), _new_roof(year))
                r = f4562.compute(s, upstream={})
                self.assertEqual(r["f4562_line_17"], EQUIPMENT_AMOUNT)
                self.assertEqual(
                    [k for k in r if k.startswith("f4562_line_19b")], [])
                self.assertEqual(
                    [row["row_label"]
                     for row in r["f4562_part_iii_section_b_rows"]], ["i"])
                self.assertEqual(r["f4562_line_19i_deduction"], ROOF_AMOUNT)
                self.assertEqual(
                    r["f4562_line_22_total_depreciation"],
                    EQUIPMENT_AMOUNT + ROOF_AMOUNT)

    def test_line_22_is_line_17_plus_line_19_and_what_the_activity_claims(
            self):
        for year in YEARS:
            with self.subTest(year=year):
                s = _scenario(
                    year, _old_building(year), _last_years_equipment(year),
                    _new_roof(year))
                r = f4562.compute(s, upstream={})
                line_19 = sum(
                    row["deduction"]
                    for row in r["f4562_part_iii_section_b_rows"])
                self.assertEqual(
                    r["f4562_line_17"], BUILDING_AMOUNT + EQUIPMENT_AMOUNT)
                self.assertEqual(line_19, ROOF_AMOUNT)
                self.assertEqual(
                    r["f4562_line_22_total_depreciation"],
                    r["f4562_line_17"] + line_19)
                self.assertEqual(
                    r["f4562_line_22_total_depreciation"],
                    resolve(s.rental_properties[0], year).amount)

    def test_line_17_uses_the_resolvers_figure_under_the_basis_ceiling(self):
        """An acknowledged prior history that ran ahead of the tables caps
        the year's deduction at the remaining basis; line 17 prints that
        capped figure, not the table's."""
        year = 2025
        building = _old_building(year)
        building.prior_depreciation = 199_000.0
        building.acknowledges_prior_depreciation_as_stated = True
        s = _scenario(year, building, _new_roof(year))
        r = f4562.compute(s, upstream={})
        self.assertEqual(r["f4562_line_17"], 1_000)
        self.assertEqual(
            r["f4562_line_22_total_depreciation"], 1_000 + ROOF_AMOUNT)
        self.assertEqual(
            r["f4562_line_22_total_depreciation"],
            resolve(s.rental_properties[0], year).amount)

    def test_no_prior_assets_prints_no_line_17(self):
        """The twin: with every asset placed this year there is no line 17
        key at all (no phantom zero), and line 22 is line 19 alone."""
        for year in YEARS:
            with self.subTest(year=year):
                r = f4562.compute(
                    _scenario(year, _new_roof(year)), upstream={})
                self.assertNotIn("f4562_line_17", r)
                self.assertEqual(
                    r["f4562_line_22_total_depreciation"], ROOF_AMOUNT)


def _printed_line_widgets(year: int) -> dict[str, list[str]]:
    """{printed line number: [field names]} over EVERY page of the blank
    template (the Part IV summary moved to page 2 in 2025)."""
    found: dict[str, list[str]] = {}
    for page in PdfReader(str(_template(year))).pages:
        labels = _left_margin_line_numbers(page)
        for row_y, _left, name in _page_widgets(page):
            number = _line_number_of(row_y, labels)
            if number is not None:
                found.setdefault(number, []).append(name)
    return found


def _text_beside(year: int, field_name: str) -> str:
    """The words printed within a wrapped line's reach of a widget's row."""
    for page in PdfReader(str(_template(year))).pages:
        rows = [y for y, _x, name in _page_widgets(page) if name == field_name]
        if not rows:
            continue
        fragments = []

        def visit(text, cm, tm, _font_dict, _font_size, row_y=rows[0]):
            text = text.strip()
            y = tm[5] + cm[5]
            if text and abs(y - row_y) <= 14:
                fragments.append((-y, tm[4] + cm[4], text))

        page.extract_text(visitor_text=visit)
        return " ".join(text for _y, _x, text in sorted(fragments))
    raise AssertionError(f"{field_name} is not a widget of the {year} form")


class TemplateAnchorTests(unittest.TestCase):
    """The line 17 and line 22 literals are what each year's blank template
    puts on the lines printed "17" and "22"."""

    def test_line_22_literal_is_the_one_widget_on_printed_line_22(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_line = _printed_line_widgets(year)
                self.assertIn("22", by_line, sorted(by_line))
                self.assertEqual(by_line["22"], [LINE_22[year]])
                self.assertNotIn(LINE_22[year], by_line["21"])

    def test_line_17_literal_is_the_one_widget_on_printed_line_17(self):
        for year in YEARS:
            with self.subTest(year=year):
                by_line = _printed_line_widgets(year)
                self.assertIn("17", by_line, sorted(by_line))
                self.assertEqual(by_line["17"], [LINE_17[year]])
                self.assertNotIn(LINE_17[year], by_line["16"])
                self.assertNotIn(LINE_17[year], by_line["18"])

    def test_the_words_beside_each_literal_are_that_lines_words(self):
        for year in YEARS:
            with self.subTest(year=year, line=17):
                self.assertIn(
                    "MACRS deductions for assets placed in service in tax "
                    f"years beginning before {year}",
                    _text_beside(year, LINE_17[year]))
            with self.subTest(year=year, line=22):
                beside = _text_beside(year, LINE_22[year])
                self.assertIn("22 Total.", beside)
                self.assertIn("Add amounts from line 12", beside)

    def test_the_old_2022_to_2024_target_is_line_25(self):
        for year in (2022, 2023, 2024):
            with self.subTest(year=year):
                self.assertEqual(
                    _printed_line_widgets(year)["25"],
                    [LINE_25_2022_TO_2024])
                self.assertIn(
                    "Special depreciation allowance for qualified listed "
                    "property",
                    _text_beside(year, LINE_25_2022_TO_2024))

    def test_a_missing_label_is_a_failure_not_a_pass(self):
        """With a line's label withheld, its widget is attributed to some
        other line or to none -- the anchor's assertEqual then fails."""
        for year in YEARS:
            for number, literal in (("17", LINE_17), ("22", LINE_22)):
                with self.subTest(year=year, line=number):
                    attributed = None
                    for page in PdfReader(str(_template(year))).pages:
                        labels = [
                            (y, n) for y, n in _left_margin_line_numbers(page)
                            if n != number]
                        for row_y, _left, name in _page_widgets(page):
                            if name == literal[year]:
                                attributed = _line_number_of(row_y, labels)
                    self.assertNotEqual(attributed, number)


class MappingTests(unittest.TestCase):
    def test_line_17_and_line_22_map_to_the_anchored_literals(self):
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            with self.subTest(year=year, line=17):
                self.assertEqual(scalars.get("f4562_line_17"), LINE_17[year])
            with self.subTest(year=year, line=22):
                self.assertEqual(
                    scalars["f4562_line_22_total_depreciation"],
                    LINE_22[year])

    def test_nothing_maps_to_the_line_25_box(self):
        for year in (2022, 2023, 2024):
            with self.subTest(year=year):
                self.assertNotIn(
                    LINE_25_2022_TO_2024,
                    Pdf4562.get_mapping(year)["scalars"].values())

    def test_every_mapped_field_exists_on_every_years_template(self):
        for year in YEARS:
            fields = PdfReader(str(_template(year))).get_fields() or {}
            for key, path in Pdf4562.get_mapping(year)["scalars"].items():
                with self.subTest(year=year, key=key):
                    self.assertIn(path, fields)


def _read(pdf_path, field_path) -> str:
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "").replace(",", "").strip()


class EmittedFormTests(unittest.TestCase):
    """End to end through the orchestrator, every template year: what the
    emitted PDFs carry at the literal paths."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _emit(self, scenario) -> dict:
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.tmp / f"work{scenario.config.year}")
        results = orchestrator.compute_federal(scenario)
        return orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out{scenario.config.year}")

    def test_mid_stream_placement_year_prints_17_19_22_and_ties_to_sch_e(
            self):
        total = str(BUILDING_AMOUNT + ROOF_AMOUNT)
        for year in YEARS:
            with self.subTest(year=year):
                emitted = self._emit(
                    _scenario(year, _old_building(year), _new_roof(year)))
                form = emitted["f4562"]
                row = RESIDENTIAL_ROW[year]
                self.assertEqual(
                    _read(form, LINE_17[year]), str(BUILDING_AMOUNT))
                self.assertEqual(_read(form, row["date"]), f"03/{year}")
                self.assertEqual(_read(form, row["basis"]), "30000")
                self.assertEqual(
                    _read(form, row["deduction"]), str(ROOF_AMOUNT))
                self.assertEqual(_read(form, LINE_22[year]), total)
                self.assertEqual(
                    _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A), total)
                if year in (2022, 2023, 2024):
                    self.assertEqual(_read(form, LINE_25_2022_TO_2024), "")

    def test_placement_only_year_leaves_line_17_blank(self):
        """The twin: nothing placed earlier, so line 17 is empty and line
        22 is the line 19 amount."""
        for year in YEARS:
            with self.subTest(year=year):
                emitted = self._emit(_scenario(year, _new_roof(year)))
                form = emitted["f4562"]
                self.assertEqual(_read(form, LINE_17[year]), "")
                self.assertEqual(
                    _read(form, LINE_22[year]), str(ROOF_AMOUNT))
                self.assertEqual(
                    _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A),
                    str(ROOF_AMOUNT))


if __name__ == "__main__":
    unittest.main()
