"""Form 1120-S Schedule B — every question answered, refused, or gated.

Covers the question-faithful Schedule B model end to end, with the REAL filled
PDFs reopened and (for the No boxes) measured in pixels:

  * cells: each question's Yes/No pair sits on the printed row it answers (the
    template's widget Rect is pinned to the row), per year;
  * emit: an all-No / line-11-Yes assignment marks every No box (on-state
    "/2"), leaves every Yes box clear, and renders visible ink for the No mark;
    printable Yes answers mark the Yes box;
  * gate: an unstated answer is refused at EMIT with every missing field listed
    at once; line 14b is required iff 14a is Yes and refused otherwise; line 16
    is required for 2023+ and refused for 2021/2022; line 11 Yes against
    receipts/assets of $250,000 or more is refused on the SAME basis as the
    Schedule L / M-1 attestation;
  * refusals: a Yes that stands for an unmodeled attachment (and a No on line
    11) raises NotImplementedError naming it at compute, and the printable
    answers do not;
  * loader: the three retired keys fail loudly and the new fields round-trip.

Every refusal test is paired with a control proving the same scenario passes
once the answer is changed, so the refusal is shown to FIRE rather than to be
unreachable. Synthetic fixture only (tests/_scorp_fixtures.py)."""
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.attestations import _has_scorp_large_balance_sheet
from tenforty.forms import f1120s
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests._pdf_pixels import dark_pixels_in_rect, widget_rect
from tests._scorp_fixtures import _make_v1_scenario

# The all-printable truth assignment (identical to the shared fixture default).
_ALL_NO = dict(
    shareholder_disregarded_entity_trust_estate_or_nominee=False,
    owns_20pct_stock_of_any_corporation=False,
    owns_20pct_interest_in_partnership_or_trust=False,
    restricted_stock_outstanding=False,
    stock_options_or_warrants_outstanding=False,
    filed_form_8918=False,
    issued_oid_debt_instruments=False,
    section_163j_election=False,
    form_8990_conditions_met=False,
    receipts_and_assets_under_250k=True,
    nonshareholder_debt_canceled=False,
    qsub_election_terminated=False,
    payments_requiring_1099s=False,
    filed_required_1099s=None,
    qualified_opportunity_fund=False,
    digital_asset_transactions=False,
    net_unrealized_built_in_gain=None,
)
_REQUIRED_BY_ALL_YEARS = [k for k in _ALL_NO
                          if k not in ("filed_required_1099s",
                                       "digital_asset_transactions",
                                       "net_unrealized_built_in_gain")]

# question -> (line, page, group for 2021/22, group for 2023-25)
_PAIRS = {
    "shareholder_disregarded_entity_trust_estate_or_nominee":
        ("3", 2, "c2_2", "c2_2"),
    "owns_20pct_stock_of_any_corporation": ("4a", 2, "c2_3", "c2_3"),
    "owns_20pct_interest_in_partnership_or_trust": ("4b", 2, "c2_4", "c2_4"),
    "restricted_stock_outstanding": ("5a", 2, "c2_05", "c2_5"),
    "stock_options_or_warrants_outstanding": ("5b", 2, "c2_06", "c2_6"),
    "filed_form_8918": ("6", 2, "c2_07", "c2_7"),
    "section_163j_election": ("9", 2, "c2_09", "c2_9"),
    "form_8990_conditions_met": ("10", 2, "c2_10", "c2_10"),
    "receipts_and_assets_under_250k": ("11", 2, "c2_11", "c2_11"),
    "nonshareholder_debt_canceled": ("12", 3, "c3_1", "c3_1"),
    "qsub_election_terminated": ("13", 3, "c3_2", "c3_2"),
    "payments_requiring_1099s": ("14a", 3, "c3_3", "c3_3"),
    "filed_required_1099s": ("14b", 3, "c3_4", "c3_4"),
    "qualified_opportunity_fund": ("15", 3, "c3_5", "c3_5"),
    "digital_asset_transactions": ("16", 3, "c3_6", "c3_6"),  # 2023+
}
_Q7 = ("c2_08", "c2_8")  # (2021/22, 2023-25) single box, page 2
_Q8_CELL = "topmostSubform[0].Page2[0].f2_48[0]"

# Template row (widget bottom y, points) each group must sit on — read off the
# printed question row of the year's own template. Page 3 shifted in 2025.
_ROW_Y_PAGE2 = {"c2_2": 661, "c2_3": 613, "c2_4": 493, "c2_5": 397,
                "c2_6": 349, "c2_7": 289, "c2_9": 181, "c2_10": 169,
                "c2_11": 97}
_ROW_Y_PAGE3_2021_2024 = {"c3_1": 709, "c3_2": 685, "c3_3": 673,
                          "c3_4": 661, "c3_5": 649, "c3_6": 613}
_ROW_Y_PAGE3_2025 = {"c3_1": 697, "c3_2": 673, "c3_3": 661,
                     "c3_4": 649, "c3_5": 637, "c3_6": 601}


def _group(field, year):
    _line, page, padded, plain = _PAIRS[field]
    return page, (padded if year <= 2022 else plain)


def _path(page, group, side):
    return f"topmostSubform[0].Page{page}[0].{group}[{side}]"


def _applicable(year):
    return [f for f in _PAIRS if f != "digital_asset_transactions" or year >= 2023]


def _scenario(year=2025, **answers):
    """Fixture scenario at ``year`` with the all-No assignment, then overrides.
    Line 16 follows the year (stated for 2023+, unstated before)."""
    s = _make_v1_scenario()
    s.config.year = year
    sb = s.s_corp_return.schedule_b_answers
    merged = {**_ALL_NO,
              "digital_asset_transactions": False if year >= 2023 else None,
              **answers}
    for k, v in merged.items():
        setattr(sb, k, v)
    return s


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
        self._n = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _emit(self, scenario):
        self._n += 1
        out = Path(self._tmp.name) / f"out{self._n}"
        self.orch.run_full_federal_scorp_return(scenario, out)
        return out / f"f1120s_{scenario.config.year}.pdf"


class CellGeometryTests(unittest.TestCase):
    """Each question's Yes/No pair sits on the row the question prints on."""

    def test_pairs_sit_on_their_printed_question_rows(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                fields = PdfReader(
                    str(Path("pdfs/federal") / str(year) / "f1120s.pdf")
                ).get_fields() or {}
                page3 = _ROW_Y_PAGE3_2025 if year == 2025 else _ROW_Y_PAGE3_2021_2024
                for field in _applicable(year):
                    line, page, padded, plain = _PAIRS[field]
                    group = padded if year <= 2022 else plain
                    for side, x0 in ((0, 539), (1, 560)):
                        path = _path(page, group, side)
                        self.assertIn(path, fields, f"{year} line {line}")
                    expect_y = (_ROW_Y_PAGE2 if page == 2 else page3)[plain]
                    for side, x0 in ((0, 539), (1, 560)):
                        pg, rect = widget_rect(
                            Path("pdfs/federal") / str(year) / "f1120s.pdf",
                            _path(page, group, side))
                        self.assertEqual(pg, page - 1, f"{year} line {line}")
                        self.assertEqual(round(rect[1]), expect_y,
                                         f"{year} line {line} side {side}")
                        self.assertEqual(round(rect[0]), x0,
                                         f"{year} line {line} side {side}")

    def test_line_16_cell_is_absent_before_2023(self):
        for year in (2021, 2022):
            fields = PdfReader(
                str(Path("pdfs/federal") / str(year) / "f1120s.pdf")
            ).get_fields() or {}
            # c3_6 exists on these templates, but only as the Schedule K-2 box
            # (one widget, no Yes/No pair): [1] must not exist.
            self.assertNotIn(_path(3, "c3_6", 1), fields, str(year))


class NoSideEmitTests(_EmitBase):
    def test_all_no_assignment_marks_every_no_box_and_no_yes_box(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                vals = _values(self._emit(_scenario(year)))
                for field in _applicable(year):
                    line, page, _p, _q = _PAIRS[field]
                    page, group = _group(field, year)
                    yes = vals[_path(page, group, 0)]
                    no = vals[_path(page, group, 1)]
                    if field == "filed_required_1099s":
                        # 14a is No: the question is unanswerable — both untouched.
                        self.assertIn(yes, (None, "/Off"), f"{year} 14b yes")
                        self.assertIn(no, (None, "/Off"), f"{year} 14b no")
                    elif field == "receipts_and_assets_under_250k":
                        self.assertEqual(yes, "/1", f"{year} line 11 Yes")
                        self.assertIn(no, (None, "/Off"), f"{year} line 11 No")
                    else:
                        self.assertIn(yes, (None, "/Off"),
                                      f"{year} line {line} Yes box")
                        self.assertEqual(no, "/2", f"{year} line {line} No box")
                # Line 7 box is clear; line 8 is blank.
                q7 = _Q7[0 if year <= 2022 else 1]
                self.assertIn(vals[_path(2, q7, 0)], (None, "/Off"), str(year))
                self.assertIn(vals[_Q8_CELL], (None, ""), str(year))

    def test_line_16_pair_is_not_written_for_2021_and_2022(self):
        for year in (2021, 2022):
            with self.subTest(year=year):
                vals = _values(self._emit(_scenario(year)))
                self.assertNotIn(_path(3, "c3_6", 1), vals)

    def test_printable_yes_answers_mark_the_yes_box(self):
        for year in (2022, 2024, 2025):
            with self.subTest(year=year):
                answers = dict(
                    filed_form_8918=True, section_163j_election=True,
                    qsub_election_terminated=True, issued_oid_debt_instruments=True,
                    payments_requiring_1099s=True, filed_required_1099s=False,
                    net_unrealized_built_in_gain=12345.6)
                if year >= 2023:
                    answers["digital_asset_transactions"] = True
                vals = _values(self._emit(_scenario(year, **answers)))
                for field in ("filed_form_8918", "section_163j_election",
                              "qsub_election_terminated",
                              "payments_requiring_1099s"):
                    page, group = _group(field, year)
                    self.assertEqual(vals[_path(page, group, 0)], "/1",
                                     f"{year} {field} Yes")
                    self.assertIn(vals[_path(page, group, 1)], (None, "/Off"),
                                  f"{year} {field} No")
                # 14a Yes makes 14b answerable: a stated No marks the No box.
                page, group = _group("filed_required_1099s", year)
                self.assertEqual(vals[_path(page, group, 1)], "/2")
                self.assertEqual(vals[_path(2, _Q7[0 if year <= 2022 else 1], 0)],
                                 "/1")
                self.assertEqual(vals[_Q8_CELL], "12346")
                if year >= 2023:
                    page, group = _group("digital_asset_transactions", year)
                    self.assertEqual(vals[_path(page, group, 0)], "/1")

    def test_14b_yes_marks_its_yes_box(self):
        vals = _values(self._emit(_scenario(
            2024, payments_requiring_1099s=True, filed_required_1099s=True)))
        page, group = _group("filed_required_1099s", 2024)
        self.assertEqual(vals[_path(page, group, 0)], "/1")
        self.assertIn(vals[_path(page, group, 1)], (None, "/Off"))


class PixelTests(_EmitBase):
    """Ink, not field state: the No mark is VISIBLE, and a Yes box that was
    never set stays empty (reachable: the same widget shows ink in the
    positive control)."""

    INK = 8  # dark pixels inside the inset 10pt box; empty box measures 0

    def _ink(self, pdf, page, group, side):
        pg, rect = widget_rect(pdf, _path(page, group, side))
        return dark_pixels_in_rect(pdf, pg, rect)

    def test_no_marks_render_on_both_pages(self):
        for year in (2021, 2024, 2025):
            with self.subTest(year=year):
                pdf = self._emit(_scenario(year))
                for field in ("shareholder_disregarded_entity_trust_estate_or_nominee",
                              "restricted_stock_outstanding",
                              "nonshareholder_debt_canceled",
                              "qualified_opportunity_fund"):
                    page, group = _group(field, year)
                    self.assertGreater(self._ink(pdf, page, group, 1), self.INK,
                                       f"{year} {field} No mark")
                    self.assertEqual(self._ink(pdf, page, group, 0), 0,
                                     f"{year} {field} Yes box")
                if year >= 2023:
                    page, group = _group("digital_asset_transactions", year)
                    self.assertGreater(self._ink(pdf, page, group, 1), self.INK)

    def test_yes_mark_renders_and_its_no_box_stays_empty(self):
        for year in (2021, 2025):
            with self.subTest(year=year):
                pdf = self._emit(_scenario(year, filed_form_8918=True))
                page, group = _group("filed_form_8918", year)
                self.assertGreater(self._ink(pdf, page, group, 0), self.INK)
                self.assertEqual(self._ink(pdf, page, group, 1), 0)

    def test_line_11_yes_renders(self):
        pdf = self._emit(_scenario(2024))
        page, group = _group("receipts_and_assets_under_250k", 2024)
        self.assertGreater(self._ink(pdf, page, group, 0), self.INK)
        self.assertEqual(self._ink(pdf, page, group, 1), 0)


class EmitGateTests(unittest.TestCase):
    """check_schedule_b_for_emit / the orchestrator emit refuse what cannot be
    printed. Each refusal has a control that passes."""

    def _msg(self, scenario):
        with self.assertRaises(ValueError) as cm:
            f1120s.check_schedule_b_for_emit(scenario)
        return str(cm.exception)

    def test_complete_answers_pass(self):
        for year in years.SCORP_FEDERAL_YEARS:
            f1120s.check_schedule_b_for_emit(_scenario(year))

    def test_unstated_answers_are_all_listed_at_once(self):
        blank = {k: None for k in _ALL_NO}
        msg = self._msg(_scenario(2025, **blank))
        for field in _REQUIRED_BY_ALL_YEARS + ["digital_asset_transactions"]:
            self.assertIn(field, msg, field)
        # 14b is not required while 14a is unstated/No; line 8 may stay blank.
        self.assertNotIn("filed_required_1099s", msg)
        self.assertNotIn("net_unrealized_built_in_gain", msg)

    def test_a_single_missing_answer_names_only_itself(self):
        msg = self._msg(_scenario(2024, filed_form_8918=None))
        self.assertIn("filed_form_8918", msg)
        for other in _REQUIRED_BY_ALL_YEARS:
            if other != "filed_form_8918":
                self.assertNotIn(other, msg)

    def test_14b_required_iff_14a_yes(self):
        msg = self._msg(_scenario(
            2024, payments_requiring_1099s=True, filed_required_1099s=None))
        self.assertIn("filed_required_1099s", msg)
        f1120s.check_schedule_b_for_emit(_scenario(
            2024, payments_requiring_1099s=True, filed_required_1099s=False))

    def test_14b_stated_with_14a_no_is_refused(self):
        msg = self._msg(_scenario(
            2024, payments_requiring_1099s=False, filed_required_1099s=False))
        self.assertIn("filed_required_1099s", msg)
        self.assertIn("14a", msg)

    def test_line_16_required_from_2023_refused_before(self):
        for year in (2023, 2024, 2025):
            msg = self._msg(_scenario(year, digital_asset_transactions=None))
            self.assertIn("digital_asset_transactions", msg, str(year))
        for year in (2021, 2022):
            msg = self._msg(_scenario(year, digital_asset_transactions=False))
            self.assertIn("digital_asset_transactions", msg, str(year))
            self.assertIn("no line 16", msg)
            # control: unstated passes where the question does not exist
            f1120s.check_schedule_b_for_emit(
                _scenario(year, digital_asset_transactions=None))

    def test_line_11_yes_against_large_receipts_or_assets_is_refused(self):
        for field, value in (("gross_receipts", 250000.0),
                             ("total_assets", 250000.0)):
            s = _scenario(2024)
            r = s.s_corp_return
            if field == "gross_receipts":
                r.income.gross_receipts = value
            else:
                r.total_assets = value
            msg = self._msg(s)
            self.assertIn("line 11", msg, field)
            self.assertIn("$250,000", msg, field)
            # control: just under the threshold on that same field passes
            if field == "gross_receipts":
                r.income.gross_receipts = 249999.0
            else:
                r.total_assets = 249999.0
            f1120s.check_schedule_b_for_emit(s)

    def test_line_11_cross_check_uses_the_attestation_gates_basis(self):
        for receipts in (0.0, 249999.99, 250000.0, 1e6):
            for assets in (0.0, 249999.99, 250000.0, 1e6):
                s = _scenario(2024)
                s.s_corp_return.income.gross_receipts = receipts
                s.s_corp_return.total_assets = assets
                large = _has_scorp_large_balance_sheet(s)
                try:
                    f1120s.check_schedule_b_for_emit(s)
                    refused = False
                except ValueError:
                    refused = True
                self.assertEqual(refused, large, (receipts, assets))

    def test_the_orchestrator_emit_applies_the_gate(self):
        with tempfile.TemporaryDirectory() as td:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(td))
            s = _scenario(2024, filed_form_8918=None)
            with self.assertRaises(ValueError) as cm:
                orch.run_full_federal_scorp_return(s, Path(td) / "out")
            self.assertIn("filed_form_8918", str(cm.exception))
            self.assertFalse((Path(td) / "out" / "f1120s_2024.pdf").exists())

    def test_compute_does_not_need_the_answers(self):
        blank = {k: None for k in _ALL_NO}
        out = f1120s.compute(_scenario(2025, **blank), upstream={})
        self.assertIs(out["f1120s_sch_b_filed_form_8918"], False)
        self.assertIs(out["f1120s_sch_b_filed_form_8918_no"], False)


class RefusalTests(unittest.TestCase):
    """A Yes that stands for an attachment tenforty does not model refuses at
    compute, naming it. Controls: the same scenario with the answer No passes,
    and the printable Yes answers do not raise."""

    UNMODELED_TRUE = {
        "shareholder_disregarded_entity_trust_estate_or_nominee": "Schedule B-1",
        "owns_20pct_stock_of_any_corporation": "line 4a",
        "owns_20pct_interest_in_partnership_or_trust": "line 4b",
        "restricted_stock_outstanding": "line 5a",
        "stock_options_or_warrants_outstanding": "line 5b",
        "form_8990_conditions_met": "Form 8990",
        "qualified_opportunity_fund": "Form 8996",
        "nonshareholder_debt_canceled": "line 12",
    }
    PRINTABLE_TRUE = ("filed_form_8918", "section_163j_election",
                      "qsub_election_terminated", "payments_requiring_1099s",
                      "issued_oid_debt_instruments")

    def test_yes_on_an_unmodeled_attachment_refuses_and_names_it(self):
        for field, needle in self.UNMODELED_TRUE.items():
            with self.subTest(field=field):
                f1120s.compute(_scenario(2025, **{field: False}), upstream={})
                with self.assertRaises(NotImplementedError) as cm:
                    f1120s.compute(_scenario(2025, **{field: True}), upstream={})
                self.assertIn(needle, str(cm.exception))
                self.assertIn(field, str(cm.exception))

    def test_refusals_fire_for_every_year(self):
        for year in years.SCORP_FEDERAL_YEARS:
            with self.subTest(year=year):
                with self.assertRaises(NotImplementedError):
                    f1120s.compute(
                        _scenario(year, form_8990_conditions_met=True),
                        upstream={})

    def test_printable_yes_answers_do_not_refuse(self):
        for field in self.PRINTABLE_TRUE:
            with self.subTest(field=field):
                f1120s.compute(_scenario(2025, **{field: True}), upstream={})
        f1120s.compute(_scenario(2025, digital_asset_transactions=True),
                       upstream={})

    def test_line_11_no_refuses_naming_schedules_l_and_m1(self):
        with self.assertRaises(NotImplementedError) as cm:
            f1120s.compute(
                _scenario(2025, receipts_and_assets_under_250k=False),
                upstream={})
        self.assertIn("Schedule", str(cm.exception))
        self.assertIn("L", str(cm.exception))
        self.assertIn("M-1", str(cm.exception))

    def test_line_11_no_refuses_even_with_the_schedule_l_attestation_true(self):
        # The fixture's acknowledges_no_1120s_schedule_l_needed is True; a
        # stated No on line 11 still refuses (the attestation only fires on the
        # numeric threshold; line 11 is its own stated fact).
        s = _scenario(2025, receipts_and_assets_under_250k=False)
        self.assertTrue(s.config.acknowledges_no_1120s_schedule_l_needed)
        with self.assertRaises(NotImplementedError):
            f1120s.compute(s, upstream={})

    def test_the_emit_path_refuses_too(self):
        with tempfile.TemporaryDirectory() as td:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(td))
            with self.assertRaises(NotImplementedError):
                orch.run_full_federal_scorp_return(
                    _scenario(2025, form_8990_conditions_met=True),
                    Path(td) / "out")


class LoaderTests(unittest.TestCase):
    FIXTURE = Path("tests/fixtures/scorp_v1_smoke.yaml")

    def _load(self, mutate):
        data = yaml.safe_load(self.FIXTURE.read_text())
        mutate(data["s_corp_return"]["schedule_b_answers"])
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "s.yaml"
            path.write_text(yaml.safe_dump(data))
            return load_scenario(path)

    def test_each_retired_key_fails_loudly_and_points_at_its_replacement(self):
        retired = {
            "has_any_foreign_shareholders":
                "shareholder_disregarded_entity_trust_estate_or_nominee",
            "any_c_corp_subsidiaries": "owns_20pct_stock_of_any_corporation",
            "owns_foreign_entity": "owns_20pct_interest_in_partnership_or_trust",
        }
        for old, new in retired.items():
            with self.subTest(old=old):
                with self.assertRaises(ValueError) as cm:
                    self._load(lambda d, old=old: d.__setitem__(old, False))
                self.assertIn(old, str(cm.exception))
                self.assertIn(new, str(cm.exception))

    def test_new_answers_round_trip_including_null_and_amount(self):
        def mutate(d):
            d["shareholder_disregarded_entity_trust_estate_or_nominee"] = False
            d["filed_form_8918"] = True
            d["filed_required_1099s"] = None
            d["net_unrealized_built_in_gain"] = 1500
            del d["restricted_stock_outstanding"]  # absent key = unstated
        sb = self._load(mutate).s_corp_return.schedule_b_answers
        self.assertIs(sb.shareholder_disregarded_entity_trust_estate_or_nominee,
                      False)
        self.assertIs(sb.filed_form_8918, True)
        self.assertIsNone(sb.filed_required_1099s)
        self.assertIsNone(sb.restricted_stock_outstanding)  # absent = unstated
        self.assertEqual(sb.net_unrealized_built_in_gain, 1500.0)

    def test_a_non_boolean_answer_is_rejected(self):
        with self.assertRaises(ValueError) as cm:
            self._load(lambda d: d.__setitem__("filed_form_8918", "no"))
        self.assertIn("filed_form_8918", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
