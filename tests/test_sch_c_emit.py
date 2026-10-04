"""Schedule C / Schedule SE emit through the real entry points.

Replaces the fail-closed emit guard test: Schedule C returns now emit for
2022-2025 and refuse only below the year floor. Every expected value is read
from the native compute for the same scenario -- the property under test is
that the EMITTED forms agree with the compute. Native pypdf fills only (no
soffice). Synthetic values only."""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import pdf_packet, years
from tenforty.forms import sch_c as form_sch_c
from tenforty.mappings.pdf_f8995 import PdfF8995
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_2 import PdfSch2
from tenforty.mappings.pdf_sch_c import PdfSchC
from tenforty.mappings.pdf_sch_ca import PdfSchCa
from tenforty.mappings.pdf_sch_se import PdfSchSe
from tenforty.models import CA540Return, ScheduleCBusiness, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import (
    CA_SCOPE_OUT_FIELDS, REPO_ROOT, make_k1_scenario, make_simple_scenario,
)


def _read_v(pdf_path, field_path):
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


def _scalars(mapping):
    return mapping["scalars"] if "scalars" in mapping else mapping


def _scenario(year=2025, businesses=None, base=None, **config_overrides):
    base = base or make_simple_scenario()
    config = dataclasses.replace(
        base.config, year=year, acknowledges_no_source_documents=True,
        **config_overrides)
    return dataclasses.replace(
        base, config=config, schedule_c_businesses=list(businesses or []))


_ONE = [ScheduleCBusiness(description="Synthetic Consulting",
                          business_code="541990", gross_receipts=80_000.0,
                          supplies=5_000.0)]
_TWO = [
    ScheduleCBusiness(description="Synthetic Tutoring",
                      gross_receipts=31_000.0, supplies=1_000.0),
    ScheduleCBusiness(description="Synthetic Crafts",
                      gross_receipts=14_500.0, utilities=500.0,
                      other_expenses=1_000.0,
                      other_expenses_description="Synthetic booth fees"),
]


class SchCEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )

    # --- year floor -------------------------------------------------------
    def test_ty2021_refuses_with_the_year_floor_message(self):
        scn = _scenario(year=2021, businesses=_ONE)
        results = self.orch.compute_federal(scn)   # compute is unrestricted
        self.assertEqual(results["sch_1_line_3_business_income"], 75_000)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.emit_pdfs(scn, results, self.tmp / "out")
        msg = str(ctx.exception)
        self.assertIn("Schedule C", msg)
        self.assertIn("2021", msg)
        self.assertIn("2022, 2023, 2024, 2025", msg)
        self.assertIn("compute_federal", msg)

    def test_ty2021_without_a_business_still_emits(self):
        scn = _scenario(year=2021)
        results = self.orch.compute_federal(scn)
        self.assertIn("1040", self.orch.emit_pdfs(scn, results, self.tmp / "o"))

    # --- threading regression guard, via emit_pdfs ------------------------
    def test_emitted_schedule_1_lines_3_and_15_equal_native(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                scn = _scenario(year=year, businesses=_ONE)
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                sch_1 = _scalars(PdfSch1.get_mapping(year))
                line_3 = int(_read_v(
                    emitted["sch_1"], sch_1["sch_1_line_3_business_income"]))
                line_15 = int(_read_v(
                    emitted["sch_1"], sch_1["sch_1_line_15_se_tax"]))
                self.assertEqual(line_3, results["sch_1_line_3_business_income"])
                self.assertEqual(line_15, results["sch_1_line_15_se_tax"])
                self.assertGreater(line_3, 0)
                self.assertGreater(line_15, 0)

    def test_form_8959_spec_values_equal_native(self):
        big = [ScheduleCBusiness(description="Synthetic Consulting",
                                 gross_receipts=200_000.0, supplies=5_000.0)]
        # acknowledges_qbi_below_threshold=True is set SOLELY to get past the
        # Form 8995 threshold gate so the Form 8959 -> Schedule 2 threading
        # can be exercised end-to-end. It is NOT an endorsement of the
        # attestation: at this income the simple-path QBI figure is invalid
        # (that is the gate's whole point), so this test asserts ONLY Form
        # 8959 / Schedule 2 / threading keys and must never assert a QBI or
        # Form 8995 output.
        scn = _scenario(businesses=big, acknowledges_qbi_below_threshold=True)
        results = self.orch.compute_federal(scn)
        self.assertGreater(results["f8959_tax_total"], 0)
        specs = {s.name: s for s in
                 self.orch._federal_individual_emit_specs(scn, results)}
        self.assertEqual(specs["8959"].values["f8959_line_18"],
                         results["f8959_tax_total"])
        self.assertGreater(specs["8959"].values["f8959_line_8"], 0)
        self.assertEqual(
            specs["sch_2"].values["sch_2_line_11_additional_medicare_tax"],
            results["f8959_tax_total"])

    def test_form_8995_spec_values_equal_native(self):
        base = make_k1_scenario()
        base = dataclasses.replace(base, schedule_k1s=[ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=10_000.0, qbi_amount=10_000.0)])
        scn = _scenario(businesses=_ONE, base=base)
        results = self.orch.compute_federal(scn)
        specs = {s.name: s for s in
                 self.orch._federal_individual_emit_specs(scn, results)}
        self.assertEqual(
            specs["f8995"].values["f8995_line_15_qbi_deduction"],
            results["qbi_deduction"])
        self.assertGreater(results["qbi_deduction"], 0)

    def test_schedule_c_only_return_emits_form_8995(self):
        # No K-1 anywhere: the QBI deduction comes from Schedule C alone, and
        # the 1040's line 13 must have its Form 8995 behind it.
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                scn = _scenario(year=year, businesses=_ONE)
                self.assertEqual(scn.schedule_k1s, [])
                results = self.orch.compute_federal(scn)
                self.assertGreater(results["qbi_deduction"], 0)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                self.assertIn("f8995", emitted)
                field = PdfF8995.get_mapping(year)["scalars"][
                    "f8995_line_15_qbi_deduction"]
                self.assertEqual(
                    int(_read_v(emitted["f8995"], field)),
                    results["qbi_deduction"])

    def test_no_qbi_source_emits_no_form_8995(self):
        scn = _scenario()
        results = self.orch.compute_federal(scn)
        self.assertNotIn(
            "f8995", self.orch.emit_pdfs(scn, results, self.tmp / "plain"))

    # --- Schedule C / SE / 2 specs ----------------------------------------
    def test_single_business_is_indexed(self):
        scn = _scenario(businesses=_ONE)
        results = self.orch.compute_federal(scn)
        emitted = self.orch.emit_pdfs(scn, results, self.tmp / "out")
        self.assertIn("sch_c_1", emitted)
        self.assertNotIn("sch_c", emitted)
        self.assertEqual(emitted["sch_c_1"].name, "f1040sc_1_2025.pdf")
        self.assertEqual(emitted["sch_se"].name, "f1040sse_2025.pdf")

    def test_multi_business_emits_n_schedule_c_and_one_schedule_se(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                scn = _scenario(year=year, businesses=_TWO)
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                self.assertEqual(
                    sorted(k for k in emitted if k.startswith("sch_c_")),
                    ["sch_c_1", "sch_c_2"])
                self.assertIn("sch_se", emitted)
                self.assertIn("sch_2", emitted)
                per_business = form_sch_c.compute(scn, {})["sch_c_businesses"]
                mapping = PdfSchC.get_mapping(year)
                for n, lines in enumerate(per_business, start=1):
                    pdf = emitted[f"sch_c_{n}"]
                    self.assertEqual(pdf.name, f"f1040sc_{n}_{year}.pdf")
                    for key in ("sch_c_line_7_gross_income",
                                "sch_c_line_28_total_expenses",
                                "sch_c_line_31_net_profit"):
                        self.assertEqual(
                            int(_read_v(pdf, mapping[key])), lines[key])
                self.assertEqual(
                    _read_v(emitted["sch_c_2"],
                            mapping["sch_c_line_a_description"]),
                    "Synthetic Crafts")
                self.assertEqual(
                    _read_v(emitted["sch_c_1"],
                            "topmostSubform[0].Page1[0].c1_1[0]"), "/1")

    def test_schedule_se_and_schedule_2_equal_native(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                scn = _scenario(year=year, businesses=_TWO)
                results = self.orch.compute_federal(scn)
                emitted = self.orch.emit_pdfs(scn, results, self.tmp / str(year))
                se_map = PdfSchSe.get_mapping(year)
                s2_map = PdfSch2.get_mapping(year)
                se_tax = results["sch_se_line_12_se_tax"]
                self.assertGreater(se_tax, 0)
                self.assertEqual(int(_read_v(
                    emitted["sch_se"], se_map["sch_se_line_12_se_tax"])), se_tax)
                self.assertEqual(int(_read_v(
                    emitted["sch_se"], se_map["sch_se_line_13_half_deduction"])),
                    results["sch_1_line_15_se_tax"])
                self.assertEqual(int(_read_v(
                    emitted["sch_2"], s2_map["sch_2_line_4_se_tax"])), se_tax)
                self.assertEqual(int(_read_v(
                    emitted["sch_2"], s2_map["sch_2_line_21_total_other_taxes"])),
                    results["other_taxes"])

    def test_under_400_net_earnings_emits_schedule_c_only(self):
        tiny = [ScheduleCBusiness(description="Synthetic Sideline",
                                  gross_receipts=1_100.0, supplies=750.0)]
        scn = _scenario(businesses=tiny)
        results = self.orch.compute_federal(scn)
        self.assertEqual(results["sch_se_line_12_se_tax"], 0)
        emitted = self.orch.emit_pdfs(scn, results, self.tmp / "out")
        self.assertIn("sch_c_1", emitted)
        self.assertIn("sch_1", emitted)
        self.assertNotIn("sch_se", emitted)
        self.assertNotIn("sch_2", emitted)

    # --- packet -----------------------------------------------------------
    def test_every_emitted_key_is_claimed_and_ordered_by_sequence(self):
        scn = _scenario(businesses=_TWO)
        results = self.orch.compute_federal(scn)
        emitted = self.orch.emit_pdfs(scn, results, self.tmp / "out")
        for key in emitted:
            with self.subTest(key=key):
                self.assertIsNotNone(pdf_packet.classify_key(key))
        names = [p.name for p in pdf_packet.ordered_members(
            emitted, pdf_packet.FEDERAL_INDIVIDUAL)]
        self.assertEqual(names, [
            "f1040_2025.pdf", "f1040s1_2025.pdf", "f1040s2_2025.pdf",
            "f1040sc_1_2025.pdf", "f1040sc_2_2025.pdf", "f1040sse_2025.pdf",
            "f8995_2025.pdf",
        ])

    # --- refusals and the source-document gate ----------------------------
    def test_compute_layer_refusal_reaches_the_emit_caller(self):
        bad = [ScheduleCBusiness(description="Synthetic Retail",
                                 gross_receipts=50_000.0,
                                 cost_of_goods_sold=10_000.0)]
        scn = _scenario(businesses=bad)
        out = self.tmp / "refused"
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.run_full_return(scn, out)
        self.assertIn("cost_of_goods_sold", str(ctx.exception))
        self.assertFalse(out.exists() and any(out.glob("*.pdf")))
        good_results = self.orch.compute_federal(_scenario(businesses=_ONE))
        with self.assertRaises(NotImplementedError):
            self.orch._federal_individual_emit_specs(scn, good_results)

    def test_source_document_gate_applies_unchanged(self):
        scn = _scenario(businesses=_ONE)
        scn = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, acknowledges_no_source_documents=False))
        with self.assertRaises(ValueError) as ctx:
            self.orch.run_full_return(scn, self.tmp / "gated")
        self.assertIn("source document", str(ctx.exception))

    def test_run_full_return_emits_the_schedule_c_family(self):
        _results, emitted = self.orch.run_full_return(
            _scenario(businesses=_ONE), self.tmp / "full")
        for key in ("1040", "sch_1", "sch_2", "sch_c_1", "sch_se"):
            self.assertIn(key, emitted)
            self.assertTrue(emitted[key].exists())

    # --- California passthrough -------------------------------------------
    def test_schedule_ca_business_income_column_a_equals_native(self):
        scn = _scenario(businesses=_ONE)
        scn = dataclasses.replace(
            scn, ca540=CA540Return(),
            config=dataclasses.replace(
                scn.config, **{k: True for k in CA_SCOPE_OUT_FIELDS}))
        fed = self.orch.compute_federal(scn)
        ca = self.orch._compute_ca_results(scn, scn.ca540, fed)
        ca_pdfs = self.orch._emit_ca_pdfs_internal(scn, ca, self.tmp / "ca")
        field = _scalars(PdfSchCa.get_mapping(2025))[
            "sch_ca_line_part_i_b_3_col_a"]
        printed = int(_read_v(ca_pdfs["sch_ca"], field))
        self.assertEqual(printed, fed["sch_1_line_3_business_income"])
        self.assertEqual(printed, 75_000)


class SchCPrintedChainTests(unittest.TestCase):
    """printed-chain ruling (SE line 12 lineage), 2026-10-04: lines 28/29/31
    compute from the whole-dollar-rounded printed operands so the page foots."""

    def test_chain_foots_with_cent_valued_inputs(self):
        # Cents chain: 2239.61 - 16.15 = 2223.46 -> 2223 (old, did not foot:
        # printed 2,240 - 16 = 2,224). Printed chain: 2240 - 16 = 2224.
        biz = ScheduleCBusiness(
            description="Synthetic Consulting", gross_receipts=2239.61,
            other_expenses=16.15, other_expenses_description="Software")
        scn = _scenario()
        scn.schedule_c_businesses = [biz]
        line = form_sch_c.compute(scn, {})["sch_c_businesses"][0]
        self.assertEqual(line["sch_c_line_7_gross_income"], 2240)
        self.assertEqual(line["sch_c_line_28_total_expenses"], 16)
        self.assertEqual(line["sch_c_line_29_tentative_profit"], 2224)
        self.assertEqual(line["sch_c_line_31_net_profit"], 2224)
        self.assertEqual(
            line["sch_c_line_29_tentative_profit"],
            line["sch_c_line_7_gross_income"]
            - line["sch_c_line_28_total_expenses"])

    def test_line_28_sums_rounded_categories(self):
        # 10.40 + 10.40 + 10.40 = 31.20 -> old 31; printed 10+10+10 = 30.
        biz = ScheduleCBusiness(
            description="Synthetic Consulting", gross_receipts=1000.0,
            advertising=10.40, supplies=10.40, utilities=10.40)
        scn = _scenario()
        scn.schedule_c_businesses = [biz]
        line = form_sch_c.compute(scn, {})["sch_c_businesses"][0]
        self.assertEqual(line["sch_c_line_28_total_expenses"], 30)
        self.assertEqual(line["sch_c_line_31_net_profit"], 970)


if __name__ == "__main__":
    unittest.main()
