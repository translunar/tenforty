"""Emit-path upstream threading for Schedule C / Schedule SE.

The emit path must hand Schedule 1, Form 8959 and Form 8995 the SAME sch_c /
sch_se upstream the native compute path gives them. Synthetic values only."""
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f8959 as form_8959
from tenforty.forms import sch_1 as form_sch_1
from tenforty.models import ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario


class SchCEmitThreadingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )
        base = make_simple_scenario()
        self.scn = Scenario(
            config=base.config, w2s=base.w2s,
            schedule_c_businesses=[
                ScheduleCBusiness(description="Synthetic Consulting",
                                  gross_receipts=80_000.0, supplies=5_000.0),
            ])

    def test_helper_matches_the_native_schedule_results(self):
        native, _fanout = self.orch._compute_native_schedules(self.scn)
        sch_c, sch_se = self.orch._compute_sch_c_and_se(self.scn)
        self.assertEqual(sch_c, native["sch_c"])
        self.assertEqual(sch_se, native["sch_se"])
        self.assertGreater(sch_se["sch_se_line_12_se_tax"], 0)

    def test_schedule_1_fill_compute_agrees_with_native_lines_3_and_15(self):
        results = self.orch.compute_federal(self.scn)
        sch_c, sch_se = self.orch._compute_sch_c_and_se(self.scn)
        sch_1 = form_sch_1.compute(self.scn, upstream={
            "f1040": results, "sch_e": {}, "sch_c": sch_c, "sch_se": sch_se})
        self.assertEqual(sch_1["sch_1_line_3_business_income"],
                         results["sch_1_line_3_business_income"])
        self.assertEqual(sch_1["sch_1_line_15_se_tax"],
                         results["sch_1_line_15_se_tax"])
        self.assertNotEqual(sch_1["sch_1_line_3_business_income"], 0)
        self.assertNotEqual(sch_1["sch_1_line_15_se_tax"], 0)

    def test_form_8959_fill_compute_agrees_with_native_total(self):
        results = self.orch.compute_federal(self.scn)
        _sch_c, sch_se = self.orch._compute_sch_c_and_se(self.scn)
        f8959 = form_8959.compute(
            self.scn, upstream={"f1040": results, "sch_se": sch_se})
        self.assertEqual(f8959["f8959_line_18"], results["f8959_tax_total"])

    def test_no_business_returns_two_empty_dicts(self):
        self.assertEqual(
            self.orch._compute_sch_c_and_se(make_simple_scenario()), ({}, {}))


if __name__ == "__main__":
    unittest.main()
