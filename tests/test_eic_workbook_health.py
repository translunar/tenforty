"""Workbook-oracle health for the childless EIC (spec §10.3) and the
oracle-only answer adapter's mechanics (tests/eic_oracle_adapter.py) — all
static: openpyxl reads and the engine's own input writer, never a
recalculation, so nothing here reaches LibreOffice. All values synthetic or
read from params; nothing typed in."""
import functools
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import openpyxl

from tenforty.oracle.engine import SpreadsheetEngine
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_params
from tests import eic_oracle_adapter as adapter
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR

YEARS = tuple(sorted(adapter.EIC_WORKBOOK_CELLS))


@functools.cache
def _workbook(year):
    """The year's template, loaded once (read-only use only)."""
    return openpyxl.load_workbook(
        SPREADSHEETS_DIR / "federal" / str(year) / "1040.xlsx")


class WorkbookConstantsMatchParamsTests(unittest.TestCase):
    """§10.3 item 1: the EIC sheet's hardcoded constants equal the attested
    params. A mismatch means that year's workbook is not an oracle for the
    affected rows until adjudicated — never allowlisted."""

    def test_every_constant_cell(self):
        for year in YEARS:
            params = load_params(year)
            wb = _workbook(year)
            for (sheet, cell), field in adapter.EIC_WORKBOOK_CELLS[year][
                    "constants"].items():
                name, column = field if isinstance(field, tuple) else (
                    field, None)
                expected = getattr(params, name)
                if column is not None:
                    expected = expected[column]
                with self.subTest(year=year, cell=f"{sheet}!{cell}"):
                    self.assertEqual(wb[sheet][cell].value, expected)


class AnswerCellStructureTests(unittest.TestCase):
    """Each question has exactly one INPUT cell (blank in the template) and
    a formula for its other answer. A vendor relayout fails here."""

    def test_inputs_are_blank_and_the_derived_side_is_a_formula(self):
        for year in YEARS:
            cells = adapter.EIC_WORKBOOK_CELLS[year]
            wb = _workbook(year)
            for key, (sheet, cell) in cells["inputs"].items():
                with self.subTest(year=year, input=key):
                    self.assertIsNone(wb[sheet][cell].value)
            for cell in cells["derived"]:
                with self.subTest(year=year, derived=cell):
                    self.assertTrue(str(wb[cells["sheet"]][cell].value)
                                    .startswith("="))
            for key, (sheet, cell) in cells["diagnostics"].items():
                with self.subTest(year=year, diagnostic=key):
                    self.assertTrue(str(wb[sheet][cell].value)
                                    .startswith("="))


class AdapterWritesEveryAnswerTests(unittest.TestCase):
    """The answers land in the input cells through the engine's own writer
    (no recalculation), and the derived formulas survive."""

    def _written(self, year, scenario):
        mapping = adapter.answering_mapping(year)
        with tempfile.TemporaryDirectory() as tmp:
            copy = Path(tmp) / "1040.xlsx"
            shutil.copy2(SPREADSHEETS_DIR / "federal" / str(year)
                         / "1040.xlsx", copy)
            SpreadsheetEngine()._write_inputs(
                copy, mapping.get_inputs(year), mapping.SHEET_MAP[year],
                adapter.answers(scenario))
            return openpyxl.load_workbook(copy)

    def test_favorable_facts_clear_every_input_and_state_no_children(self):
        year = 2025
        cells = adapter.EIC_WORKBOOK_CELLS[year]
        wb = self._written(year, eic_battery.battery_for(
            year, "single")["plateau"](year))
        for key, (sheet, cell) in cells["inputs"].items():
            with self.subTest(input=key):
                expected = 0 if key == "eic_answer_qualifying_children" \
                    else None
                self.assertEqual(wb[sheet][cell].value, expected)
        for cell in cells["derived"]:
            self.assertTrue(str(wb[cells["sheet"]][cell].value)
                            .startswith("="))

    def test_each_unfavorable_fact_marks_only_its_own_answer(self):
        # Pure: which answer each stated fact sets (the cell it lands in is
        # proven by the writes in this class).
        for kind, key in (
                ("fact_ssn_not_valid", "eic_answer_ssn_not_valid"),
                ("fact_nonresident_alien", "eic_answer_nonresident_alien"),
                ("fact_main_home_not_in_us", "eic_answer_main_home_not_us"),
                ("fact_qualifying_child_of_another",
                 "eic_answer_qc_of_another"),
                ("fact_claimable_as_dependent", "eic_answer_dependent_you")):
            with self.subTest(kind=kind):
                got = adapter.answers(eic_battery.battery_for(
                    2025, "single")[kind](2025))
                self.assertEqual({k for k, v in got.items() if v == "X"},
                                 {key})

    def test_an_unfavorable_fact_lands_in_its_cell(self):
        year = 2025
        sheet, cell = adapter.EIC_WORKBOOK_CELLS[year]["inputs"][
            "eic_answer_ssn_not_valid"]
        wb = self._written(year, eic_battery.battery_for(
            year, "single")["fact_ssn_not_valid"](year))
        self.assertEqual(wb[sheet][cell].value, "X")


class AdapterRoutesThroughTheEngineTests(unittest.TestCase):
    """Inside the adapter, the workbook path hands the engine the answering
    mapping and the answers (the engine is stopped before recalculation)."""

    def test_the_engine_receives_the_answers(self):
        class Stop(Exception):
            pass
        seen = {}

        def record(**kwargs):
            seen.update(kwargs)
            raise Stop
        scenario = eic_battery.battery_for(2025, "single")["plateau"](2025)
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            with mock.patch.object(orch.engine, "compute", record):
                with adapter.eic_answers_adapter(orch):
                    eff, _ = orch._build_effective_scenario(scenario)
                    with self.assertRaises(Stop):
                        orch._compute_1040_via_workbook(eff)
        self.assertIn("eic_answer_qualifying_children", seen["inputs"])
        self.assertIn("eic_answer_ssn_not_valid",
                      seen["mapping"].get_inputs(2025))
        self.assertIn("eic_diag_prompt_ao",
                      seen["mapping"].get_outputs(2025))
