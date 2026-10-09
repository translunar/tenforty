"""Schedule 2 emit gate and fill, for returns WITHOUT a Schedule C business.

Native pypdf fills only (no soffice). Synthetic values only."""
import dataclasses
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from pypdf import PdfReader

from tenforty import pdf_packet, years
from tenforty.mappings.pdf_sch_2 import PdfSch2
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_ptc_capped_repayment
from tests.helpers import REPO_ROOT, make_simple_scenario


def _read_v(pdf_path, field_path):
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


def _high_wage_scenario(year: int):
    """Single filer whose Medicare wages clear the Additional Medicare Tax
    threshold in every year."""
    base = make_simple_scenario()
    w2 = dataclasses.replace(
        base.w2s[0], wages=260_000.0, federal_tax_withheld=60_000.0,
        ss_wages=140_000.0, ss_tax_withheld=8_680.0,
        medicare_wages=260_000.0, medicare_tax_withheld=4_310.0)
    return dataclasses.replace(
        base, config=dataclasses.replace(base.config, year=year), w2s=[w2])


class Sch2EmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )

    def test_additional_medicare_tax_emits_schedule_2(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                scn = _high_wage_scenario(year)
                results = self.orch.compute_federal(scn)
                self.assertGreater(results["f8959_tax_total"], 0)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                self.assertIn("sch_2", emitted)
                self.assertEqual(
                    emitted["sch_2"].name, f"f1040s2_{year}.pdf")
                mapping = PdfSch2.get_mapping(year)
                self.assertEqual(
                    int(_read_v(emitted["sch_2"],
                                mapping["sch_2_line_11_additional_medicare_tax"])),
                    results["f8959_tax_total"])
                self.assertEqual(
                    int(_read_v(emitted["sch_2"],
                                mapping["sch_2_line_21_total_other_taxes"])),
                    results["other_taxes"])
                self.assertEqual(
                    pdf_packet.classify_key("sch_2"), "federal_individual")

    def test_excess_aptc_repayment_emits_schedule_2_on_the_years_line(self):
        for year, key in ((2021, "sch_2_line_2_excess_aptc_repayment"),
                          (2023, "sch_2_line_2_excess_aptc_repayment"),
                          (2024, "sch_2_line_1a_excess_aptc_repayment")):
            with self.subTest(year=year):
                scn = build_ptc_capped_repayment(year)
                results = self.orch.compute_federal(scn)
                self.assertGreater(results["f8962_repayment"], 0)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                mapping = PdfSch2.get_mapping(year)
                self.assertEqual(
                    int(_read_v(emitted["sch_2"], mapping[key])),
                    results["f8962_repayment"])
                self.assertEqual(
                    int(_read_v(emitted["sch_2"],
                                mapping["sch_2_line_3_part_i_total"])),
                    results["schedule2_tax"])

    def test_no_component_no_schedule_2(self):
        scn = make_simple_scenario()
        results = self.orch.compute_federal(scn)
        self.assertNotIn(
            "sch_2", self.orch.emit_pdfs(scn, results, self.tmp / "plain"))

    def test_a_year_outside_the_family_never_emits_schedule_2(self):
        # The Schedule 2 gate reads years.SCHEDULE_C_FAMILY_YEARS and nothing
        # else: with 2021 taken out of the family, the same TY2021 return
        # that emits Schedule 2 above emits none.
        scn = build_ptc_capped_repayment(2021)
        results = self.orch.compute_federal(scn)
        self.assertGreater(results["f8962_repayment"], 0)
        with mock.patch.object(
                years, "SCHEDULE_C_FAMILY_YEARS", (2022, 2023, 2024, 2025)):
            self.assertNotIn(
                "sch_2",
                self.orch.emit_pdfs(scn, results, self.tmp / "y2021"))

    def test_gate_tolerates_none_and_missing_components(self):
        scn = make_simple_scenario()
        self.assertFalse(self.orch._should_emit_sch_2(scn, {}))
        self.assertFalse(self.orch._should_emit_sch_2(
            scn, {"f8962_repayment": None, "f8959_tax_total": None}))
        self.assertTrue(self.orch._should_emit_sch_2(
            scn, {"f8959_tax_total": 90}))

    def test_workbook_path_results_never_emit_schedule_2(self):
        # The workbook path's results carry the harvested line-24 key; its
        # 1040 can include AMT / NIIT that Schedule 2's modeled lines do not,
        # so an attached Schedule 2 could total less than its own 1040.
        scn = make_simple_scenario()
        self.assertFalse(self.orch._should_emit_sch_2(
            scn, {"f8959_tax_total": 90, "tax_liability_line24": 40_000}))


if __name__ == "__main__":
    unittest.main()
