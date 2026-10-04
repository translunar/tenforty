"""Form 1120-S page-1 header identity block — filled-emit and pixel tests.

The header block (items A, D, E, F, I and the name/address cells) must carry
the entity's identity from ``SCorpReturn`` onto the printed form. Drives
``run_full_federal_scorp_return`` for every federal S-corp year, reopens the
REAL filled PDF, and asserts (a) the field values AND (b) that ink is actually
rendered in the cells (field state is not pixels).

Cell paths below were certified per year by a marker-probe render of each
year's own template (every cell filled with its own label, page rendered, the
label read against the printed item caption). 2021-2024 share one layout (name,
street, and one combined city/state/ZIP cell); 2025 splits the address into
city / state / country / ZIP cells and moves the right-hand cells to f1_13-16.

Negative space is reachable: every asserted cell is a real writable text widget
on the template (``TemplateCellsExistTests``), and the same emit already writes
neighbouring page-1 header cells (item B business code), so an absent value
means the pipeline dropped it, not that the cell was unfillable.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario

_P1 = "topmostSubform[0].Page1[0]."
_NAME_BLOCK_2021_2024 = _P1 + "CalendarYear-TypePrint_ReadOrder[0]."
_NAME_BLOCK_2025 = _P1 + "Date_Name_ReadOrder[0]."

# header item -> full field path, per year.
_CELLS_2021_2024 = {
    "A_s_election_date": _P1 + "ABC[0].f1_7[0]",
    "name": _NAME_BLOCK_2021_2024 + "f1_4[0]",
    "street": _NAME_BLOCK_2021_2024 + "f1_5[0]",
    "city_state_zip": _NAME_BLOCK_2021_2024 + "f1_6[0]",
    "D_ein": _P1 + "f1_9[0]",
    "E_date_incorporated": _P1 + "f1_10[0]",
    "F_total_assets": _P1 + "f1_11[0]",
    "I_shareholder_count": _P1 + "f1_12[0]",
}
_CELLS_2025 = {
    "A_s_election_date": _P1 + "ABC[0].f1_11[0]",
    "name": _NAME_BLOCK_2025 + "f1_4[0]",
    "street": _NAME_BLOCK_2025 + "f1_5[0]",
    "city": _NAME_BLOCK_2025 + "f1_7[0]",
    "state": _NAME_BLOCK_2025 + "f1_8[0]",
    "zip": _NAME_BLOCK_2025 + "f1_10[0]",
    "D_ein": _P1 + "f1_13[0]",
    "E_date_incorporated": _P1 + "f1_14[0]",
    "F_total_assets": _P1 + "f1_15[0]",
    "I_shareholder_count": _P1 + "f1_16[0]",
}
_BUSINESS_CODE_CELL = {y: _P1 + "ABC[0].f1_8[0]" for y in (2021, 2022, 2023, 2024)}
_BUSINESS_CODE_CELL[2025] = _P1 + "ABC[0].f1_12[0]"
# A page-1 header text cell the emit never fills (tax-year "beginning" date).
_UNFILLED_CELL = {
    y: _NAME_BLOCK_2021_2024 + "f1_1[0]" for y in (2021, 2022, 2023, 2024)}
_UNFILLED_CELL[2025] = _NAME_BLOCK_2025 + "f1_1[0]"


def _cells(year):
    return _CELLS_2025 if year == 2025 else _CELLS_2021_2024


def _expected(year, shareholders=1):
    exp = {
        "A_s_election_date": "01/01/2020",
        "name": "Example S-Corp Inc.",
        "street": "1 Example Ave",
        "D_ein": "00-0000000",
        "E_date_incorporated": "01/01/2020",
        "F_total_assets": "50000",
        "I_shareholder_count": str(shareholders),
    }
    if year == 2025:
        exp.update({"city": "Example City", "state": "EX", "zip": "00000"})
    else:
        exp["city_state_zip"] = "Example City, EX 00000"
    return exp


def _values(pdf_path):
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return {k: (None if v.get("/V") is None else str(v.get("/V")))
            for k, v in fields.items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, shareholder_pcts=None):
        s = _make_v1_scenario(shareholder_pcts=shareholder_pcts)
        s.config.year = year
        out = Path(self._tmp.name) / f"fed_{year}"
        self.orch.run_full_federal_scorp_return(s, out)
        return out / f"f1120s_{year}.pdf"


class TemplateCellsExistTests(unittest.TestCase):
    """The asserted cells are real writable text widgets on each year's own
    template — so a missing value in the emit is the pipeline's doing."""

    def test_every_header_cell_is_a_text_widget_on_the_template(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                template = Path("pdfs/federal") / str(year) / "f1120s.pdf"
                fields = PdfReader(str(template)).get_fields() or {}
                for item, path in {**_cells(year),
                                   "biz": _BUSINESS_CODE_CELL[year],
                                   "unfilled": _UNFILLED_CELL[year]}.items():
                    self.assertIn(path, fields, f"{year} {item}")
                    self.assertEqual(
                        str(fields[path].get("/FT")), "/Tx", f"{year} {item}")


class HeaderFieldValueTests(_EmitBase):
    def test_header_values_are_written_every_year(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year))
                # Positive control: the same emit writes a neighbouring header
                # cell (item B), so these cells were fillable and reachable.
                self.assertEqual(vals[_BUSINESS_CODE_CELL[year]], "541990")
                for item, want in _expected(year).items():
                    self.assertEqual(
                        vals[_cells(year)[item]], want, f"{year} {item}")

    def test_shareholder_count_is_len_of_shareholders(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                vals = _values(self._emit(year, shareholder_pcts=[60.0, 40.0]))
                self.assertEqual(
                    vals[_cells(year)["I_shareholder_count"]], "2")

    def test_year_unfilled_neighbour_stays_empty(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year))
                self.assertIn(vals[_UNFILLED_CELL[year]], (None, ""))


class HeaderPixelTests(_EmitBase):
    """Ink, not field state: the header cells actually render text."""

    INK = 25  # dark pixels; a filled 10-char cell renders several hundred

    def _ink(self, pdf, path):
        page, rect = widget_rect(pdf, path)
        self.assertEqual(page, 0, path)
        return dark_pixels_in_rect(pdf, page, rect)

    def test_header_cells_render_ink_every_year(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                for item, path in _cells(year).items():
                    self.assertGreater(self._ink(pdf, path), self.INK,
                                       f"{year} {item}")

    def test_unfilled_header_cell_renders_no_ink(self):
        # Reachable negative space: same band, real text widget, never filled.
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                self.assertEqual(
                    self._ink(pdf, _UNFILLED_CELL[year]), 0, str(year))


if __name__ == "__main__":
    unittest.main()
