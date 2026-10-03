"""Task 7 — Form 8962 (PTC) PDF mapping, filled-emit read-back, and the
orchestrator emit predicate / changed-forms selector universe.

The mapping is the probe-certified year-keyed pack in
``tenforty.mappings.pdf_f8962``. These tests exercise it three ways:

1. Static: every mapped field path (scalar leaves + the 4c derivation cell)
   exists on that year's own blank template — a direct per-year subTest on
   top of what the catalog fields-on-template gate does once the gap cells
   are retired.
2. Filled-emit read-back: fill the real template with distinctive values via
   the SAME mapping/checkbox_states/derivations the orchestrator passes, then
   read the cells back — for 2021 (ARPA UI box A ON -> /2 + monthly write-in
   rows) and 2024 (UI box absent/off + repayment lines). Plus the checkbox
   both-ways (2021) and the team-lead PIN (uncapped line 28 = None renders a
   BLANK cell, never the string "None").
3. Orchestrator: ``_should_emit_8962`` fires only for a 1095-A with a nonzero
   month, and f8962 joins / leaves the changed-forms selector universe (the
   emit-spec name set) accordingly.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f8962 import PdfF8962
from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

_PDFS = REPO_ROOT / "pdfs"
_YEARS = (2021, 2022, 2023, 2024, 2025)


def _template(year: int) -> Path:
    return _PDFS / "federal" / str(year) / "f8962.pdf"


def _read_fields(pdf_path: Path) -> dict[str, str]:
    """Read back {field_path: value-as-str} from a filled PDF. Checkbox
    on-states come back as name objects (e.g. /3); text as strings; blanks
    as ""."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    out: dict[str, str] = {}
    for path, fld in fields.items():
        v = fld.get("/V")
        out[path] = "" if v is None else str(v)
    return out


def _fill(year: int, values: dict, out: Path) -> Path:
    """Fill the real f8962 template exactly as the orchestrator emit spec
    does: scalars mapping + this year's checkbox_states + derivations."""
    mapping = PdfF8962.get_mapping(year)["scalars"]
    PdfFiller().fill(
        template_path=_template(year),
        output_path=out,
        field_mapping=mapping,
        values=values,
        checkbox_states=PdfF8962.get_checkbox_states(year) or None,
        derivations=PdfF8962.get_derivations(year) or None,
    )
    return out


# PDF field paths pinned here so read-back assertions can name cells directly.
_ROOT = "topmostSubform[0].Page1[0]"
_UI_BOX = f"{_ROOT}.c1_1[0]"          # 2021 ARPA unemployment Box A
_BOX_4C = f"{_ROOT}.c1_2[2]"          # poverty table "Other 48 + DC"
_LINE_1 = f"{_ROOT}.f1_3[0]"
_LINE_5 = f"{_ROOT}.f1_8[0]"
_LINE_24 = f"{_ROOT}.f1_91[0]"
_LINE_28 = f"{_ROOT}.f1_95[0]"        # repayment limitation
_LINE_29 = f"{_ROOT}.f1_96[0]"
_MONTH1_A = f"{_ROOT}.Part2Table2[0].BodyRow1[0].f1_19[0]"
_MONTH1_F = f"{_ROOT}.Part2Table2[0].BodyRow1[0].f1_24[0]"


def _capped_values() -> dict:
    """A capped (line 5 < 400%) single-filer f8962 detail dict with one
    monthly write-in row and a real repayment limitation on line 28."""
    return {
        "f8962_line_1": 1,
        "f8962_line_2a": 30_000,
        "f8962_line_3": 30_000,
        "f8962_line_4": 13_590,
        "f8962_line_5": 220,           # 220% FPL — capped band
        "f8962_line_7": 0.06,
        "f8962_line_8a": 1_800,
        "f8962_line_8b": 150,
        "f8962_month_1_a": 511,
        "f8962_month_1_b": 522,
        "f8962_month_1_c": 150,
        "f8962_month_1_d": 372,
        "f8962_month_1_e": 372,
        "f8962_month_1_f": 400,
        "f8962_line_24": 372,
        "f8962_line_25": 400,
        "f8962_line_26_net_ptc": 0,
        "f8962_line_27": 28,
        "f8962_line_28": 1_500,        # repayment limitation (capped)
        "f8962_line_29_repayment": 28,
    }


class FieldsOnTemplatePerYearTests(unittest.TestCase):
    def test_every_mapped_path_is_on_that_years_template(self):
        for year in _YEARS:
            with self.subTest(year=year):
                template = _template(year)
                self.assertTrue(template.exists(), f"missing {template}")
                on_template = set(
                    (PdfReader(str(template)).get_fields() or {}).keys())
                mapping = PdfF8962.get_mapping(year)
                referenced = set(mapping["scalars"].values())
                referenced |= set(PdfF8962.get_derivations(year).keys())
                self.assertGreater(len(referenced), 0)
                self.assertEqual(
                    referenced - on_template, set(),
                    f"f8962 {year}: mapping references off-template fields")

    def test_2021_maps_ui_box_but_later_years_do_not(self):
        self.assertIn("f8962_ui_box_checked",
                      PdfF8962.get_mapping(2021)["scalars"])
        for year in (2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertNotIn("f8962_ui_box_checked",
                                 PdfF8962.get_mapping(year)["scalars"])


class FilledEmitReadBackTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_2021_ui_box_on_and_monthly_write_in_rows(self):
        values = {**_capped_values(), "f8962_ui_box_checked": True}
        out = _fill(2021, values, self.tmp / "f8962_2021.pdf")
        read = _read_fields(out)
        # ARPA UI Box A ON with its own /2 token (NOT /1); 4c hardwired /3.
        self.assertEqual(read[_UI_BOX], "/2")
        self.assertEqual(read[_BOX_4C], "/3")
        # Monthly write-in row 1 (Jan) cells a & f, plus Part I / totals.
        self.assertEqual(read[_MONTH1_A], "511")
        self.assertEqual(read[_MONTH1_F], "400")
        self.assertEqual(read[_LINE_1], "1")
        self.assertEqual(read[_LINE_5], "220")
        self.assertEqual(read[_LINE_24], "372")

    def test_2024_no_ui_box_and_repayment_lines(self):
        # 2024 c1_1[0] is the MFS box — tenforty never maps it, so even a
        # True ui-box compute key must NOT land on the form (stays /Off).
        values = {**_capped_values(), "f8962_ui_box_checked": True}
        out = _fill(2024, values, self.tmp / "f8962_2024.pdf")
        read = _read_fields(out)
        # 2024 c1_1[0] is the MFS box (ON /1); unmapped -> stays unchecked.
        self.assertIn(read[_UI_BOX], ("", "/Off"))
        self.assertNotEqual(read[_UI_BOX], "/1")
        self.assertEqual(read[_BOX_4C], "/3")        # 4c still hardwired ON
        self.assertEqual(read[_LINE_28], "1500")     # repayment limitation
        self.assertEqual(read[_LINE_29], "28")       # excess APTC repayment

    def test_2021_checkbox_both_ways(self):
        on = _fill(2021, {**_capped_values(), "f8962_ui_box_checked": True},
                   self.tmp / "on.pdf")
        off = _fill(2021, {**_capped_values(), "f8962_ui_box_checked": False},
                    self.tmp / "off.pdf")
        self.assertEqual(_read_fields(on)[_UI_BOX], "/2")
        # False -> explicit /Off (never carries the /2 on-token).
        self.assertNotEqual(_read_fields(off)[_UI_BOX], "/2")

    def test_uncapped_line_28_none_renders_blank_not_the_string_none(self):
        # team-lead PIN: an uncapped case (line 5 >= 400%) has line 28 = None
        # in the result; the emitted cell must be BLANK, never "None".
        values = {
            **_capped_values(),
            "f8962_line_5": 450,          # >= 400% FPL -> uncapped
            "f8962_line_28": None,        # repayment limitation absent
            "f8962_line_29_repayment": 28,
        }
        out = _fill(2024, values, self.tmp / "uncapped.pdf")
        read = _read_fields(out)
        self.assertEqual(read[_LINE_28], "")
        self.assertNotIn("None", read[_LINE_28])
        # Sanity: a present neighbor still fills (blank isn't swallowing all).
        self.assertEqual(read[_LINE_29], "28")


def _scenario(year: int, *, form_1095a=None) -> Scenario:
    """Single-filer W-2 scenario above the EIC ceiling so PTC scenarios route
    to the native spine (mirrors tests/test_f8962_spine_wiring.py)."""
    wages = 40_000
    return Scenario(
        config=TaxReturnConfig(
            digital_assets=False,
            year=year,
            filing_status="single",
            birthdate="1990-06-15",
            state="TX",
            # Emit-time source-document gate (Task 3):
            # test_end_to_end_2024_emit_writes_f8962_with_4c_on drives
            # run_full_return with a W-2 carrying no `pdf`.
            acknowledges_no_source_documents=True,
            **scope_out_attestation_defaults(),
        ),
        w2s=[
            W2(
                employer="Acme Corp",
                wages=wages,
                federal_tax_withheld=4_000,
                ss_wages=wages,
                ss_tax_withheld=round(wages * 0.062),
                medicare_wages=wages,
                medicare_tax_withheld=round(wages * 0.0145),
            ),
        ],
        form_1095a=form_1095a,
    )


def _months(premium: float, slcsp: float, aptc: float):
    return tuple(
        Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc)
        for _ in range(12)
    )


class ShouldEmit8962Tests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def test_no_1095a_absent_from_predicate_emit_set_and_selector_universe(self):
        scenario = _scenario(2024, form_1095a=None)
        self.assertFalse(self.orch._should_emit_8962(scenario))
        results = self.orch.compute_federal(scenario)
        specs = self.orch._federal_individual_emit_specs(scenario, results)
        universe = {s.name for s in specs}
        self.assertNotIn("8962", universe)

    def test_all_zero_months_do_not_emit(self):
        scenario = _scenario(2024, form_1095a=Form1095A(months=_months(0, 0, 0)))
        self.assertFalse(self.orch._should_emit_8962(scenario))

    def test_1095a_with_nonzero_month_emits_and_joins_universe(self):
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=0))
        scenario = _scenario(2024, form_1095a=block)
        self.assertTrue(self.orch._should_emit_8962(scenario))
        results = self.orch.compute_federal(scenario)
        specs = self.orch._federal_individual_emit_specs(scenario, results)
        universe = {s.name for s in specs}
        self.assertIn("8962", universe)
        # The joined spec carries the year's checkbox_states + derivations so
        # the render and selector payload agree on the 4c always-on cell.
        (spec,) = [s for s in specs if s.name == "8962"]
        self.assertIn(_BOX_4C, spec.derivations)

    def test_end_to_end_2024_emit_writes_f8962_with_4c_on(self):
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=400))
        scenario = _scenario(2024, form_1095a=block)
        with tempfile.TemporaryDirectory() as tmp:
            _results, emitted = self.orch.run_full_return(scenario, Path(tmp))
            self.assertIn("8962", emitted)
            read = _read_fields(emitted["8962"])
            self.assertEqual(read[_BOX_4C], "/3")
            # Single filer -> 2024 MFS box c1_1[0] never checked (stays /Off).
            self.assertIn(read[_UI_BOX], ("", "/Off"))
            self.assertNotEqual(read[_UI_BOX], "/1")


_LINE_7 = f"{_ROOT}.f1_9[0]"          # applicable figure (a decimal, not dollars)


class Line7DecimalFormatTests(unittest.TestCase):
    """The renderer rounds numerics to whole dollars; the applicable figure
    (line 7, e.g. 0.0850) is a 4-decimal RATE, so it needs a per-field format
    override or it prints "0" and line 3 x line 7 = line 8a cannot foot."""

    # Synthetic figures that foot: 127649 * 0.085 = 10850.165 -> 10850.
    _VALUES = {
        "f8962_line_3": 127_649,
        "f8962_line_7": 0.085,
        "f8962_line_8a": 10_850,
    }

    @staticmethod
    def _fill_with_formats(year: int, values: dict, out: Path) -> Path:
        mapping = PdfF8962.get_mapping(year)["scalars"]
        PdfFiller().fill(
            template_path=_template(year),
            output_path=out,
            field_mapping=mapping,
            values=values,
            field_formats=PdfF8962.get_field_formats(year) or None,
        )
        return out

    def test_fill_and_read_back_shows_four_decimals_every_year(self):
        for year in _YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as tmp:
                out = self._fill_with_formats(
                    year, self._VALUES, Path(tmp) / "f8962.pdf")
                read = _read_fields(out)
                self.assertEqual(read[_LINE_7], "0.0850")
                # Neighbouring dollar lines keep the whole-dollar default.
                self.assertEqual(read[f"{_ROOT}.f1_6[0]"], "127649")
                self.assertEqual(read[f"{_ROOT}.f1_10[0]"], "10850")

    def test_override_leaves_ordinary_dollar_fields_untouched(self):
        """Pin: with the override mechanism engaged, every OTHER field renders
        byte-identically to the no-override render (whole dollars)."""
        year = 2025
        mapping = PdfF8962.get_mapping(year)["scalars"]
        values = {**_capped_values(), "f8962_line_7": 0.085,
                  "f8962_line_3": 30_000.5}  # a fractional dollar value too
        plain = PdfFiller.resolve_fields(mapping, values)
        formatted = PdfFiller.resolve_fields(
            mapping, values, field_formats=PdfF8962.get_field_formats(year))
        changed = {k for k in plain if plain[k] != formatted[k]}
        self.assertEqual(changed, {mapping["f8962_line_7"]})
        # Reachability of the negative space: the fractional dollar value DID
        # pass through the whole-dollar renderer (so an override that leaked
        # onto dollar fields would have shown up as a changed key).
        self.assertEqual(formatted[mapping["f8962_line_3"]], "30001")

    def test_declared_overrides_are_exactly_line_7_and_are_mapped_keys(self):
        for year in _YEARS:
            with self.subTest(year=year):
                formats = PdfF8962.get_field_formats(year)
                self.assertEqual(set(formats), {"f8962_line_7"})
                self.assertLessEqual(
                    set(formats), set(PdfF8962.get_mapping(year)["scalars"]))

    def test_emit_spec_carries_formats_and_payload_prints_decimal(self):
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets", work_dir=Path("."))
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=400))
        scenario = _scenario(2024, form_1095a=block)
        results = orch.compute_federal(scenario)
        specs = orch._federal_individual_emit_specs(scenario, results)
        (spec,) = [sp for sp in specs if sp.name == "8962"]
        payload = orch._federal_spec_payload(spec)
        line_7 = results["f8962_line_7"]
        self.assertGreater(line_7, 0)
        self.assertEqual(payload[_LINE_7], f"{line_7:.4f}")


class PartTwoPresentationTests(unittest.TestCase):
    """Lines 9 / 10 checkboxes, line 11 annual row, rows 12-23 monthly rows.

    i8962 (2024) Line 10: annual (line 11) is MANDATORY when enrolled all 12
    months (premium > 0) with identical col A and col B; otherwise "No" and the
    monthly rows are filled. Line 9 is always "No". Synthetic figures."""

    @staticmethod
    def _compute(months, year=2024, magi=30_000):
        from tenforty.forms import f8962 as form_f8962
        from tenforty.params import f8962 as params_f8962
        blk = Form1095A(months=tuple(
            Form1095AMonth(*m) if m else Form1095AMonth() for m in months))
        return form_f8962.compute(blk, magi, year, params_f8962.load(year))

    @staticmethod
    def _field_name(widget) -> str:
        parts = []
        node = widget
        while node is not None:
            node = node.get_object()
            if "/T" in node:
                parts.append(str(node["/T"]))
            node = node.get("/Parent")
        return ".".join(reversed(parts))

    def _fill_read(self, year, results, tmp):
        """Fill via the orchestrator's exact inputs; return ({name: /V},
        {name: widget /AS})."""
        out = Path(tmp) / "f8962.pdf"
        PdfFiller().fill(
            template_path=_template(year), output_path=out,
            field_mapping=PdfF8962.get_mapping(year)["scalars"],
            values=results,
            checkbox_states=PdfF8962.get_checkbox_states(year) or None,
            derivations=PdfF8962.get_derivations(year) or None,
            field_formats=PdfF8962.get_field_formats(year) or None,
        )
        reader = PdfReader(str(out))
        values = _read_fields(out)
        as_states = {}
        for page in reader.pages:
            for annot in page.get("/Annots", []):
                w = annot.get_object()
                if "/AS" in w:
                    as_states[self._field_name(w)] = str(w["/AS"])
        return values, as_states

    def _p(self, name):  # full path under Page1
        return f"{_ROOT}.{name}"

    def _assert_boxes(self, as_states, *, line10):
        no9 = self._p("c1_4[1]"); yes9 = self._p("c1_4[0]")
        yes10 = self._p("c1_5[0]"); no10 = self._p("c1_5[1]")
        self.assertEqual(as_states[no9], "/2")
        self.assertEqual(as_states[yes9], "/Off")
        if line10 == "yes":
            self.assertEqual(as_states[yes10], "/1")
            self.assertEqual(as_states[no10], "/Off")
        else:
            self.assertEqual(as_states[no10], "/2")
            self.assertEqual(as_states[yes10], "/Off")

    @staticmethod
    def _row_cell(year, n, letter):
        return PdfF8962.get_mapping(year)["scalars"][f"f8962_month_{n}_{letter}"]

    def test_full_year_identical_uses_annual_line_11(self):
        months = [(900.0, 850.0, 500.0)] * 12
        for year in _YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as tmp:
                r = self._compute(months, year)
                values, as_states = self._fill_read(year, r, tmp)
                self._assert_boxes(as_states, line10="yes")
                sc = PdfF8962.get_mapping(year)["scalars"]
                cells = [values[sc[f"f8962_line_11_{c}"]] for c in "abcdef"]
                self.assertEqual(cells[0], "10800")   # 12 * 900
                self.assertEqual(cells[1], "10200")   # 12 * 850
                self.assertEqual(cells[2], str(r["f8962_line_8a"]))
                self.assertEqual(
                    cells[3], str(max(0, 10_200 - r["f8962_line_8a"])))
                self.assertEqual(cells[4], str(r["f8962_line_24"]))  # 11(e)
                self.assertEqual(cells[5], "6000")    # 12 * 500 = 11(f)
                self.assertEqual(values[sc["f8962_line_25"]], cells[5])
                self.assertEqual(values[sc["f8962_line_24"]], cells[4])
                # rows 12-23 all blank
                for n in range(1, 13):
                    for c in "abcdef":
                        self.assertEqual(values[self._row_cell(year, n, c)], "")

    def test_aptc_variation_alone_does_not_block_annual(self):
        months = [(900.0, 850.0, 500.0 + 10 * i) for i in range(12)]
        r = self._compute(months)
        self.assertTrue(r["f8962_line_10_yes"])
        self.assertEqual(r["f8962_line_11_f"], sum(500 + 10 * i for i in range(12)))

    def test_full_year_varying_premium_stays_monthly(self):
        months = [(900.0, 850.0, 500.0)] * 6 + [(950.0, 850.0, 500.0)] * 6
        for year in _YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as tmp:
                r = self._compute(months, year)
                values, as_states = self._fill_read(year, r, tmp)
                self._assert_boxes(as_states, line10="no")
                sc = PdfF8962.get_mapping(year)["scalars"]
                for c in "abcdef":
                    self.assertEqual(values[sc[f"f8962_line_11_{c}"]], "")
                for n in range(1, 13):
                    self.assertNotEqual(values[self._row_cell(year, n, "a")], "")
                self.assertEqual(
                    int(values[sc["f8962_line_24"]]),
                    sum(int(values[self._row_cell(year, n, "e")])
                        for n in range(1, 13)))

    def test_varying_slcsp_stays_monthly(self):
        months = [(900.0, 850.0, 500.0)] * 11 + [(900.0, 860.0, 500.0)]
        self.assertTrue(self._compute(months)["f8962_line_10_no"])

    def test_unenrolled_month_blocks_annual_even_if_other_figures_identical(self):
        # Month 12: premium 0 (not enrolled) though SLCSP matches.
        months = [(900.0, 850.0, 500.0)] * 11 + [(0.0, 850.0, 0.0)]
        r = self._compute(months)
        self.assertTrue(r["f8962_line_10_no"])
        self.assertNotIn("f8962_line_10_yes", r)

    def test_zero_premium_all_year_is_not_enrolled_so_not_annual(self):
        # Identical (0, slcsp, 0) every month: identical col A and B, but no
        # enrollment premium -> not "enrolled" -> annual is NOT allowed.
        r = self._compute([(0.0, 850.0, 0.0)] * 12)
        self.assertTrue(r["f8962_line_10_no"])
        self.assertNotIn("f8962_line_11_a", r)

    def test_partial_year_jan_to_apr_monthly_rows_and_footing(self):
        months = [(800.0, 760.0, 450.0)] * 4 + [None] * 8
        for year in _YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as tmp:
                r = self._compute(months, year)
                values, as_states = self._fill_read(year, r, tmp)
                self._assert_boxes(as_states, line10="no")
                sc = PdfF8962.get_mapping(year)["scalars"]
                for c in "abcdef":
                    self.assertEqual(values[sc[f"f8962_line_11_{c}"]], "")
                for n in range(1, 5):                      # rows 12-15 filled
                    for c in "abcdef":
                        self.assertNotEqual(
                            values[self._row_cell(year, n, c)], "")
                for n in range(5, 13):                     # rows 16-23 blank
                    for c in "abcdef":
                        self.assertEqual(
                            values[self._row_cell(year, n, c)], "")
                col_e = sum(int(values[self._row_cell(year, n, "e")]) for n in range(1, 5))
                col_f = sum(int(values[self._row_cell(year, n, "f")]) for n in range(1, 5))
                self.assertEqual(int(values[sc["f8962_line_24"]]), col_e)
                self.assertEqual(int(values[sc["f8962_line_25"]]), col_f)
                self.assertEqual(col_f, 4 * 450)

    def test_box_and_line_11_widgets_sit_on_their_printed_lines(self):
        """Geometry cross-check of the probed paths (not derived from the
        mapping's own comments): widgets bind to the printed line labels."""
        for year in _YEARS:
            with self.subTest(year=year):
                page = PdfReader(str(_template(year))).pages[0]
                labels = {}
                def visit(text, cm, tm, fd, fs):
                    t = text.strip()
                    if t in ("9", "10", "11") and tm[4] < 50:
                        labels[t] = tm[5]
                page.extract_text(visitor_text=visit)
                lly = {}
                for annot in page.get("/Annots", []):
                    w = annot.get_object()
                    lly[self._field_name(w)] = float(w["/Rect"][1])
                for box, label in (("c1_4[0]", "9"), ("c1_4[1]", "9"),
                                   ("c1_5[0]", "10"), ("c1_5[1]", "10")):
                    y = lly[self._p(box)]
                    self.assertLess(y, labels[label])
                    self.assertGreaterEqual(y, labels[label] - 30, box)
                # line 9 boxes sit above line 10's label; line 10's above 11's.
                self.assertGreaterEqual(lly[self._p("c1_4[1]")], labels["10"])
                self.assertGreaterEqual(lly[self._p("c1_5[1]")], labels["11"])
                row11 = lly[self._p("Part2Table1[0].BodyRow1[0].f1_13[0]")]
                self.assertLess(abs(row11 + 2 - labels["11"]), 6)


if __name__ == "__main__":
    unittest.main()
