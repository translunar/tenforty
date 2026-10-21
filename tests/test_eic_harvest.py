"""Form 1040 line 27 (earned income credit) and line 32 harvest wiring, and
the line-32 footing guard.

The vendor workbook computes the credit into the workbook-scoped `EIC` name
(the 1040 sheet's line-27 cell) in every year, sums it with lines 28-31 into
an unnamed line-32 cell, and sums that into `Tot_Payments` (line 33). Neither
27 nor 32 was harvested, so the credit reached line 33 while both printed
blank and the payments section did not foot. Static workbook checks use
openpyxl (no recalc); the computed amounts are exercised on the oracle tier
(test_eic_harvest_oracle.py). All identities synthetic.
"""
import dataclasses
import re
import tempfile
import unittest
from pathlib import Path

import openpyxl
import pypdf

from tenforty.mappings.f1040 import F1040
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import FilingStatus
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import eic_battery, spine_battery
from tests.helpers import SPREADSHEETS_DIR

YEARS = (2021, 2022, 2023, 2024, 2025)

# The line-32 cell ("total other payments and refundable credits") on the
# '1040' sheet and its SUM terms (lines 27-31), recon 2026-10-20. Unnamed in
# every year, so pinned by address; the exact-terms pin is the staleness
# guard against a silent vendor relayout.
LINE_32 = {
    2021: ("AC82", ["EIC", "Y78", "Y79", "RecoveryRebateCredit", "Y81"]),
    2022: ("AC86", ["EIC", "Y82", "Y83", "Y85"]),
    2023: ("AD92", ["EIC", "Z88", "Z89", "Z91"]),
    2024: ("AD95", ["EIC", "Z91", "Z92", "Z94"]),
    2025: ("AL123", ["EIC", "AF119", "AF120", "AU121", "AF122"]),
}


def _resolve(wb, name: str) -> tuple[str, str]:
    sheet, cell = wb.defined_names[name].value.split("!")
    return sheet.strip("'"), cell.replace("$", "")


def _orch(tmp: str) -> ReturnOrchestrator:
    return ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                              work_dir=Path(tmp) / "work")


def _printed(pdf_path: Path, year: int):
    fields = pypdf.PdfReader(str(pdf_path)).get_fields()
    paths = Pdf1040.get_mapping(year)

    def printed(key: str) -> str:
        value = fields[paths[key]].get("/V")
        return str(value) if value not in (None, "") else ""
    return printed


class EicHarvestWiringTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.workbooks = {
            year: openpyxl.load_workbook(
                SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx")
            for year in YEARS}

    @classmethod
    def tearDownClass(cls):
        for wb in cls.workbooks.values():
            wb.close()

    def test_eic_output_harvests_the_named_range(self):
        for year in YEARS:
            with self.subTest(year=year):
                self.assertEqual(F1040.get_outputs(year).get("eic"), "EIC")

    def test_eic_name_is_the_line_27_cell(self):
        for year, wb in self.workbooks.items():
            with self.subTest(year=year):
                sheet, cell = _resolve(wb, "EIC")
                self.assertEqual(sheet, "1040")
                self.assertIn("EarnedIncomeCredit", wb[sheet][cell].value)

    def test_line_32_output_harvests_the_pinned_cell(self):
        for year, (cell, _) in LINE_32.items():
            with self.subTest(year=year):
                self.assertEqual(
                    F1040.get_outputs(year).get("total_other_payments"), cell)
                self.assertEqual(
                    F1040.SHEET_MAP[year].get("total_other_payments"), "1040")

    def test_line_32_cell_sums_exactly_the_pinned_terms(self):
        for year, (cell, terms) in LINE_32.items():
            with self.subTest(year=year):
                formula = self.workbooks[year]["1040"][cell].value
                match = re.fullmatch(r"=SUM\(([^()]*)\)", formula)
                self.assertIsNotNone(match, f"{year} {cell}: {formula!r}")
                self.assertEqual(match.group(1).split(","), terms)

    def test_total_payments_sums_the_line_32_cell(self):
        for year, (cell, _) in LINE_32.items():
            with self.subTest(year=year):
                wb = self.workbooks[year]
                sheet, total = _resolve(wb, "Tot_Payments")
                self.assertEqual(sheet, "1040")
                self.assertIn(cell, wb[sheet][total].value)

    def test_lines_27_and_32_are_mapped_on_every_year_pdf(self):
        for year in YEARS:
            with self.subTest(year=year):
                mapping = Pdf1040.get_mapping(year)
                self.assertIn("eic", mapping)
                self.assertIn("total_other_payments", mapping)


class Line32FootingGuardTests(unittest.TestCase):
    """At 1040 emit, a harvested line 32 must equal the sum of the line-32
    components tenforty prints; otherwise the workbook included a payment
    tenforty cannot print and the emit refuses. Driven through the real emit
    path on a native compute, with the workbook harvest keys injected."""

    YEAR = 2024

    def _emit(self, tmp, **harvested):
        orch = _orch(tmp)
        scenario = spine_battery.build_wages_only(self.YEAR,
                                                  FilingStatus.SINGLE)
        results = {**orch.compute_federal(scenario), **harvested}
        return orch.emit_pdfs(scenario, results, Path(tmp) / "out")

    def test_footing_line_32_prints_with_line_27(self):
        with tempfile.TemporaryDirectory() as tmp:
            emitted = self._emit(tmp, eic=632, total_other_payments=632)
            printed = _printed(emitted["1040"], self.YEAR)
            self.assertEqual(printed("eic"), "632")
            self.assertEqual(printed("total_other_payments"), "632")

    def test_a_zero_credit_prints_zero_on_both_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            emitted = self._emit(tmp, eic=0, total_other_payments=0)
            printed = _printed(emitted["1040"], self.YEAR)
            self.assertEqual(printed("eic"), "0")
            self.assertEqual(printed("total_other_payments"), "0")

    def test_an_unprinted_component_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NotImplementedError) as ctx:
                self._emit(tmp, eic=632, total_other_payments=1632)
            self.assertIn("line 32", str(ctx.exception))
            self.assertIn("1632", str(ctx.exception))

    def test_line_32_without_line_27_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(NotImplementedError):
                self._emit(tmp, eic=None, total_other_payments=632)

    def test_no_harvested_line_32_is_not_guarded(self):
        # The native path never harvests line 32: nothing to compare.
        with tempfile.TemporaryDirectory() as tmp:
            emitted = self._emit(tmp)
            printed = _printed(emitted["1040"], self.YEAR)
            self.assertEqual(printed("total_other_payments"), "")


class OverCeilingRowTests(unittest.TestCase):
    """eic_battery over-ceiling: routes native (no EIC math), so line 27 and
    line 32 print blank by absence."""

    def test_line_27_is_blank(self):
        year = eic_battery.YEAR
        scenario = eic_battery.build_over_ceiling(year)
        with tempfile.TemporaryDirectory() as tmp:
            orch = _orch(tmp)
            self.assertTrue(orch._scenario_in_spine_scope(scenario))
            results = orch.compute_federal(scenario)
            self.assertNotIn("eic", results)
            emitted = orch.emit_pdfs(scenario, results, Path(tmp) / "out")
            printed = _printed(emitted["1040"], year)
            self.assertEqual(printed("eic"), "")
            self.assertEqual(printed("total_other_payments"), "")
