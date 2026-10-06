"""California Form 100S Schedule Q stated answers — filled-emit read-back and
pixel tests: Question F (date incorporated), the audit question (Question I on
the 2022 form, Question J from 2023), and Question O (required information
returns filed: N/A / Yes / No).

Drives ``run_full_california_scorp_return`` for every year that carries the
features (2022-2025; 2021 refuses a stated answer rather than dropping it),
reopens the REAL filled 100S, asserts the answer's own box carries its
certified on-state and NO sibling box is marked, and that the marked box draws
ink. The cell table below is written independently of the mapping module and
was certified per year by label position: the Schedule Q questions renumber
between years (the audit question is field 3011 in 2022, 3011a from 2023) and
the radio on-state tokens differ per year (Question O's Yes box is /1 in 2024
but /2 in 2025), so only each year's own template distinguishes them.

Synthetic fixture only (tests/_scorp_fixtures.py)."""
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


def _name(year, bare):
    """Field-name namespace: bare through 2023, '100S Form ' prefixed after."""
    return bare if year <= 2023 else f"100S Form {bare}"


# year -> {question: {answer: (field name, widget on-state)}}
def _cells(year):
    audit_field = {2022: "3011 rb", 2023: "3011a rb"}.get(year, "3011a rb")
    if year == 2023:
        audit_states = {True: "/Yes", False: "/No"}
    else:
        audit_states = {True: "/0", False: "/1"}
    audit = {a: (_name(year, audit_field), st) for a, st in audit_states.items()}
    if year <= 2023:
        info = {"not_applicable": (_name(year, "3018 CB"), "/Yes"),
                "yes": (_name(year, "3019 CB"), "/Yes"),
                "no": (_name(year, "3020 CB"), "/Yes")}
    else:
        states = ({"not_applicable": "/0", "yes": "/1", "no": "/2"}
                  if year == 2024 else
                  {"not_applicable": "/0", "yes": "/2", "no": "/1"})
        info = {a: (_name(year, "3018 RB"), st) for a, st in states.items()}
    return {"audit": audit, "information_returns": info}


def _date_incorporated_cell(year):
    return _name(year, "3006")


def _widget_states(pdf, field_name):
    """{on_state: rect} for every kid widget carrying ``field_name``."""
    out = {}
    reader = PdfReader(str(pdf))
    for page in reader.pages:
        for annot in page.get("/Annots", []) or []:
            w = annot.get_object()
            node, names = w, []
            while node is not None:
                if "/T" in node:
                    names.append(str(node["/T"]))
                p = node.get("/Parent")
                node = p.get_object() if p is not None else None
            if ".".join(reversed(names)) != field_name:
                continue
            for st in (w.get("/AP", {}).get("/N", {}) or {}):
                if st != "/Off":
                    out.setdefault(st, []).append(
                        [float(v) for v in w["/Rect"]])
    return out


def _selected(pdf, field_name):
    """The set of on-states currently selected on ``field_name`` (a radio's
    parent /V, or a checkbox's /V)."""
    fields = PdfReader(str(pdf)).get_fields() or {}
    v = fields[field_name].get("/V")
    return None if v is None else str(v)


class _EmitBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, year, audit=None, info=None, tag="x"):
        s = _make_v1_scenario()
        set_tax_year(s, year)
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=False, estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0, depreciation_adjustment=0.0,
            apportionment_ca_only=True,
            under_irs_audit=audit, information_returns_filed=info)
        out = Path(self._tmp.name) / f"ca_{year}_{audit}_{info}_{tag}"
        self.orch.run_full_california_scorp_return(s, out)
        return out / f"f100s_{year}.pdf"


class TemplateCellsExistTests(unittest.TestCase):
    def test_every_certified_cell_exists_with_its_on_state(self):
        for year in _YEARS:
            template = Path("pdfs/california") / str(year) / "f100s.pdf"
            for q, answers in _cells(year).items():
                for answer, (field, on) in answers.items():
                    with self.subTest(year=year, q=q, answer=answer):
                        self.assertIn(on, _widget_states(template, field))
            fields = PdfReader(str(template)).get_fields() or {}
            self.assertEqual(
                str(fields[_date_incorporated_cell(year)].get("/FT")), "/Tx")


class DateIncorporatedTests(_EmitBase):
    def test_date_incorporated_prints_mm_dd_yyyy(self):
        # Every CA S-corp year incl. 2021: field 3006 sits beside the printed
        # "F Date incorporated" caption on each template.
        for year in (2021, *_YEARS):
            with self.subTest(year=year):
                pdf = self._emit(year)
                fields = PdfReader(str(pdf)).get_fields()
                self.assertEqual(
                    str(fields[_date_incorporated_cell(year)]["/V"]),
                    "01/01/2020")


class StatedAnswerTests(_EmitBase):
    def _check(self, year, question, answer, **kw):
        pdf = self._emit(year, **kw)
        cells = _cells(year)[question]
        field, on = cells[answer]
        # The chosen box carries its own certified on-state ...
        self.assertEqual(_selected(pdf, field), on, f"{year} {question} {answer}")
        # ... and draws ink.
        page, rect = widget_rect(pdf, field, on)
        self.assertGreater(
            dark_pixels_in_rect(pdf, page, rect, inset=1.0), 0,
            f"{year} {question} {answer}: marked box draws no ink")
        # No sibling answer is marked: a different cell never reads ON, and a
        # shared radio's selection is exactly the chosen token.
        for other, (ofield, oon) in cells.items():
            if other == answer:
                continue
            if ofield == field:
                self.assertNotEqual(_selected(pdf, field), oon)
            else:
                self.assertIn(_selected(pdf, ofield), (None, "/Off"),
                              f"{year} {question}: {other} also marked")

    def test_audit_yes_and_no(self):
        for year in _YEARS:
            for answer in (True, False):
                with self.subTest(year=year, answer=answer):
                    self._check(year, "audit", answer, audit=answer)

    def test_information_returns_all_three_answers(self):
        for year in _YEARS:
            for answer in ("yes", "no", "not_applicable"):
                with self.subTest(year=year, answer=answer):
                    self._check(year, "information_returns", answer, info=answer)

    def test_unstated_answers_leave_every_box_unmarked(self):
        for year in _YEARS:
            with self.subTest(year=year):
                pdf = self._emit(year)
                seen = set()
                for answers in _cells(year).values():
                    for field, _ in answers.values():
                        if field in seen:
                            continue
                        seen.add(field)
                        self.assertIn(_selected(pdf, field), (None, "/Off"),
                                      f"{year} {field}")

    def test_questions_are_independent(self):
        year = 2025
        pdf = self._emit(year, audit=True, info="no")
        a_field, a_on = _cells(year)["audit"][True]
        i_field, i_on = _cells(year)["information_returns"]["no"]
        self.assertEqual(_selected(pdf, a_field), a_on)
        self.assertEqual(_selected(pdf, i_field), i_on)


class Refuse2021Tests(_EmitBase):
    def test_2021_refuses_a_stated_answer_instead_of_dropping_it(self):
        with self.assertRaises(ValueError):
            self._emit(2021, audit=True)
        with self.assertRaises(ValueError):
            self._emit(2021, info="yes", tag="b")


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

    def test_stated_keys_load(self):
        ca = self._load({"under_irs_audit": False,
                         "information_returns_filed": "not_applicable"})
        self.assertIs(ca.under_irs_audit, False)
        self.assertEqual(ca.information_returns_filed, "not_applicable")

    def test_absent_keys_default_unstated(self):
        ca = self._load({})
        self.assertIsNone(ca.under_irs_audit)
        self.assertIsNone(ca.information_returns_filed)

    def test_bad_values_rejected(self):
        with self.assertRaises(ValueError):
            self._load({"under_irs_audit": "yes"})
        with self.assertRaises(ValueError):
            self._load({"information_returns_filed": True})
        with self.assertRaises(ValueError):
            self._load({"information_returns_filed": "maybe"})


if __name__ == "__main__":
    unittest.main()
