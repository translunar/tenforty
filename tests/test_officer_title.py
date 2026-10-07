"""Officer TITLE in the entity signature blocks: Form 1120-S page 1 ("Signature
of officer / Date / Title") and Form 100S Side 3 (Sign Here, "Title of the
signing officer"), every year 2021-2025, from ``s_corp_return.officer_title``.
None leaves the cell blank. The signature and date cells are NEVER filled
(policy): asserted untouched.

Cells certified per year from each template: the 1120-S Title field sits
directly above its printed "Title" caption on 2021-2024 and to the right of the
caption on 2025 (2021 f1_49, 2022 f1_49, 2023 f1_50, 2024 f1_50, 2025 f1_56);
the 100S cell is field 3040 on every year (bare name through 2023, "100S Form "
prefix after), above the "Title" caption at x 276.

Synthetic fixture only."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_P1 = "topmostSubform[0].Page1[0].f1_"
_FED_TITLE = {2021: 49, 2022: 49, 2023: 50, 2024: 50, 2025: 56}
_TITLE = "Example President"


def _n(year, bare):
    return bare if year <= 2023 else f"100S Form {bare}"


def _rect(pdf, name):
    for page_i, page in enumerate(PdfReader(str(pdf)).pages):
        for a in page.get("/Annots", []) or []:
            a = a.get_object()
            names, n = [], a
            while n is not None:
                if "/T" in n:
                    names.append(str(n["/T"]))
                p = n.get("/Parent")
                n = p.get_object() if p else None
            if ".".join(reversed(names)) == name:
                return page_i, [float(v) for v in a["/Rect"]]
    raise KeyError(name)


def _v(pdf):
    return {k: (None if x.get("/V") is None else str(x["/V"]))
            for k, x in (PdfReader(str(pdf)).get_fields() or {}).items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _scenario(self, year, title):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.officer_title = title
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        return s

    def _fed(self, year, title):
        out = Path(self._tmp.name) / f"fed_{year}_{title}"
        self.orch.run_full_federal_scorp_return(self._scenario(year, title), out)
        return out / f"f1120s_{year}.pdf"

    def _ca(self, year, title):
        out = Path(self._tmp.name) / f"ca_{year}_{title}"
        self.orch.run_full_california_scorp_return(
            self._scenario(year, title), out)
        return out / f"f100s_{year}.pdf"


class Federal1120STitleTests(_EmitBase):
    def test_title_prints_in_the_certified_cell_with_ink(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                pdf = self._fed(year, _TITLE)
                name = f"{_P1}{_FED_TITLE[year]}[0]"
                v = _v(pdf)
                self.assertEqual(v[f"topmostSubform[0].Page1[0].f1_{_FED_TITLE[year]}[0]"], _TITLE)
                page, rect = _rect(pdf, name)
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)

    def test_unstated_is_blank_and_other_signature_area_cells_untouched(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                v = _v(self._fed(year, None))
                self.assertIn(v[f"{_P1}{_FED_TITLE[year]}[0]"], (None, ""))
                # control: EIN prints in the same emit
                ein = "f1_13[0]" if year == 2025 else "f1_9[0]"
                self.assertEqual(v[f"topmostSubform[0].Page1[0].{ein}"],
                                 "00-0000000")

    def test_title_does_not_land_in_any_other_signature_area_text_cell(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                v = _v(self._fed(year, _TITLE))
                hits = [k for k, x in v.items() if x == _TITLE]
                self.assertEqual(hits, [
                    f"topmostSubform[0].Page1[0].f1_{_FED_TITLE[year]}[0]"])


class Ca100STitleTests(_EmitBase):
    def test_title_prints_and_date_cell_stays_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                pdf = self._ca(year, _TITLE)
                v = _v(pdf)
                self.assertEqual(v[_n(year, "3040")], _TITLE)
                self.assertIn(v[_n(year, "3041")], (None, ""))   # date signed
                page, rect = _rect(pdf, _n(year, "3040"))
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)

    def test_unstated_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                v = _v(self._ca(year, None))
                self.assertIn(v[_n(year, "3040")], (None, ""))
                self.assertEqual(v[_n(year, "3001")], "541990")  # control


class LoaderTests(unittest.TestCase):
    def _load(self, value="absent"):
        extra = None if value == "absent" else {"officer_title": value}
        data = _scenario_yaml_dict(extra_scorp=extra)
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return

    def test_default_none_and_stated_loads(self):
        self.assertIsNone(self._load().officer_title)
        self.assertEqual(self._load("President").officer_title, "President")

    def test_bad_values_refused(self):
        self._load("President")  # reachability: the key is known
        for bad in ("", "   ", 5, True):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load(bad)


if __name__ == "__main__":
    unittest.main()
