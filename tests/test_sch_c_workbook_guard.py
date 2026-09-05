"""Fail-closed guard: Schedule C / SE activity on the XLSX workbook path.

The native single-filer spine wires Schedule C (net profit) and Schedule SE
(self-employment tax) into the 1040. The XLSX workbook path
(`_compute_1040_via_workbook`, taken by non-single / EIC-possible filers) does
NOT wire Schedule C / SE — the workbook would silently emit a return WITHOUT the
business income and SE tax. Until that wiring lands, a workbook-path return
carrying a Schedule C business must REFUSE loudly rather than understate income
and tax.

These tests exercise the guard WITHOUT LibreOffice: the guard sits at the very
top of `_compute_1040_via_workbook`, before any spreadsheet evaluation, so the
"fires" case raises before soffice is ever reached, and the "empty" case is
proven to get PAST the guard by short-circuiting the engine step with a sentinel
— never launching soffice. Synthetic values only.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.models import ScheduleCBusiness
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario


# Synthetic (non-PII) gross-receipts amount used to trip the guard.
_SYNTHETIC_GROSS_RECEIPTS = 1234.0


class _EngineReached(Exception):
    """Sentinel: execution passed the guard and reached the workbook engine."""


class SchCWorkbookGuardTests(unittest.TestCase):
    def _orch(self, tmp: str) -> ReturnOrchestrator:
        return ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp),
        )

    def _workbook_path_scenario(self):
        """A scenario that GENUINELY routes to the workbook path.

        Married-filing-jointly is not a single filer, so
        `_scenario_in_spine_scope` returns False and `_compute_1040_pipeline`
        routes to `_compute_1040_via_workbook`. The assertions in the tests
        confirm the routing predicate directly, so the branch is not assumed.
        """
        s = make_simple_scenario()
        s.config.filing_status = "married_jointly"
        return s

    def test_fires_when_business_set_on_workbook_path(self):
        """A Schedule C business on a workbook-path scenario -> refuse.

        Routes through `_compute_1040_pipeline` so the PIPELINE'S OWN routing
        (not a direct call) selects the workbook branch, then the guard raises
        NotImplementedError before any spreadsheet evaluation. Falsifiable:
        delete the guard and the pipeline proceeds into the workbook compute
        instead of raising here.
        """
        s = self._workbook_path_scenario()
        s.schedule_c_businesses = [
            ScheduleCBusiness(
                description="Synthetic sole prop",
                gross_receipts=_SYNTHETIC_GROSS_RECEIPTS,
            )
        ]
        with tempfile.TemporaryDirectory() as tmp:
            orch = self._orch(tmp)
            eff, _ = orch._build_effective_scenario(s)
            # Prove the scenario really takes the workbook branch (guard useless
            # otherwise): the spine-scope predicate excludes it.
            self.assertFalse(orch._scenario_in_spine_scope(eff))
            self.assertTrue(eff.schedule_c_businesses)
            with self.assertRaises(NotImplementedError) as ctx:
                orch._compute_1040_pipeline(eff)
        msg = str(ctx.exception).lower()
        # Message must name BOTH the cause (workbook wiring) and the truth
        # (native single-filer path supports it) so a reworded raise can't
        # silently pass.
        self.assertIn("workbook", msg)
        self.assertIn("native", msg)

    def test_does_not_fire_when_no_business_on_workbook_path(self):
        """SAME workbook-path scenario, no business -> guard lets it through.

        The engine step is replaced with a sentinel-raising mock so execution
        never launches soffice. Reaching `_EngineReached` proves the guard did
        NOT fire with no business (it would raise NotImplementedError first).
        Falsifiable: if the guard over-fires, NotImplementedError propagates and
        `_EngineReached` is never raised, so `assertRaises(_EngineReached)`
        fails.
        """
        s = self._workbook_path_scenario()
        # No Schedule C business — assert the precondition explicitly.
        self.assertEqual([], s.schedule_c_businesses)
        with tempfile.TemporaryDirectory() as tmp:
            orch = self._orch(tmp)
            eff, _ = orch._build_effective_scenario(s)
            self.assertFalse(orch._scenario_in_spine_scope(eff))
            self.assertEqual([], eff.schedule_c_businesses)
            with mock.patch.object(
                orch.engine, "compute", side_effect=_EngineReached,
            ):
                with self.assertRaises(_EngineReached):
                    orch._compute_1040_via_workbook(eff)


if __name__ == "__main__":
    unittest.main()
