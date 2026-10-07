"""The "may we discuss this return with the preparer / a designee" questions.

Juno's standing ruling is NO everywhere (self-prepared, no designee); these are
STATED answers, None = blank:

* Form 1120-S page 1 "May the IRS discuss this return with the preparer shown
  below?" -> ``s_corp_return.discuss_with_preparer`` (Yes/No pair).
* Form 100S Side 3 "May the FTB discuss this return with the preparer shown
  above?" -> ``s_corp_return.ca.discuss_with_preparer`` (Yes/No pair).
* Form 1040 third party designee "Do you want to allow another person to discuss
  this return with the IRS?" -> ``config.third_party_designee``: False checks
  "No"; True is refused (NotImplementedError) because the designee name/phone/PIN
  cells are unmodeled. The same field refuses True on the CA 540, whose designee
  "No" box is already hardwired by the 540 presentation layer (pinned in
  test_ca_540_presentation.py), so the 540 print is unchanged.

Cells certified per year from each template (widget Rects against the printed
Yes / No caption): 1120-S c1_10[0]=Yes /1, c1_10[1]=No /2 on 2021-2024, c1_11 on
2025; 100S radio 3051 rb Yes /0 (left) No /1 (bare name through 2023, "100S Form "
prefix after); 1040 page 2 group c2_7 (2021), c2_06 (2022), c2_6 (2023, 2024),
c2_17 (2025): Yes /1 left, No /2 right.

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
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.helpers import scope_out_attestation_defaults
from tests.test_orchestrator_emit_pdfs import (
    SAMPLE_RESULTS, make_scenario_with_identity)
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_P1 = "topmostSubform[0].Page1[0]."
_P2 = "topmostSubform[0].Page2[0]."


def _fed_cells(year):
    grp = "c1_11" if year == 2025 else "c1_10"
    return {True: (f"{_P1}{grp}[0]", "/1"), False: (f"{_P1}{grp}[1]", "/2")}


def _ca_cells(year):
    name = f"100S Form 3051 rb" if year >= 2024 else "3051 rb"
    return {True: (name, "/0"), False: (name, "/1")}


_F1040_GROUP = {2021: "c2_7", 2022: "c2_06", 2023: "c2_6", 2024: "c2_6",
                2025: "c2_17"}


def _f1040_cells(year):
    g = _F1040_GROUP[year]
    return {True: (f"{_P2}{g}[0]", "/1"), False: (f"{_P2}{g}[1]", "/2")}


def _v(pdf):
    return {k: (None if x.get("/V") is None else str(x["/V"]))
            for k, x in (PdfReader(str(pdf)).get_fields() or {}).items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"), work_dir=self.out / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def _assert_pair(self, pdf, cells, chosen):
        v = _v(pdf)
        for answer, (path, on) in cells.items():
            if answer is chosen:
                self.assertEqual(v[path], on, answer)
                page, rect = widget_rect(pdf, path, on)
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)
            elif path == cells[chosen][0]:      # one radio: other token unset
                self.assertNotEqual(v[path], on, answer)
            else:
                self.assertIn(v[path], (None, "/Off"), answer)


class TemplateCellsTests(unittest.TestCase):
    def test_yes_is_left_of_no_every_year(self):
        for year in years.SCORP_FEDERAL_YEARS:
            tmpl = f"pdfs/federal/{year}/f1120s.pdf"
            c = _fed_cells(year)
            self.assertLess(widget_rect(tmpl, *c[True])[1][0],
                            widget_rect(tmpl, *c[False])[1][0], year)
        for year in years.CA_SCORP_YEARS:
            tmpl = f"pdfs/california/{year}/f100s.pdf"
            c = _ca_cells(year)
            self.assertLess(widget_rect(tmpl, *c[True])[1][0],
                            widget_rect(tmpl, *c[False])[1][0], year)
        for year in years.FEDERAL_YEARS:
            tmpl = f"pdfs/federal/{year}/f1040.pdf"
            c = _f1040_cells(year)
            self.assertLess(widget_rect(tmpl, *c[True])[1][0],
                            widget_rect(tmpl, *c[False])[1][0], year)


class Form1120STests(_EmitBase):
    def _emit(self, year, answer):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.discuss_with_preparer = answer
        d = self.out / f"f_{year}_{answer}"
        self.orch.run_full_federal_scorp_return(s, d)
        return d / f"f1120s_{year}.pdf"

    def test_unstated_blank_and_each_answer_marks_only_its_box(self):
        for year in years.SCORP_FEDERAL_YEARS:
            for answer in (None, True, False):
                with self.subTest(year=year, answer=answer):
                    pdf = self._emit(year, answer)
                    if answer is None:
                        v = _v(pdf)
                        for path, _ in _fed_cells(year).values():
                            self.assertIn(v[path], (None, "/Off"))
                    else:
                        self._assert_pair(pdf, _fed_cells(year), answer)


class Form100STests(_EmitBase):
    def _emit(self, year, answer):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True, discuss_with_preparer=answer)
        d = self.out / f"c_{year}_{answer}"
        self.orch.run_full_california_scorp_return(s, d)
        return d / f"f100s_{year}.pdf"

    def test_unstated_blank_and_each_answer_marks_only_its_box(self):
        for year in years.CA_SCORP_YEARS:
            for answer in (None, True, False):
                with self.subTest(year=year, answer=answer):
                    pdf = self._emit(year, answer)
                    if answer is None:
                        v = _v(pdf)
                        for path, _ in _ca_cells(year).values():
                            self.assertIn(v[path], (None, "/Off"))
                    else:
                        self._assert_pair(pdf, _ca_cells(year), answer)


class Form1040DesigneeTests(_EmitBase):
    def _emit(self, year, designee):
        s = make_scenario_with_identity()
        s.config.year = year
        s.config.third_party_designee = designee
        return self.orch.emit_pdfs(
            s, SAMPLE_RESULTS, self.out / f"d_{year}_{designee}")["1040"]

    def test_unstated_blank_and_false_checks_only_no(self):
        for year in years.FEDERAL_YEARS:
            with self.subTest(year=year):
                v = _v(self._emit(year, None))
                for path, _ in _f1040_cells(year).values():
                    self.assertIn(v[path], (None, "/Off"))
                pdf = self._emit(year, False)
                self._assert_pair(pdf, _f1040_cells(year), False)

    def test_true_is_refused_at_emit(self):
        for year in years.FEDERAL_YEARS:
            with self.subTest(year=year):
                with self.assertRaises(NotImplementedError):
                    self._emit(year, True)


class LoaderTests(unittest.TestCase):
    def _write(self, data):
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return Path(f.name)

    def _scorp(self, **extra):
        return load_scenario(self._write(
            _scenario_yaml_dict(extra_scorp=extra or None))).s_corp_return

    def test_s_corp_fields_load(self):
        self.assertIs(self._scorp(discuss_with_preparer=False)
                      .discuss_with_preparer, False)
        self.assertIsNone(self._scorp().discuss_with_preparer)
        with self.assertRaises(ValueError):
            self._scorp(discuss_with_preparer="no")

    def test_ca_field_loads(self):
        data = _scenario_yaml_dict()
        data["s_corp_return"]["ca"] = {
            "first_year": False, "estimated_tax_payments": 0.0,
            "prior_year_overpayment_applied": 0.0,
            "state_tax_deducted_federally": 0.0,
            "depreciation_adjustment": 0.0, "apportionment_ca_only": True,
            "discuss_with_preparer": False}
        ca = load_scenario(self._write(data)).s_corp_return.ca
        self.assertIs(ca.discuss_with_preparer, False)
        data["s_corp_return"]["ca"]["discuss_with_preparer"] = "no"
        with self.assertRaises(ValueError):
            load_scenario(self._write(data))

    def _config(self, **cfg):
        data = _scenario_yaml_dict()
        data["config"].update(cfg)
        return load_scenario(self._write(data)).config

    def test_designee_loads_and_true_is_refused_at_load(self):
        self.assertIs(self._config(third_party_designee=False)
                      .third_party_designee, False)
        self.assertIsNone(self._config().third_party_designee)
        with self.assertRaises(NotImplementedError):
            self._config(third_party_designee=True)
        with self.assertRaises(ValueError):
            self._config(third_party_designee="no")


if __name__ == "__main__":
    unittest.main()
