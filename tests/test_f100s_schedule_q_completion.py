"""CA Form 100S Schedule Q (Side 3) completion — filled-emit read-back and pixel
tests: Question C (activity code, business activity, product or service), G
(maximum shareholders), H (date business began in California), L (accounting
method), the derived Question P answer, and the stated Yes/No answers D, E, Q,
R, S.

Cell tables below are independent of the mapping module, certified per year by
printed caption + widget Rect: Yes box left (/0), No box right (/1) — except the
2021 template, whose P / Q radios carry '/Yes' / '/No' style tokens, and whose
2022 Question P group is named plain "3021" (2023+ "3021 RB"). Question L is
three checkboxes through 2023 and one radio (/0 Cash /1 Accrual /2 Other) from
2024. Names are bare through 2023 and "100S Form " prefixed after.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
import datetime
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.models import AccountingMethod, SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_ALL = tuple(years.CA_SCORP_YEARS)
_FLOOR = (2022, 2023, 2024, 2025)


def _n(year, bare):
    return bare if year <= 2023 else f"100S Form {bare}"


_YESNO_FIELD = {
    "water_edge_basis": "3004 RB",
    "includes_qsubs": "3005 rb",
    "included_reportable_transaction": "3022 rb",
    "filed_federal_schedule_m3": "3023 rb",
    "ftb_3544_attached": "3024 rb",
}


def _yesno(year, question):
    field = _n(year, _YESNO_FIELD[question])
    return {True: (field, "/0"), False: (field, "/1")}


def _line_p(year):  # derived: 100% CA apportionment => NOT using Schedule R
    if year == 2021:
        return {False: ("3021 rb", "/No"), True: ("3021 rb", "/Yes")}
    field = _n(year, "3021" if year == 2022 else "3021 RB")
    return {True: (field, "/0"), False: (field, "/1")}


def _line_l(year):
    if year <= 2023:
        return {m: (f"{3013 + i} cb", "/Yes") for i, m in
                enumerate(("cash", "accrual", "other"))}
    return {m: (_n(year, "3013 RB"), f"/{i}") for i, m in
            enumerate(("cash", "accrual", "other"))}


def _values(pdf):
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in (PdfReader(str(pdf)).get_fields() or {}).items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, method=None, **ca_kw):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        if method is not None:
            s.s_corp_return.schedule_b_answers.accounting_method = method
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True, **ca_kw)
        out = Path(self._tmp.name) / f"q_{year}_{method}_{sorted(ca_kw.items())}"
        self.orch.run_full_california_scorp_return(s, out)
        return out / f"f100s_{year}.pdf"

    def _assert_only(self, pdf, cells, chosen):
        vals = _values(pdf)
        field, on = cells[chosen]
        self.assertEqual(vals[field], on)
        page, rect = widget_rect(pdf, field, on)
        self.assertGreater(
            dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0,
            f"{chosen}: marked box draws no ink")
        for other, (ofield, oon) in cells.items():
            if other == chosen:
                continue
            if ofield == field:
                self.assertNotEqual(vals[field], oon)
            else:
                self.assertIn(vals[ofield], (None, "/Off"), other)


class TemplateCellsExistTests(unittest.TestCase):
    def test_every_certified_cell_is_a_real_widget(self):
        for year in _ALL:
            tmpl = f"pdfs/california/{year}/f100s.pdf"
            fields = PdfReader(tmpl).get_fields() or {}
            for num in ("3001", "3002", "3003", "3009", "3010"):
                self.assertEqual(str(fields[_n(year, num)].get("/FT")), "/Tx")
            tables = [_line_p(year), _line_l(year)]
            if year in _FLOOR:
                tables += [_yesno(year, q) for q in _YESNO_FIELD]
            for cells in tables:
                for key, (field, on) in cells.items():
                    with self.subTest(year=year, key=key):
                        widget_rect(tmpl, field, on)  # KeyError if absent


class TextCellTests(_EmitBase):
    def test_activity_product_shareholders_and_date_print_every_year(self):
        for year in _ALL:
            with self.subTest(year=year):
                vals = _values(self._emit(
                    year, max_shareholders=3,
                    date_business_began_in_ca=datetime.date(2019, 6, 1)))
                self.assertEqual(vals[_n(year, "3001")], "541990")
                self.assertEqual(vals[_n(year, "3002")], "Services")
                self.assertEqual(vals[_n(year, "3003")], "Consulting")
                self.assertEqual(vals[_n(year, "3009")], "3")
                self.assertEqual(vals[_n(year, "3010")], "06/01/2019")

    def test_unstated_shareholders_and_began_date_stay_blank(self):
        for year in _ALL:
            with self.subTest(year=year):
                vals = _values(self._emit(year))
                self.assertEqual(vals[_n(year, "3001")], "541990")  # control
                self.assertIn(vals[_n(year, "3009")], (None, ""))
                self.assertIn(vals[_n(year, "3010")], (None, ""))


class AccountingMethodTests(_EmitBase):
    def test_each_method_marks_only_its_own_box(self):
        for year in _ALL:
            for method in AccountingMethod:
                with self.subTest(year=year, method=method.value):
                    pdf = self._emit(year, method=method)
                    self._assert_only(pdf, _line_l(year), method.value)


class DerivedQuestionPTests(_EmitBase):
    def test_apportionment_ca_only_answers_p_no(self):
        for year in _ALL:
            with self.subTest(year=year):
                self._assert_only(self._emit(year), _line_p(year), False)


class StatedYesNoTests(_EmitBase):
    def test_each_answer_marks_only_its_own_box(self):
        for year in _FLOOR:
            for question in _YESNO_FIELD:
                for answer in (True, False):
                    with self.subTest(year=year, q=question, a=answer):
                        pdf = self._emit(year, **{question: answer})
                        self._assert_only(pdf, _yesno(year, question), answer)

    def test_unstated_leaves_boxes_unmarked(self):
        for year in _FLOOR:
            with self.subTest(year=year):
                vals = _values(self._emit(year))
                for q in _YESNO_FIELD:
                    for field, _ in _yesno(year, q).values():
                        self.assertIn(vals[field], (None, "/Off"), q)

    def test_2021_refuses_a_stated_answer(self):
        for q in _YESNO_FIELD:
            with self.subTest(q=q), self.assertRaises(ValueError):
                self._emit(2021, **{q: True})


class LoaderTests(unittest.TestCase):
    def _load(self, ca_extra):
        data = _scenario_yaml_dict()
        data["s_corp_return"]["ca"] = {
            "first_year": False, "estimated_tax_payments": 0.0,
            "prior_year_overpayment_applied": 0.0,
            "state_tax_deducted_federally": 0.0,
            "depreciation_adjustment": 0.0, "apportionment_ca_only": True,
            **ca_extra}
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return.ca

    def test_stated_values_load(self):
        ca = self._load({
            "max_shareholders": 2,
            "date_business_began_in_ca": datetime.date(2019, 6, 1),
            "water_edge_basis": False, "includes_qsubs": False,
            "included_reportable_transaction": False,
            "filed_federal_schedule_m3": False, "ftb_3544_attached": True})
        self.assertEqual(ca.max_shareholders, 2)
        self.assertEqual(ca.date_business_began_in_ca,
                         datetime.date(2019, 6, 1))
        self.assertIs(ca.ftb_3544_attached, True)
        self.assertIs(ca.water_edge_basis, False)

    def test_absent_default_unstated(self):
        ca = self._load({})
        self.assertIsNone(ca.max_shareholders)
        self.assertIsNone(ca.date_business_began_in_ca)
        self.assertIsNone(ca.includes_qsubs)

    def test_bad_values_refused(self):
        self._load({"max_shareholders": 1})  # reachability
        for bad in ({"max_shareholders": 0}, {"max_shareholders": -2},
                    {"max_shareholders": True}, {"max_shareholders": 1.5},
                    {"max_shareholders": "3"},
                    {"water_edge_basis": "no"},
                    {"date_business_began_in_ca": "someday"}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load(bad)


if __name__ == "__main__":
    unittest.main()
