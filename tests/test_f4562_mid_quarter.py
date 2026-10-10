"""Form 4562 Section B rows 19a-19f: the convention and method columns,
and what a personal-property row does and does not print.

A personal-property row prints "MQ" in column (e) when the return year's
cohort trips the 40% test, "HY" otherwise; real property stays "MM". Column
(f) prints the class's method, spelled as the instructions spell it:
"200 DB" for 3-, 5-, 7- and 10-year property, "150 DB" for 15- and 20-year.
Column (b), month and year placed in service, is shaded on rows 19a-19f of
every year's form and is left empty there; it is filled only on the
residential and nonresidential rows.

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

# Rows 19a-19f, every column the row prints, as literal widget numbers:
# (subform, shaded (b) date widget -- never filled, (c) basis, (d) recovery
# period, (e) convention, (f) method, (g) deduction).
_ROWS_2021_2024 = {
    "a": ("Line19a", "R4", 26, 27, 28, 29, 30),
    "b": ("Line19b", "R5", 31, 32, 33, 34, 35),
    "c": ("Line19c", "R6", 36, 37, 38, 39, 40),
    "d": ("Line19d", "R7", 41, 42, 43, 44, 45),
    "e": ("Line19e", "R8", 46, 47, 48, 49, 50),
    "f": ("Line19f", "R9", 51, 52, 53, 54, 55),
}
_ROWS_2025 = {
    "a": ("Line19a", "f1_26", 27, 28, 29, 30, 31),
    "b": ("Line19b", "f1_32", 33, 34, 35, 36, 37),
    "c": ("Line19c", "f1_38", 39, 40, 41, 42, 43),
    "d": ("Line19d", "f1_44", 45, 46, 47, 48, 49),
    "e": ("Line19e", "f1_50", 51, 52, 53, 54, 55),
    "f": ("Line19f", "f1_56", 57, 58, 59, 60, 61),
}
ROWS = {2021: _ROWS_2021_2024, 2022: _ROWS_2021_2024, 2023: _ROWS_2021_2024,
        2024: _ROWS_2021_2024, 2025: _ROWS_2025}
PRINTED_COLUMNS = (
    "basis", "recovery_period", "convention", "method", "deduction")
# The one widget this return's filing depends on, spelled out in full: the
# 2025 template's 15-year row, column (f) Method.
METHOD_15_YEAR_2025 = f"{_SB}.Line19e[0].f1_54[0]"


def _literal(year: int, row: str, column: str) -> str:
    subform, _date_widget, *numbers = ROWS[year][row]
    number = numbers[PRINTED_COLUMNS.index(column)]
    return f"{_SB}.{subform}[0].f1_{number}[0]"


def _date_widget(year: int, row: str) -> str:
    subform, date_widget, *_numbers = ROWS[year][row]
    return f"{_SB}.{subform}[0].{date_widget}[0]"


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


class PersonalRowColumnTests(unittest.TestCase):
    """Every printed cell of a personal-property row lands in its own
    column, on every year's layout."""

    def test_literal_paths_for_every_printed_column(self):
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            for row in PERSONAL_ROWS:
                for column in PRINTED_COLUMNS:
                    with self.subTest(year=year, row=row, column=column):
                        self.assertEqual(
                            scalars[f"f4562_line_19{row}_{column}"],
                            _literal(year, row, column))

    def test_convention_literals_agree_with_the_row_literals(self):
        for year in YEARS:
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    self.assertEqual(
                        _literal(year, row, "convention"),
                        CONVENTION_WIDGETS[year][row])

    def test_literals_are_the_row_widgets_left_to_right(self):
        """Independent of the mapping: the literals above are the row's own
        six widgets in page order -- the shaded date cell first, then the
        five printed columns."""
        for year in YEARS:
            rows = _row_widgets(year)
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    on_page = [path for _x0, _x1, path
                               in rows[f"Line19{row}[0]"]]
                    self.assertEqual(
                        on_page,
                        [_date_widget(year, row)] + [
                            _literal(year, row, column)
                            for column in PRINTED_COLUMNS])

    def test_method_literal_sits_under_the_method_header(self):
        for year in YEARS:
            method_x = _header_x(year, "Method")
            convention_x = _header_x(year, "Convention")
            rows = _row_widgets(year)
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    spans = {path: (x0, x1)
                             for x0, x1, path in rows[f"Line19{row}[0]"]}
                    x0, x1 = spans[_literal(year, row, "method")]
                    self.assertTrue(x0 <= method_x <= x1)
                    self.assertFalse(x0 <= convention_x <= x1)

    def test_shaded_date_cell_is_not_mapped(self):
        """Column (b) is shaded on rows 19a-19f: no key, and no other key
        pointing at the widget."""
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            for row in PERSONAL_ROWS:
                with self.subTest(year=year, row=row):
                    self.assertNotIn(
                        f"f4562_line_19{row}_date_placed_in_service", scalars)
                    self.assertNotIn(
                        _date_widget(year, row), scalars.values())

    def test_real_property_rows_keep_their_date(self):
        for year in YEARS:
            scalars = Pdf4562.get_mapping(year)["scalars"]
            for row in ("i", "j"):
                with self.subTest(year=year, row=row):
                    self.assertIn(
                        f"f4562_line_19{row}_date_placed_in_service", scalars)


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


class MethodLabelTests(unittest.TestCase):
    def test_method_follows_the_class_not_the_convention(self):
        expected = {"3-year": ("a", "200 DB"), "5-year": ("b", "200 DB"),
                    "7-year": ("c", "200 DB"), "10-year": ("d", "200 DB"),
                    "15-year": ("e", "150 DB"), "20-year": ("f", "150 DB")}
        for month, tripped in ((3, False), (11, True)):
            scenario = _scenario(2025, *[
                _asset(cls, cls, month, 1_000.0, 2025) for cls in expected])
            result = form_f4562.compute(scenario, upstream={})
            for cls, (row, method) in expected.items():
                with self.subTest(recovery_class=cls, mid_quarter=tripped):
                    self.assertEqual(
                        result[f"f4562_line_19{row}_method"], method)
                    self.assertEqual(
                        result[f"f4562_line_19{row}_convention"],
                        "MQ" if tripped else "HY")

    def test_real_property_is_straight_line(self):
        result = form_f4562.compute(_scenario(
            2025, _asset("Building", "27.5-year", 1, 200_000.0, 2025),
            _asset("Shop", "39-year", 6, 500_000.0, 2025)), upstream={})
        self.assertEqual(result["f4562_line_19i_method"], "S/L")
        self.assertEqual(result["f4562_line_19j_method"], "S/L")

    def test_fifteen_year_row_prints_150_db_on_the_2025_template(self):
        """The filing-visible cell: a fence is 15-year property, and its
        row's column (f) must read "150 DB"."""
        result = form_f4562.compute(_scenario(
            2025, _asset("Fence", "15-year", 5, 12_000.0, 2025)), upstream={})
        fields = _filled_fields(2025, result)
        self.assertEqual(fields[METHOD_15_YEAR_2025], "150 DB")
        self.assertEqual(
            Pdf4562.get_mapping(2025)["scalars"]["f4562_line_19e_method"],
            METHOD_15_YEAR_2025)
        self.assertEqual(fields[f"{_SB}.Line19e[0].f1_53[0]"], "HY")
        self.assertEqual(fields[f"{_SB}.Line19e[0].f1_51[0]"], "12000")
        self.assertEqual(fields[f"{_SB}.Line19e[0].f1_52[0]"], "15 yrs.")
        self.assertEqual(fields[f"{_SB}.Line19e[0].f1_55[0]"], "600")
        self.assertIn(fields[f"{_SB}.Line19e[0].f1_50[0]"], (None, ""))

    def test_method_prints_in_the_method_column_on_every_layout(self):
        for year in YEARS:
            result = form_f4562.compute(_scenario(
                year,
                _asset("Laptop", "5-year", 2, 1_000.0, year),
                _asset("Fence", "15-year", 5, 12_000.0, year)), upstream={})
            fields = _filled_fields(year, result)
            with self.subTest(year=year):
                self.assertEqual(
                    fields[_literal(year, "b", "method")], "200 DB")
                self.assertEqual(
                    fields[_literal(year, "e", "method")], "150 DB")


class ShadedDateCellTests(unittest.TestCase):
    def test_personal_rows_compute_no_date_key(self):
        result = form_f4562.compute(_untripped(2025), upstream={})
        self.assertEqual(
            [k for k in result if k.endswith("_date_placed_in_service")], [])

    def test_real_property_rows_still_compute_one(self):
        scenario = _untripped(2025)
        scenario.rental_properties[0].depreciable_assets.append(
            _asset("Building", "27.5-year", 4, 200_000.0, 2025))
        result = form_f4562.compute(scenario, upstream={})
        self.assertEqual(
            [k for k in result if k.endswith("_date_placed_in_service")],
            ["f4562_line_19i_date_placed_in_service"])
        self.assertEqual(
            result["f4562_line_19i_date_placed_in_service"], "04/2025")

    def test_filled_form_leaves_the_shaded_cell_empty(self):
        for year in YEARS:
            fields = _filled_fields(
                year, form_f4562.compute(_untripped(year), upstream={}))
            for row in ("b", "c"):
                with self.subTest(year=year, row=row):
                    self.assertIn(
                        fields[_date_widget(year, row)], (None, ""))
                    self.assertEqual(
                        fields[_literal(year, row, "recovery_period")],
                        "5 yrs." if row == "b" else "7 yrs.")
                    self.assertEqual(
                        fields[_literal(year, row, "basis")],
                        "6000" if row == "b" else "4000")


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
