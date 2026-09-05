"""§162(l) self-employed health-insurance refusals — earned-income limit +
multi-business plan-establishment.

Task 7 of the Schedule C/SE compute unit. §162(l)'s deduction is limited to the
earned income of the business under which the health plan is ESTABLISHED, and
plan-establishment designation is UNMODELED in tenforty v1 (team-lead D4 ruling).
The guard lives in ``sch_1.compute`` (runs on every native path, after it reads
sch_c/sch_se from upstream) and produces THREE behaviors:

  * exactly ONE Schedule C business -> refuse when the self-employed
    health-insurance deduction exceeds (net profit - half-SE-tax), the §162(l)
    earned-income limit;
  * TWO OR MORE businesses AND nonzero SE-health -> refuse OUTRIGHT
    (plan-establishment across multiple businesses is unmodeled);
  * ZERO businesses -> existing SE-health passthrough UNCHANGED.

This guard is what makes Task 6's QBI single-business attribution assumption
TRUE: a nonzero SE-health deduction always attributes to exactly one business,
because the multi-business case refuses here.

Each refusal is PROVEN reachable by a test, and mutation-checked (neuter the
branch, watch exactly the target test go red, restore byte-clean). Non-offending
scenarios (no business, business with SE-health within the limit, multi-business
without SE-health, no business at all) must be UNAFFECTED.

The tests drive the FULL native pipeline via ``ReturnOrchestrator.compute_federal``
(the only entry where the guard site runs). Synthetic values only.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.models import ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario


def _scn(*biz, se_health=0.0):
    # Single-filer native-spine base (no W-2 income) with only the Schedule C
    # businesses and the self-employed health-insurance deduction varied, so the
    # earned-income limit is a clean function of the business net profit alone.
    base = make_simple_scenario()
    cfg = dataclasses.replace(
        base.config, self_employed_health_insurance_deduction=se_health
    )
    return Scenario(config=cfg, schedule_c_businesses=list(biz))


class SchC162lGuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _compute_federal(self, scn):
        return self.orch.compute_federal(scn)

    def test_single_business_refuses_when_se_health_exceeds_limit(self):
        # net profit 10,000; half-SE ~707 -> limit ~9,293; SE-health 12,000 >
        # limit -> §162(l) earned-income-limit refusal.
        scn = _scn(
            ScheduleCBusiness(description="a", gross_receipts=10_000.0),
            se_health=12_000.0,
        )
        with self.assertRaises(NotImplementedError):
            self._compute_federal(scn)

    def test_single_business_allows_within_limit(self):
        # net profit 100,000; SE-health 5,000 well under the ~92,900 limit -> no
        # refusal; the deduction passes through verbatim on line 17.
        scn = _scn(
            ScheduleCBusiness(description="a", gross_receipts=100_000.0),
            se_health=5_000.0,
        )
        out = self._compute_federal(scn)
        self.assertEqual(out["sch_1_line_17_se_health"], 5_000)

    def test_se_health_exactly_at_limit_is_allowed(self):
        # §162(l)(2)(A) boundary: a deduction EXACTLY EQUAL to the earned-income
        # limit is ALLOWED; only a strictly-exceeding deduction refuses. This
        # pins the `>` (not `>=`) in the guard — a `>`→`>=` mutation would wrongly
        # refuse this case and redden here. The limit = net − half-SE isn't a
        # round number, so derive it from the return itself: compute once with
        # SE-health 0 (which does not affect net profit or the half-SE deduction),
        # read the two components, then rebuild at exactly that limit.
        biz = ScheduleCBusiness(description="a", gross_receipts=100_000.0)
        probe = self._compute_federal(_scn(biz, se_health=0.0))
        net = probe["sch_1_line_3_business_income"]
        half_se = probe["sch_1_line_15_se_tax"]
        limit = net - half_se
        out = self._compute_federal(_scn(biz, se_health=float(limit)))
        self.assertEqual(out["sch_1_line_17_se_health"], limit)

    def test_two_businesses_with_se_health_refuses_outright(self):
        # Two businesses AND any nonzero SE-health -> outright refusal
        # (plan-establishment designation unmodeled), regardless of the limit.
        scn = _scn(
            ScheduleCBusiness(description="a", gross_receipts=100_000.0),
            ScheduleCBusiness(description="b", gross_receipts=80_000.0),
            se_health=1.0,
        )
        with self.assertRaises(NotImplementedError):
            self._compute_federal(scn)

    def test_two_businesses_without_se_health_ok(self):
        # Two businesses but NO SE-health -> the multi-business refusal does not
        # fire (guard is gated on nonzero SE-health); the return computes.
        scn = _scn(
            ScheduleCBusiness(description="a", gross_receipts=100_000.0),
            ScheduleCBusiness(description="b", gross_receipts=80_000.0),
            se_health=0.0,
        )
        out = self._compute_federal(scn)
        self.assertEqual(out["sch_1_line_3_business_income"], 180_000)

    def test_no_schedule_c_passthrough_unchanged(self):
        # No business at all -> the guard is skipped entirely and the stated
        # SE-health deduction passes through unchanged on line 17.
        scn = _scn(se_health=20_000.0)
        out = self._compute_federal(scn)
        self.assertEqual(out["sch_1_line_17_se_health"], 20_000)


if __name__ == "__main__":
    unittest.main()
