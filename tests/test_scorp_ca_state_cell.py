"""CA Form 100S Side 1 "State" identity cell — filled-emit and pixel tests.

The address block prints City, State, ZIP. The emit must carry
``Address.state`` into the State cell for every CA S-corp year; it once
injected city and ZIP but no state, leaving the State cell blank.

The State cell is the widget numbered 1011 (bare name 2021-2023, prefixed
"100S Form 1011" 2024-2025). Certified per year by marker-probe: the widget's
rect sits between City (1010) and ZIP (1012) on one row, directly under the
printed "State" caption, and a filled marker renders ink inside that rect.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.mappings.pdf_f100s import PdfF100S
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._pdf_pixels import dark_pixels_in_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year


def _state_cell(year: int) -> str:
    return "1011" if year <= 2023 else "100S Form 1011"


def _city_cell(year: int) -> str:
    return "1010" if year <= 2023 else "100S Form 1010"


def _zip_cell(year: int) -> str:
    return "1012" if year <= 2023 else "100S Form 1012"


def _rect(pdf_path, name):
    for a in PdfReader(str(pdf_path)).pages[0].get("/Annots", []):
        a = a.get_object()
        n = a.get("/T") or a["/Parent"].get_object().get("/T")
        if str(n) == name:
            return [float(x) for x in a["/Rect"]]
    raise AssertionError(f"{name} not on page 1")


class StateCellGeometryTests(unittest.TestCase):
    """Marker-probe evidence, per year's own template: 1011 is a text widget
    on the City/ZIP row, between them, under the printed 'State' caption."""

    def test_state_cell_sits_between_city_and_zip(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                t = Path("pdfs/california") / str(year) / "f100s.pdf"
                fields = PdfReader(str(t)).get_fields() or {}
                self.assertEqual(
                    str(fields[_state_cell(year)].get("/FT")), "/Tx")
                city, st, zp = (_rect(t, f(year)) for f in
                                (_city_cell, _state_cell, _zip_cell))
                self.assertEqual(city[1], st[1])
                self.assertEqual(st[1], zp[1])
                self.assertLess(city[2], st[0])
                self.assertLess(st[2], zp[0])


class StateCellEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year):
        s = _make_v1_scenario()
        s.s_corp_return.name = "Testco LLC"
        s.s_corp_return.address.state = "ZQ"
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        set_tax_year(s, year)
        out = Path(self._tmp.name) / f"ca_{year}"
        self.orch.run_full_california_scorp_return(s, out)
        return out / f"f100s_{year}.pdf"

    def test_state_value_reaches_state_cell_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                self.assertEqual(
                    PdfF100S.get_mapping(year)["f100s_entity_state"],
                    _state_cell(year))
                fields = PdfReader(str(pdf)).get_fields() or {}
                # Positive control: neighbouring cell is filled by same emit.
                self.assertEqual(
                    str(fields[_zip_cell(year)].get("/V")), "00000")
                self.assertEqual(
                    str(fields[_state_cell(year)].get("/V")), "ZQ")

    def test_state_ink_is_rendered_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                rect = _rect(pdf, _state_cell(year))
                self.assertGreater(
                    dark_pixels_in_rect(pdf, 0, rect, inset=1.0), 0)
