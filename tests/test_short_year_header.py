"""Short tax year header dates: ``s_corp_return.tax_year_beginning`` /
``tax_year_ending`` (ISO ``YYYY-MM-DD`` strings or YAML dates) print in the
entity forms' header date boxes — Form 1120-S page 1, Schedule K-1 (1120-S),
Form 100S Side 1, Schedule K-1 (100S). The motivating case is a 2021 first year
03/10/2021-12/31/2021; the fields are year-agnostic, so every year's cells are
exercised. None (the default) = calendar year = all those boxes blank.

Validation: both or neither; ending must be Dec 31 of the scenario year (fiscal
years are unsupported); beginning must fall in the scenario year and not after
the ending.

Cells certified per year from each template's header caption against widget
Rects. 1120-S: "tax year beginning [f1_1] , <year>, ending [f1_2] , 20 [f1_3]"
-- beginning and ending month/day ("03/10", "12/31") plus the two-digit ending
year (the beginning year is preprinted); path group CalendarYear-TypePrint_
ReadOrder through 2024, Date_Name_ReadOrder in 2025. Fed K-1: five boxes
month/day beginning, month/day/4-digit-year ending (beginning year preprinted);
group Header[0] through 2023 and Header[0].ForCalendarYear[0] from 2024.
100S and CA K-1: full "mm/dd/yyyy" strings in 1001 / 1002 (bare names through
2023, "100S Form " / "Sch K-1 (100s) " prefixed after).

Synthetic fixture only."""
import datetime
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.test_scorp_amended_marks import _scenario_yaml_dict

_FED = tuple(years.SCORP_FEDERAL_YEARS)
_CA = tuple(years.CA_SCORP_YEARS)


def _v(pdf):
    return {k: (None if x.get("/V") is None else str(x["/V"]))
            for k, x in (PdfReader(str(pdf)).get_fields() or {}).items()}


def _blank(x):
    return x in (None, "")


def _fed_cells(year):
    grp = "Date_Name_ReadOrder[0]" if year == 2025 else \
        "CalendarYear-TypePrint_ReadOrder[0]"
    return [f"topmostSubform[0].Page1[0].{grp}.f1_{n}[0]" for n in (1, 2, 3)]


def _k1_cells(year):
    grp = "Header[0].ForCalendarYear[0]" if year >= 2024 else "Header[0]"
    return [f"topmostSubform[0].Page1[0].{grp}.f1_0{n}[0]" for n in range(1, 6)]


def _ca_cells(year):
    return [f"100S Form {n}" if year >= 2024 else n for n in ("1001", "1002")]


def _ca_k1_cells(year):
    return [f"Sch K-1 (100s) {n}" if year >= 2024 else n
            for n in ("1001", "1002")]


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _scenario(self, year, begin, end):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.tax_year_beginning = begin
        s.s_corp_return.tax_year_ending = end
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        return s

    def _short(self, year):
        return (datetime.date(year, 3, 10), datetime.date(year, 12, 31))

    def _fed(self, year, begin, end):
        out = Path(self._tmp.name) / f"f_{year}_{begin}_{end}"
        self.orch.run_full_federal_scorp_return(
            self._scenario(year, begin, end), out)
        return out

    def _ca(self, year, begin, end):
        out = Path(self._tmp.name) / f"c_{year}_{begin}_{end}"
        self.orch.run_full_california_scorp_return(
            self._scenario(year, begin, end), out)
        return out


class StatedShortYearTests(_EmitBase):
    def test_form_1120s_header(self):
        for year in _FED:
            with self.subTest(year=year):
                v = _v(self._fed(year, *self._short(year))
                       / f"f1120s_{year}.pdf")
                b, e, yy = (v[c] for c in _fed_cells(year))
                self.assertEqual((b, e, yy), ("03/10", "12/31", str(year)[2:]))

    def test_federal_k1_header(self):
        for year in _FED:
            with self.subTest(year=year):
                v = _v(self._fed(year, *self._short(year))
                       / f"f1120s_k1_1_{year}.pdf")
                got = tuple(v[c] for c in _k1_cells(year))
                self.assertEqual(got, ("03", "10", "12", "31", str(year)))

    def test_form_100s_header(self):
        for year in _CA:
            with self.subTest(year=year):
                v = _v(self._ca(year, *self._short(year))
                       / f"f100s_{year}.pdf")
                got = tuple(v[c] for c in _ca_cells(year))
                self.assertEqual(
                    got, (f"03/10/{year}", f"12/31/{year}"))

    def test_ca_k1_header(self):
        for year in _CA:
            with self.subTest(year=year):
                v = _v(self._ca(year, *self._short(year))
                       / f"f100s_k1_1_{year}.pdf")
                got = tuple(v[c] for c in _ca_k1_cells(year))
                self.assertEqual(
                    got, (f"03/10/{year}", f"12/31/{year}"))

    def test_full_year_stated_prints_the_calendar_dates(self):
        year = 2023
        v = _v(self._fed(year, datetime.date(year, 1, 1),
                         datetime.date(year, 12, 31)) / f"f1120s_{year}.pdf")
        self.assertEqual(tuple(v[c] for c in _fed_cells(year)),
                         ("01/01", "12/31", "23"))


class UnstatedCalendarYearTests(_EmitBase):
    def test_all_header_date_boxes_blank_when_unstated(self):
        for year in _CA:
            with self.subTest(year=year):
                fed = self._fed(year, None, None)
                ca = self._ca(year, None, None)
                f = _v(fed / f"f1120s_{year}.pdf")
                k = _v(fed / f"f1120s_k1_1_{year}.pdf")
                c = _v(ca / f"f100s_{year}.pdf")
                ck = _v(ca / f"f100s_k1_1_{year}.pdf")
                for cell in _fed_cells(year):
                    self.assertTrue(_blank(f[cell]), cell)
                for cell in _k1_cells(year):
                    self.assertTrue(_blank(k[cell]), cell)
                for cell in _ca_cells(year):
                    self.assertTrue(_blank(c[cell]), cell)
                for cell in _ca_k1_cells(year):
                    self.assertTrue(_blank(ck[cell]), cell)
                # control: the same emits do fill neighbouring header cells
                self.assertEqual(c[("100S Form 1003" if year >= 2024
                                    else "1003")], "Example S-Corp Inc.")


class ValidationTests(_EmitBase):
    def test_refused_combinations_at_emit(self):
        y = 2021
        d = datetime.date
        cases = [
            (d(y, 3, 10), None), (None, d(y, 12, 31)),            # one alone
            (d(y, 3, 10), d(y, 11, 30)),                          # not Dec 31
            (d(y, 3, 10), d(y + 1, 12, 31)),                      # wrong year
            (d(y - 1, 3, 10), d(y, 12, 31)),                      # begin prior yr
            (d(y, 12, 31), d(y, 12, 30)),                         # begin > end
        ]
        for begin, end in cases:
            with self.subTest(begin=begin, end=end):
                with self.assertRaises(ValueError):
                    self._fed(y, begin, end)
                with self.assertRaises(ValueError):
                    self._ca(y, begin, end)

    def test_begin_equal_to_end_is_allowed(self):
        y = 2021
        self._fed(y, datetime.date(y, 12, 31), datetime.date(y, 12, 31))


class LoaderTests(unittest.TestCase):
    def _load(self, year=2021, **extra):
        data = _scenario_yaml_dict(extra_scorp=extra or None)
        data["config"]["year"] = year
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return

    def test_iso_strings_and_dates_load(self):
        r = self._load(tax_year_beginning="2021-03-10",
                       tax_year_ending=datetime.date(2021, 12, 31))
        self.assertEqual(r.tax_year_beginning, datetime.date(2021, 3, 10))
        self.assertEqual(r.tax_year_ending, datetime.date(2021, 12, 31))

    def test_absent_default_calendar_year(self):
        r = self._load()
        self.assertIsNone(r.tax_year_beginning)
        self.assertIsNone(r.tax_year_ending)

    def test_bad_values_refused_at_load(self):
        self._load(tax_year_beginning="2021-03-10",
                   tax_year_ending="2021-12-31")  # reachability
        for kw in ({"tax_year_beginning": "2021-03-10"},
                   {"tax_year_ending": "2021-12-31"},
                   {"tax_year_beginning": "2021-03-10",
                    "tax_year_ending": "2021-11-30"},
                   {"tax_year_beginning": "03/10/2021",
                    "tax_year_ending": "2021-12-31"},
                   {"tax_year_beginning": "2020-03-10",
                    "tax_year_ending": "2021-12-31"},
                   {"tax_year_beginning": 5, "tax_year_ending": "2021-12-31"}):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self._load(**kw)


if __name__ == "__main__":
    unittest.main()
