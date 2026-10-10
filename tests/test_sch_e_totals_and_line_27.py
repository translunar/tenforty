"""Schedule E page 1 totals block (lines 23a-24) and page 2 line 27.

Form text (transcribed from pdfs/federal/<year>/f1040se.pdf, identical
2021-2025):
  23a  Total of all amounts reported on line 3 for all rental properties
  23b  Total of all amounts reported on line 4 for all royalty properties
  23c  Total of all amounts reported on line 12 for all properties
  23d  Total of all amounts reported on line 18 for all properties
  23e  Total of all amounts reported on line 20 for all properties
  24   Income. Add positive amounts shown on line 21. Do not include any
       losses
  27   Are you reporting any loss not allowed in a prior year due to the
       at-risk or basis limitations, a prior year unallowed loss from a
       passive activity (if that loss was not reported on Form 8582), or
       unreimbursed partnership expenses?   Yes / No

Every PDF assertion names its widget by literal path. All figures invented.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.attestations import enforce_scoped_refusals
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import sch_e as form_sch_e
from tenforty.models import (
    RentalProperty, Scenario, ScheduleK1, TaxReturnConfig, W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

_YEARS = (2021, 2022, 2023, 2024, 2025)

# Literal widget paths. The leaf names are the same on all five templates
# (two-digit leaves, so 2022's single-digit zero-padding does not touch them).
_P1 = "topmostSubform[0].Page1[0]."
_LINE_23A = _P1 + "f1_77[0]"
_LINE_23B = _P1 + "f1_78[0]"
_LINE_23C = _P1 + "f1_79[0]"
_LINE_23D = _P1 + "f1_80[0]"
_LINE_23E = _P1 + "f1_81[0]"
_LINE_24 = _P1 + "f1_82[0]"
_LINE_25 = _P1 + "f1_83[0]"
_LINE_26 = _P1 + "f1_84[0]"
_LINE_22_A = _P1 + "Table_Expenses[0].Line22[0].f1_74[0]"
_LINE_27_YES = "topmostSubform[0].Page2[0].c2_1[0]"
_LINE_27_NO = "topmostSubform[0].Page2[0].c2_1[1]"

_K1_GATES = (
    "acknowledges_qbi_below_threshold", "acknowledges_unlimited_at_risk",
    "basis_tracked_externally", "acknowledges_no_partnership_se_earnings",
    "acknowledges_no_section_1231_gain", "acknowledges_no_more_than_four_k1s",
    "acknowledges_no_k1_credits", "acknowledges_no_section_179",
    "acknowledges_no_estate_trust_k1",
)


def _scenario(year: int = 2024, *, rentals=(), k1s=()) -> Scenario:
    config = TaxReturnConfig(
        year=year, filing_status="single", birthdate="1990-06-15",
        state="TX", digital_assets=False,
        **scope_out_attestation_defaults(),
    )
    for name in _K1_GATES:
        setattr(config, name, True)
    return Scenario(
        config=config,
        w2s=[W2(employer="Acme Corp", wages=100_000,
                federal_tax_withheld=15_000, ss_wages=100_000,
                ss_tax_withheld=6_200, medicare_wages=100_000,
                medicare_tax_withheld=1_450)],
        rental_properties=list(rentals),
        schedule_k1s=list(k1s),
    )


def _rental(**overrides) -> RentalProperty:
    """Income property: rents 24,000; line 12 8,000; line 16 3,000; line 18
    5,000 -> line 20 16,000; line 21 8,000."""
    fields = dict(
        address="123 Main St", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=24_000.0,
        mortgage_interest=8_000.0, taxes=3_000.0, depreciation=5_000.0,
        acknowledges_depreciation_stated_outside_macrs=True,
    )
    fields.update(overrides)
    return RentalProperty(**fields)


def _k1(**overrides) -> ScheduleK1:
    fields = dict(
        entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
        entity_type="s_corp", material_participation=True,
        ordinary_business_income=50_000.0,
    )
    fields.update(overrides)
    return ScheduleK1(**fields)


class PartOneTotalsComputeTests(unittest.TestCase):
    def test_totals_repeat_the_printed_property_lines(self):
        r = form_sch_e.compute(_scenario(rentals=[_rental()]), upstream={})
        self.assertEqual(r["sch_e_line_23a_total_rents"], 24_000)
        self.assertEqual(r["sch_e_line_23c_total_mortgage_interest"], 8_000)
        self.assertEqual(r["sch_e_line_23d_total_depreciation"], 5_000)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 16_000)
        self.assertEqual(r["sch_e_line_24_income"], 8_000)

    def test_totals_are_the_rounded_printed_lines_not_raw_inputs(self):
        # Line 3 prints 24,001 (24,000.50 rounds up); line 12 prints 8,000
        # (8,000.49 rounds down); line 20 = 8,000 + 3,000 + 5,000.
        r = form_sch_e.compute(_scenario(rentals=[_rental(
            rents_received=24_000.50, mortgage_interest=8_000.49)]),
            upstream={})
        self.assertEqual(r["sch_e_line_23a_total_rents"], 24_001)
        self.assertEqual(r["sch_e_line_23c_total_mortgage_interest"], 8_000)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 16_000)
        self.assertEqual(r["sch_e_line_24_income"], 8_001)

    def test_blank_source_line_leaves_its_total_blank(self):
        # Lines 12 and 18 print nothing when zero, so 23c and 23d stay absent.
        r = form_sch_e.compute(_scenario(rentals=[_rental(
            mortgage_interest=0.0, depreciation=0.0,
            acknowledges_depreciation_stated_outside_macrs=False)]),
            upstream={})
        self.assertNotIn("sch_e_line_23c_total_mortgage_interest", r)
        self.assertNotIn("sch_e_line_23d_total_depreciation", r)
        self.assertEqual(r["sch_e_line_23a_total_rents"], 24_000)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 3_000)
        self.assertEqual(r["sch_e_line_24_income"], 21_000)

    def test_a_loss_property_adds_nothing_to_line_24(self):
        # Line 24: "Do not include any losses." Line 21 here is (10,000).
        r = form_sch_e.compute(_scenario(rentals=[_rental(
            rents_received=6_000.0)]), upstream={})
        self.assertEqual(r["sch_e_property_a_income_loss"], -10_000)
        self.assertNotIn("sch_e_line_24_income", r)
        self.assertEqual(r["sch_e_line_23a_total_rents"], 6_000)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 16_000)

    def test_a_break_even_property_adds_nothing_to_line_24(self):
        # Line 24 adds POSITIVE line 21 amounts; zero is not one.
        r = form_sch_e.compute(_scenario(rentals=[_rental(
            rents_received=16_000.0)]), upstream={})
        self.assertEqual(r["sch_e_property_a_income_loss"], 0)
        self.assertNotIn("sch_e_line_24_income", r)

    def test_loss_property_prints_lines_22_and_25(self):
        # Line 22: "Deductible rental real estate loss after limitation, if
        # any, on Form 8582". Line 25: "Losses. Add royalty losses from line
        # 21 and rental real estate losses from line 22."
        #
        # Line 22 is the property's whole line 21 loss: a return on which
        # Form 8582 allows LESS than the whole loss never prints (refusal
        # passive_loss_limitation_not_applied), so on every return that does
        # print, "after limitation" is the full loss. Both lines sit in
        # preprinted parentheses, so they are stored positive.
        #
        # Line 25's royalty-loss leg is unreachable: nothing is ever printed
        # as a royalty property (line 4 has no producer), so line 25 is the
        # line 22 total alone.
        r = form_sch_e.compute(_scenario(rentals=[_rental(
            rents_received=6_000.0)]), upstream={})
        self.assertEqual(r["sch_e_property_a_income_loss"], -10_000)
        self.assertEqual(r["sch_e_property_a_deductible_loss"], 10_000)
        self.assertEqual(r["sch_e_line_25_losses"], 10_000)
        # Line 26 combines lines 24 and 25 and is unchanged by this block.
        self.assertEqual(r["sch_e_line_26_total"], -10_000)

    def test_income_property_prints_neither_line_22_nor_line_25(self):
        r = form_sch_e.compute(_scenario(rentals=[_rental()]), upstream={})
        self.assertNotIn("sch_e_property_a_deductible_loss", r)
        self.assertNotIn("sch_e_line_25_losses", r)
        zero = form_sch_e.compute(_scenario(rentals=[_rental(
            rents_received=16_000.0)]), upstream={})
        self.assertNotIn("sch_e_property_a_deductible_loss", zero)
        self.assertNotIn("sch_e_line_25_losses", zero)

    def test_line_26_combines_lines_24_and_25(self):
        for rents in (24_000.0, 16_000.0, 6_000.0):
            with self.subTest(rents=rents):
                r = form_sch_e.compute(_scenario(rentals=[_rental(
                    rents_received=rents)]), upstream={})
                self.assertEqual(
                    r["sch_e_line_26_total"],
                    r.get("sch_e_line_24_income", 0)
                    - r.get("sch_e_line_25_losses", 0))

    def test_no_rental_property_emits_no_totals(self):
        r = form_sch_e.compute(_scenario(k1s=[_k1()]), upstream={})
        for key in ("sch_e_line_23a_total_rents",
                    "sch_e_line_23e_total_expenses", "sch_e_line_24_income"):
            with self.subTest(key=key):
                self.assertNotIn(key, r)


class _EmitCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _specs(self, scenario: Scenario):
        results = self.orch.compute_federal(scenario)
        return self.orch._federal_individual_emit_specs(scenario, results)

    def _emit_sch_e(self, scenario: Scenario, tag: str):
        """Render Schedule E through the real emit spec; return
        ({path: /V}, {path: widget /AS})."""
        (spec,) = [s for s in self._specs(scenario) if s.name == "sch_e"]
        out_dir = self.tmp / tag
        out_dir.mkdir()
        path = self.orch._render_federal_spec(PdfFiller(), spec, out_dir)
        reader = PdfReader(str(path))
        values = {p: ("" if f.get("/V") is None else str(f.get("/V")))
                  for p, f in (reader.get_fields() or {}).items()}
        states = {}
        for page in reader.pages:
            for annot in page.get("/Annots", []):
                widget = annot.get_object()
                if "/AS" in widget:
                    states[_widget_path(widget)] = str(widget["/AS"])
        return values, states


def _widget_path(widget) -> str:
    parts = []
    node = widget
    while node is not None:
        node = node.get_object()
        if "/T" in node:
            parts.append(str(node["/T"]))
        node = node.get("/Parent")
    return ".".join(reversed(parts))


class PartOneTotalsEmitTests(_EmitCase):
    def test_income_property_prints_the_totals_block(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, rentals=[_rental()]), f"inc{year}")
                self.assertEqual(values[_LINE_23A], "24000")
                self.assertEqual(values[_LINE_23C], "8000")
                self.assertEqual(values[_LINE_23D], "5000")
                self.assertEqual(values[_LINE_23E], "16000")
                self.assertEqual(values[_LINE_24], "8000")
                self.assertEqual(values[_LINE_26], "8000")

    def test_loss_property_leaves_line_24_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, rentals=[_rental(rents_received=6_000.0)]),
                    f"loss{year}")
                self.assertEqual(values[_LINE_23A], "6000")
                self.assertEqual(values[_LINE_23E], "16000")
                self.assertEqual(values[_LINE_24], "")

    def test_loss_property_prints_lines_22_and_25(self):
        # Wages 100,000: Form 8582 allows the whole 10,000 loss, so the
        # return prints. Parenthesized cells carry the loss unsigned.
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, rentals=[_rental(rents_received=6_000.0)]),
                    f"l22{year}")
                self.assertEqual(values[_LINE_22_A], "10000")
                self.assertEqual(values[_LINE_25], "10000")
                self.assertEqual(values[_LINE_26], "-10000")

    def test_income_property_leaves_lines_22_and_25_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, rentals=[_rental()]), f"i22{year}")
                self.assertEqual(values[_LINE_22_A], "")
                self.assertEqual(values[_LINE_25], "")

    def test_line_23b_stays_blank(self):
        # Line 23b totals line 4 (royalties). Nothing ever reaches line 4: a
        # property loaded with the royalty type code prints its income on
        # line 3 today (a reported defect, not fixed here), so there is no
        # royalty total to print -- even for that property.
        for year in _YEARS:
            for code in (1, 6):
                with self.subTest(year=year, property_type=code):
                    values, _ = self._emit_sch_e(
                        _scenario(year, rentals=[_rental(property_type=code)]),
                        f"b{year}_{code}")
                    self.assertEqual(values[_LINE_23B], "")
                    self.assertEqual(values[_LINE_23A], "24000")

    def test_k1_only_return_leaves_the_part_i_totals_blank(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, _ = self._emit_sch_e(
                    _scenario(year, k1s=[_k1()]), f"k1{year}")
                for path in (_LINE_23A, _LINE_23C, _LINE_23D, _LINE_23E,
                             _LINE_24):
                    self.assertEqual(values[path], "", path)


class TotalsWidgetGeometryTests(unittest.TestCase):
    """The literal paths above, tied to the printed page rather than to the
    mapping: each totals widget sits on its own printed line label."""

    def test_line_23_widgets_sit_on_their_printed_rows(self):
        wanted = {"23a": _LINE_23A, "b": _LINE_23B, "c": _LINE_23C,
                  "d": _LINE_23D, "e": _LINE_23E}
        for year in _YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
                )).pages[0]
                rects = {_widget_path(a.get_object()):
                         [float(v) for v in a.get_object()["/Rect"]]
                         for a in page.get("/Annots", [])}
                top = rects[_P1 + "Table_Expenses[0].Line22[0].f1_74[0]"][1]
                labels: dict[str, float] = {}

                def visit(text, cm, tm, fd, fs):
                    t = text.strip()
                    if t in wanted and 0 < tm[4] < 60 and 0 < tm[5] < top:
                        labels.setdefault(t, tm[5])

                page.extract_text(visitor_text=visit)
                self.assertEqual(set(labels), set(wanted))
                for label, path in wanted.items():
                    self.assertLess(
                        abs(rects[path][1] + 3 - labels[label]), 4,
                        f"{path} is not on the line labelled {label}")

    def test_line_22_property_a_widget_is_the_first_cell_on_row_22(self):
        for year in _YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
                )).pages[0]
                rects = {_widget_path(a.get_object()):
                         [float(v) for v in a.get_object()["/Rect"]]
                         for a in page.get("/Annots", [])}
                labels: list[float] = []

                def visit(text, cm, tm, fd, fs):
                    if text.strip() == "22" and 0 < tm[4] < 60:
                        labels.append(tm[5])

                page.extract_text(visitor_text=visit)
                self.assertEqual(len(labels), 1)
                row = sorted(
                    (r[0], p) for p, r in rects.items()
                    if abs(r[1] + 2 - labels[0] + 14) < 4)
                # Line 22's label is the first of its two text rows; the
                # cells sit on the second, one row (about 12pt) lower.
                self.assertEqual(len(row), 3)
                self.assertEqual(row[0][1], _LINE_22_A)
                # Property A's line 22 cell is directly below its line 21.
                line_21 = rects[_P1 + "Table_Expenses[0].Line21[0].f1_71[0]"]
                self.assertLess(abs(line_21[0] - rects[_LINE_22_A][0]), 6)
                self.assertGreater(line_21[1], rects[_LINE_22_A][1])

    def test_lines_24_25_26_stack_below_23e_and_25_is_the_loss_cell(self):
        for year in _YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
                )).pages[0]
                rects = {_widget_path(a.get_object()):
                         [float(v) for v in a.get_object()["/Rect"]]
                         for a in page.get("/Annots", [])}
                y = [rects[p][1] for p in
                     (_LINE_23E, _LINE_24, _LINE_25, _LINE_26)]
                self.assertEqual(y, sorted(y, reverse=True))
                self.assertEqual(len(set(y)), 4)
                # Lines 24-26 are the three bottom-most widgets on the page.
                lowest = sorted(rects.items(), key=lambda kv: kv[1][1])[:3]
                self.assertEqual(
                    {path for path, _ in lowest},
                    {_LINE_24, _LINE_25, _LINE_26})
                # Line 25 is the only one printed inside parentheses, so its
                # entry cell is inset: narrower than lines 24 and 26.
                width = lambda p: rects[p][2] - rects[p][0]  # noqa: E731
                self.assertLess(width(_LINE_25), width(_LINE_24))
                self.assertLess(width(_LINE_25), width(_LINE_26))


class Line27AnswerTests(_EmitCase):
    def test_part_ii_without_prior_year_losses_answers_no(self):
        for year in _YEARS:
            with self.subTest(year=year):
                values, states = self._emit_sch_e(
                    _scenario(year, k1s=[_k1()]), f"no{year}")
                self.assertEqual(values[_LINE_27_NO], "/2")
                self.assertEqual(states[_LINE_27_NO], "/2")
                self.assertEqual(states[_LINE_27_YES], "/Off")
                self.assertNotEqual(values[_LINE_27_YES], "/1")

    def test_rental_only_return_leaves_line_27_unanswered(self):
        # Line 27 belongs to Part II; with no K-1, Part II is not used.
        for year in _YEARS:
            with self.subTest(year=year):
                _, states = self._emit_sch_e(
                    _scenario(year, rentals=[_rental()]), f"rent{year}")
                self.assertEqual(states[_LINE_27_NO], "/Off")
                self.assertEqual(states[_LINE_27_YES], "/Off")

    def test_line_27_boxes_are_the_yes_no_pair_on_the_line_27_text(self):
        """Geometry, from the template: the pair sits on line 27's last text
        row, Yes to the left of No, with on-states /1 and /2."""
        for year in _YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040se.pdf"
                )).pages[1]
                widgets = {_widget_path(a.get_object()): a.get_object()
                           for a in page.get("/Annots", [])}
                yes, no = widgets[_LINE_27_YES], widgets[_LINE_27_NO]
                self.assertEqual(list(yes["/AP"]["/N"].keys()), ["/1"])
                self.assertEqual(list(no["/AP"]["/N"].keys()), ["/2"])
                self.assertLess(float(yes["/Rect"][0]), float(no["/Rect"][0]))
                rows: list[float] = []

                def visit(text, cm, tm, fd, fs):
                    if text.strip().startswith(
                            "see instructions before completing this section"):
                        rows.append(tm[5])

                page.extract_text(visitor_text=visit)
                self.assertEqual(len(rows), 1)
                for box in (yes, no):
                    self.assertLess(abs(float(box["/Rect"][1]) - rows[0]), 4)


class Line27YesRefusalTests(_EmitCase):
    """A prior-year unallowed loss would require answering Yes and the line 28
    separate-line treatment, which is not produced: the emit refuses."""

    def test_nonpassive_k1_carryforward_refuses_the_emit(self):
        # A carryforward on a materially-participating K-1 is dropped by
        # compute (it never enters Form 8582), so the numbers compute and the
        # return reaches the emit -- where line 27 could only be answered Yes.
        clean = _scenario(k1s=[_k1()])
        self.orch._federal_individual_emit_specs(
            clean, self.orch.compute_federal(clean))  # twin: emits
        carrying = _scenario(k1s=[_k1(
            prior_year_passive_loss_carryforward=3_000.0)])
        results = self.orch.compute_federal(carrying)  # compute still runs
        with self.assertRaisesRegex(
                NotImplementedError, r"Schedule E line 27.*'Fake S-Corp Inc'"):
            self.orch._federal_individual_emit_specs(carrying, results)

    def test_passive_k1_carryforward_is_stopped_earlier_at_compute(self):
        # On a PASSIVE K-1 the carryforward enters Form 8582, whose result is
        # never applied to the return: the compute-side refusal fires before
        # any emit. The emit-stage entry would flag the same K-1.
        carrying = _scenario(k1s=[_k1(
            entity_name="Fake LP", entity_type="partnership",
            material_participation=False, ordinary_business_income=9_000.0,
            prior_year_passive_loss_carryforward=3_000.0)])
        with self.assertRaisesRegex(
                NotImplementedError, r"Form 8582 limitation.*not applied"):
            self.orch.compute_federal(carrying)
        with self.assertRaisesRegex(
                NotImplementedError, r"Schedule E line 27.*'Fake LP'"):
            enforce_scoped_refusals(carrying, "emit")

    def test_refusal_is_an_emit_stage_ledger_entry(self):
        carrying = _scenario(k1s=[_k1(
            prior_year_passive_loss_carryforward=3_000.0)])
        enforce_scoped_refusals(carrying, "load")
        enforce_scoped_refusals(carrying, "compute")
        with self.assertRaisesRegex(NotImplementedError, r"Schedule E line 27"):
            enforce_scoped_refusals(carrying, "emit")
        enforce_scoped_refusals(_scenario(k1s=[_k1()]), "emit")

    def test_refusal_fires_in_every_supported_year(self):
        for year in _YEARS:
            with self.subTest(year=year):
                carrying = _scenario(year, k1s=[_k1(
                    prior_year_passive_loss_carryforward=3_000.0)])
                results = self.orch.compute_federal(carrying)
                with self.assertRaisesRegex(
                        NotImplementedError, r"Schedule E line 27"):
                    self.orch._federal_individual_emit_specs(carrying, results)


if __name__ == "__main__":
    unittest.main()
