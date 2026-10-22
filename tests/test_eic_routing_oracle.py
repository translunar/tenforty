"""Ruling R-S6-1, oracle tier: on every SINGLE/MFJ spine cell whose
childless credit is NOT native yet (years.NATIVE_EIC_STATUSES), an
EIC-possible childless return keeps the workbook route AND gets its
harvested line 27. The fast tier (test_eic_routing.TransitionalCoverageTests)
proves the route; this proves the credit is there. Each cell's case dies
when that cell lands in the EIC grid. All identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path

from tenforty import years
from tenforty.models import FilingStatus
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice
from tests.test_eic_routing import _eic_possible_childless, _spine_cells

SINGLE, MFJ = FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY


@needs_libreoffice
class TransitionalCellsGetTheirCreditTests(unittest.TestCase):

    def test_each_undeclared_cell_routes_to_the_workbook_with_a_credit(self):
        cells = [(y, s) for y, s in _spine_cells()
                 if not years.native_eic_supports(y, s.value)]
        self.assertGreater(len(cells), 0)
        for year, status in cells:
            with self.subTest(year=year, status=status.value):
                scenario = _eic_possible_childless(year, status)
                with tempfile.TemporaryDirectory() as tmp:
                    orch = ReturnOrchestrator(
                        spreadsheets_dir=SPREADSHEETS_DIR,
                        work_dir=Path(tmp))
                    eff, _ = orch._build_effective_scenario(scenario)
                    self.assertFalse(orch._scenario_in_spine_scope(eff))
                    results = orch.compute_federal(scenario)
                self.assertGreater(results.get("eic") or 0, 0)
