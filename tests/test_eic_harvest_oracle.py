"""Earned income credit battery, workbook path (oracle tier: these rows
route to the workbook, so they cannot run without LibreOffice).

Structural footing invariants only, on the emitted Form 1040: the credit
prints on line 27, line 32 equals the printed line-32 components, and line
33 equals 25d + 26 + 32 as printed. Exact credit amounts are pinned from the
first oracle run, not transcribed here. All identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice

YEAR = eic_battery.YEAR
LINE_32_COMPONENTS = (
    "eic", "additional_child_tax_credit", "american_opportunity_credit",
    "adoption_credit_8839", "schedule3_payments",
)


def _amount(fields, paths, key) -> int:
    value = fields[paths[key]].get("/V") if key in paths else None
    return int(str(value)) if value not in (None, "") else 0


@needs_libreoffice
class EicWorkbookRowsFootTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.printed = {}
        paths = Pdf1040.get_mapping(YEAR)
        for name in ("plateau", "phase-out"):
            scenario = eic_battery.SCENARIOS[name](YEAR)
            orch = ReturnOrchestrator(
                spreadsheets_dir=SPREADSHEETS_DIR,
                work_dir=Path(cls._tmp.name) / name / "work")
            assert not orch._scenario_in_spine_scope(scenario), name
            results = orch.compute_federal(scenario)
            emitted = orch.emit_pdfs(scenario, results,
                                     Path(cls._tmp.name) / name / "out")
            fields = pypdf.PdfReader(str(emitted["1040"])).get_fields()
            cls.printed[name] = {
                key: _amount(fields, paths, key)
                for key in (*LINE_32_COMPONENTS, "total_other_payments",
                            "federal_withheld", "estimated_tax_payments",
                            "total_payments")}

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_plateau_prints_the_credit_on_line_27(self):
        self.assertGreater(self.printed["plateau"]["eic"], 0)

    def test_phase_out_prints_a_partial_credit(self):
        partial = self.printed["phase-out"]["eic"]
        self.assertGreater(partial, 0)
        self.assertLess(partial, self.printed["plateau"]["eic"])

    def test_line_32_is_its_printed_components(self):
        for name, p in self.printed.items():
            with self.subTest(row=name):
                self.assertEqual(
                    p["total_other_payments"],
                    sum(p[key] for key in LINE_32_COMPONENTS))

    def test_line_33_is_25d_plus_26_plus_32(self):
        for name, p in self.printed.items():
            with self.subTest(row=name):
                self.assertEqual(
                    p["total_payments"],
                    p["federal_withheld"] + p["estimated_tax_payments"]
                    + p["total_other_payments"])
