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

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms.f1040_tax import qdcgt_tax
from tenforty.models import ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params
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


def _scn(net_receipts=0.0, expenses=0.0, est_payments=0.0, ack_qbi=False):
    # Single-filer native-spine base; the ONLY variable across arms is the
    # Schedule C business + estimated payments. `ack_qbi` bypasses the Task-6
    # QBI over-threshold gate on the high-income fixtures (QBI correctness is
    # Task 6's concern, not this task's).
    base = make_simple_scenario()
    cfg = dataclasses.replace(base.config, estimated_tax_payments=est_payments,
                              acknowledges_qbi_below_threshold=ack_qbi)
    biz = [ScheduleCBusiness(description="consult", gross_receipts=net_receipts,
                             supplies=expenses)] if net_receipts else []
    return Scenario(config=cfg, w2s=base.w2s, schedule_c_businesses=biz)


class SchCSeTaxLiabilityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")

    def test_total_tax_is_line16_income_tax_se_tax_excluded(self):
        # NON-TAUTOLOGICAL pin (mirrors the "which line does the key name" pin
        # in tests/test_total_tax_semantics.py): total_tax must equal the
        # independently-recomputed 1040 line 16 (QDCGT worksheet) at this
        # scenario's taxable income — NOT that plus SE tax. If SE tax leaked
        # into total_tax, this equality would fail.
        scn = _scn(80_000.0, 5_000.0, ack_qbi=True)   # net profit 75,000
        out = self.orch.compute_federal(scn)
        self.assertGreater(out["sch_se_line_12_se_tax"], 0)
        params = load_federal_params(scn.config.year)
        expected_line16 = qdcgt_tax(
            taxable_income=out["taxable_income"],
            qualified_dividends=out.get("qualified_dividends", 0.0),
            net_capital_gain=out.get("net_capital_gain", 0.0) or 0.0,
            params=params, filing_status=scn.config.filing_status)
        self.assertEqual(out["total_tax"], expected_line16)

    def test_se_tax_lowers_overpaid_by_income_tax_delta_plus_se_tax(self):
        # CONCRETE counterfactual: sibling WITHOUT the business, same payments.
        # overpaid falls by exactly (income-tax delta from the business income)
        # + the SE tax. The +SE-tax term proves SE tax entered the liability.
        ow = self.orch.compute_federal(
            _scn(80_000.0, 5_000.0, est_payments=40_000.0, ack_qbi=True))
        wo = self.orch.compute_federal(_scn(est_payments=40_000.0))
        self.assertGreater(ow["sch_se_line_12_se_tax"], 0)
        self.assertGreater(ow["overpaid"], 0)   # unfloored both sides → identity exact
        self.assertGreater(wo["overpaid"], 0)
        income_tax_delta = ow["total_tax"] - wo["total_tax"]
        self.assertEqual(wo["overpaid"] - ow["overpaid"],
                         income_tax_delta + ow["sch_se_line_12_se_tax"])

    def test_other_taxes_is_exact_total_of_modeled_part_ii(self):
        # PARTIAL-TOTAL PROOF: other_taxes == f8959 Additional Medicare + SE tax,
        # on a fixture where BOTH are nonzero (net earnings clear the $200k
        # single-filer Additional-Medicare threshold). Provably the total.
        out = self.orch.compute_federal(_scn(400_000.0, 0.0, ack_qbi=True))
        self.assertGreater(out["f8959_tax_total"], 0)
        self.assertGreater(out["sch_se_line_12_se_tax"], 0)
        self.assertEqual(out["other_taxes"],
                         out["f8959_tax_total"] + out["sch_se_line_12_se_tax"])

    def test_f8959_part_ii_sees_se_income_above_threshold(self):
        # SE net earnings on 400k profit (~369k) clear the $200k threshold, so
        # f8959 Part II is nonzero — SE income genuinely entered line 8.
        out = self.orch.compute_federal(_scn(400_000.0, 0.0, ack_qbi=True))
        self.assertGreater(out["f8959_tax_total"], 0)


if __name__ == "__main__":
    unittest.main()
