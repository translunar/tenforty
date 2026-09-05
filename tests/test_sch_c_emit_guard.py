"""Emit-path fail-closed guard on Schedule C (Task 8b, team-lead mandated).

The Schedule C/SE unit wires sole-proprietor income through the NATIVE compute
path (``compute_federal``) but NOT the PDF EMIT path. ``emit_pdfs`` gates only on
``s_corp_return``, so a single-filer Schedule C scenario reaches
``_federal_individual_emit_specs``, whose emit-path ``sch_1`` / ``f8995`` /
``f8959`` computes receive ``upstream`` WITHOUT sch_c/sch_se — a printed
Schedule 1 line 3/15 = 0 and a Form 8995 QBI omitting the Schedule C component,
silently disagreeing with the compute (or a §162(l) crash when SE-health > 0).

This codebase fails closed on wrong printed artifacts (U-1 / no silent
wrong-zero). Until the PDF-mapping follow-on unit (deferred tickets (ee)/(ff))
threads sch_c/sch_se into the emit path, ANY Schedule C business raises
``NotImplementedError`` at the top of ``_federal_individual_emit_specs`` — the
SHARED chokepoint for both ``emit_pdfs`` and ``run_amendment_packet``. The
COMPUTE path is UNAFFECTED (``compute_federal`` does not route through it).

``emit_pdfs`` / PdfFiller use pypdf, NOT LibreOffice — these tests never touch a
soffice entry point. Synthetic values only.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario

# Clearly synthetic: gross receipts 80,000 − supplies 5,000 = net profit 75,000.
_GROSS = 80_000.0
_SUPPLIES = 5_000.0


class SchCEmitGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.output_dir = Path(self._tmp.name) / "out"
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _scn(self, with_business: bool) -> Scenario:
        # Single-filer W-2 base. se_health defaults to 0 so the §162(l) guard is
        # NOT what fires on the business arm — the emit guard is.
        base = make_simple_scenario()
        biz = (
            [ScheduleCBusiness(description="consult", gross_receipts=_GROSS,
                               supplies=_SUPPLIES)]
            if with_business else []
        )
        return Scenario(config=base.config, w2s=base.w2s,
                        schedule_c_businesses=biz)

    def test_compute_succeeds_then_emit_fails_closed_for_schedule_c(self):
        # A: the COMPUTE path is UNAFFECTED — compute_federal succeeds and
        # populates the Schedule C net profit — but the EMIT path fails closed.
        scn = self._scn(with_business=True)
        results = self.orch.compute_federal(scn)
        # Guard must NOT block the compute path: the Schedule C figure is here.
        self.assertEqual(results["sch_1_line_3_business_income"], 75_000)

        with self.assertRaises(NotImplementedError) as ctx:
            self.orch.emit_pdfs(scn, results, self.output_dir)
        msg = str(ctx.exception)
        # The refusal names Schedule C, the PDF emit path, and the follow-on.
        self.assertIn("Schedule C", msg)
        self.assertIn("PDF", msg)
        self.assertIn("(ee)", msg)
        self.assertIn("(ff)", msg)
        self.assertIn("follow-on", msg)
        # Points the user at the working native path.
        self.assertIn("compute_federal", msg)

    def test_emit_succeeds_for_no_business_scenario(self):
        # B: no Schedule C business → the guard does NOT over-fire; emit_pdfs
        # runs the real (soffice-free) pypdf fill and returns a dict of paths.
        scn = self._scn(with_business=False)
        results = self.orch.compute_federal(scn)
        emitted = self.orch.emit_pdfs(scn, results, self.output_dir)
        self.assertIsInstance(emitted, dict)
        # The always-emitted federal forms are present with real written paths.
        self.assertIn("1040", emitted)
        self.assertIn("4868", emitted)
        for path in emitted.values():
            self.assertTrue(path.exists())


if __name__ == "__main__":
    unittest.main()
