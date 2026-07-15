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
            year=year,
            filing_status="single",
            birthdate="1990-06-15",
            state="TX",
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


if __name__ == "__main__":
    unittest.main()
