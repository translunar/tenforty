"""Schedule E page 1 lines A and B (the Form 1099 questions), federal TY2022-2025.

Line A: "Did you make any payments in <year> that would require you to file Form(s)
1099?" (Yes / No). Line B: "If 'Yes,' did you or will you file required Form(s)
1099?" (Yes / No). Scenario config fields ``payments_requiring_1099s`` and
``filed_required_1099s`` state the answers:

  * both unstated            -> every box stays blank (backward compatible)
  * payments False           -> A "No" only; B blank; a stated B is a ValueError
  * payments True            -> A "Yes"; B REQUIRED and prints Yes or No

Cell table below is written independently of the mapping module and certified
per year from each template's own widget list + the printed Yes/No caption
positions (Yes box left, export /1; No box right, export /2) on 2022, 2023, 2024
and 2025. The 2021 template has different geometry and is out of scope (a stated
answer there is refused, not dropped).

Synthetic fixture only. Emission is exercised through ``emit_pdfs`` with a
rental property so Schedule E is produced."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.models import RentalProperty
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests.helpers import scope_out_attestation_defaults
from tests.test_orchestrator_emit_pdfs import (
    SAMPLE_RESULTS, make_scenario_with_identity)

_YEARS = (2022, 2023, 2024, 2025)
_P1 = "topmostSubform[0].Page1[0]."
# (question, answer) -> (field path, export on-state); same every year 2022-2025
# (each year verified separately against its own template below).
_CELLS = {
    ("A", True): (_P1 + "c1_1[0]", "/1"),
    ("A", False): (_P1 + "c1_1[1]", "/2"),
    ("B", True): (_P1 + "c1_2[0]", "/1"),
    ("B", False): (_P1 + "c1_2[1]", "/2"),
}


def _v(pdf, path):
    fields = PdfReader(str(pdf)).get_fields() or {}
    got = fields[path].get("/V")
    return None if got is None else str(got)


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.out = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"), work_dir=self.out / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def _scenario(self, year, payments=None, filed=None):
        s = make_scenario_with_identity()
        s.config.year = year
        s.config.payments_requiring_1099s = payments
        s.config.filed_required_1099s = filed
        s.rental_properties = [RentalProperty(
            address="123 Main St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=24000.0,
            mortgage_interest=8000.0, taxes=3000.0, depreciation=5000.0,
            acknowledges_depreciation_stated_outside_macrs=True)]
        return s

    def _emit(self, year, payments=None, filed=None):
        out = self.out / f"{year}_{payments}_{filed}"
        emitted = self.orch.emit_pdfs(
            self._scenario(year, payments, filed), SAMPLE_RESULTS, out)
        return emitted["sch_e"]


class TemplateCellsTests(unittest.TestCase):
    def test_each_year_has_the_certified_widgets_and_yes_is_left(self):
        for year in _YEARS:
            tmpl = f"pdfs/federal/{year}/f1040se.pdf"
            for (q, ans), (path, on) in _CELLS.items():
                with self.subTest(year=year, q=q, ans=ans):
                    _, rect = widget_rect(tmpl, path, on)
                    # Yes box left of No box on the same row
                    other = _CELLS[(q, not ans)]
                    _, orect = widget_rect(tmpl, other[0], other[1])
                    self.assertEqual(rect[0] < orect[0], ans is True)


class StatedAnswerTests(_EmitBase):
    def _marked(self, pdf):
        return {k for k, (path, on) in _CELLS.items()
                if _v(pdf, path) == on}

    def test_unstated_marks_nothing(self):
        for year in _YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                self.assertEqual(self._marked(pdf), set())
                # control: the same emit does fill Part I (rental rents line)
                self.assertGreater(len(
                    [1 for v in (PdfReader(str(pdf)).get_fields() or {}).values()
                     if v.get("/V") not in (None, "")]), 3)

    def test_no_to_a_marks_only_a_no(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    self._marked(self._emit(year, payments=False)),
                    {("A", False)})

    def test_yes_then_filed_yes(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    self._marked(self._emit(year, True, True)),
                    {("A", True), ("B", True)})

    def test_yes_then_filed_no(self):
        for year in _YEARS:
            with self.subTest(year=year):
                self.assertEqual(
                    self._marked(self._emit(year, True, False)),
                    {("A", True), ("B", False)})

    def test_every_marked_box_draws_ink_and_unmarked_pair_is_clear(self):
        for year in _YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year, True, False)
                for key in (("A", True), ("B", False)):
                    path, on = _CELLS[key]
                    page, rect = widget_rect(pdf, path, on)
                    self.assertGreater(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0, key)
                for key in (("A", False), ("B", True)):
                    path, on = _CELLS[key]
                    page, rect = widget_rect(pdf, path, on)
                    self.assertEqual(
                        dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0, key)


class RefusalTests(_EmitBase):
    def test_contradictory_or_incomplete_combinations_refused_at_emit(self):
        for payments, filed in ((False, True), (False, False),
                                (True, None), (None, True), (None, False)):
            with self.subTest(payments=payments, filed=filed):
                with self.assertRaises(ValueError):
                    self._emit(2025, payments, filed)

    def test_non_bool_refused_at_emit(self):
        with self.assertRaises(ValueError):
            self._emit(2025, "no")

    def test_2021_refuses_a_stated_answer(self):
        with self.assertRaises(ValueError):
            self._emit(2021, False)


class LoaderTests(unittest.TestCase):
    def _load(self, **cfg):
        config = {
            "year": 2025, "filing_status": "single",
            "birthdate": "01-01-1980", "state": "EX", "first_name": "T",
            "last_name": "A", "ssn": "000-00-0000",
            **scope_out_attestation_defaults(), **cfg}
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump({"config": config}, f)
        f.close()
        return load_scenario(Path(f.name)).config

    def test_stated_values_load(self):
        c = self._load(payments_requiring_1099s=True, filed_required_1099s=False)
        self.assertIs(c.payments_requiring_1099s, True)
        self.assertIs(c.filed_required_1099s, False)

    def test_absent_defaults_unstated(self):
        c = self._load()
        self.assertIsNone(c.payments_requiring_1099s)
        self.assertIsNone(c.filed_required_1099s)

    def test_bad_combinations_refused_at_load(self):
        self._load(payments_requiring_1099s=False)  # reachability: names known
        for cfg in ({"payments_requiring_1099s": False,
                     "filed_required_1099s": True},
                    {"payments_requiring_1099s": True},
                    {"filed_required_1099s": False},
                    {"payments_requiring_1099s": "no"},
                    {"payments_requiring_1099s": True,
                     "filed_required_1099s": "yes"},
                    {"year": 2021, "payments_requiring_1099s": False}):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                self._load(**cfg)


if __name__ == "__main__":
    unittest.main()
