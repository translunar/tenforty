"""Form 4562 under the mid-quarter convention: the convention column.

A personal-property row prints "MQ" in column (e) when the return year's
cohort trips the 40% test, "HY" otherwise; real property stays "MM".

The widget paths below are LITERALS read off each year's template (the
row's widgets enumerated left to right, the printed column headers located
on the page), not derived from the mapping under test. Amounts under the
mid-quarter convention use the sentinel tables of tests/test_mid_quarter_
engine: this module pins the column, not the percentages.
"""

import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f4562 as form_f4562
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.models import DepreciableAsset, RentalProperty
from tenforty.rounding import irs_round
from tests.helpers import make_simple_scenario
from tests.test_mid_quarter_engine import _patched, _sentinel

REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2021, 2022, 2023, 2024, 2025)
PERSONAL_ROWS = ("a", "b", "c", "d", "e", "f")
_SB = "topmostSubform[0].Page1[0].SectionBTable[0]"

# Column (e) "Convention", rows 19a-19f. 2021-2024 share one Section B
# widget tree; 2025 renumbered it.
_CONVENTION_2021_2024 = {
    "a": f"{_SB}.Line19a[0].f1_28[0]",
    "b": f"{_SB}.Line19b[0].f1_33[0]",
    "c": f"{_SB}.Line19c[0].f1_38[0]",
    "d": f"{_SB}.Line19d[0].f1_43[0]",
    "e": f"{_SB}.Line19e[0].f1_48[0]",
    "f": f"{_SB}.Line19f[0].f1_53[0]",
}
CONVENTION_WIDGETS = {
    2021: _CONVENTION_2021_2024,
    2022: _CONVENTION_2021_2024,
    2023: _CONVENTION_2021_2024,
    2024: _CONVENTION_2021_2024,
    2025: {
        "a": f"{_SB}.Line19a[0].f1_29[0]",
        "b": f"{_SB}.Line19b[0].f1_35[0]",
        "c": f"{_SB}.Line19c[0].f1_41[0]",
        "d": f"{_SB}.Line19d[0].f1_47[0]",
        "e": f"{_SB}.Line19e[0].f1_53[0]",
        "f": f"{_SB}.Line19f[0].f1_59[0]",
    },
}

# Rows 19a-19f on the 2022-2024 layouts, every mapped column, left to right:
# (b) date, (c) basis, (d) recovery period, (e) convention, (g) deduction.
# Column (f) Method has a widget on these years that no mapping fills.
_ROWS_2022_2024 = {
    "a": ("Line19a", "R4", 26, 27, 28, 30),
    "b": ("Line19b", "R5", 31, 32, 33, 35),
    "c": ("Line19c", "R6", 36, 37, 38, 40),
    "d": ("Line19d", "R7", 41, 42, 43, 45),
    "e": ("Line19e", "R8", 46, 47, 48, 50),
    "f": ("Line19f", "R9", 51, 52, 53, 55),
}
_COLUMNS_2022_2024 = (
    "date_placed_in_service", "basis", "recovery_period", "convention",
    "deduction")


def _template(year: int) -> Path:
    return REPO_ROOT / "pdfs" / "federal" / str(year) / "f4562.pdf"


def _row_widgets(year: int) -> dict[str, list[tuple[float, float, str]]]:
    """{row subform: [(x0, x1, full path)] left to right} for Section B."""
    rows: dict[str, list] = {}
    page = PdfReader(str(_template(year))).pages[0]
    for annotation in page.get("/Annots", []):
        widget = annotation.get_object()
        if widget.get("/Subtype") != "/Widget":
            continue
        names, node = [], widget
        while node is not None:
            if "/T" in node:
                names.append(str(node["/T"]))
            parent = node.get("/Parent")
            node = parent.get_object() if parent is not None else None
        path = ".".join(reversed(names))
        if not path.startswith(_SB + "."):
            continue
        rect = widget["/Rect"]
        rows.setdefault(names[1], []).append(
            (float(rect[0]), float(rect[2]), path))
    return {row: sorted(widgets) for row, widgets in rows.items()}


def _header_x(year: int, word: str) -> float:
    """The x position of a column-header word printed on page 1."""
    found = []

    def visit(text, _cm, tm, _font, _size):
        if text.strip() == word:
            found.append(float(tm[4]))

    PdfReader(str(_template(year))).pages[0].extract_text(visitor_text=visit)
    assert len(found) == 1, f"{year}: {word!r} found {len(found)} times"
    return found[0]


def _asset(description, recovery_class, month, basis, year):
    return DepreciableAsset(
        description=description, date_placed_in_service=date(year, month, 15),
        basis=basis, recovery_class=recovery_class,
        no_bonus_or_section_179_history=(
            None if recovery_class.startswith(("27.5", "39")) else True))


def _scenario(year: int, *assets):
    s = make_simple_scenario()
    s.config.first_name = "Round"
    s.config.last_name = "Trip"
    s.config.ssn = "000-00-0000"
    s.config.year = year
    s.acknowledges_no_listed_property = True
    s.rental_properties = [RentalProperty(
        address="100 Example Street", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=0.0,
        depreciable_assets=list(assets))]
    return s


def _tripped(year: int):
    """5-year in February (first quarter), 7-year in November (fourth
    quarter): 9,000 of 10,000 in the last three months."""
    return _scenario(
        year,
        _asset("Laptop", "5-year", 2, 1_000.0, year),
        _asset("Desk", "7-year", 11, 9_000.0, year))


def _untripped(year: int):
    """The same two assets with the late one at exactly 40%."""
    return _scenario(
        year,
        _asset("Laptop", "5-year", 2, 6_000.0, year),
        _asset("Desk", "7-year", 11, 4_000.0, year))


def _filled_fields(year: int, values: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "f4562.pdf"
        PdfFiller().fill_with_repeaters(
            template_path=_template(year), output_path=out,
            mapping=Pdf4562.get_mapping(year), values=values)
        return {name: field.get("/V")
                for name, field in PdfReader(str(out)).get_fields().items()}


class ConventionColumnWidgetTests(unittest.TestCase):
    def test_mapping_points_at_the_literal_widget(self):
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    self.assertEqual(
                        scalars[f"f4562_line_19{row}_convention"],
                        CONVENTION_WIDGETS[year][row])

    def test_literal_widget_sits_under_the_convention_header(self):
        """Independent of the mapping: the literal is the row's widget
        under the printed "Convention" header and not the one under
        "Method"."""
        for year in YEARS:
            convention_x = _header_x(year, "Convention")
            method_x = _header_x(year, "Method")
            rows = _row_widgets(year)
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    spans = {path: (x0, x1)
                             for x0, x1, path in rows[f"Line19{row}[0]"]}
                    x0, x1 = spans[CONVENTION_WIDGETS[year][row]]
                    self.assertTrue(x0 <= convention_x <= x1)
                    self.assertFalse(x0 <= method_x <= x1)

    def test_every_personal_row_has_six_widgets(self):
        """(b) through (g): what the left-to-right pins below count on."""
        for year in YEARS:
            rows = _row_widgets(year)
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    self.assertEqual(len(rows[f"Line19{row}[0]"]), 6)


class PersonalRowColumnOrderTests(unittest.TestCase):
    """Every mapped cell of a personal-property row lands in its own
    column: the mapped widgets are the row's widgets in left-to-right
    order, (f) Method skipped where the year's mapping has no such key."""

    def test_2022_through_2024_literal_paths(self):
        for year in (2022, 2023, 2024):
            scalars = Pdf4562.get_mapping(year)["scalars"]
            for row, (subform, date_widget, *numbers) in (
                    _ROWS_2022_2024.items()):
                literals = [f"{_SB}.{subform}[0].{date_widget}[0]"] + [
                    f"{_SB}.{subform}[0].f1_{n}[0]" for n in numbers]
                for column, literal in zip(_COLUMNS_2022_2024, literals):
                    with self.subTest(year=year, row=row, column=column):
                        self.assertEqual(
                            scalars[f"f4562_line_19{row}_{column}"], literal)

    def test_mapped_cells_are_the_row_widgets_left_to_right(self):
        columns = ("date_placed_in_service", "basis", "recovery_period",
                   "convention", "method", "deduction")
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            rows = _row_widgets(year)
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    on_page = [path for _x0, _x1, path
                               in rows[f"Line19{row}[0]"]]
                    mapped = [
                        scalars.get(f"f4562_line_19{row}_{column}")
                        for column in columns]
                    for position, path in enumerate(mapped):
                        if path is None:
                            self.assertEqual(columns[position], "method")
                            continue
                        self.assertEqual(path, on_page[position])


class ComputeTests(unittest.TestCase):
    def test_tripped_year_rows_are_mid_quarter(self):
        with _patched():
            result = form_f4562.compute(_tripped(2025), upstream={})
        laptop = irs_round(1_000.0 * _sentinel(1, 5, 1))
        desk = irs_round(9_000.0 * _sentinel(4, 7, 1))
        self.assertEqual(result["f4562_line_19b_convention"], "MQ")
        self.assertEqual(result["f4562_line_19c_convention"], "MQ")
        self.assertEqual(result["f4562_line_19b_deduction"], laptop)
        self.assertEqual(result["f4562_line_19c_deduction"], desk)
        self.assertEqual(
            result["f4562_line_22_total_depreciation"], laptop + desk)
        self.assertEqual(
            [row["convention"]
             for row in result["f4562_part_iii_section_b_rows"]],
            ["mid-quarter", "mid-quarter"])

    def test_untripped_twin_is_half_year(self):
        result = form_f4562.compute(_untripped(2025), upstream={})
        self.assertEqual(result["f4562_line_19b_convention"], "HY")
        self.assertEqual(result["f4562_line_19c_convention"], "HY")
        self.assertEqual(result["f4562_line_19b_deduction"], 1_200)

    def test_same_class_assets_in_different_quarters_sum_in_one_row(self):
        scenario = _scenario(
            2025,
            _asset("Laptop", "5-year", 2, 1_000.0, 2025),
            _asset("Printer", "5-year", 8, 1_000.0, 2025),
            _asset("Server", "5-year", 12, 8_000.0, 2025))
        with _patched():
            result = form_f4562.compute(scenario, upstream={})
        self.assertEqual(result["f4562_line_19b_convention"], "MQ")
        self.assertEqual(
            result["f4562_line_19b_deduction"],
            irs_round(1_000.0 * _sentinel(1, 5, 1))
            + irs_round(1_000.0 * _sentinel(3, 5, 1))
            + irs_round(8_000.0 * _sentinel(4, 5, 1)))

    def test_real_property_row_stays_mid_month_in_a_tripped_year(self):
        scenario = _tripped(2025)
        scenario.rental_properties[0].depreciable_assets.append(
            _asset("Building", "27.5-year", 12, 200_000.0, 2025))
        with _patched():
            result = form_f4562.compute(scenario, upstream={})
        self.assertEqual(result["f4562_line_19i_convention"], "MM")
        self.assertEqual(result["f4562_line_19b_convention"], "MQ")


class FilledFormTests(unittest.TestCase):
    def test_convention_code_prints_in_the_convention_column(self):
        for year in YEARS:
            with _patched():
                tripped = form_f4562.compute(_tripped(year), upstream={})
            untripped = form_f4562.compute(_untripped(year), upstream={})
            mq = _filled_fields(year, tripped)
            hy = _filled_fields(year, untripped)
            for row in ("b", "c"):
                with self.subTest(year=year, row=row):
                    widget = CONVENTION_WIDGETS[year][row]
                    self.assertEqual(mq[widget], "MQ")
                    self.assertEqual(hy[widget], "HY")
            for row in ("a", "d", "e", "f"):
                with self.subTest(year=year, row=row, state="empty"):
                    self.assertIn(mq[CONVENTION_WIDGETS[year][row]], (None, ""))


if __name__ == "__main__":
    unittest.main()
