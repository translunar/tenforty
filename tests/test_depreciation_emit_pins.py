"""Literal-path pins: resolved depreciation as it lands on the filled PDFs.

The field paths below are LITERALS, read off each year's own template by
probe (the widget beside the printed "18" depreciation label in Schedule E's
property A column; the widget beside Schedule C's printed "13" label) --
never looked up through the mapping under test. They happen to be the same
path in every year 2021-2025; each year was probed separately.

6,970 and 2,000 are legacy regression pins (a January 27.5-year building on
200,000; first year of a five-year asset on 10,000), not hand oracles.
"""

import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.models import DepreciableAsset, RentalProperty, ScheduleCBusiness
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario

SCH_E_LINE_18_PROPERTY_A = {
    year: "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]"
    for year in (2021, 2022, 2023, 2024, 2025)}
SCH_C_LINE_13 = {
    year: "topmostSubform[0].Page1[0].Lines8-17[0].f1_22[0]"
    for year in (2021, 2022, 2023, 2024, 2025)}
# The neighbouring lines, to show the amount is on line 18 / 13 and nowhere
# adjacent (Schedule E line 17 utilities; Schedule C line 12 depletion).
SCH_E_LINE_17_PROPERTY_A = (
    "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_58[0]")
SCH_C_LINE_12 = "topmostSubform[0].Page1[0].Lines8-17[0].f1_21[0]"


def _read(pdf_path, field_path) -> str:
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "").replace(",", "").strip()


def _scenario(year: int, *, with_assets: bool = True):
    base = make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, first_name="Test", last_name="Filer",
        ssn="000-00-0000", acknowledges_no_source_documents=True)
    building = DepreciableAsset(
        description="Rental building", date_placed_in_service=date(year, 1, 15),
        basis=200_000.0, recovery_class="27.5-year")
    equipment = DepreciableAsset(
        description="Equipment", date_placed_in_service=date(year, 2, 1),
        basis=10_000.0, recovery_class="5-year",
        no_bonus_or_section_179_history=True)
    return dataclasses.replace(
        base, config=config,
        rental_properties=[RentalProperty(
            address="100 Example Street", property_type=1,
            fair_rental_days=365, personal_use_days=0, rents_received=24_000.0,
            depreciable_assets=[building] if with_assets else [])],
        schedule_c_businesses=[ScheduleCBusiness(
            description="Consulting", business_code="541990",
            gross_receipts=50_000.0,
            depreciable_assets=(equipment,) if with_assets else ())])


class DepreciationEmitPinTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR, work_dir=self.tmp / "work")

    def _emit(self, year: int, **kwargs) -> dict:
        scenario = _scenario(year, **kwargs)
        results = self.orchestrator.compute_federal(scenario)
        return self.orchestrator.emit_pdfs(
            scenario, results, self.tmp / f"out_{year}_{len(kwargs)}")

    def test_schedule_e_line_18_prints_the_resolved_amount(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                emitted = self._emit(year)
                self.assertEqual(
                    _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A[year]),
                    "6970")
                self.assertEqual(
                    _read(emitted["sch_e"], SCH_E_LINE_17_PROPERTY_A), "")

    def test_schedule_c_line_13_prints_the_resolved_amount(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                emitted = self._emit(year)
                self.assertEqual(
                    _read(emitted["sch_c_1"], SCH_C_LINE_13[year]), "2000")
                self.assertEqual(_read(emitted["sch_c_1"], SCH_C_LINE_12), "")

    def test_both_lines_blank_without_depreciation(self):
        for year in (2021, 2025):
            with self.subTest(year=year):
                emitted = self._emit(year, with_assets=False)
                self.assertEqual(
                    _read(emitted["sch_e"], SCH_E_LINE_18_PROPERTY_A[year]), "")
                self.assertEqual(
                    _read(emitted["sch_c_1"], SCH_C_LINE_13[year]), "")


if __name__ == "__main__":
    unittest.main()
