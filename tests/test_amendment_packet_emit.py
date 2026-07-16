"""End-to-end amendment-packet emit tests (spec §3/§4/§6).

Drives ``ReturnOrchestrator.run_amendment_packet`` over synthetic original +
amended scenario twins, reopens the REAL filled PDFs, and reads distinctive
values back. Native throughout (no soffice): the amendment assembly is
arithmetic over two already-validated runs and the emit is a straight
PdfFiller fill against the committed 1040-X / Schedule X templates.

The ONE sanctioned recompute-as-filed spot is ``_write_federal_filed`` /
``_write_ca_filed`` below: the filed-values files are written FROM THE ORIGINAL
run's outputs, inside the test, because the test controls both sides of the
amendment. It is done nowhere else.
"""
import dataclasses
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import yaml
from pypdf import PdfReader

from tenforty import years
from tenforty.amendment import OutOfScopeAmendmentError
from tenforty.forms import f1040x as form_f1040x
from tenforty.forms import schedule_x as form_schedule_x
from tenforty.mappings.pdf_f1040x import PdfF1040X
from tenforty.mappings.pdf_schedule_x import PdfScheduleX
from tenforty.models import (
    AmendmentCase,
    CA540Return,
    FilingStatus,
    Form1095A,
    Form1095AMonth,
    Form1099INT,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import (
    _CA_COMPUTE_ONLY_NOTE,
    _FEDERAL_COMPUTE_ONLY_NOTE,
    ReturnOrchestrator,
)
from tenforty.params.federal import load as load_federal_params
from tests.fixtures.spine_battery import (
    build_canonical_wage_investment_rental,
    build_charitable_nonitemizer_2021,
)
from tests.helpers import (
    CA_SCOPE_OUT_FIELDS,
    needs_libreoffice,
    scope_out_attestation_defaults,
)

REPO_ROOT = Path(__file__).parent.parent
_REVISION = years.AMENDMENT_TEMPLATE_REVISIONS["f1040x"]


def _with_ca(scenario):
    """CA-resident twin of a battery scenario: flip every CA scope-out True and
    attach an empty CA540Return so the CA pipeline runs."""
    cfg = dataclasses.replace(
        scenario.config, **{k: True for k in CA_SCOPE_OUT_FIELDS})
    return dataclasses.replace(scenario, config=cfg, ca540=CA540Return())


def _bump_interest(scenario, amount):
    """Amended twin differing in ONE income component (taxable interest)."""
    return dataclasses.replace(
        scenario, form1099_int=[Form1099INT(payer="Synthetic Bank", interest=amount)])


def _wages_and_interest_only(scenario):
    """Strip the scenario to wages + interest so Sch B's ONLY trigger is the
    interest threshold (the canonical's $5k dividends would keep Sch B alive)."""
    return dataclasses.replace(
        scenario, form1099_div=[], form1099_b=[], rental_properties=[])


def _build_eic_eligible_qbi_scenario(k1_qbi_amount: float) -> Scenario:
    """Single filer, low enough wages to be EIC-eligible (out of native-spine
    scope -> routes to `_compute_1040_via_workbook`, the oracle path Bug #6
    fixes), plus an S-corp K-1 so Form 8995 yields a nonzero QBI deduction.

    Wages $8,000 + K-1 ordinary business income (== `k1_qbi_amount`) keeps
    the EIC cheap-ceiling-gate estimate under the 2025 single/0-dependent
    ceiling ($26,214) for both the $10,000 and $15,000 K-1 amounts this test
    uses, so both the "original" and "amended" twins stay oracle-routed.
    """
    defaults = scope_out_attestation_defaults()
    for name in (
        "acknowledges_qbi_below_threshold",
        "acknowledges_unlimited_at_risk",
        "basis_tracked_externally",
        "acknowledges_no_partnership_se_earnings",
        "acknowledges_no_section_1231_gain",
        "acknowledges_no_more_than_four_k1s",
        "acknowledges_no_k1_credits",
        "acknowledges_no_section_179",
        "acknowledges_no_estate_trust_k1",
    ):
        defaults[name] = True
    defaults["prior_year_itemized"] = False
    cfg = TaxReturnConfig(
        year=2025,
        filing_status=FilingStatus.SINGLE,
        birthdate="1980-01-01",
        state="TX",
        first_name="Bob", last_name="Example", ssn="000-00-0002",
        **defaults,
    )
    return Scenario(
        config=cfg,
        w2s=[W2(
            employer="Synthetic Employer", wages=8_000.0,
            federal_tax_withheld=500.0, ss_wages=8_000.0,
            ss_tax_withheld=496.0, medicare_wages=8_000.0,
            medicare_tax_withheld=116.0,
        )],
        schedule_k1s=[ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=k1_qbi_amount, qbi_amount=k1_qbi_amount,
        )],
    )


def _read_v(pdf_path, field_path):
    """Read one AcroForm field's /V, normalizing thousands-comma / dollar."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


class AmendmentPacketEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )

    def tearDown(self):
        self._tmp.cleanup()

    # --- filed-values files: the one sanctioned recompute-as-filed spot -----
    def _write_federal_filed(self, original_scenario, extra=None):
        """Write the federal Column-A file from the ORIGINAL run's outputs."""
        results = self.orch.compute_federal(original_scenario)
        data = {k: results[k] for k in form_f1040x.REQUIRED_FILED_KEYS}
        if extra:
            data.update(extra)
        path = self.tmp / "federal_filed.yaml"
        path.write_text(yaml.safe_dump(data))
        return path, results

    def _balance_withholding(self, scenario):
        """Rebuild the scenario's single W-2 so federal withholding EXACTLY
        covers the computed tax → the return has a zero refund/owed balance, so
        a null self-amendment's tail is exactly zero (line 16, amount-paid-with-
        original, is an unsourced v1 zero)."""
        tax = self.orch.compute_federal(scenario)["total_tax"]
        w2 = dataclasses.replace(
            scenario.w2s[0], federal_tax_withheld=float(tax))
        return dataclasses.replace(scenario, w2s=[w2])

    def _write_ca_filed(self, original_scenario, original_federal):
        """Write the CA Column-A file from the ORIGINAL CA run's net position."""
        ca = self.orch._compute_ca_results(
            original_scenario, original_scenario.ca540, original_federal)
        path = self.tmp / "ca_filed.yaml"
        path.write_text(yaml.safe_dump(
            {"f540_total_liability": ca["f540_total_liability"]}))
        return path, ca

    # ------------------------------------------------------------------ tests
    def test_happy_path_full_emit_year(self):
        """Full-emit year (2024) + CA side, amended by one income component.

        Asserts the changed federal forms AND ONLY those attach, both amendment
        forms + the complete amended 540 emit, the manifest lists each mailed
        file with a reason, and three distinctive 1040-X values + the Schedule X
        balance read back from the REAL PDFs."""
        original = _with_ca(build_canonical_wage_investment_rental(2024))
        amended = _bump_interest(original, 3_000.0)  # original interest 2_000

        filed_path, orig_fed = self._write_federal_filed(original)
        ca_filed_path, orig_ca = self._write_ca_filed(original, orig_fed)
        case = AmendmentCase(
            year=2024, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            ca_original_refund_received=max(0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0,
        )
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # (a) amendment forms + complete amended 540 present.
        for name in ("f1040x_2024.pdf", "f540_amended_2024.pdf",
                     "schedule_x_2024.pdf", "packet_manifest.txt"):
            self.assertTrue((out / name).exists(), f"missing {name}")

        # (b) changed federal forms attach; the UNCHANGED ones do NOT.
        self.assertTrue((out / "f1040sb_2024.pdf").exists())   # sch_b changed
        self.assertFalse((out / "f1040sd_2024.pdf").exists())  # sch_d unchanged
        self.assertFalse((out / "f1040se_2024.pdf").exists())  # sch_e unchanged
        self.assertFalse((out / "f1040s1_2024.pdf").exists())  # sch_1 unchanged

        # (c) manifest lists each mailed file, with a reason.
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertEqual(by_name["f1040x_2024.pdf"].reason, "amendment form")
        self.assertEqual(by_name["f1040sb_2024.pdf"].reason, "changed")
        self.assertEqual(
            by_name["f540_amended_2024.pdf"].reason, "complete amended return")
        self.assertEqual(by_name["schedule_x_2024.pdf"].reason, "amendment form")
        # No compute-only notes on a full-emit year.
        self.assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertNotIn(_CA_COMPUTE_ONLY_NOTE, manifest.caveats)
        # The standing spec §4 caveat is always present.
        self.assertTrue(any("preparer must confirm" in c for c in manifest.caveats))
        manifest_txt = (out / "packet_manifest.txt").read_text()
        self.assertIn("f1040sb_2024.pdf", manifest_txt)
        self.assertIn("f540_amended_2024.pdf", manifest_txt)

        # (d) read back REAL values: recompute the corrected picture the packet
        # used and compare the assembler's figures to what the PDFs carry.
        corrected_fed = self.orch.compute_federal(amended)
        expected_x = form_f1040x.assemble(
            {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS},
            corrected_fed, case)
        xmap = PdfF1040X.get_mapping(_REVISION)
        f1040x_pdf = out / "f1040x_2024.pdf"
        # Column-B AGI delta == the +$1,000 interest bump.
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line1_b"]))), 1_000)
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line1_b"]))),
            round(expected_x["f1040x_line1_b"]))
        # Line 22 (refund on this return) round-trips.
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line22"]))),
            round(expected_x["f1040x_line22"]))
        # Part II explanation passes through verbatim.
        self.assertEqual(
            _read_v(f1040x_pdf, xmap["f1040x_explanation"]),
            "Corrected taxable interest income.")

        # Schedule X balance line (L7 amount you owe) round-trips.
        corrected_ca = self.orch._compute_ca_results(
            amended, amended.ca540, corrected_fed)
        expected_sx = form_schedule_x.assemble_ca(
            {"f540_total_liability": orig_ca["f540_total_liability"]},
            corrected_ca, case)
        smap = PdfScheduleX.get_mapping(2024)
        self.assertEqual(
            int(float(_read_v(out / "schedule_x_2024.pdf", smap["schedule_x_line7"]))),
            round(expected_sx["schedule_x_line7"]))

    def test_happy_path_full_emit_ca_2021(self):
        """2021 full-emit CA side, amended by one income component (mirrors
        ``test_happy_path_full_emit_year`` for year 2021).

        2021 is now a full-emit CALIFORNIA_YEARS member (its f540/sch_ca/
        sch_d_540 emit packs landed), so the complete amended 540 REALLY emits
        — the CA compute-only note is ABSENT, not stubbed. Asserts the changed
        federal form AND ONLY it attaches, both amendment forms + the complete
        amended 540 emit, the manifest reasons, and the Schedule X balance
        reads back from the REAL PDF."""
        original = _with_ca(build_canonical_wage_investment_rental(2021))
        amended = _bump_interest(original, 3_000.0)  # original interest 2_000

        filed_path, orig_fed = self._write_federal_filed(original)
        ca_filed_path, orig_ca = self._write_ca_filed(original, orig_fed)
        case = AmendmentCase(
            year=2021, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            ca_original_refund_received=max(0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0,
        )
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # (a) amendment forms + complete amended 540 present.
        for name in ("f1040x_2021.pdf", "f540_amended_2021.pdf",
                     "schedule_x_2021.pdf", "packet_manifest.txt"):
            self.assertTrue((out / name).exists(), f"missing {name}")

        # (b) changed federal forms attach; the UNCHANGED ones do NOT.
        self.assertTrue((out / "f1040sb_2021.pdf").exists())   # sch_b changed
        self.assertFalse((out / "f1040sd_2021.pdf").exists())  # sch_d unchanged
        self.assertFalse((out / "f1040se_2021.pdf").exists())  # sch_e unchanged
        self.assertFalse((out / "f1040s1_2021.pdf").exists())  # sch_1 unchanged

        # (c) manifest lists each mailed file, with a reason.
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertEqual(by_name["f1040x_2021.pdf"].reason, "amendment form")
        self.assertEqual(by_name["f1040sb_2021.pdf"].reason, "changed")
        self.assertEqual(
            by_name["f540_amended_2021.pdf"].reason, "complete amended return")
        self.assertEqual(by_name["schedule_x_2021.pdf"].reason, "amendment form")
        # No compute-only notes: the CA attachment is really emitted, not
        # stubbed — the MISSING-attachment note is ABSENT.
        self.assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertNotIn(_CA_COMPUTE_ONLY_NOTE, manifest.caveats)
        # The standing spec §4 caveat is always present.
        self.assertTrue(any("preparer must confirm" in c for c in manifest.caveats))
        manifest_txt = (out / "packet_manifest.txt").read_text()
        self.assertIn("f1040sb_2021.pdf", manifest_txt)
        self.assertIn("f540_amended_2021.pdf", manifest_txt)

        # (d) read back a REAL value: the Schedule X balance line (L7 amount
        # you owe) round-trips against the assembler's figure.
        corrected_fed = self.orch.compute_federal(amended)
        corrected_ca = self.orch._compute_ca_results(
            amended, amended.ca540, corrected_fed)
        expected_sx = form_schedule_x.assemble_ca(
            {"f540_total_liability": orig_ca["f540_total_liability"]},
            corrected_ca, case)
        smap = PdfScheduleX.get_mapping(2021)
        self.assertEqual(
            int(float(_read_v(out / "schedule_x_2021.pdf", smap["schedule_x_line7"]))),
            round(expected_sx["schedule_x_line7"]))

    def test_happy_path_full_emit_ca_2022(self):
        """2022 full-emit CA side, amended by one income component (mirrors
        ``test_happy_path_full_emit_year`` for year 2022).

        2022 is now a full-emit CALIFORNIA_YEARS member (its f540/sch_ca/
        sch_d_540 emit packs landed), so the complete amended 540 REALLY emits
        — the CA compute-only note is ABSENT, not stubbed. Asserts the changed
        federal form AND ONLY it attaches, both amendment forms + the complete
        amended 540 emit, the manifest reasons, and the Schedule X balance
        reads back from the REAL PDF."""
        original = _with_ca(build_canonical_wage_investment_rental(2022))
        amended = _bump_interest(original, 3_000.0)  # original interest 2_000

        filed_path, orig_fed = self._write_federal_filed(original)
        ca_filed_path, orig_ca = self._write_ca_filed(original, orig_fed)
        case = AmendmentCase(
            year=2022, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            ca_original_refund_received=max(0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0,
        )
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # (a) amendment forms + complete amended 540 present.
        for name in ("f1040x_2022.pdf", "f540_amended_2022.pdf",
                     "schedule_x_2022.pdf", "packet_manifest.txt"):
            self.assertTrue((out / name).exists(), f"missing {name}")

        # (b) changed federal forms attach; the UNCHANGED ones do NOT.
        self.assertTrue((out / "f1040sb_2022.pdf").exists())   # sch_b changed
        self.assertFalse((out / "f1040sd_2022.pdf").exists())  # sch_d unchanged
        self.assertFalse((out / "f1040se_2022.pdf").exists())  # sch_e unchanged
        self.assertFalse((out / "f1040s1_2022.pdf").exists())  # sch_1 unchanged

        # (c) manifest lists each mailed file, with a reason.
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertEqual(by_name["f1040x_2022.pdf"].reason, "amendment form")
        self.assertEqual(by_name["f1040sb_2022.pdf"].reason, "changed")
        self.assertEqual(
            by_name["f540_amended_2022.pdf"].reason, "complete amended return")
        self.assertEqual(by_name["schedule_x_2022.pdf"].reason, "amendment form")
        # No compute-only notes: the CA attachment is really emitted, not
        # stubbed — the MISSING-attachment note is ABSENT.
        self.assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertNotIn(_CA_COMPUTE_ONLY_NOTE, manifest.caveats)
        # The standing spec §4 caveat is always present.
        self.assertTrue(any("preparer must confirm" in c for c in manifest.caveats))
        manifest_txt = (out / "packet_manifest.txt").read_text()
        self.assertIn("f1040sb_2022.pdf", manifest_txt)
        self.assertIn("f540_amended_2022.pdf", manifest_txt)

        # (d) read back a REAL value: the Schedule X balance line (L7 amount
        # you owe) round-trips against the assembler's figure.
        corrected_fed = self.orch.compute_federal(amended)
        corrected_ca = self.orch._compute_ca_results(
            amended, amended.ca540, corrected_fed)
        expected_sx = form_schedule_x.assemble_ca(
            {"f540_total_liability": orig_ca["f540_total_liability"]},
            corrected_ca, case)
        smap = PdfScheduleX.get_mapping(2022)
        self.assertEqual(
            int(float(_read_v(out / "schedule_x_2022.pdf", smap["schedule_x_line7"]))),
            round(expected_sx["schedule_x_line7"]))

    def test_null_self_amendment(self):
        """amended == original → only the amendment form (1040-X) mails, Column B
        is all zero, the changed-forms selection is empty, the refund/owed tail
        is zero, and the manifest SAYS the selection is empty.

        A form_1095a block (Sch 2 Part I excess-APTC repayment) rides on BOTH
        sides via its OWN filed key (f8962_repayment), not a guard key, and
        the null invariant — including the new L6/L8/L10/L11 sourcing — still
        holds when filed == corrected.
        """
        block = Form1095A(months=tuple(
            Form1095AMonth(premium=500.0, slcsp=500.0, aptc=400.0)
            for _ in range(12)))
        base = dataclasses.replace(
            build_canonical_wage_investment_rental(2024), form_1095a=block)
        # Balance federal withholding to total_tax + f8962_repayment (not just
        # total_tax) so the tail — which now nets Sch 2 Part I into L11 — is
        # exactly zero for this self-amendment.
        prelim = self.orch.compute_federal(base)
        self.assertGreater(prelim["f8962_repayment"], 0)  # actually exercises Sch 2
        target = prelim["total_tax"] + prelim["f8962_repayment"]
        w2 = dataclasses.replace(base.w2s[0], federal_tax_withheld=float(target))
        original = dataclasses.replace(base, w2s=[w2])
        amended = original  # exact self-amendment

        filed_path, orig_fed = self._write_federal_filed(original)
        # Overlay the modeled Sch 2 Part I component under its own key — not
        # folded into a guard key.
        data = yaml.safe_load(filed_path.read_text())
        data["f8962_repayment"] = orig_fed["f8962_repayment"]
        filed_path.write_text(yaml.safe_dump(data))

        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2024, explanation="No changes.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # Only the 1040-X + manifest mail; no attachments, no CA forms.
        self.assertEqual(
            sorted(p.name for p in out.iterdir()),
            ["f1040x_2024.pdf", "packet_manifest.txt"])
        # Empty selection: no "changed"/"new" mailed files.
        self.assertEqual(
            [mf for mf in manifest.mailed_files
             if mf.reason in ("changed", "new")], [])
        self.assertTrue(any(
            "selection is empty" in c for c in manifest.caveats))

        # Column B all zero; refund/owed tail zero.
        xmap = PdfF1040X.get_mapping(_REVISION)
        f1040x_pdf = out / "f1040x_2024.pdf"
        for line in ("f1040x_line1_b", "f1040x_line5_b", "f1040x_line11_b"):
            self.assertEqual(
                int(float(_read_v(f1040x_pdf, xmap[line]) or "0")), 0)
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line20"]) or "0")), 0)
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line22"]) or "0")), 0)

        # Lines 6/7/8/10 aren't PDF-mapped yet (out of this task's scope), so
        # verify their null-invariance directly on the assembled dict.
        expected_x = form_f1040x.assemble(data, orig_fed, case)
        for line in ("6", "7", "8", "10", "11"):
            self.assertEqual(
                expected_x[f"f1040x_line{line}_b"], 0,
                msg=f"line {line}_b should be 0 in the null self-amendment")

    def test_f8962_repayment_rides_own_key_e2e(self):
        """A filed-values file carrying f8962_repayment as ITS OWN key (not
        folded into other_taxes) assembles cleanly against a corrected
        scenario whose form_1095a block yields a DIFFERENT repayment: no
        OutOfScopeAmendmentError, f8962 is selected as a changed federal
        form, and A+B=C holds on the modeled Sch 2 lines (6/8/10/11)."""
        def _months(aptc):
            return tuple(
                Form1095AMonth(premium=500.0, slcsp=500.0, aptc=aptc)
                for _ in range(12))

        base = build_canonical_wage_investment_rental(2024)
        original = dataclasses.replace(
            base, form_1095a=Form1095A(months=_months(400.0)))
        amended = dataclasses.replace(
            base, form_1095a=Form1095A(months=_months(450.0)))

        orig_fed = self.orch.compute_federal(original)
        self.assertNotEqual(
            orig_fed["f8962_repayment"],
            self.orch.compute_federal(amended)["f8962_repayment"])

        filed_path, _ = self._write_federal_filed(original)
        data = yaml.safe_load(filed_path.read_text())
        data["f8962_repayment"] = orig_fed["f8962_repayment"]
        filed_path.write_text(yaml.safe_dump(data))

        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2024, explanation="Corrected Form 1095-A APTC.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = self.tmp / "packet"

        # No OutOfScopeAmendmentError: f8962_repayment rides its own key now,
        # not the other_taxes guard.
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # f8962 selected as a changed federal form (repayment differs).
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertIn("f8962_2024.pdf", by_name)
        self.assertEqual(by_name["f8962_2024.pdf"].reason, "changed")

        # A+B=C on the modeled Sch 2 lines.
        corrected_fed = self.orch.compute_federal(amended)
        expected_x = form_f1040x.assemble(data, corrected_fed, case)
        for line in ("6", "7", "8", "10", "11"):
            a = expected_x[f"f1040x_line{line}_a"]
            b = expected_x[f"f1040x_line{line}_b"]
            c = expected_x[f"f1040x_line{line}_c"]
            self.assertEqual(a + b, c, msg=f"line {line}: {a} + {b} != {c}")

        # Line 11 IS PDF-mapped; the fill round-trips the sourced total.
        xmap = PdfF1040X.get_mapping(_REVISION)
        f1040x_pdf = out / "f1040x_2024.pdf"
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line11_c"]))),
            round(expected_x["f1040x_line11_c"]))

    def test_ruling2_out_of_scope_guard_propagates(self):
        """A filed-values file carrying a nonzero out-of-scope guard key
        (schedule_1a_deduction) → the assembler's OutOfScopeAmendmentError
        propagates out of run_amendment_packet unswallowed.

        Migrated off estimated_payments: the federal spine now emits
        ``estimated_tax_payments`` (line 26), so 1040-X line 13 is SOURCED,
        not guarded — a nonzero estimated_payments no longer refuses. The
        propagation demo moved to schedule_1a_deduction (line 4b, Schedule
        1-A tips/overtime/car-loan-interest/seniors), which remains
        unmodeled and stays in ``_OUT_OF_SCOPE_FILED_KEYS``.
        """
        original = build_canonical_wage_investment_rental(2024)
        amended = _bump_interest(original, 3_000.0)
        filed_path, _ = self._write_federal_filed(
            original, extra={"schedule_1a_deduction": 500.0})
        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2024, explanation="x",
            original_refund_received=0.0, original_refund_applied=0.0)
        with self.assertRaises(OutOfScopeAmendmentError):
            self.orch.run_amendment_packet(
                original, amended, case, filed_path, ca_filed_path,
                self.tmp / "packet")

    def test_dropped_form_appears_in_manifest_and_not_attached(self):
        """The corrected run drops a form the original carried (Sch B, when the
        amended return removes the interest that put it over threshold) →
        that form is in the manifest's dropped class and is NOT attached."""
        original = _wages_and_interest_only(
            build_canonical_wage_investment_rental(2024))  # interest 2_000 only
        amended = _bump_interest(original, 0.0)  # no interest → Sch B drops

        filed_path, _ = self._write_federal_filed(original)
        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2024, explanation="Removed erroneous interest.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        self.assertIn("sch_b", manifest.dropped)
        self.assertFalse((out / "f1040sb_2024.pdf").exists())
        manifest_txt = (out / "packet_manifest.txt").read_text()
        self.assertIn("sch_b: no longer applies", manifest_txt)

    def test_federal_2021_is_now_full_emit_no_compute_only_note(self):
        """2021 is a REAL full-emit federal year now: its individual-form emit
        packs exist (federal-2021-emit Tasks 2-3), so a real 2021 amendment
        selects and EMITS its changed federal attachments — no synthetic
        manifest patch. The federal compute-only NOTE, which fires only in the
        ``else`` of ``year in years.FEDERAL_YEARS``, is therefore ABSENT.

        Mirrors ``test_happy_path_full_emit_year`` (2024) for a federal-only
        2021 case: the changed federal form attaches, an UNCHANGED form does
        NOT, the note is absent at the same manifest level Task 1 pinned
        (``assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)``) — now
        backed by a real full-emit run — and a distinctive 1040-X value reads
        back from the REAL PDF.
        """
        # Precondition: 2021 really is a full-emit federal year (Task 1 move).
        self.assertIn(2021, years.FEDERAL_YEARS)

        original = build_canonical_wage_investment_rental(2021)  # federal-only
        amended = _bump_interest(original, 3_000.0)  # original interest 2_000

        filed_path, orig_fed = self._write_federal_filed(original)
        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2021, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = self.tmp / "packet"
        manifest = self.orch.run_amendment_packet(
            original, amended, case, filed_path, ca_filed_path, out)

        # (a) amendment form + manifest present.
        for name in ("f1040x_2021.pdf", "packet_manifest.txt"):
            self.assertTrue((out / name).exists(), f"missing {name}")

        # (b) the changed federal form EMITS; UNCHANGED ones do NOT.
        self.assertTrue((out / "f1040sb_2021.pdf").exists())   # sch_b changed
        self.assertFalse((out / "f1040sd_2021.pdf").exists())  # sch_d unchanged
        self.assertFalse((out / "f1040se_2021.pdf").exists())  # sch_e unchanged

        # (c) manifest lists each mailed file with a reason.
        by_name = {mf.filename: mf for mf in manifest.mailed_files}
        self.assertEqual(by_name["f1040x_2021.pdf"].reason, "amendment form")
        self.assertEqual(by_name["f1040sb_2021.pdf"].reason, "changed")
        manifest_txt = (out / "packet_manifest.txt").read_text()
        self.assertIn("f1040sb_2021.pdf", manifest_txt)

        # (d) BOTH directions: the changed attachment emitted (above) AND the
        # federal compute-only note is ABSENT — at the manifest level Task 1
        # pinned, now backed by a real full-emit run. (No CA side either.)
        self.assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertNotIn(_CA_COMPUTE_ONLY_NOTE, manifest.caveats)
        # The standing spec §4 caveat is always present.
        self.assertTrue(any("preparer must confirm" in c for c in manifest.caveats))

        # (e) read back a REAL 1040-X value: Column-B AGI delta == the +$1,000
        # interest bump.
        corrected_fed = self.orch.compute_federal(amended)
        expected_x = form_f1040x.assemble(
            {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS},
            corrected_fed, case)
        xmap = PdfF1040X.get_mapping(_REVISION)
        f1040x_pdf = out / "f1040x_2021.pdf"
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line1_b"]))), 1_000)
        self.assertEqual(
            int(float(_read_v(f1040x_pdf, xmap["f1040x_line1_b"]))),
            round(expected_x["f1040x_line1_b"]))

    def test_federal_compute_only_note_machinery_via_synthetic_manifest(self):
        """The federal compute-only-note MACHINERY stays tested even though no
        real federal compute-only year remains — a future backfill can re-enter
        the tier, and its note must still emit. A SYNTHETIC manifest fixture
        reconstructs the pre-move state for 2021: removed from FEDERAL_YEARS
        (so the orchestrator takes the compute-only ``else`` branch) AND added
        to FEDERAL_COMPUTE_ONLY_YEARS (so the params loader — which gates on
        FEDERAL_YEARS + FEDERAL_COMPUTE_ONLY_YEARS — still resolves 2021's real
        params, tax table, and 1040-X mapping). Both the orchestrator and the
        params loader read these as live attributes of the ``years`` module, so
        patching the module attributes reaches every consumer.

        Precondition: the tier really is empty (else this fixture would be
        masking a still-populated tier rather than synthesizing one)."""
        self.assertEqual(years.FEDERAL_COMPUTE_ONLY_YEARS, ())

        original = build_canonical_wage_investment_rental(2021)  # federal-only
        amended = _bump_interest(original, 3_000.0)
        # Build the filed-values file under the REAL manifest (2021 computes).
        filed_path, _ = self._write_federal_filed(original)
        ca_filed_path = self.tmp / "unused_ca.yaml"
        ca_filed_path.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=2021, explanation="x",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = self.tmp / "packet"

        synthetic_federal = tuple(
            y for y in years.FEDERAL_YEARS if y != 2021)
        synthetic_compute_only = tuple(sorted(
            set(years.FEDERAL_COMPUTE_ONLY_YEARS) | {2021}))
        with unittest.mock.patch.object(
                years, "FEDERAL_YEARS", synthetic_federal), \
             unittest.mock.patch.object(
                years, "FEDERAL_COMPUTE_ONLY_YEARS", synthetic_compute_only):
            manifest = self.orch.run_amendment_packet(
                original, amended, case, filed_path, ca_filed_path, out)

        self.assertIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertTrue((out / "f1040x_2021.pdf").exists())
        # No year-keyed individual-form attachments for a compute-only year.
        self.assertFalse((out / "f1040_2021.pdf").exists())
        self.assertFalse((out / "f1040sb_2021.pdf").exists())

    def test_ca_2021_2022_now_full_emit_ca_no_compute_only_note(self):
        """2021 and 2022 are now full-emit CALIFORNIA_YEARS members
        (ca-2021-2022-emit Task 1 manifest move), so the orchestrator's CA
        branch gate — ``if year in years.CALIFORNIA_YEARS`` — takes the
        full-emit path and the ``else`` that appends ``_CA_COMPUTE_ONLY_NOTE``
        is unreachable for them. This is asserted at the MANIFEST level, not by
        driving a real full-emit CA amendment: the 2021/2022 CA emit packs
        (probe-certified f540/sch_ca/sch_d_540 mappings) are owed by later
        tasks (Tasks 2-3), so a real full-emit CA run would raise until they
        land — exactly the situation the federal side was in when its Task 1
        pinned the analogous federal note-absence at the manifest level (see
        ``test_federal_2021_is_now_full_emit_no_compute_only_note``, which only
        flipped to a real run once the federal packs existed). The predicate
        below is the exact one the orchestrator branches on, so it is a live
        check, not a tautology."""
        for year in (2021, 2022):
            with self.subTest(year=year):
                self.assertIn(year, years.CALIFORNIA_YEARS)
                self.assertNotIn(year, years.CALIFORNIA_COMPUTE_ONLY_YEARS)

    def test_ca_compute_only_note_machinery_via_synthetic_manifest(self):
        """The CA compute-only-note MACHINERY stays tested even though no real
        CA compute-only year remains after the Task 1 move — a future backfill
        can re-enter the tier, and its note must still emit. A SYNTHETIC
        manifest fixture reconstructs the pre-move state for 2022: removed from
        CALIFORNIA_YEARS (so the orchestrator takes the compute-only ``else``
        branch that appends ``_CA_COMPUTE_ONLY_NOTE``) AND added to
        CALIFORNIA_COMPUTE_ONLY_YEARS (so the CA params loader — which gates on
        CALIFORNIA_YEARS + CALIFORNIA_COMPUTE_ONLY_YEARS — still resolves 2022's
        real params). Both the orchestrator and the params loader read these as
        live attributes of the ``years`` module, so patching the module
        attributes reaches every consumer. Schedule X still emits (its per-year
        pack exists for every amendable CA year); the complete amended 540 does
        NOT (the compute-only branch never calls ``_emit_ca_pdfs_internal``).

        Precondition: the tier really is empty (else this fixture would be
        masking a still-populated tier rather than synthesizing one)."""
        self.assertEqual(years.CALIFORNIA_COMPUTE_ONLY_YEARS, ())

        original = _with_ca(build_canonical_wage_investment_rental(2022))
        amended = _bump_interest(original, 3_000.0)

        filed_path, orig_fed = self._write_federal_filed(original)
        ca_filed_path, orig_ca = self._write_ca_filed(original, orig_fed)
        case = AmendmentCase(
            year=2022, explanation="x",
            original_refund_received=0.0, original_refund_applied=0.0,
            ca_original_refund_received=max(0.0, -orig_ca["f540_total_liability"]),
            ca_original_refund_applied=0.0)
        out = self.tmp / "packet"

        synthetic_california = tuple(
            y for y in years.CALIFORNIA_YEARS if y != 2022)
        synthetic_compute_only = tuple(sorted(
            set(years.CALIFORNIA_COMPUTE_ONLY_YEARS) | {2022}))
        with unittest.mock.patch.object(
                years, "CALIFORNIA_YEARS", synthetic_california), \
             unittest.mock.patch.object(
                years, "CALIFORNIA_COMPUTE_ONLY_YEARS", synthetic_compute_only):
            manifest = self.orch.run_amendment_packet(
                original, amended, case, filed_path, ca_filed_path, out)

        self.assertIn(_CA_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertNotIn(_FEDERAL_COMPUTE_ONLY_NOTE, manifest.caveats)
        self.assertTrue((out / "schedule_x_2022.pdf").exists())
        self.assertFalse((out / "f540_amended_2022.pdf").exists())

    def test_2021_filed_12b_reproduced_in_column_c(self):
        """2021 line-12b non-itemizer charitable ($250) survives amendment:
        a null self-amendment of ``build_charitable_nonitemizer_2021(2021)``
        carries the 12b through BOTH Column A (as filed) and Column C
        (corrected) via the EXISTING grid — NO 1040-X line change is needed.
        The spine folds ``charitable_nonitemizer`` into ``total_deductions``
        (1040-X line 2), which reduces ``taxable_income`` (1040-X line 5).

        2021 is FEDERAL_COMPUTE_ONLY (no PDF attachments render), so this
        test drives ``form_f1040x.assemble`` directly rather than the full
        ``run_amendment_packet`` — the assembler-level assertion is exactly
        what "Column C reproduces the filed 12b" requires; the surrounding
        compute-only packet plumbing is already covered by
        ``test_federal_compute_only_year_note`` above.

        Why this scenario SURVIVES the load guards (tenforty/scenario.py):
        it is SINGLE filing status + STANDARD deduction (no itemized_
        deductions block) + $250 <= the 2021 single-filer $300 cap — the
        ONLY combination that passes all three 12b guards: the non-single
        scope-out (`filing_status is not FilingStatus.SINGLE` -> refuse),
        the over-cap guard (`charitable_cash_nonitemizer > cap` -> refuse),
        and the conservative itemizer guard in `_validate_charitable_itemizer`
        (nonzero 12b + a supplied `itemized_deductions` block -> refuse). Any
        other combination (married, itemized, or > $300) is refused at LOAD,
        before an amendment could even be attempted.

        Hand-derived expected values (team-lead pin — NOT read back from the
        assembler's own output):
          Scenario: single filer, one W-2, wages = $60,000, no other income
          or adjustments -> AGI = $60,000 (wages is the only total-income
          component and there are no above-the-line adjustments in this
          scenario, so AGI = total_income = wages verbatim).
          standard deduction 2021 single = load_federal_params(2021)
              .standard_deduction["single"] = $12,550.
          12b (charitable_nonitemizer) = $250 (under the $300 single cap).
          => line-2 total_deductions (Column C) = 12,550 + 250 = $12,800.
          => line-5 taxable income (Column C) = 60,000 - 12,800 = $47,200
             (no QBI deduction: the scenario carries no business income, so
             the Form 8995 component of the taxable-income line is 0).
        Because this is a null self-amendment (corrected == filed), the SAME
        hand-derived figures also reproduce on Column A (line2_a/line5_a) and
        Column B nets to zero — asserted below as well.
        """
        original = build_charitable_nonitemizer_2021(2021)
        amended = original  # null self-amendment: 12b rides through unchanged

        filed_path, orig_fed = self._write_federal_filed(original)
        filed = yaml.safe_load(filed_path.read_text())
        corrected_fed = self.orch.compute_federal(amended)

        case = AmendmentCase(
            year=2021,
            explanation="No changes; confirms 2021 line-12b non-itemizer "
                        "charitable deduction carries through the amendment.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = form_f1040x.assemble(filed, corrected_fed, case)

        agi = 60_000.0
        standard_deduction_2021_single = float(
            load_federal_params(2021).standard_deduction["single"])
        self.assertEqual(standard_deduction_2021_single, 12_550.0)
        charitable_12b = 250.0
        expected_total_deductions = standard_deduction_2021_single + charitable_12b
        expected_taxable_income = agi - expected_total_deductions

        # Column C (corrected) reproduces the hand-derived figures.
        self.assertEqual(out["f1040x_line2_c"], expected_total_deductions)
        self.assertEqual(out["f1040x_line5_c"], expected_taxable_income)

        # Column A (as filed) carries the SAME 12b-inclusive figures — the
        # filed return already claimed 12b, so Column A must show it too.
        self.assertEqual(out["f1040x_line2_a"], expected_total_deductions)
        self.assertEqual(out["f1040x_line5_a"], expected_taxable_income)

        # Column B (net change) is zero — a null self-amendment changes
        # nothing, including the 12b figure.
        self.assertEqual(out["f1040x_line2_b"], 0)
        self.assertEqual(out["f1040x_line5_b"], 0)

    # Oracle-routed (out-of-spine) amendment → workbook path → requires LibreOffice; oracle-tier.
    @needs_libreoffice
    def test_oracle_routed_qbi_amendment_line2_is_12c_exclusive(self):
        """Bug #6 regression: an oracle-routed amendment with QBI > 0 must
        show 1040-X line 2 (total_deductions) as the 12c-EXCLUSIVE figure on
        BOTH Column A (as filed) and Column C (corrected) — not the
        14-inclusive (12c + QBI) figure the oracle path emitted pre-fix
        (which would have double-counted QBI once line 4a/13 was added back
        on top, per the assembler's L3 = L1 - L2 and L5 = AGI - L2 - QBI-
        adjacent arithmetic driven off `total_deductions`).

        Scenario (`_build_eic_eligible_qbi_scenario`): single filer, wages
        $8,000 (well under the 2025 EIC-ceiling gate's threshold even after
        adding K-1 income), so `_scenario_in_spine_scope` is False and
        `_compute_1040_pipeline` routes to `_compute_1040_via_workbook` — the
        oracle path this bug fixes. Verified directly below, not assumed.
        Original K-1: ordinary_business_income = qbi_amount = $10,000 -> AGI
        $18,000, QBI deduction $450 (binding limit: 20% of the $2,250
        taxable-income-before-QBI, not 20% of the $10,000 QBI itself).
        Amended K-1: bumped to $15,000 -> AGI $23,000, QBI deduction $1,450.
        The standard deduction ($15,750, single) is unchanged by the K-1
        bump, so 12c-exclusive total_deductions is $15,750 on BOTH sides;
        pre-fix, the oracle path's (buggy, 14-inclusive) total_deductions
        would have been $16,200 (original) / $17,200 (amended) instead —
        wrong on line 2, and wrong differently on each side.

        NOTE — two separate, pre-existing gaps surfaced while building this
        test have since been FIXED IN PRODUCTION, so this test now consumes
        the real oracle-routed result directly (no in-test workarounds):
        (#7) `tenforty/forms/f1040.py::compute` used to pop
        `_qbi_deduction_1040` into a local var and never re-emit the key
        under its original name, so `compute_federal()` results for ANY
        oracle-routed scenario were missing `_qbi_deduction_1040` —
        one of `form_f1040x.REQUIRED_FILED_KEYS` (feeds 1040-X line 4a).
        `f1040.compute` now re-emits it, normalized, alongside `qbi_deduction`.
        (#8) The oracle path used to leave `f8959_tax_total` (Additional
        Medicare Tax, Sch 2 Part II) as `None` rather than 0 when it doesn't
        apply, present-as-None rather than absent, which defeats
        `assemble()`'s `.get(key, 0.0)` default and TypeErrors on
        `None - 0.0`. `f1040.compute` now normalizes `f8959_tax_total`
        None -> 0.
        """
        original = _build_eic_eligible_qbi_scenario(10_000.0)
        amended = _build_eic_eligible_qbi_scenario(15_000.0)

        eff_original, _ = self.orch._build_effective_scenario(original)
        eff_amended, _ = self.orch._build_effective_scenario(amended)
        self.assertFalse(
            self.orch._scenario_in_spine_scope(eff_original),
            "original scenario unexpectedly routed to the native spine, not "
            "the oracle/workbook path this test targets")
        self.assertFalse(
            self.orch._scenario_in_spine_scope(eff_amended),
            "amended scenario unexpectedly routed to the native spine, not "
            "the oracle/workbook path this test targets")

        orig_fed = self.orch.compute_federal(original)
        corrected_fed = self.orch.compute_federal(amended)
        self.assertGreater(orig_fed["qbi_deduction"], 0)
        self.assertGreater(corrected_fed["qbi_deduction"], 0)
        self.assertNotEqual(orig_fed["qbi_deduction"], corrected_fed["qbi_deduction"])

        filed = {k: orig_fed[k] for k in form_f1040x.REQUIRED_FILED_KEYS}
        corrected = dict(corrected_fed)

        case = AmendmentCase(
            year=2025, explanation="Corrected K-1 qualified business income.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out = form_f1040x.assemble(filed, corrected, case)

        applied_deduction = 15_750.0  # 2025 single standard deduction
        self.assertEqual(orig_fed["applied_deduction"], applied_deduction)
        self.assertEqual(corrected_fed["applied_deduction"], applied_deduction)

        # Line 2, Column A and C: 12c-exclusive, identical on both sides (the
        # standard deduction doesn't move when only the K-1 QBI changes).
        self.assertEqual(out["f1040x_line2_a"], applied_deduction)
        self.assertEqual(out["f1040x_line2_c"], applied_deduction)
        self.assertEqual(out["f1040x_line2_b"], 0)


if __name__ == "__main__":
    unittest.main()
