"""CA Form 100S Schedule Q item U: (1) has the entity previously filed an
unclaimed property Holder Remit Report with the State Controller's Office
(Yes / No); (2) if Yes, the date the last report was filed (mm/dd/yyyy);
(3) the amount last remitted (dollars + separate cents cell).

Dependent-answer pattern (like Schedule E lines A/B): all three unstated ->
blank; filed False -> "No" only and a stated date or amount is refused;
filed True -> "Yes" and BOTH date and amount are REQUIRED (an amount of 0.00 is
legal). Cells verified per year on each template: item letter U on every year;
U1 is radio 3027 (Yes left /0, No right /1) on 2021-2025 (bare name through
2023, "100S Form " prefix after); U2 date 3028; U3 dollars 3029 and cents 3030.
2021 refuses a stated answer (Schedule Q feature floor TY2022).

Synthetic fixture only."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_YEARS = (2022, 2023, 2024, 2025)


def _n(year, bare):
    return bare if year <= 2023 else f"100S Form {bare}"


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

    def _emit(self, year, filed=None, date=None, amount=None):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True, filed_unclaimed_property_report=filed,
            unclaimed_property_report_date=date,
            unclaimed_property_amount_remitted=amount)
        out = Path(self._tmp.name) / f"u_{year}_{filed}_{date}_{amount}".replace(
            "/", "-")
        self.orch.run_full_california_scorp_return(s, out)
        return out / f"f100s_{year}.pdf"


class TemplateCellsTests(unittest.TestCase):
    def test_cells_exist_yes_is_left_every_year(self):
        for year in (2021, *_YEARS):
            tmpl = f"pdfs/california/{year}/f100s.pdf"
            _, yes = widget_rect(tmpl, _n(year, "3027 rb"), "/0")
            _, no = widget_rect(tmpl, _n(year, "3027 rb"), "/1")
            self.assertLess(yes[0], no[0], year)
            fields = PdfReader(tmpl).get_fields()
            for num in ("3028", "3029", "3030"):
                self.assertEqual(str(fields[_n(year, num)].get("/FT")), "/Tx")


class StatedAnswerTests(_EmitBase):
    def test_unstated_all_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                v = _v(self._emit(year))
                self.assertIn(v[_n(year, "3027 rb")], (None, "/Off"))
                for num in ("3028", "3029", "3030"):
                    self.assertIn(v[_n(year, num)], (None, ""))

    def test_no_marks_only_no_and_leaves_dependents_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year, filed=False)
                v = _v(pdf)
                self.assertEqual(v[_n(year, "3027 rb")], "/1")
                page, rect = widget_rect(pdf, _n(year, "3027 rb"), "/1")
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)
                for num in ("3028", "3029", "3030"):
                    self.assertIn(v[_n(year, num)], (None, ""))

    def test_yes_prints_date_and_amount_split_dollars_cents(self):
        for year in _YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year, True, "03/15/2024", 1234.56)
                v = _v(pdf)
                self.assertEqual(v[_n(year, "3027 rb")], "/0")
                page, rect = widget_rect(pdf, _n(year, "3027 rb"), "/0")
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0)
                self.assertEqual(v[_n(year, "3028")], "03/15/2024")
                self.assertEqual(v[_n(year, "3029")], "1234")
                self.assertEqual(v[_n(year, "3030")], "56")

    def test_zero_amount_is_legal_and_prints_0_00(self):
        for year in _YEARS:
            with self.subTest(year=year):
                v = _v(self._emit(year, True, "01/02/2023", 0.0))
                self.assertEqual(v[_n(year, "3029")], "0")
                self.assertEqual(v[_n(year, "3030")], "00")

    def test_whole_dollar_amount_has_two_digit_cents(self):
        v = _v(self._emit(2025, True, "01/02/2023", 700.0))
        self.assertEqual((v[_n(2025, "3029")], v[_n(2025, "3030")]),
                         ("700", "00"))


class RefusalTests(_EmitBase):
    def test_contradictory_or_incomplete_refused(self):
        cases = [
            (True, None, 5.0), (True, "03/15/2024", None),
            (True, None, None),
            (False, "03/15/2024", None), (False, None, 5.0),
            (None, "03/15/2024", None), (None, None, 5.0),
            (True, "2024-03-15", 5.0), (True, "13/40/2024", 5.0),
            (True, "03/15/2024", -1.0),
        ]
        for filed, date, amount in cases:
            with self.subTest(filed=filed, date=date, amount=amount):
                with self.assertRaises(ValueError):
                    self._emit(2025, filed, date, amount)

    def test_2021_refuses_a_stated_answer(self):
        with self.assertRaises(ValueError):
            self._emit(2021, False)


class LoaderTests(unittest.TestCase):
    def _load(self, **ca):
        data = _scenario_yaml_dict()
        data["s_corp_return"]["ca"] = {
            "first_year": False, "estimated_tax_payments": 0.0,
            "prior_year_overpayment_applied": 0.0,
            "state_tax_deducted_federally": 0.0,
            "depreciation_adjustment": 0.0, "apportionment_ca_only": True,
            **ca}
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return.ca

    def test_stated_load(self):
        ca = self._load(filed_unclaimed_property_report=True,
                        unclaimed_property_report_date="03/15/2024",
                        unclaimed_property_amount_remitted=12.5)
        self.assertIs(ca.filed_unclaimed_property_report, True)
        self.assertEqual(ca.unclaimed_property_report_date, "03/15/2024")
        self.assertEqual(ca.unclaimed_property_amount_remitted, 12.5)
        self.assertIsNone(self._load().filed_unclaimed_property_report)

    def test_bad_combinations_refused_at_load(self):
        self._load(filed_unclaimed_property_report=False)  # reachability
        for kw in ({"filed_unclaimed_property_report": True},
                   {"filed_unclaimed_property_report": False,
                    "unclaimed_property_amount_remitted": 1.0},
                   {"filed_unclaimed_property_report": "yes"},
                   {"filed_unclaimed_property_report": True,
                    "unclaimed_property_report_date": "bad",
                    "unclaimed_property_amount_remitted": 1.0}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self._load(**kw)


if __name__ == "__main__":
    unittest.main()
