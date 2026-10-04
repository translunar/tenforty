"""Schedule C Part V itemization: the line 48 total needs a printed row.

Line 48 (total other expenses) flows to line 27a/27b; the paper form wants the
itemization above it. v1 is single-aggregate: ONE row (description + amount),
whose amount equals line 48. A nonzero total with no description is refused AT
EMIT (the number is computable; the PAPER requires the itemization), in the
`digital_assets` style. Synthetic figures only."""
import dataclasses
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.models import ScheduleCBusiness
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults
from tests.test_sch_c_emit import _scenario

_PAGE2 = "topmostSubform[0].Page2[0]"
_DESC = f"{_PAGE2}.PartVTable[0].Item1[0].f2_15[0]"
_AMT = f"{_PAGE2}.PartVTable[0].Item1[0].f2_16[0]"
_ROW2_DESC = f"{_PAGE2}.PartVTable[0].Item2[0].f2_17[0]"
_LINE_48 = f"{_PAGE2}.f2_33[0]"


def _biz(**kw):
    base = dict(description="Synthetic Consulting", gross_receipts=80_000.0,
                supplies=5_000.0)
    base.update(kw)
    return ScheduleCBusiness(**base)


def _read(pdf, path):
    fields = PdfReader(str(pdf)).get_fields() or {}
    return str(fields[path].get("/V") or "")


class PartVItemizationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _emit(self, year, biz):
        scn = _scenario(year=year, businesses=[biz])
        results = self.orch.compute_federal(scn)
        return self.orch.emit_pdfs(scn, results, self.tmp / f"o{year}")

    def test_nonzero_other_expenses_without_description_refused_at_emit(self):
        scn = _scenario(businesses=[_biz(other_expenses=1_200.0)])
        results = self.orch.compute_federal(scn)  # compute is NOT refused
        self.assertGreater(results["sch_1_line_3_business_income"], 0)
        with self.assertRaises(ValueError) as ctx:
            self.orch.emit_pdfs(scn, results, self.tmp / "out")
        msg = str(ctx.exception)
        self.assertIn("other_expenses_description", msg)
        self.assertIn("Synthetic Consulting", msg)

    def test_whitespace_description_is_empty(self):
        scn = _scenario(businesses=[_biz(
            other_expenses=1_200.0, other_expenses_description="   ")])
        results = self.orch.compute_federal(scn)
        with self.assertRaises(ValueError):
            self.orch.emit_pdfs(scn, results, self.tmp / "out")

    def test_zero_other_expenses_needs_no_description(self):
        emitted = self._emit(2025, _biz())
        self.assertEqual(_read(emitted["sch_c_1"], _DESC), "")
        self.assertEqual(_read(emitted["sch_c_1"], _AMT), "")

    def test_row_one_filled_and_line_48_equals_it_every_year(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                emitted = self._emit(year, _biz(
                    other_expenses=1_200.0,
                    other_expenses_description="Synthetic software fees"))
                pdf = emitted["sch_c_1"]
                self.assertEqual(_read(pdf, _DESC), "Synthetic software fees")
                self.assertEqual(_read(pdf, _AMT), "1200")
                self.assertEqual(_read(pdf, _LINE_48), "1200")
                # Single-aggregate v1: row 2 stays blank.
                self.assertEqual(_read(pdf, _ROW2_DESC), "")

    def test_mapping_paths_every_year(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                m = PdfSchC.get_mapping(year)
                self.assertEqual(m["sch_c_part_v_row_1_description"], _DESC)
                self.assertEqual(m["sch_c_part_v_row_1_amount"], _AMT)

    def test_loader_reads_the_description_field(self):
        body = {
            "config": {
                "year": 2025, "filing_status": "single",
                "birthdate": "1985-04-20", "state": "CA",
                "has_foreign_accounts": False, "prior_year_itemized": False,
                **scope_out_attestation_defaults(),
            },
            "schedule_c_businesses": [{
                "description": "Synthetic Consulting", "gross_receipts": 1000,
                "other_expenses": 10,
                "other_expenses_description": "Synthetic fees"}],
        }
        path = self.tmp / "s.yaml"
        path.write_text(yaml.safe_dump(body))
        scn = load_scenario(path)
        self.assertEqual(
            scn.schedule_c_businesses[0].other_expenses_description,
            "Synthetic fees")


if __name__ == "__main__":
    unittest.main()
