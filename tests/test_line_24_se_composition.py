"""1040 line 24 (native path) includes Schedule 2 Part II — self-employment tax.

The native composition in forms/f4868.py::total_tax_liability_line_24 omitted
Part II (its docstring claimed there was no Schedule C surface), so a Schedule C
return printed line 24 = line 22 while line 23 was nonzero. The refund lines
were right (the spine's settlement math includes SE tax); only the printed
line 24 and the 4868's line 4 were short. Synthetic figures only."""
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f4868
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT
from tests.test_sch_c_emit import _ONE, _scenario


class ComposeFromSpineOtherTaxesTests(unittest.TestCase):
    def test_native_line_24_adds_the_spines_schedule_2_part_ii_total(self):
        f1040 = {"total_tax": 10_000, "schedule2_tax": 0,
                 "nonrefundable_credits": 0, "other_taxes": 3_150}
        self.assertEqual(f4868.total_tax_liability_line_24(f1040), 13_150)

    def test_zero_floor_still_sits_inside_line_22_only(self):
        # Credits exceed line 18: line 22 floors at 0, Part II still added.
        f1040 = {"total_tax": 1_000, "schedule2_tax": 0,
                 "nonrefundable_credits": 5_000, "other_taxes": 3_150}
        self.assertEqual(f4868.total_tax_liability_line_24(f1040), 3_150)

    def test_workbook_harvest_is_untouched_by_other_taxes(self):
        f1040 = {"tax_liability_line24": 9_999, "total_tax": 1,
                 "other_taxes": 3_150}
        self.assertEqual(f4868.total_tax_liability_line_24(f1040), 9_999)


class SchCPrintedChainTests(unittest.TestCase):
    YEAR = 2025

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")
        self.scn = _scenario(year=self.YEAR, businesses=_ONE)
        self.results = self.orch.compute_federal(self.scn)

    def _fields(self):
        specs = self.orch._federal_individual_emit_specs(self.scn, self.results)
        spec = next(s for s in specs if s.name == "1040")
        return ReturnOrchestrator._federal_spec_payload(spec)

    def test_scenario_really_has_se_tax_in_line_23(self):
        # Precondition: the case under test has a nonzero Part II.
        self.assertGreater(self.results["sch_se_line_12_se_tax"], 0)
        self.assertEqual(
            self.results["other_taxes"],
            round(self.results["sch_se_line_12_se_tax"]
                  + self.results["f8959_tax_total"]))

    def test_printed_line_24_equals_printed_line_22_plus_line_23(self):
        fields = self._fields()
        m = Pdf1040.get_mapping(self.YEAR)
        line_22 = int(fields[m["tax_after_credits"]])
        line_23 = int(fields[m["other_taxes"]])
        line_24 = int(fields[m["tax_liability_line24"]])
        self.assertGreater(line_23, 0)
        self.assertEqual(line_24, line_22 + line_23)

    def test_4868_line_4_is_the_se_inclusive_total(self):
        out = f4868.compute(self.scn, upstream={"f1040": self.results})
        line_22 = round(self.results["tax_after_credits"])
        self.assertEqual(
            out["estimated_total_tax"],
            line_22 + self.results["other_taxes"])
        self.assertGreater(
            out["estimated_total_tax"], line_22)

    def test_schedule_2_emit_gate_unchanged_on_native_path(self):
        # The gate keys on the WORKBOOK-harvested key's presence; the native
        # spine still must not publish it.
        self.assertNotIn("tax_liability_line24", self.results)
        self.assertTrue(
            self.orch._should_emit_sch_2(self.scn, self.results))


if __name__ == "__main__":
    unittest.main()
