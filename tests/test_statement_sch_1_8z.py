"""The Schedule 1 line 8z statement (sch_1-8z-9-mapping-gap lane, phase P3;
Juno's 8z ruling, team-lead R6/R7).

Two or more nonzero Form 1099-G types: the 8z write-in reads "See statement"
and the return attaches a statement listing each type and amount, footing to
line 8z. One type: its caption in the write-in, no statement. None: no 8z at
all. The emitter renders the statement from the SAME values the Schedule 1
fill used (one producer). Native throughout; all identities synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

import pypdf
import yaml

from tenforty import pdf_packet
from tenforty.declarations import registry
from tenforty.forms import f1040x as form_f1040x
from tenforty.filing.statement_sch_1_8z import render_sch_1_8z_statement
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.models import AmendmentCase, FilingStatus, Form1099G
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_wages_only
from tests.helpers import REPO_ROOT

YEAR = 2024
KEY = "sch_1_8z_stmt"
ROWS = (("RTAA payments", 500), ("Taxable grants", 1_000))


def _scenario(*forms):
    base = build_wages_only(YEAR, FilingStatus.SINGLE)
    return dataclasses.replace(base, form1099_g=list(forms))


class Sch1Line8zStatementRendererTests(unittest.TestCase):

    def _render(self, d, name="s.pdf"):
        return render_sch_1_8z_statement(
            name="Example Filer", ssn="000-00-0001", year=YEAR, rows=ROWS,
            output_path=Path(d) / name)

    def test_one_page_listing_each_type_and_the_8z_total(self):
        with tempfile.TemporaryDirectory() as d:
            reader = pypdf.PdfReader(str(self._render(d)))
            self.assertEqual(len(reader.pages), 1)
            text = reader.pages[0].extract_text()
            for needle in ("Schedule 1 (Form 1040), Line 8z",
                           "Name(s) shown on return", "Example Filer",
                           "Your social security number", "000-00-0001",
                           "RTAA payments", "500", "Taxable grants", "1,000",
                           "Other income total (Schedule 1, line 8z)",
                           "1,500"):
                self.assertIn(needle, text)
            self.assertNotIn("Corporation", text)

    def test_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(self._render(d, "a.pdf").read_bytes(),
                             self._render(d, "b.pdf").read_bytes())


class Sch1Line8zStatementEmitTests(unittest.TestCase):

    def _emit(self, scenario):
        tmp = Path(tempfile.mkdtemp())
        orch = ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                                  work_dir=tmp / "work")
        results = orch.compute_federal(scenario)
        return orch.emit_pdfs(scenario, results, tmp / "out")

    def _write_in(self, emitted):
        path = PdfSch1.get_mapping(YEAR)["scalars"]["sch_1_line_8z_description"]
        fields = pypdf.PdfReader(str(emitted["sch_1"])).get_fields()
        return str(fields[path].get("/V") or "")

    def test_two_types_attach_the_statement_and_say_see_statement(self):
        emitted = self._emit(_scenario(Form1099G(
            payer="Example State", rtaa_payments=500.0,
            taxable_grants=1_000.0)))
        self.assertIn(KEY, emitted)
        self.assertEqual(self._write_in(emitted), "See statement")
        text = pypdf.PdfReader(str(emitted[KEY])).pages[0].extract_text()
        for needle in ("RTAA payments", "Taxable grants", "1,500"):
            self.assertIn(needle, text)

    def test_one_type_writes_its_caption_and_attaches_nothing(self):
        emitted = self._emit(_scenario(Form1099G(
            payer="Example State", taxable_grants=1_000.0)))
        self.assertNotIn(KEY, emitted)
        self.assertEqual(self._write_in(emitted), "Taxable grants")

    def test_no_8z_income_attaches_nothing(self):
        emitted = self._emit(_scenario())
        self.assertNotIn(KEY, emitted)


class Sch1Line8zStatementPacketTests(unittest.TestCase):

    def test_claimed_by_the_federal_individual_packet(self):
        self.assertEqual(pdf_packet.classify_key(KEY), "federal_individual")

    def test_placed_right_after_schedule_1(self):
        keys = [m.key for m in pdf_packet.FEDERAL_INDIVIDUAL.members]
        self.assertEqual(keys.index(KEY), keys.index("sch_1") + 1)

    def test_registered_as_a_non_fill(self):
        self.assertIsNotNone(registry.non_fill_reason(KEY))


class Sch1Line8zAmendmentGuardTests(unittest.TestCase):
    """The amendment packet renders only the selected changed specs and does
    not yet attach the 8z statement: a changed Schedule 1 reading "See
    statement" is refused (fail closed) until the follow-up lane lands.
    Native: a wages-only original amended to add Form 1099-G income."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def tearDown(self):
        self._tmp.cleanup()

    def _amend(self, original, amended):
        results = self.orch.compute_federal(original)
        filed = self.tmp / "federal_filed.yaml"
        filed.write_text(yaml.safe_dump(
            {k: results[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
        ca_filed = self.tmp / "unused_ca.yaml"
        ca_filed.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
        case = AmendmentCase(
            year=YEAR, explanation="Added omitted Form 1099-G income.",
            original_refund_received=0.0, original_refund_applied=0.0,
            original_tax_paid=0.0)
        self.out = self.tmp / "packet"
        return self.orch.run_amendment_packet(
            original, amended, case, filed, ca_filed, self.out)

    def test_a_changed_schedule_1_saying_see_statement_is_refused(self):
        with self.assertRaises(NotImplementedError) as cm:
            self._amend(_scenario(), _scenario(Form1099G(
                payer="Example State", rtaa_payments=500.0,
                taxable_grants=1_000.0)))
        for needle in ("sch_1-8z-amendment-statement",
                       "partial Form 1040-X with no manifest",
                       "absence of packet_manifest.txt"):
            self.assertIn(needle, str(cm.exception))
        self.assertFalse((self.out / "packet_manifest.txt").exists())

    def test_a_changed_schedule_1_with_one_type_still_mails(self):
        manifest = self._amend(_scenario(), _scenario(Form1099G(
            payer="Example State", taxable_grants=1_000.0)))
        names = {mf.filename for mf in manifest.mailed_files}
        self.assertIn(f"f1040s1_{YEAR}.pdf", names)
