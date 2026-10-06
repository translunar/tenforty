"""Schedule K-1 (Form 1120-S) face items the filer STATES: Part I item C (IRS
Center), Part II item H (shares, beginning / end), item I (loans from
shareholder, beginning / end), and the "Final K-1" box.

Drives ``run_full_federal_scorp_return`` for every federal S-corp year, reopens
the REAL filled K-1 PDF, and asserts the field values, that the Final box
actually renders ink (field state is not pixels), and that unstated items leave
their cells blank. Cell paths below were certified per template by label
position (the printed caption sits beside the widget Rect): 2021-2023 share one
layout and 2024-2025 another, so item H/I cells MOVE between them. Written
independently of the mapping module on purpose: a wrong cell must fail here.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_LEFT = "topmostSubform[0].Page1[0].LeftCol[0]."
_FINAL_BOX = "topmostSubform[0].Page1[0].c1_01[0]"
_AMENDED_BOX = "topmostSubform[0].Page1[0].c1_02[0]"
_CELLS_2021_2023 = {
    "irs_center": _LEFT + "f1_08[0]",
    "shares_beginning": _LEFT + "f1_14[0]",
    "shares_end": _LEFT + "f1_15[0]",
    "loans_beginning": _LEFT + "f1_16[0]",
    "loans_end": _LEFT + "f1_17[0]",
}
_CELLS_2024_2025 = {
    "irs_center": _LEFT + "f1_08[0]",
    "shares_beginning": _LEFT + "f1_17[0]",
    "shares_end": _LEFT + "f1_18[0]",
    "loans_beginning": _LEFT + "f1_19[0]",
    "loans_end": _LEFT + "f1_20[0]",
}


def _cells(year):
    return _CELLS_2024_2025 if year >= 2024 else _CELLS_2021_2023


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

    def _emit(self, year, stated=True, final=False, pcts=None):
        s = _make_v1_scenario(shareholder_pcts=pcts)
        set_tax_year(s, year)
        r = s.s_corp_return
        if stated:
            r.irs_center = "Ogden, UT"
            for i, sh in enumerate(r.shareholders):
                sh.shares_beginning = 1000.0 + i
                sh.shares_end = 900.0 + i
                sh.loans_beginning = 12345.0 + i
                sh.loans_end = 6789.0 + i
        r.shareholders[0].final_k1 = final
        out = Path(self._tmp.name) / f"fed_{year}_{stated}_{final}"
        self.orch.run_full_federal_scorp_return(s, out)
        return out


class TemplateCellsExistTests(unittest.TestCase):
    def test_every_asserted_cell_is_a_writable_widget_on_the_template(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                template = Path("pdfs/federal") / str(year) / "f1120s_k1.pdf"
                fields = PdfReader(str(template)).get_fields() or {}
                for item, path in _cells(year).items():
                    self.assertEqual(
                        str(fields[path].get("/FT")), "/Tx", f"{year} {item}")
                for path in (_FINAL_BOX, _AMENDED_BOX):
                    self.assertEqual(
                        str(fields[path].get("/FT")), "/Btn", f"{year} {path}")


class StatedFaceItemTests(_EmitBase):
    def test_stated_items_print_in_the_certified_cells(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year) / f"f1120s_k1_1_{year}.pdf")
                # Positive control: a neighbouring cell on the same emit.
                self.assertEqual(vals[_LEFT + "f1_06[0]"], "00-0000000")
                want = {"irs_center": "Ogden, UT",
                        "shares_beginning": "1000", "shares_end": "900",
                        "loans_beginning": "12345", "loans_end": "6789"}
                for item, text in want.items():
                    self.assertEqual(
                        vals[_cells(year)[item]], text, f"{year} {item}")

    def test_each_shareholder_gets_their_own_figures(self):
        for year in (2022, 2025):
            with self.subTest(year=year):
                out = self._emit(year, pcts=[60.0, 40.0])
                second = _values(out / f"f1120s_k1_2_{year}.pdf")
                self.assertEqual(second[_cells(year)["shares_beginning"]], "1001")
                self.assertEqual(second[_cells(year)["loans_end"]], "6790")

    def test_fractional_shares_are_not_rounded_to_whole(self):
        for year in (2022, 2025):
            with self.subTest(year=year):
                s = _make_v1_scenario()
                set_tax_year(s, year)
                s.s_corp_return.shareholders[0].shares_beginning = 33.5
                out = Path(self._tmp.name) / f"frac_{year}"
                self.orch.run_full_federal_scorp_return(s, out)
                vals = _values(out / f"f1120s_k1_1_{year}.pdf")
                self.assertEqual(vals[_cells(year)["shares_beginning"]], "33.5")

    def test_unstated_items_leave_their_cells_blank(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year, stated=False)
                               / f"f1120s_k1_1_{year}.pdf")
                self.assertEqual(vals[_LEFT + "f1_06[0]"], "00-0000000")
                for item, path in _cells(year).items():
                    self.assertIn(vals[path], (None, ""), f"{year} {item}")


class FinalK1BoxTests(_EmitBase):
    def test_final_box_checked_and_visible_not_amended(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year, final=True) / f"f1120s_k1_1_{year}.pdf"
                vals = _values(pdf)
                self.assertEqual(vals[_FINAL_BOX], "/1")
                self.assertIn(vals[_AMENDED_BOX], (None, "/Off"))
                page, rect = widget_rect(pdf, _FINAL_BOX)
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0,
                    f"{year}: Final K-1 box is checked but draws no ink")

    def test_final_box_unchecked_by_default(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year) / f"f1120s_k1_1_{year}.pdf")
                self.assertIn(vals[_FINAL_BOX], (None, "/Off"))

    def test_final_applies_only_to_the_flagged_shareholder(self):
        year = 2025
        out = self._emit(year, final=True, pcts=[60.0, 40.0])
        self.assertEqual(
            _values(out / f"f1120s_k1_1_{year}.pdf")[_FINAL_BOX], "/1")
        self.assertIn(
            _values(out / f"f1120s_k1_2_{year}.pdf")[_FINAL_BOX], (None, "/Off"))


class LoaderTests(unittest.TestCase):
    def _load(self, shareholder_extra=None, scorp_extra=None):
        data = _scenario_yaml_dict(extra_scorp=scorp_extra)
        if shareholder_extra:
            data["s_corp_return"]["shareholders"][0].update(shareholder_extra)
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name))

    def test_stated_keys_load(self):
        s = self._load(
            {"shares_beginning": 1000, "shares_end": 900,
             "loans_beginning": 5000.5, "loans_end": 0, "final_k1": True},
            {"irs_center": "Ogden, UT"})
        sh = s.s_corp_return.shareholders[0]
        self.assertEqual(
            (sh.shares_beginning, sh.shares_end, sh.loans_beginning,
             sh.loans_end, sh.final_k1), (1000.0, 900.0, 5000.5, 0.0, True))
        self.assertEqual(s.s_corp_return.irs_center, "Ogden, UT")

    def test_absent_keys_default_unstated(self):
        s = self._load()
        sh = s.s_corp_return.shareholders[0]
        self.assertIsNone(sh.shares_beginning)
        self.assertIsNone(sh.loans_end)
        self.assertFalse(sh.final_k1)
        self.assertIsNone(s.s_corp_return.irs_center)

    def test_non_numeric_and_bool_amounts_rejected(self):
        for bad in ("lots", True, [1]):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load({"shares_beginning": bad})
        with self.assertRaises(ValueError):
            self._load({"loans_end": "n/a"})

    def test_negative_shares_rejected(self):
        with self.assertRaises(ValueError):
            self._load({"shares_end": -1})

    def test_non_bool_final_rejected(self):
        with self.assertRaises(ValueError):
            self._load({"final_k1": "yes"})

    def test_unknown_shareholder_key_fails_closed(self):
        with self.assertRaises(ValueError):
            self._load({"share_count": 5})


if __name__ == "__main__":
    unittest.main()
