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
    Form1095A,
    Form1095AMonth,
    Form1099INT,
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
from tests.helpers import CA_SCOPE_OUT_FIELDS

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

    def test_ca_compute_only_year_note(self):
        """CA compute-only year (2022): Schedule X emits, but the complete
        amended 540 cannot — the manifest carries its OWN distinct CA note,
        separate from the federal one, and the 540 is absent."""
        self.assertIn(2022, years.CALIFORNIA_COMPUTE_ONLY_YEARS)
        self.assertIn(2022, years.FEDERAL_YEARS)  # federal side is full-emit
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


if __name__ == "__main__":
    unittest.main()
