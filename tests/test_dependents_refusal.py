"""A native-spine return with claimed dependents refuses (fail-closed).

The native 1040 spine does not model dependents: the Child Tax Credit /
Credit for Other Dependents (Schedule 8812, Form 1040 line 19) is never
computed, so the tax would be overstated, and the Form 1040 PDF mapping has
no fields for the Dependents section, so the printed return could not be
facially complete. Until the dependents release (0.2.1: Schedule 8812 plus
the dependents section), any return that routes to the native spine with a
non-empty ``dependents`` list REFUSES -- on compute and on emit, before any
math, with no acknowledge-and-proceed. Returns without dependents are
unaffected.

Synthetic values only.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.models import FilingStatus, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario

_STATUSES = (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY,
             FilingStatus.HEAD_OF_HOUSEHOLD)

# Both causes, the absence of an override, and both remedies, in order.
_MESSAGE = (r"(?s)dependent.*native 1040 spine"
            r".*Child Tax Credit.*Schedule 8812.*line 19.*overstated"
            r".*Form 1040 PDF mapping has no fields for the Dependents section"
            r".*facially complete"
            r".*no acknowledge-and-proceed"
            r".*File this return by hand.*dependents release.*0\.2\.1")


def _scenario(status, dependents=("Example Child",), year=2025):
    """A wage return well above every EIC income ceiling, so it routes to
    the native spine whatever the dependent count."""
    base = make_simple_scenario()
    extra = {}
    if status is FilingStatus.MARRIED_FILING_JOINTLY:
        extra = dict(spouse_first_name="Spouse", spouse_last_name="Example",
                     spouse_ssn="000-00-0002", spouse_birthdate="1990-03-07")
    config = dataclasses.replace(base.config, year=year, filing_status=status,
                                 dependents=list(dependents), **extra)
    return Scenario(config=config, w2s=list(base.w2s))


class NativeDependentsRefusalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def _assert_native(self, scn):
        # Reachability: the refusal is about the native path, so every
        # vehicle here must actually route native.
        eff, _ = self.orch._build_effective_scenario(scn)
        self.assertTrue(self.orch._scenario_in_spine_scope(eff))

    def test_compute_refuses_each_declared_status_with_dependents(self):
        for status in _STATUSES:
            with self.subTest(status=status.value):
                scn = _scenario(status)
                self._assert_native(scn)
                with self.assertRaisesRegex(NotImplementedError, _MESSAGE):
                    self.orch.compute_federal(scn)

    def test_emit_refuses_each_declared_status_and_writes_nothing(self):
        for status in _STATUSES:
            with self.subTest(status=status.value):
                scn = _scenario(status)
                self._assert_native(scn)
                out = self.tmp / f"emit-{status.value}"
                with self.assertRaisesRegex(NotImplementedError, _MESSAGE):
                    self.orch.emit_pdfs(scn, {}, out)
                self.assertFalse(out.exists() and any(out.iterdir()))

    def test_full_return_refuses_and_writes_nothing(self):
        out = self.tmp / "full"
        scn = _scenario(FilingStatus.SINGLE)
        # Past the packet's source-document gate, so the refusal under test
        # is the one that fires.
        scn = dataclasses.replace(scn, config=dataclasses.replace(
            scn.config, acknowledges_no_source_documents=True))
        with self.assertRaisesRegex(NotImplementedError, _MESSAGE):
            self.orch.run_full_return(scn, out)
        self.assertFalse(out.exists() and any(out.iterdir()))

    def test_message_counts_the_dependents(self):
        with self.assertRaisesRegex(NotImplementedError, r"lists 3 dependents"):
            self.orch.compute_federal(_scenario(
                FilingStatus.HEAD_OF_HOUSEHOLD,
                dependents=("Child A", "Child B", "Child C")))

    def test_refuses_before_any_math(self):
        # Neither the native schedules (compute) nor the shared Schedule C/SE
        # wiring (emit) may run on a refused return.
        boom = AssertionError("math ran before the dependents refusal")
        scn = _scenario(FilingStatus.SINGLE)
        with mock.patch.object(ReturnOrchestrator, "_compute_native_schedules",
                               side_effect=boom), \
                mock.patch.object(ReturnOrchestrator, "_compute_sch_c_and_se",
                                  side_effect=boom):
            with self.assertRaisesRegex(NotImplementedError, _MESSAGE):
                self.orch.compute_federal(scn)
            with self.assertRaisesRegex(NotImplementedError, _MESSAGE):
                self.orch.emit_pdfs(scn, {}, self.tmp / "before-math")


class NoDependentsUnaffectedTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work")

    def test_each_declared_status_without_dependents_computes(self):
        for status in _STATUSES:
            with self.subTest(status=status.value):
                out = self.orch.compute_federal(_scenario(status, dependents=()))
                self.assertEqual(out["agi"], 100_000)

    def test_without_dependents_emits_the_1040(self):
        scn = _scenario(FilingStatus.SINGLE, dependents=())
        results = self.orch.compute_federal(scn)
        emitted = self.orch.emit_pdfs(scn, results, self.tmp / "emit")
        self.assertTrue(emitted["1040"].exists())


if __name__ == "__main__":
    unittest.main()
