"""Catalog #10 / ruling R-S8-11: the 2022 template's Step 1 question 4
(nonresident alien) "No" derive is inverted, so an ordinary return leaves Q4
unanswered, EIC_Started is FALSE, and taxable interest, dividends and capital
gains drop out of investment income (E48:E50) — the Step 2 gate never fires
and the R-S7-10 refusal is never armed. The workbook path restores the derive
the other years carry. Static and engine-stopped checks only; the oracle
half is tests/test_eic_q4_answer_oracle.py. All identities synthetic.
"""
import functools
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import openpyxl

from tenforty.mappings.f1040 import (
    EIC_Q4_NO_CELL, EIC_Q4_NO_KEY, F1040, eic_q4_no_answer)
from tenforty.models import FilingStatus
from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.eic_battery import favorable_eligibility, favorable_person
from tests.helpers import SPREADSHEETS_DIR
from tests.test_eic_routing import _eic_possible_childless

# Each year's Q4 "No" cell (beside EIC_Started) as the template carries it.
Q4_NO_DERIVE = {
    2021: ("Line 27a (EIC)", "H39", "X"),
    2022: ("Line 27 (EIC)", "H38", '=IF(AND(B38="",EIC_Check),"X","")'),
    2023: ("Line 27 (EIC)", "H38", '=IF(B38="","X","")'),
    2024: ("Line 27 (EIC)", "H39", '=IF(AND(B39="",NOT(EIC_Check)),"X","")'),
    2025: ("Line 27a (EIC)", "H39", '=IF(AND(B39="",NOT(EIC_Check)),"X","")'),
}


@functools.cache
def _template(year):
    return openpyxl.load_workbook(
        SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx")


class Q4DeriveTests(unittest.TestCase):

    def test_each_years_q4_no_cell(self):
        # 2022 is the adjudicated observation (inverted: AND(…, EIC_Check));
        # a vendor change in any year fails here and is re-adjudicated.
        for year, (sheet, cell, value) in sorted(Q4_NO_DERIVE.items()):
            with self.subTest(year=year):
                self.assertEqual(_template(year)[sheet][cell].value, value)

    def test_only_2022_is_restored(self):
        self.assertEqual(set(EIC_Q4_NO_CELL), {2022})
        for year in sorted(F1040.INPUTS):
            with self.subTest(year=year):
                self.assertEqual(EIC_Q4_NO_KEY in F1040.get_inputs(year),
                                 year == 2022)

    def test_the_restored_answer_is_2023s_own_derive(self):
        self.assertEqual(eic_q4_no_answer(2022), Q4_NO_DERIVE[2023][2])
        self.assertEqual(EIC_Q4_NO_CELL[2022], Q4_NO_DERIVE[2022][:2])

    def test_the_2022_chain_the_inversion_starves(self):
        wb = _template(2022)
        sheet = wb["Line 27 (EIC)"]
        self.assertEqual(wb.defined_names["EIC_Started"].attr_text,
                         "'Line 27 (EIC)'!$A$38")
        self.assertEqual(sheet["A38"].value, '=OR(B38<>"",H38<>"")')
        for cell, source in (("E48", "TaxableInterest"),
                             ("E49", "OrdinaryDividends"),
                             ("E50", "MAX(0,CapitalGains)")):
            with self.subTest(cell=cell):
                self.assertEqual(
                    sheet[cell].value,
                    f'=IF(OR(NOT(EIC_Started),EIC_Check),"",{source})')
        self.assertEqual(sheet["B59"].value, '=IF(E52>N57,"X","")')
        # The prompt side (display only): 1040!AL84 -> AC82:AC84.
        self.assertEqual(
            wb["1040"]["AL84"].value,
            "=AND(EIC_trigger,NOT(EIC_Started),NumFileStatusBoxes=1)")


class Q4AnswerOnTheWorkbookPathTests(unittest.TestCase):

    def test_the_engine_writes_it_as_a_formula(self):
        sheet, cell = EIC_Q4_NO_CELL[2022]
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "1040.xlsx"
            shutil.copy2(SPREADSHEETS_DIR / "federal" / "2022" / "1040.xlsx",
                         copy)
            SpreadsheetEngine()._write_inputs(
                copy, F1040.get_inputs(2022), F1040.SHEET_MAP[2022],
                {EIC_Q4_NO_KEY: eic_q4_no_answer(2022)})
            self.assertEqual(openpyxl.load_workbook(copy)[sheet][cell].value,
                             eic_q4_no_answer(2022))

    def _handed(self, scenario):
        class Stop(Exception):
            pass
        seen = {}

        def record(**kwargs):
            seen.update(kwargs)
            raise Stop
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            eff, _ = orch._build_effective_scenario(scenario)
            with mock.patch.object(orch.engine, "compute", record), \
                    self.assertRaises(Stop):
                orch._compute_1040_via_workbook(eff)
        return seen["inputs"]

    def test_2022_hands_the_engine_the_answer_and_no_other_year_does(self):
        for year in (2022, 2021):
            for status in (FilingStatus.SINGLE,
                           FilingStatus.MARRIED_FILING_JOINTLY):
                with self.subTest(year=year, status=status.value):
                    inputs = self._handed(
                        _eic_possible_childless(year, status))
                    if year == 2022:
                        self.assertEqual(inputs[EIC_Q4_NO_KEY],
                                         eic_q4_no_answer(2022))
                    else:
                        self.assertNotIn(EIC_Q4_NO_KEY, inputs)

    def test_a_stated_nonresident_alien_refuses_before_the_answer(self):
        # R-S7-2 runs first: "No" is never written over a stated "Yes".
        scenario = _eic_possible_childless(2022, FilingStatus.SINGLE)
        scenario.eic_eligibility = favorable_eligibility(
            taxpayer=favorable_person(nonresident_alien_any_part_of_year=True))
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            eff, _ = orch._build_effective_scenario(scenario)
            engine = mock.Mock(side_effect=AssertionError("engine reached"))
            with mock.patch.object(orch.engine, "compute", engine), \
                    self.assertRaises(NotImplementedError) as ctx:
                orch._compute_1040_via_workbook(eff)
        self.assertTrue(str(ctx.exception).startswith(
            "workbook_eic_fact_not_modeled"))
        engine.assert_not_called()
