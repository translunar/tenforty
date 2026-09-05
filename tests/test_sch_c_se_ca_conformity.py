"""California conformity — Schedule C income + half-SE-tax deduction (no new form).

Task 9 of the Schedule C/SE compute unit. California has NO separate Schedule C
and NO separate Schedule SE. Sole-proprietor business income and the deductible
half of self-employment tax reach the California return entirely THROUGH FEDERAL
AGI, via the existing Schedule CA (540) chain:

  * Schedule 1 line 3 (business income) → Schedule CA Part I §B 3 Column A
    (`_FEDERAL_TO_SCH_CA_COL_A_MAP["sch_1_line_3_business_income"]`, sch_ca.py:51),
  * Schedule 1 line 15 (half-SE-tax deduction) → Schedule CA Part I §C 15 Column A
    (`_FEDERAL_TO_SCH_CA_COL_A_MAP["sch_1_line_15_se_tax"]`, sch_ca.py:60).

Because California FULLY CONFORMS on both lines, NO Schedule CA adjustment
(Column B subtraction or Column C addition) is emitted: CA AGI equals federal
AGI. The federal AGI already reflects both the business income (raising it) and
the half-SE-tax deduction (lowering it), so the CA return inherits both with no
divergence. QBI never enters CA and is handled elsewhere (no CA QBI deduction).

This is a VERIFICATION task: the Col-A passthrough mappings pre-exist, so the
conformity assertions PASS without any code change. The non-vacuity of the
Column-A passthrough claim is proven by an out-of-band mutation check (neuter the
federal `sch_1_line_3_business_income` emission → the §B 3 Col-A assertion goes
RED), recorded in the task report — NOT by any code committed here.

Synthetic values only.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.forms import sch_ca
from tenforty.models import CA540Return, ScheduleCBusiness, Scenario
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, make_simple_scenario

# Clearly synthetic: gross receipts 80,000 − supplies 5,000 = net profit 75,000.
_GROSS = 80_000.0
_SUPPLIES = 5_000.0

# Normalized Col-A key suffixes, resolved via the production normalizer so the
# key names can never drift from `_FEDERAL_TO_SCH_CA_COL_A_MAP`'s line labels.
_B3_COL_A = f"sch_ca_line_{sch_ca._normalize_line('Part I §B 3')}_col_a"
_C15_COL_A = f"sch_ca_line_{sch_ca._normalize_line('Part I §C 15')}_col_a"


class SchCSeCaConformityTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def _ca_single_scn_with_business(self) -> Scenario:
        # make_simple_scenario is already a CA single filer (state="CA").
        base = make_simple_scenario()
        self.assertEqual(base.config.state, "CA")
        self.assertEqual(base.config.filing_status, "single")
        biz = ScheduleCBusiness(
            description="consult", gross_receipts=_GROSS, supplies=_SUPPLIES,
        )
        return Scenario(config=base.config, w2s=base.w2s,
                        schedule_c_businesses=[biz])

    def test_business_income_flows_to_ca_agi_col_a(self):
        scn = self._ca_single_scn_with_business()
        fed = self.orch.compute_federal(scn)
        # No CA-return-level divergences: a bare CA540Return with no user
        # divergences; business income triggers no auto-divergence either.
        ca = sch_ca.compute(
            ca540=CA540Return(divergences=[]),
            federal_results=fed,
            year=scn.config.year,
        )

        # Business income passes through to Schedule CA §B 3 Column A unchanged.
        self.assertEqual(ca[_B3_COL_A], fed["sch_1_line_3_business_income"])
        # Half-SE-tax deduction passes through to Schedule CA §C 15 Column A.
        self.assertEqual(ca[_C15_COL_A], fed["sch_1_line_15_se_tax"])

        # FULL CONFORMITY: no Schedule CA adjustment line — CA AGI == federal AGI.
        # (If a divergence were required, these totals would be nonzero and CA
        # AGI would part from federal AGI — that would be a STOP-and-report
        # finding, not a papered-over pass.)
        self.assertEqual(ca["sch_ca_total_subtractions"], 0)
        self.assertEqual(ca["sch_ca_total_additions"], 0)
        self.assertEqual(ca["sch_ca_ca_agi"], ca["sch_ca_federal_agi"])

    def test_business_income_actually_present(self):
        # Guards the conformity assertions against a vacuous pass on absent keys:
        # both Col-A cells must be genuinely populated (nonzero) for the equality
        # checks above to have teeth.
        scn = self._ca_single_scn_with_business()
        fed = self.orch.compute_federal(scn)
        self.assertGreater(fed["sch_1_line_3_business_income"], 0)
        self.assertGreater(fed["sch_1_line_15_se_tax"], 0)
        ca = sch_ca.compute(
            ca540=CA540Return(divergences=[]),
            federal_results=fed,
            year=scn.config.year,
        )
        self.assertIn(_B3_COL_A, ca)
        self.assertIn(_C15_COL_A, ca)
        self.assertGreater(ca[_B3_COL_A], 0)
        self.assertGreater(ca[_C15_COL_A], 0)


if __name__ == "__main__":
    unittest.main()
