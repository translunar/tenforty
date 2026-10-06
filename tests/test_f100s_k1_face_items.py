"""California Schedule K-1 (100S) face items beyond identity / Item A / Line 1:
Line B shares (beginning / ending), Line C loans from shareholder (beginning /
ending), Line E "final Schedule K-1", the shareholder and corporation address
cells, and (2024+) Line H corporation's total shares.

Drives ``run_full_california_scorp_return`` for every CA S-corp year, reopens the
REAL filled K-1 and asserts values and ink. The cell table is written
independently of the mapping module and certified per template by printed
caption: the field NUMBERS are stable across years (Line B 1017/1018, Line C
1019/1020) but the name namespace differs (bare through 2023, "Sch K-1 (100s) "
after), Line E is two checkboxes through 2023 and ONE radio from 2024 whose
final / amended tokens differ per year (2024 '/1. A final Schedule K-1' vs
'/(2) An amended Schedule K-1.'; 2025 '/0' final vs '/1' amended, per the
radio's /Opt), and Line H exists only on the 2024 and 2025 forms.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year


def _n(year, number):
    return number if year <= 2023 else f"Sch K-1 (100s) {number}"


# year -> (final field, final on-state, amended field, amended on-state)
_LINE_E = {
    2021: ("1022 cb", "/Yes", "1023 cb", "/Yes"),
    2022: ("1022 cb", "/Yes", "1023 cb", "/Yes"),
    2023: ("1022 cb", "/Yes", "1023 cb", "/Yes"),
    2024: ("Sch K-1 (100s) 1023 RB", "/1. A final Schedule K-1",
           "Sch K-1 (100s) 1023 RB", "/(2) An amended Schedule K-1."),
    2025: ("Sch K-1 (100s) 1023 RB", "/0",
           "Sch K-1 (100s) 1023 RB", "/1"),
}
_SHARED_RADIO_YEARS = (2024, 2025)


# Line F "What type of entity is this shareholder?" — printed choices, left to
# right: Individual, Estate/trust, Qualified exempt organization, Single member
# LLC. 2021-2023: four separate checkboxes 1024-1027 (on /Yes). 2024-2025: one
# radio 1024 RB whose widgets /0../3 sit left to right under (a)-(d).
_F_CHOICES = ("individual", "estate_trust", "qualified_exempt_organization",
              "single_member_llc")


def _line_f(year):
    if year <= 2023:
        return {c: (f"{1024 + i} cb", "/Yes") for i, c in enumerate(_F_CHOICES)}
    return {c: ("Sch K-1 (100s) 1024 RB", f"/{i}")
            for i, c in enumerate(_F_CHOICES)}


# Line G "Is this shareholder a resident of California?": Yes box left (/0), No
# box right (/1), one radio 1028 rb every year.
def _line_g(year):
    return {True: (_n(year, "1028 rb"), "/0"), False: (_n(year, "1028 rb"), "/1")}


def _values(pdf):
    fields = PdfReader(str(pdf)).get_fields() or {}
    return {k: (None if v.get("/V") is None else str(v["/V"]))
            for k, v in fields.items()}


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, stated=True, final=False, amended=False, pcts=None):
        s = _make_v1_scenario(shareholder_pcts=pcts)
        set_tax_year(s, year)
        r = s.s_corp_return
        r.amended_return = amended
        r.total_shares_beginning = 2500.0
        r.total_shares_end = 2400.0
        r.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        for i, sh in enumerate(r.shareholders):
            if stated:
                sh.shares_beginning = 1000.0 + i
                sh.shares_end = 900.5 + i
                sh.loans_beginning = 12345.0 + i
                sh.loans_end = 6789.0 + i
        r.shareholders[0].final_k1 = final
        out = Path(self._tmp.name) / f"ca_{year}_{stated}_{final}_{amended}"
        self.orch.run_full_california_scorp_return(s, out)
        return out


class TemplateCellsExistTests(unittest.TestCase):
    def test_certified_cells_exist_on_each_template(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                fields = PdfReader(
                    f"pdfs/california/{year}/f100s_k1.pdf").get_fields() or {}
                for num in ("1005", "1006", "1007", "1008", "1012", "1013",
                            "1014", "1015", "1017", "1018", "1019", "1020"):
                    self.assertEqual(
                        str(fields[_n(year, num)].get("/FT")), "/Tx", num)
                self.assertIn(_LINE_E[year][0], fields)
                if year in _SHARED_RADIO_YEARS:
                    # Line H. (On 2021-2023 bare "1029"/"1030" are the Line 1
                    # income columns, NOT Line H, which those forms lack.)
                    for num in ("1029", "1030"):
                        self.assertEqual(
                            str(fields[_n(year, num)].get("/FT")), "/Tx", num)


class StatedFaceItemTests(_EmitBase):
    def test_shares_loans_and_addresses_print(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                out = self._emit(year)
                vals = _values(out / f"f100s_k1_1_{year}.pdf")
                self.assertEqual(vals[_n(year, "1003")], "Taxpayer A")  # control
                want = {"1017": "1000", "1018": "900.5",
                        "1019": "12345", "1020": "6789",
                        "1005": "1 Example Ave", "1006": "Example City",
                        "1007": "EX", "1008": "00000",
                        "1012": "1 Example Ave", "1013": "Example City",
                        "1014": "EX", "1015": "00000"}
                for num, text in want.items():
                    self.assertEqual(vals[_n(year, num)], text, f"{year} {num}")

    def test_each_shareholder_gets_their_own_figures(self):
        for year in (2022, 2025):
            with self.subTest(year=year):
                out = self._emit(year, pcts=[60.0, 40.0])
                second = _values(out / f"f100s_k1_2_{year}.pdf")
                self.assertEqual(second[_n(year, "1017")], "1001")
                self.assertEqual(second[_n(year, "1020")], "6790")

    def test_unstated_figures_leave_cells_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year, stated=False)
                               / f"f100s_k1_1_{year}.pdf")
                for num in ("1017", "1018", "1019", "1020"):
                    self.assertIn(vals[_n(year, num)], (None, ""), num)

    def test_corporation_total_shares_only_where_the_form_has_the_line(self):
        for year in _SHARED_RADIO_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year) / f"f100s_k1_1_{year}.pdf")
                self.assertEqual(vals[_n(year, "1029")], "2500")
                self.assertEqual(vals[_n(year, "1030")], "2400")


class FinalK1Tests(_EmitBase):
    def test_final_marks_its_own_box_visibly_and_not_amended(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year, final=True) / f"f100s_k1_1_{year}.pdf"
                f_field, f_on, a_field, a_on = _LINE_E[year]
                vals = _values(pdf)
                self.assertEqual(vals[f_field], f_on)
                if year not in _SHARED_RADIO_YEARS:
                    self.assertIn(vals[a_field], (None, "/Off"))
                page, rect = widget_rect(pdf, f_field, f_on)
                self.assertGreater(
                    dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0,
                    f"{year}: Final box marked but draws no ink")

    def test_default_is_not_final(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year) / f"f100s_k1_1_{year}.pdf")
                f_field, f_on, _, _ = _LINE_E[year]
                self.assertNotEqual(vals[f_field], f_on)

    def test_final_applies_only_to_the_flagged_shareholder(self):
        year = 2023
        out = self._emit(year, final=True, pcts=[60.0, 40.0])
        f_field = _LINE_E[year][0]
        self.assertEqual(
            _values(out / f"f100s_k1_1_{year}.pdf")[f_field], "/Yes")
        self.assertIn(
            _values(out / f"f100s_k1_2_{year}.pdf")[f_field], (None, "/Off"))

    def test_final_and_amended_are_two_boxes_through_2023(self):
        for year in (2021, 2022, 2023):
            with self.subTest(year=year):
                vals = _values(self._emit(year, final=True, amended=True)
                               / f"f100s_k1_1_{year}.pdf")
                f_field, _, a_field, _ = _LINE_E[year]
                self.assertEqual(vals[f_field], "/Yes")
                self.assertEqual(vals[a_field], "/Yes")

    def test_final_plus_amended_refused_where_one_radio_holds_both(self):
        for year in _SHARED_RADIO_YEARS:
            with self.subTest(year=year):
                with self.assertRaises(ValueError) as cm:
                    self._emit(year, final=True, amended=True)
                self.assertIn("final", str(cm.exception).lower())
                self.assertIn("amended", str(cm.exception).lower())

    def test_amended_alone_still_works_on_the_shared_radio(self):
        for year in _SHARED_RADIO_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(year, amended=True)
                               / f"f100s_k1_1_{year}.pdf")
                _, _, a_field, a_on = _LINE_E[year]
                self.assertEqual(vals[a_field], a_on)


class CorporationNumberTests(_EmitBase):
    def _emit_with_number(self, year, number="1234567"):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True, corporation_number=number)
        out = Path(self._tmp.name) / f"num_{year}_{number}"
        self.orch.run_full_california_scorp_return(s, out)
        return out

    def test_number_prints_on_100s_and_k1_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                out = self._emit_with_number(year)
                f100s = _values(out / f"f100s_{year}.pdf")
                k1 = _values(out / f"f100s_k1_1_{year}.pdf")
                prefix = "" if year <= 2023 else "100S Form "
                self.assertEqual(f100s[prefix + "1004"], "1234567")
                self.assertEqual(k1[_n(year, "1010")], "1234567")
                # control: the FEIN beside it prints in the same emit
                self.assertEqual(k1[_n(year, "1009")], "00-0000000")

    def test_twelve_digit_file_number_prints(self):
        out = self._emit_with_number(2025, "201912345678")
        self.assertEqual(
            _values(out / "f100s_k1_1_2025.pdf")[_n(2025, "1010")],
            "201912345678")

    def test_unstated_number_stays_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                out = self._emit(year)
                prefix = "" if year <= 2023 else "100S Form "
                self.assertIn(
                    _values(out / f"f100s_{year}.pdf")[prefix + "1004"], (None, ""))
                self.assertIn(
                    _values(out / f"f100s_k1_1_{year}.pdf")[_n(year, "1010")],
                    (None, ""))


class EntityTypeAndResidencyTests(_EmitBase):
    def _emit_one(self, year, **sh_kw):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        for k, v in sh_kw.items():
            setattr(s.s_corp_return.shareholders[0], k, v)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True)
        out = Path(self._tmp.name) / f"et_{year}_{sorted(sh_kw.items())}"
        self.orch.run_full_california_scorp_return(s, out)
        return out / f"f100s_k1_1_{year}.pdf"

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

    def test_certified_cells_are_real_widgets_with_those_on_states(self):
        for year in years.CA_SCORP_YEARS:
            tmpl = f"pdfs/california/{year}/f100s_k1.pdf"
            for cells in (_line_f(year), _line_g(year)):
                for key, (field, on) in cells.items():
                    with self.subTest(year=year, key=key):
                        widget_rect(tmpl, field, on)  # KeyError if absent

    def test_every_entity_type_marks_only_its_own_box(self):
        for year in years.CA_SCORP_YEARS:
            for choice in _F_CHOICES:
                with self.subTest(year=year, choice=choice):
                    pdf = self._emit_one(year, ca_entity_type=choice)
                    self._assert_only(pdf, _line_f(year), choice)

    def test_resident_yes_and_no_mark_only_their_own_box(self):
        for year in years.CA_SCORP_YEARS:
            for answer in (True, False):
                with self.subTest(year=year, answer=answer):
                    pdf = self._emit_one(year, ca_resident=answer)
                    self._assert_only(pdf, _line_g(year), answer)

    def test_unstated_leaves_f_and_g_blank(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit_one(year))
                for cells in (_line_f(year), _line_g(year)):
                    for field, _ in cells.values():
                        self.assertIn(vals[field], (None, "/Off"), field)

    def test_f_and_g_are_independent(self):
        pdf = self._emit_one(2025, ca_entity_type="estate_trust",
                             ca_resident=False)
        vals = _values(pdf)
        self.assertEqual(vals[_line_f(2025)["estate_trust"][0]], "/1")
        self.assertEqual(vals[_line_g(2025)[False][0]], "/1")


class LoaderTests(unittest.TestCase):
    def _load(self, shareholder_extra=None, ca_extra=None):
        import yaml
        from tenforty.scenario import load_scenario
        from tests.test_scorp_amended_marks import _scenario_yaml_dict
        data = _scenario_yaml_dict()
        data["s_corp_return"]["ca"] = {
            "first_year": False, "estimated_tax_payments": 0.0,
            "prior_year_overpayment_applied": 0.0,
            "state_tax_deducted_federally": 0.0,
            "depreciation_adjustment": 0.0, "apportionment_ca_only": True,
            **(ca_extra or {})}
        data["s_corp_return"]["shareholders"][0].update(shareholder_extra or {})
        f = tempfile.NamedTemporaryFile(
            "w", suffix=".yaml", delete=False, encoding="utf-8")
        yaml.safe_dump(data, f)
        f.close()
        return load_scenario(Path(f.name)).s_corp_return

    def test_stated_values_load(self):
        r = self._load({"ca_resident": True,
                        "ca_entity_type": "single_member_llc"},
                       {"corporation_number": "0123456"})
        self.assertIs(r.shareholders[0].ca_resident, True)
        self.assertEqual(r.shareholders[0].ca_entity_type, "single_member_llc")
        self.assertEqual(r.ca.corporation_number, "0123456")

    def test_bad_values_refused(self):
        self._load({"ca_resident": False})  # reachability: key is known
        for bad in ({"ca_resident": "yes"}, {"ca_entity_type": "trust"},
                    {"ca_entity_type": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self._load(bad)
        for bad in ("12AB", 1234567, "", "1234567890123"):
            with self.subTest(number=bad), self.assertRaises(ValueError):
                self._load(None, {"corporation_number": bad})


if __name__ == "__main__":
    unittest.main()
