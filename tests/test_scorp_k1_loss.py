"""S corporation K-1 box 1 LOSS on Schedule E Part II.

Three things a loss row needs on the filed page:

  * lines 30 and 31 -- the printed addends of line 32 ("Combine lines 30 and
    31") -- carry the income and loss totals, on every K-1 return;
  * line 28 column (e) "Check if basis computation is required" is checked
    for an S corporation row reporting a loss;
  * the basis computation (Form 7203) is attached. tenforty does not produce
    it, so the loss computes only under
    `acknowledges_form_7203_attached_separately`, and the amendment manifest
    names the hand attachment.

Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty.forms import f1040x as form_f1040x
from tenforty.forms import sch_e_part_ii
from tenforty.mappings.pdf_sch_e import PdfSchE
from tenforty.models import AmendmentCase, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year
from tests.helpers import REPO_ROOT, make_k1_scenario

ATTESTATION = "acknowledges_form_7203_attached_separately"
BASIS_KEY = "sch_e_part_ii_row_a_basis_computation_required"

_P2 = "topmostSubform[0].Page2[0]"
# Literal paths, the same in every year 2022-2025.
_COL_E_ROW_A = f"{_P2}.Table_Line28a-f[0].RowA[0].c2_3[0]"
_COL_E_ROW_B = f"{_P2}.Table_Line28a-f[0].RowB[0].c2_6[0]"
_LINE_30 = f"{_P2}.f2_45[0]"
_LINE_31 = f"{_P2}.f2_46[0]"
_LINE_32 = f"{_P2}.f2_47[0]"
_YEARS = (2022, 2023, 2024, 2025)


def _k1(amount, entity_type="s_corp", name="Synthetic S Corp"):
    return ScheduleK1(
        entity_name=name, entity_ein="00-0000000", entity_type=entity_type,
        material_participation=True, ordinary_business_income=amount,
        qbi_amount=amount)


def _scenario(*k1s, attached=True, year=2025):
    base = make_k1_scenario()
    config = dataclasses.replace(
        base.config, year=year, acknowledges_no_source_documents=True,
        first_name="Example", last_name="Filer", ssn="000-00-0000",
        **{ATTESTATION: attached})
    return dataclasses.replace(base, config=config, schedule_k1s=list(k1s))


def _field(pdf_path, field_path):
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    return str(fields[field_path].get("/V") or "")


class PartIITotalsTests(unittest.TestCase):
    def test_lines_30_and_31_are_the_addends_of_line_32(self):
        out, _ = sch_e_part_ii.compute(
            _scenario(_k1(500.0, name="Synthetic Profit Corp"), _k1(-70.0)),
            upstream={})
        self.assertEqual(out["sch_e_line_30_total_income"], 500)
        self.assertEqual(out["sch_e_line_31_total_loss"], 70)
        self.assertEqual(out["sch_e_line_32_total_partnership_scorp"], 430)
        self.assertEqual(
            out["sch_e_line_30_total_income"] - out["sch_e_line_31_total_loss"],
            out["sch_e_line_32_total_partnership_scorp"])

    def test_passive_and_nonpassive_columns_both_reach_the_totals(self):
        passive_loss = dataclasses.replace(
            _k1(-40.0, entity_type="partnership", name="Synthetic LP"),
            material_participation=False)
        passive_income = dataclasses.replace(
            _k1(300.0, entity_type="partnership", name="Synthetic LP Two"),
            material_participation=False)
        out, _ = sch_e_part_ii.compute(
            _scenario(_k1(500.0, name="Synthetic Profit Corp"), _k1(-70.0),
                      passive_loss, passive_income),
            upstream={})
        self.assertEqual(out["sch_e_line_30_total_income"], 800)
        self.assertEqual(out["sch_e_line_31_total_loss"], 110)


class BasisComputationBoxTests(unittest.TestCase):
    def test_scorp_loss_row_requires_the_basis_computation(self):
        out, _ = sch_e_part_ii.compute(_scenario(_k1(-70.0)), upstream={})
        self.assertIs(out[BASIS_KEY], True)
        self.assertEqual(out["sch_e_part_ii_row_a_nonpassive_loss"], 70)

    def test_scorp_profit_row_does_not(self):
        out, _ = sch_e_part_ii.compute(_scenario(_k1(500.0)), upstream={})
        self.assertNotIn(BASIS_KEY, out)

    def test_partnership_loss_row_does_not(self):
        out, _ = sch_e_part_ii.compute(
            _scenario(_k1(-70.0, entity_type="partnership")), upstream={})
        self.assertNotIn(BASIS_KEY, out)


class Form7203AttestationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")

    def test_scorp_loss_refuses_without_the_attestation_and_names_it(self):
        scn = _scenario(_k1(-70.0), attached=False)
        self.assertIs(getattr(scn.config, ATTESTATION), False)
        with self.assertRaises(NotImplementedError) as ctx:
            sch_e_part_ii.compute(scn, upstream={})
        self.assertIn(ATTESTATION, str(ctx.exception))
        self.assertIn("Form 7203", str(ctx.exception))

    def test_refusal_fires_through_the_real_entry_point(self):
        scn = _scenario(_k1(-70.0), attached=False)
        self.assertIs(getattr(scn.config, ATTESTATION), False)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scn)
        self.assertIn(ATTESTATION, str(ctx.exception))

    def test_scorp_profit_and_partnership_loss_do_not_trigger_it(self):
        for label, k1 in (("scorp profit", _k1(500.0)),
                          ("partnership loss",
                           _k1(-70.0, entity_type="partnership"))):
            with self.subTest(case=label):
                scn = _scenario(k1, attached=False)
                self.assertIs(getattr(scn.config, ATTESTATION), False)
                out, _ = sch_e_part_ii.compute(scn, upstream={})
                self.assertIn("sch_e_line_32_total_partnership_scorp", out)

    def test_entity_computed_k1_loss_hits_the_same_gate(self):
        # 1120-S with deductions above receipts -> synthesized K-1 box 1 loss.
        scn = set_tax_year(_make_v1_scenario(
            gross_receipts=400.0, compensation_of_officers=470.0), 2025)
        self.assertIs(getattr(scn.config, ATTESTATION), False)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.compute_federal(scn)
        self.assertIn(ATTESTATION, str(ctx.exception))


class ScorpLossEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def test_loss_row_prints_the_box_and_the_footing_lines(self):
        for year in _YEARS:
            with self.subTest(year=year):
                scn = _scenario(
                    _k1(-70.0), _k1(500.0, name="Synthetic Profit Corp"),
                    year=year)
                emitted = self.orch.emit_pdfs(
                    scn, self.orch.compute_federal(scn),
                    self.tmp / f"out_{year}")
                sch_e = emitted["sch_e"]
                self.assertEqual(_field(sch_e, _COL_E_ROW_A), "/1")
                self.assertIn(_field(sch_e, _COL_E_ROW_B), ("", "/Off"))
                self.assertEqual(_field(sch_e, _LINE_30), "500")
                self.assertEqual(_field(sch_e, _LINE_31), "70")
                self.assertEqual(_field(sch_e, _LINE_32), "430")
                scalars = PdfSchE.get_mapping(year)["scalars"]
                self.assertEqual(
                    scalars["sch_e_line_30_total_income"], _LINE_30)
                self.assertEqual(scalars["sch_e_line_31_total_loss"], _LINE_31)
                self.assertEqual(
                    PdfSchE.get_basis_computation_cells(year)["a"],
                    (_COL_E_ROW_A, "/1"))

    def test_entity_loss_reaches_the_shareholders_schedule_e_and_8995(self):
        scn = set_tax_year(_make_v1_scenario(
            gross_receipts=400.0, compensation_of_officers=470.0), 2025)
        scn = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, acknowledges_no_source_documents=True,
            first_name="Example", last_name="Filer", ssn="000-00-0000",
            **{ATTESTATION: True}))
        results, emitted = self.orch.run_full_return(scn, self.tmp / "out")
        self.assertEqual(results["f1120s_ordinary_business_income"], -70)
        self.assertEqual(results["sch_1_line_5_rental_re_royalty"], -70)
        self.assertEqual(_field(emitted["sch_e"], _COL_E_ROW_A), "/1")
        self.assertEqual(_field(emitted["sch_e"], _LINE_31), "70")
        self.assertEqual(_field(emitted["sch_e"], _LINE_32), "-70")
        self.assertEqual(
            _field(emitted["f8995"], "topmostSubform[0].Page1[0].f1_32[0]"),
            "-70")

    def test_a_year_without_the_box_mapping_refuses_at_emit(self):
        scn = _scenario(_k1(-70.0), year=2021)
        results = self.orch.compute_federal(scn)
        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.emit_pdfs(scn, results, self.tmp / "out_2021")
        self.assertIn("column (e)", str(ctx.exception))


class HandAttachmentNoteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def test_note_names_form_7203_and_the_entity_only_on_a_scorp_loss(self):
        notes = sch_e_part_ii.hand_attachment_notes(_scenario(_k1(-70.0)))
        self.assertEqual(len(notes), 1)
        self.assertIn("Form 7203", notes[0])
        self.assertIn("Synthetic S Corp", notes[0])
        self.assertEqual(
            sch_e_part_ii.hand_attachment_notes(_scenario(_k1(500.0))), ())

    def test_amendment_manifest_carries_the_note(self):
        original = _scenario(_k1(500.0), year=2024)
        amended = _scenario(_k1(-70.0), year=2024)
        filed = self.orch.compute_federal(original)
        filed_path = self.tmp / "federal_filed.yaml"
        filed_path.write_text(yaml.safe_dump(
            {k: filed[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2024, explanation="Corrected the K-1 to a loss.",
            original_refund_received=0.0, original_refund_applied=0.0,
            original_tax_paid=0.0)
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path,
            self.tmp / "packet")
        matching = [c for c in manifest.caveats if "Form 7203" in c]
        self.assertEqual(len(matching), 1)
        self.assertIn(
            "Form 7203",
            (self.tmp / "packet" / "packet_manifest.txt").read_text())


if __name__ == "__main__":
    unittest.main()
