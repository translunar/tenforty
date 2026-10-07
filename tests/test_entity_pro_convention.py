"""Professional-software print convention on the entity forms: a DETAIL line
(an input-driven amount) prints only when nonzero; a COMPUTED result or total
prints always, even when 0.

Covers Form 1120-S page 1 (income, deductions, tax and payments), CA Form 100S
(Side 1 state adjustments, Side 2 payments and totals, Side 4 Schedule F, Side 6
Schedule K) for every year 2021-2025. Federal Schedule K has its own file
(test_f1120s_sch_k_pro_convention.py).

1120-S page 1 income/deduction cells are certified per year by the printed line
captions: field numbers run in line order from 1a (f1_13 on 2021-2024, f1_17 on
2025); 2023-2025 carry the extra line 19 "Energy efficient ..." field; 2021-2022
do not (so "Other deductions" is one field earlier there). Tax / payment cells
are looked up through the mapping (their certification lives in
test_pdf_f1120s_mapping.py).

Footing: a total must equal the sum of its operands with blanks counted as 0.

Synthetic fixture only."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.models import OtherDeductionComponent, SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year

_P1 = "topmostSubform[0].Page1[0].f1_"
_FED = tuple(years.SCORP_FEDERAL_YEARS)
_CA = tuple(years.CA_SCORP_YEARS)


def _fields(pdf):
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in (PdfReader(str(pdf)).get_fields() or {}).items()}


def _blank(v):
    return v in (None, "")


def _fed_cells(year):
    """line label -> field path for 1120-S page 1 income/deduction lines."""
    n0 = 17 if year == 2025 else 13
    names = ["1a", "1b", "1c", "2", "3", "4", "5", "6",
             "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18"]
    out = {name: f"{_P1}{n0 + i}[0]" for i, name in enumerate(names)}
    nxt = n0 + len(names)
    if year >= 2023:
        out["19"] = f"{_P1}{nxt}[0]"
        nxt += 1
    out["20"] = f"{_P1}{nxt}[0]"        # Other deductions
    out["tot_ded"] = f"{_P1}{nxt + 1}[0]"
    out["obi"] = f"{_P1}{nxt + 2}[0]"
    return out


_FED_DETAIL_INCOME = ("1b", "2", "4", "5")
_FED_ALWAYS_INCOME = ("1a", "1c", "3", "6")
_FED_DETAIL_DED = ("7", "8", "9", "10", "11", "12", "13", "14", "15", "16",
                   "17", "18", "20")


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()


class Fed1120SPage1Tests(_EmitBase):
    def _emit(self, year, **kw):
        s = _make_v1_scenario(**{k: v for k, v in kw.items()
                                 if k in ("gross_receipts",
                                          "compensation_of_officers")})
        set_tax_year(s, year)
        inc, ded = s.s_corp_return.income, s.s_corp_return.deductions
        for k, v in kw.items():
            if hasattr(inc, k) and k != "gross_receipts":
                setattr(inc, k, v)
            elif hasattr(ded, k) and k != "compensation_of_officers":
                setattr(ded, k, v)
        # PDF emit requires the line 19 statement rows (merge of the
        # other-deductions-statement gate with this branch's fixtures).
        if ded.other_deductions and not ded.other_deductions_components:
            ded.other_deductions_components = [
                OtherDeductionComponent("Synthetic misc expense",
                                        ded.other_deductions)]
        out = Path(self._tmp.name) / f"p1_{year}_{sorted(kw.items())}"
        self.orch.run_full_federal_scorp_return(s, out)
        return _fields(out / f"f1120s_{year}.pdf")

    def test_inactive_detail_lines_blank_and_computed_lines_print(self):
        for year in _FED:
            with self.subTest(year=year):
                v, c = self._emit(year), _fed_cells(year)
                for line in _FED_ALWAYS_INCOME:
                    self.assertEqual(v[c[line]], "100000", f"1120S {line}")
                for line in _FED_DETAIL_INCOME:
                    self.assertTrue(_blank(v[c[line]]), f"1120S {line}")
                self.assertEqual(v[c["7"]], "30000")        # active detail line
                for line in _FED_DETAIL_DED:
                    if line != "7":
                        self.assertTrue(_blank(v[c[line]]), f"1120S {line}")
                if year >= 2023:
                    self.assertTrue(_blank(v[c["19"]]))
                self.assertEqual(v[c["tot_ded"]], "30000")
                self.assertEqual(v[c["obi"]], "70000")

    def test_nonzero_detail_lines_print(self):
        for year in _FED:
            with self.subTest(year=year):
                v = self._emit(
                    year, returns_and_allowances=500.0, cogs_aggregate=600.0,
                    net_gain_loss_4797=700.0, other_income=800.0,
                    salaries_wages=111.0, rents=222.0, depletion=33.0,
                    other_deductions=44.0)
                c = _fed_cells(year)
                self.assertEqual(v[c["1b"]], "500")
                self.assertEqual(v[c["2"]], "600")
                self.assertEqual(v[c["4"]], "700")
                self.assertEqual(v[c["5"]], "800")
                self.assertEqual(v[c["8"]], "111")
                self.assertEqual(v[c["11"]], "222")
                self.assertEqual(v[c["15"]], "33")
                self.assertEqual(v[c["20"]], "44")

    def test_totals_print_when_zero_and_foot_with_blanks_as_zero(self):
        for year in _FED:
            with self.subTest(year=year):
                v = self._emit(year, gross_receipts=0.0,
                               compensation_of_officers=0.0)
                c = _fed_cells(year)
                for line in _FED_ALWAYS_INCOME + ("tot_ded", "obi"):
                    self.assertEqual(v[c[line]], "0", line)
                for line in _FED_DETAIL_INCOME + _FED_DETAIL_DED:
                    self.assertTrue(_blank(v[c[line]]), line)

    def test_deductions_foot_with_blanks_counted_as_zero(self):
        for year in _FED:
            with self.subTest(year=year):
                v = self._emit(year, salaries_wages=111.0, rents=222.0)
                c = _fed_cells(year)
                lines = [l for l in c if l in _FED_DETAIL_DED
                         or (l == "19" and year >= 2023)]
                self.assertEqual(
                    sum(int(v[c[l]] or 0) for l in lines),
                    int(v[c["tot_ded"]]))

    def test_inactive_tax_and_payment_inputs_blank_totals_print(self):
        always = ("f1120s_total_tax", "f1120s_total_payments",
                  "f1120s_amount_owed", "f1120s_overpayment")
        detail = ("f1120s_net_passive_income_tax",
                  "f1120s_tax_deposited_with_7004",
                  "f1120s_credit_for_federal_excise_tax",
                  "f1120s_estimated_tax_penalty",
                  "f1120s_credited_to_next_year")
        for year in _FED:
            with self.subTest(year=year):
                v = self._emit(year)
                mp = PdfF1120S.get_mapping(year)
                for k in detail:
                    self.assertTrue(_blank(v[mp[k]]), k)
                for k in always:
                    cell = mp.get(k)
                    if cell is None:     # 23c / 24a live in aggregations
                        continue
                    self.assertEqual(v[cell], "0", k)
                agg = PdfF1120S.get_aggregations(year)
                for cell, keys in agg.items():
                    if keys[0] == "f1120s_total_tax":
                        self.assertEqual(v[cell], "0")      # 23c always
                    else:
                        self.assertTrue(_blank(v[cell]))    # 24a detail sum


def _n(year, bare):
    return bare if year <= 2023 else f"100S Form {bare}"


class Ca100SConventionTests(_EmitBase):
    def _emit(self, year, addback=0.0, depr=0.0, estimated=0.0,
              prior=0.0, obi_zero=False, **ded):
        if obi_zero:
            s = _make_v1_scenario(gross_receipts=30000.0,
                                  compensation_of_officers=30000.0)
        else:
            s = _make_v1_scenario()
        set_tax_year(s, year)
        for k, v in ded.items():
            setattr(s.s_corp_return.deductions, k, v)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=estimated,
            prior_year_overpayment_applied=prior,
            state_tax_deducted_federally=addback,
            depreciation_adjustment=depr, apportionment_ca_only=True)
        out = Path(self._tmp.name) / (
            f"ca_{year}_{addback}_{depr}_{estimated}_{prior}_{obi_zero}"
            f"_{sorted(ded.items())}")
        self.orch.run_full_california_scorp_return(s, out)
        return _fields(out / f"f100s_{year}.pdf")

    def test_side_1_detail_lines_blank_when_zero_totals_print(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year)
                self.assertEqual(v[_n(year, "1031")], "70000")  # computed
                for n in ("1032", "1033", "1034", "1035", "1036", "1037"):
                    if year == 2024 and n == "1034":
                        n = "034"   # the 2024 template's own name for line 4
                    self.assertTrue(_blank(v[_n(year, n)]), n)
                self.assertEqual(v[_n(year, "1038")], "70000")  # line 8 total

    def test_side_1_nonzero_adjustments_print_and_foot(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year, addback=1000.0, depr=-500.0)
                self.assertEqual(v[_n(year, "1032")], "1000")
                self.assertEqual(v[_n(year, "1035")], "-500")
                parts = sum(int(v[_n(year, n)] or 0) for n in (
                    "1031", "1032", "1033", "1035", "1036", "1037"))
                self.assertEqual(int(v[_n(year, "1038")]), parts)

    def test_side_2_payment_inputs_blank_when_zero_totals_print(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year)
                for n in ("2028", "2029"):                  # lines 31, 32
                    self.assertTrue(_blank(v[_n(year, n)]), n)
                self.assertEqual(v[_n(year, "2033")], "0")
                self.assertEqual(v[_n(year, "2035")], "0")
                self.assertEqual(v[_n(year, "2038")], "0")

    def test_side_2_nonzero_payments_print(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year, estimated=200.0, prior=50.0)
                self.assertEqual(v[_n(year, "2029")], "200")
                self.assertEqual(v[_n(year, "2028")], "50")
                self.assertEqual(v[_n(year, "2033")], "250")

    def test_zero_income_totals_all_print(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year, obi_zero=True)
                for n in ("1031", "1038", "2005", "2006", "2007", "2012"):
                    self.assertEqual(v[_n(year, n)], "0", n)

    def test_schedule_f_detail_blank_totals_print(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year)
                for n in ("4001", "4003", "4005", "4008"):  # 1a 1c 3 6
                    self.assertEqual(v[_n(year, n)], "100000", n)
                self.assertEqual(v[_n(year, "4009")], "30000")  # line 7
                for n in ("4002", "4004", "4006", "4007", "4010", "4011",
                          "4012", "4013", "4014", "4015", "4018 a", "4018 b",
                          "4019", "4020", "4021", "4024"):
                    self.assertTrue(_blank(v[_n(year, n)]), n)
                self.assertEqual(v[_n(year, "4025")], "30000")
                self.assertEqual(v[_n(year, "4026")], "70000")

    def test_schedule_f_totals_print_when_zero(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year, obi_zero=True)
                for n in ("4003", "4005", "4008", "4025"):
                    self.assertEqual(v[_n(year, n)], "30000", n)
                self.assertEqual(v[_n(year, "4026")], "0")   # line 22 prints 0

    def test_schedule_k_line_1_and_19_print_even_when_zero_adjustment(self):
        for year in _CA:
            with self.subTest(year=year):
                v = self._emit(year)
                self.assertEqual(
                    (v[_n(year, "6001")], v[_n(year, "6002")],
                     v[_n(year, "6003")]), ("70000", "0", "70000"))


if __name__ == "__main__":
    unittest.main()
