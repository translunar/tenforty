"""A net premium tax credit prints inside Form 1040 line 33 through
Schedule 3 lines 9-15 and 1040 lines 31/32, none of which tenforty
produces: the page cannot foot and the Schedule 3 it references is not
attached. Emitting such a return refuses unless the scenario states
`acknowledges_schedule_3_not_produced: true` (draft/review use, with the
gap). Juno's ruling; Schedule 3 support is queued for the end of the
program. All identities synthetic."""
import dataclasses
import tempfile
import unittest
from pathlib import Path

import pypdf
import yaml

from tenforty.forms import f1040x as form_f1040x
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.models import AmendmentCase, FilingStatus, Form1099INT
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.fixtures import spine_battery
from tests.helpers import REPO_ROOT

YEAR = 2024
FLAG = "acknowledges_schedule_3_not_produced"


def _orch(tmp):
    return ReturnOrchestrator(spreadsheets_dir=REPO_ROOT / "spreadsheets",
                              work_dir=Path(tmp) / "work")


def _unattested():
    return dataclasses.replace(spine_battery.build_ptc_net_credit(YEAR),
                               **{FLAG: None})


class NetPtcRefusalTests(unittest.TestCase):

    def test_emitting_without_the_acknowledgment_refuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = _unattested()
            orch = _orch(tmp)
            results = orch.compute_federal(scenario)
            self.assertGreater(results["f8962_net_ptc"], 0)
            out = Path(tmp) / "out"
            with self.assertRaises(NotImplementedError) as cm:
                orch.emit_pdfs(scenario, results, out)
            msg = str(cm.exception)
            for needle in ("Schedule 3", "line 31", "line 32", "line 33",
                           "will not foot", "not attached", "queued",
                           f"{FLAG}: true", "DRAFT"):
                self.assertIn(needle, msg)
            self.assertEqual(sorted(out.glob("*.pdf")), [])

    def test_a_false_acknowledgment_refuses_too(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = dataclasses.replace(_unattested(), **{FLAG: False})
            orch = _orch(tmp)
            with self.assertRaises(NotImplementedError):
                orch.emit_pdfs(scenario, orch.compute_federal(scenario),
                               Path(tmp) / "out")

    def test_compute_is_not_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertGreater(
                _orch(tmp).compute_federal(_unattested())["f8962_net_ptc"], 0)


class NetPtcAmendmentTests(unittest.TestCase):
    """An amendment that mails a changed Form 1040 refuses the same way,
    and says the Form 1040-X it already wrote is a partial packet (the
    line 8z guard's precedent)."""

    def test_a_changed_1040_refuses_naming_the_partial_output(self):
        original = _unattested()
        amended = dataclasses.replace(original, form1099_int=[Form1099INT(
            payer="Example Bank", interest=2_000.0)])
        with tempfile.TemporaryDirectory() as tmp:
            orch = _orch(tmp)
            results = orch.compute_federal(original)
            filed = Path(tmp) / "filed.yaml"
            filed.write_text(yaml.safe_dump(
                {k: results[k] for k in form_f1040x.REQUIRED_FILED_KEYS}))
            ca_filed = Path(tmp) / "ca.yaml"
            ca_filed.write_text(yaml.safe_dump({"f540_total_liability": 0.0}))
            case = AmendmentCase(
                year=YEAR, explanation="Added omitted interest income.",
                original_refund_received=0.0, original_refund_applied=0.0,
                original_tax_paid=0.0)
            out = Path(tmp) / "packet"
            with self.assertRaises(NotImplementedError) as cm:
                orch.run_amendment_packet(original, amended, case, filed,
                                          ca_filed, out)
            msg = str(cm.exception)
            self.assertIn("Schedule 3", msg)
            self.assertIn(f"f1040x_{YEAR}.pdf is already written", msg)
            self.assertIn("packet_manifest.txt", msg)
            self.assertEqual(sorted(p.name for p in out.iterdir()),
                             [f"f1040x_{YEAR}.pdf"])


class NetPtcAttestedEmitTests(unittest.TestCase):
    """With the acknowledgment, the 1040 payments-footing guard still
    applies (ruling R-P1: one guard, both paths, no acknowledgment bypass).
    A NONZERO net PTC sits in line 33 with no printed line holding it, so
    the emit refuses; a net PTC of exactly 0 is arithmetic-neutral and the
    acknowledged return still emits, footing."""

    def test_a_nonzero_net_ptc_refuses_even_acknowledged(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = spine_battery.build_ptc_net_credit(YEAR)
            self.assertIs(getattr(scenario, FLAG), True)
            orch = _orch(tmp)
            results = orch.compute_federal(scenario)
            self.assertGreater(results["f8962_net_ptc"], 0)
            out = Path(tmp) / "out"
            with self.assertRaises(NotImplementedError) as cm:
                orch.emit_pdfs(scenario, results, out)
            msg = str(cm.exception)
            for needle in ("line 33", "line 31", "Schedule 3", "Form 8962",
                           "would not foot", FLAG):
                self.assertIn(needle, msg)
            self.assertEqual(sorted(out.glob("*.pdf")), [])

    def test_a_zero_net_ptc_acknowledged_return_emits_and_foots(self):
        with tempfile.TemporaryDirectory() as tmp:
            scenario = dataclasses.replace(
                spine_battery.build_ptc_capped_repayment(YEAR), **{FLAG: True})
            orch = _orch(tmp)
            results = orch.compute_federal(scenario)
            self.assertEqual(results["f8962_net_ptc"], 0)
            emitted = orch.emit_pdfs(scenario, results, Path(tmp) / "out")
            scalars = Pdf1040.get_mapping(YEAR)
            fields = pypdf.PdfReader(str(emitted["1040"])).get_fields()

            def printed(key):
                value = fields[scalars[key]].get("/V")
                return int(value) if value not in (None, "") else 0

            self.assertEqual(printed("total_payments"),
                             printed("federal_withheld")
                             + printed("estimated_tax_payments")
                             + printed("total_other_payments"))


class AcknowledgmentPlumbingTests(unittest.TestCase):
    # A stray True (net PTC 0) is NOT refused, unlike a positions election
    # the return never reaches: an election chooses between contested
    # outcomes, so a dangling one is a live footgun; an acknowledgment
    # accepts a limitation, and accepting one that does not apply costs
    # nothing (and refusing would break reusing a scenario across years
    # whose net PTC varies). The family-wide question stays on the
    # stray-attribute audit item (team-lead ruling).

    def test_the_net_ptc_battery_builders_state_it(self):
        # The three builders whose native rows carry a net PTC.
        for name, scenario in (
                ("ptc_net_credit", spine_battery.build_ptc_net_credit(YEAR)),
                ("ptc_reconciliation", spine_battery.build_ptc_reconciliation(
                    YEAR, FilingStatus.MARRIED_FILING_JOINTLY)),
                ("ptc_2021_ui_flat133",
                 spine_battery.build_ptc_2021_ui_flat133(2021))):
            with self.subTest(builder=name):
                self.assertIs(getattr(scenario, FLAG), True)

    def _load(self, value):
        data = yaml.safe_load(
            (REPO_ROOT / "tests" / "fixtures" / "simple_w2.yaml").read_text())
        data[FLAG] = value
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "s.yaml"
            path.write_text(yaml.safe_dump(data))
            return load_scenario(path)

    def test_the_yaml_key_loads(self):
        self.assertIs(getattr(self._load(True), FLAG), True)

    def test_a_non_boolean_refuses(self):
        with self.assertRaisesRegex(ValueError,
                                    f"{FLAG} must be true or false"):
            self._load("yes")


if __name__ == "__main__":
    unittest.main()
