"""Fail-closed guard: SE-health deduction on the XLSX workbook path (ticket (dd)).

The native single-filer spine (Task 1) honors
`config.self_employed_health_insurance_deduction` (Schedule 1 line 17). The XLSX
workbook path (`_compute_1040_via_workbook`, taken by non-single / EIC-possible
filers) does NOT wire that input — the wiring is deferred to ticket (dd). Until it
lands, a workbook-path return carrying the deduction must REFUSE loudly rather than
silently drop line 17 and overstate AGI.

These tests exercise the guard WITHOUT LibreOffice: the guard sits at the very top
of `_compute_1040_via_workbook`, before any spreadsheet evaluation, so the "fires"
case raises before soffice is ever reached, and the "field=0" case is proven to get
PAST the guard by short-circuiting the engine step with a sentinel — never launching
soffice. Synthetic values only.
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario


# Synthetic (non-PII) SE-health deduction amount used to trip the guard.
_SYNTHETIC_SE_HEALTH = 1234.0


class _EngineReached(Exception):
    """Sentinel: execution passed the guard and reached the workbook engine."""


class SeHealthWorkbookGuardTests(unittest.TestCase):
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

    def test_fires_when_deduction_set_on_workbook_path(self):
        """Nonzero SE-health deduction on a workbook-path scenario -> refuse.

        Routes through `_compute_1040_pipeline` so the PIPELINE'S OWN routing
        (not a direct call) selects the workbook branch, then the guard raises
        NotImplementedError before any spreadsheet evaluation. Falsifiable:
        delete the guard and the pipeline proceeds into the workbook compute
        instead of raising here.
        """
        s = self._workbook_path_scenario()
        s.config.self_employed_health_insurance_deduction = _SYNTHETIC_SE_HEALTH
        with tempfile.TemporaryDirectory() as tmp:
            orch = self._orch(tmp)
            eff, _ = orch._build_effective_scenario(s)
            # Prove the scenario really takes the workbook branch (guard useless
            # otherwise): the spine-scope predicate excludes it.
            self.assertFalse(orch._scenario_in_spine_scope(eff))
            with self.assertRaises(NotImplementedError) as ctx:
                orch._compute_1040_pipeline(eff)
        msg = str(ctx.exception).lower()
        # Message must name BOTH the cause (workbook wiring) and the truth
        # (native path honors it) so a reworded raise can't silently pass.
        self.assertIn("workbook", msg)
        self.assertIn("native", msg)
        self.assertIn("(dd)", msg)

    def test_does_not_fire_when_deduction_zero_on_workbook_path(self):
        """SAME workbook-path scenario, field unset -> guard lets it through.

        The engine step is replaced with a sentinel-raising mock so execution
        never launches soffice. Reaching `_EngineReached` proves the guard did
        NOT fire at field=0 (it would raise NotImplementedError first).
        Falsifiable: if the guard over-fires, NotImplementedError propagates and
        `_EngineReached` is never raised, so `assertRaises(_EngineReached)`
        fails.
        """
        s = self._workbook_path_scenario()
        # Field left at its 0.0 default — assert the precondition explicitly.
        self.assertEqual(
            0.0, s.config.self_employed_health_insurance_deduction,
        )
        with tempfile.TemporaryDirectory() as tmp:
            orch = self._orch(tmp)
            eff, _ = orch._build_effective_scenario(s)
            self.assertFalse(orch._scenario_in_spine_scope(eff))
            with mock.patch.object(
                orch.engine, "compute", side_effect=_EngineReached,
            ):
                with self.assertRaises(_EngineReached):
                    orch._compute_1040_via_workbook(eff)


if __name__ == "__main__":
    unittest.main()
