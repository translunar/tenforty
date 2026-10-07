"""Form 1120-S page 1 item G ("Is the corporation electing to be an S
corporation beginning with this tax year?", Yes / No) and the item H "Check if:"
boxes (1) Final return, (2) Name change, (3) Address change, (5) S election
termination or revocation, federal TY2021-2025.

Item G is a stated Yes/No pair: None leaves both boxes blank, True / False marks
only the chosen box. Item H boxes are check-if-applicable: ONLY True draws a
mark, False and None are both blank. H(4) "Amended return" is wired separately
(``amended_return``) and must be undisturbed.

Cell table written independently of the mapping module and certified on EACH of
the five templates (the 2021 template included, checked on its own) from the
widget Rects against the printed captions: item G Yes / No boxes sit left of
their "Yes" / "No" labels (c1_2[0] export /1, c1_2[1] export /2); the H boxes sit
between each "(n)" marker and its caption (c1_3 = (1), c1_4 = (2), c1_5 = (3),
c1_6 = (4), c1_7 = (5), each export /1). The geometry is identical in every year.

Synthetic fixture only."""
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

_P1 = "topmostSubform[0].Page1[0]."
_G = {True: (_P1 + "c1_2[0]", "/1"), False: (_P1 + "c1_2[1]", "/2")}
_H = {
    "final_return": (_P1 + "c1_3[0]", "/1"),
    "name_change": (_P1 + "c1_4[0]", "/1"),
    "address_change": (_P1 + "c1_5[0]", "/1"),
    "amended": (_P1 + "c1_6[0]", "/1"),
    "s_election_terminated": (_P1 + "c1_7[0]", "/1"),
}
_H_FIELDS = ("final_return", "name_change", "address_change",
             "s_election_terminated")
_ALL = tuple(years.SCORP_FEDERAL_YEARS)


def _v(pdf, path):
    got = (PdfReader(str(pdf)).get_fields() or {})[path].get("/V")
    return None if got is None else str(got)


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, **stated):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        for k, v in stated.items():
            setattr(s.s_corp_return, k, v)
        out = Path(self._tmp.name) / f"{year}_{sorted(stated.items())}"
        self.orch.run_full_federal_scorp_return(s, out)
        return out / f"f1120s_{year}.pdf"

    def _marked(self, pdf):
        cells = {("G", k): c for k, c in _G.items()}
        cells.update({("H", k): c for k, c in _H.items()})
        return {k for k, (path, on) in cells.items() if _v(pdf, path) == on}


class TemplateCellsTests(unittest.TestCase):
    def test_cells_exist_and_geometry_matches_captions_every_year(self):
        for year in _ALL:
            tmpl = f"pdfs/federal/{year}/f1120s.pdf"
            with self.subTest(year=year):
                rects = {}
                for key, (path, on) in {**{("G", k): c for k, c in _G.items()},
                                        **{("H", k): c for k, c in _H.items()}
                                        }.items():
                    rects[key] = widget_rect(tmpl, path, on)[1]
                # G: Yes box left of No box, same row
                self.assertLess(rects[("G", True)][0], rects[("G", False)][0])
                # H boxes ordered (1) < (2) < (3) < (4) < (5) left to right
                xs = [rects[("H", k)][0] for k in (
                    "final_return", "name_change", "address_change", "amended",
                    "s_election_terminated")]
                self.assertEqual(xs, sorted(xs))


class ItemGTests(_EmitBase):
    def test_unstated_marks_nothing(self):
        for year in _ALL:
            with self.subTest(year=year):
                pdf = self._emit(year)
                self.assertEqual(self._marked(pdf), set())
                # control: header cells print in the same emit
                self.assertEqual(_v(pdf, _P1 + "f1_9[0]" if year < 2025
                                    else _P1 + "f1_13[0]"), "00-0000000")

    def test_yes_marks_only_yes_and_draws_ink(self):
        for year in _ALL:
            for answer in (True, False):
                with self.subTest(year=year, answer=answer):
                    pdf = self._emit(year, electing_s_this_year=answer)
                    self.assertEqual(self._marked(pdf), {("G", answer)})
                    path, on = _G[answer]
                    page, rect = widget_rect(pdf, path, on)
                    self.assertGreater(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)
                    opath, oon = _G[not answer]
                    opage, orect = widget_rect(pdf, opath, oon)
                    self.assertEqual(
                        dark_pixels_in_rect(pdf, opage, orect, inset=1.0), 0)


class ItemHTests(_EmitBase):
    def test_true_marks_only_its_own_box_and_draws_ink(self):
        for year in _ALL:
            for field in _H_FIELDS:
                with self.subTest(year=year, field=field):
                    pdf = self._emit(year, **{field: True})
                    self.assertEqual(self._marked(pdf), {("H", field)})
                    path, on = _H[field]
                    page, rect = widget_rect(pdf, path, on)
                    self.assertGreater(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)

    def test_false_and_none_print_nothing(self):
        for year in _ALL:
            with self.subTest(year=year):
                none_pdf = self._emit(year)
                false_pdf = self._emit(
                    year, **{f: False for f in _H_FIELDS})
                self.assertEqual(self._marked(false_pdf), set())
                self.assertEqual(self._marked(none_pdf), set())
                # False is indistinguishable from unstated: same field payload
                fn = {k: v.get("/V") for k, v in
                      (PdfReader(str(none_pdf)).get_fields() or {}).items()}
                ff = {k: v.get("/V") for k, v in
                      (PdfReader(str(false_pdf)).get_fields() or {}).items()}
                self.assertEqual(fn, ff)

    def test_several_boxes_can_be_checked_together(self):
        pdf = self._emit(2025, final_return=True, name_change=True,
                         s_election_terminated=True)
        self.assertEqual(self._marked(pdf), {
            ("H", "final_return"), ("H", "name_change"),
            ("H", "s_election_terminated")})


class AmendedUndisturbedTests(_EmitBase):
    def test_amended_alone_still_marks_only_h4(self):
        for year in _ALL:
            with self.subTest(year=year):
                self.assertEqual(
                    self._marked(self._emit(year, amended_return=True)),
                    {("H", "amended")})

    def test_amended_with_h_boxes_marks_both_independently(self):
        for year in _ALL:
            with self.subTest(year=year):
                pdf = self._emit(year, amended_return=True, final_return=True,
                                 electing_s_this_year=True)
                self.assertEqual(self._marked(pdf), {
                    ("H", "amended"), ("H", "final_return"), ("G", True)})

    def test_h_boxes_do_not_set_amended(self):
        for year in _ALL:
            with self.subTest(year=year):
                pdf = self._emit(year, **{f: True for f in _H_FIELDS})
                self.assertNotIn(("H", "amended"), self._marked(pdf))


class LoaderTests(unittest.TestCase):
    def _load(self, extra=None):
        data = _scenario_yaml_dict(extra_scorp=extra)
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return

    def test_stated_values_load(self):
        r = self._load({"electing_s_this_year": True, "final_return": True,
                        "name_change": False, "address_change": True,
                        "s_election_terminated": False})
        self.assertIs(r.electing_s_this_year, True)
        self.assertIs(r.final_return, True)
        self.assertIs(r.name_change, False)
        self.assertIs(r.address_change, True)

    def test_absent_default_unstated(self):
        r = self._load()
        for f in ("electing_s_this_year", *_H_FIELDS):
            self.assertIsNone(getattr(r, f), f)

    def test_non_bool_refused(self):
        self._load({"final_return": True})  # reachability: key is known
        for key in ("electing_s_this_year", *_H_FIELDS):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self._load({key: "yes"})


if __name__ == "__main__":
    unittest.main()
