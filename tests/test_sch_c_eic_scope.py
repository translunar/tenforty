"""EIC-scope AGI estimate must include Schedule C net profit (partial-total fix).

`ReturnOrchestrator._scenario_in_spine_scope` builds a cheap `agi_estimate` to
gate whether a single filer is *possibly* EIC-eligible (below the year's EIC
income ceiling) and therefore must route to the XLSX workbook rather than the
native 1040 spine. That estimate is documented to "include ALL scenario income
components", but the Schedule C / SE unit added Schedule C net profit to the
model WITHOUT adding it to this aggregate -- a partial total.

Consequence (the class this unit exists to serve): a single filer with LOW W-2
wages (below the EIC ceiling) but HIGH Schedule C net profit (so true AGI clears
the ceiling) reads as low-AGI, routes to the workbook, and hits the Task-8
fail-closed refusal (the workbook path does not wire Schedule C / SE) -- instead
of computing natively on the spine that now supports Schedule C.

This test pins that such a filer routes NATIVE and computes. It also pins the
non-raising `net_profit_estimate` helper directly.

Synthetic values only.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import sch_c as form_sch_c
from tenforty.models import ScheduleCBusiness, Scenario, W2
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_federal_params
from tests.helpers import REPO_ROOT, make_simple_scenario

# Year 2025, single, 0 dependents -> EIC income ceiling[0] = 26_214 (y2025.py).
# Choose synthetic amounts so WAGES ALONE are below the ceiling but WAGES + Sch C
# net profit clear it comfortably:
#   wages 15,000  <  26,214  (ceiling[0])
#   net profit = gross 50,000 - supplies 5,000 = 45,000
#   wages + net profit = 60,000  >  26,214
_LOW_WAGES = 15_000.0
_GROSS = 50_000.0
_SUPPLIES = 5_000.0
_NET_PROFIT = 45_000


class SchCNetProfitEstimateHelperTests(unittest.TestCase):
    def test_net_profit_estimate_is_gross_minus_expenses(self):
        # Non-raising helper: gross_receipts - sum of the 12 Part II expense
        # categories, with NO refusal guards (it is a pre-compute gate estimate).
        biz = ScheduleCBusiness(
            description="synthetic", gross_receipts=_GROSS,
            supplies=_SUPPLIES, advertising=1_000.0, utilities=500.0,
        )
        self.assertEqual(
            form_sch_c.net_profit_estimate(biz),
            _GROSS - (_SUPPLIES + 1_000.0 + 500.0),
        )

    def test_net_profit_estimate_does_not_raise_on_net_loss(self):
        # A net-loss business is refused by sch_c.compute, but the estimate runs
        # BEFORE that refusal -- it must NOT raise (returns a negative number).
        biz = ScheduleCBusiness(
            description="synthetic loss", gross_receipts=1_000.0,
            supplies=9_000.0,
        )
        self.assertEqual(form_sch_c.net_profit_estimate(biz), 1_000.0 - 9_000.0)


class SchCEicScopeRoutingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _low_wage_high_schc_scenario(self) -> Scenario:
        base = make_simple_scenario()
        low_wage_w2 = W2(
            employer="Acme Corp",
            wages=_LOW_WAGES,
            federal_tax_withheld=1_000.0,
            ss_wages=_LOW_WAGES,
            ss_tax_withheld=930.0,
            medicare_wages=_LOW_WAGES,
            medicare_tax_withheld=217.5,
        )
        biz = ScheduleCBusiness(
            description="consult", gross_receipts=_GROSS, supplies=_SUPPLIES,
        )
        return Scenario(config=base.config, w2s=[low_wage_w2],
                        schedule_c_businesses=[biz])

    def test_wages_below_ceiling_but_schc_clears_it_routes_native(self):
        scn = self._low_wage_high_schc_scenario()
        # Precondition: this is exactly the mis-routing class -- wages ALONE are
        # below the ceiling, so a wages-only (or Sch-C-omitting) estimate would
        # route this filer to the workbook.
        params = load_federal_params(scn.config.year)
        ceiling = params.eic_income_ceiling[0]
        self.assertLess(_LOW_WAGES, ceiling)
        self.assertGreater(_LOW_WAGES + _NET_PROFIT, ceiling)

        eff, _ = self.orch._build_effective_scenario(scn)
        # With Sch C net profit in the estimate, the filer clears the ceiling and
        # is ruled EIC-INELIGIBLE -> in native spine scope.
        self.assertTrue(self.orch._scenario_in_spine_scope(eff))

        # And the native pipeline actually computes it -- no Task-8 workbook
        # refusal -- carrying the Schedule C net profit to Schedule 1 line 3.
        out = self.orch.compute_federal(scn)
        self.assertEqual(out["sch_1_line_3_business_income"], _NET_PROFIT)


if __name__ == "__main__":
    unittest.main()
