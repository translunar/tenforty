"""Spine integration — Schedule C net profit + Schedule SE half-deduction → AGI.

Task 4 of the Schedule C/SE compute unit. The orchestrator threads sch_c
(before Schedule 1) and sch_se (after sch_c) into the native pipeline; Schedule
1 line 3 reads the aggregate Schedule C net profit and line 15 reads the Schedule
SE half-of-SE-tax deduction. This test drives the FULL native pipeline via
``ReturnOrchestrator.compute_federal`` (the only entry where sch_c/sch_se are
wired) and proves:

  * line 3 populates with the Schedule C net profit,
  * line 15 (half-SE-tax) populates and is positive,
  * AGI rises by exactly (net profit − half-SE-tax deduction), and that the
    deduction genuinely LOWERS AGI below the raw business income (a non-
    tautological check: neutering the line-15 read would leave AGI at the raw
    business income and this fails RED).

Empty sch_c/sch_se (no business) → both reads default 0 → every existing
scenario UNCHANGED; that no-regression contract is proven by the full suite.

Synthetic values only.
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
_NET_PROFIT = 75_000


class SchCSpineIntegrationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _scn(self, with_business: bool) -> Scenario:
        # Same single-filer W-2 base in BOTH arms so the ONLY difference is the
        # Schedule C business — the AGI delta is attributable to it alone.
        base = make_simple_scenario()
        biz = (
            [ScheduleCBusiness(description="consult", gross_receipts=_GROSS,
                               supplies=_SUPPLIES)]
            if with_business else []
        )
        return Scenario(config=base.config, w2s=base.w2s,
                        schedule_c_businesses=biz)

    def test_business_income_and_half_se_reach_agi(self):
        out_with = self.orch.compute_federal(self._scn(with_business=True))
        out_base = self.orch.compute_federal(self._scn(with_business=False))

        # Line 3 carries the Schedule C net profit.
        self.assertEqual(out_with["sch_1_line_3_business_income"], _NET_PROFIT)
        # No-business arm carries nothing on line 3 (empty sch_c → 0).
        self.assertEqual(out_base["sch_1_line_3_business_income"], 0)

        # Line 15 (half of SE tax) populates and is positive.
        half_se = out_with["sch_1_line_15_se_tax"]
        self.assertGreater(half_se, 0)
        self.assertEqual(out_base["sch_1_line_15_se_tax"], 0)

        # AGI rises by exactly (net profit − half-SE-tax deduction) ...
        agi_delta = out_with["agi"] - out_base["agi"]
        self.assertEqual(agi_delta, _NET_PROFIT - half_se)
        # ... and the deduction genuinely LOWERS AGI below the raw business
        # income (RED if the line-15 read is neutered to 0).
        self.assertLess(agi_delta, _NET_PROFIT)


if __name__ == "__main__":
    unittest.main()
