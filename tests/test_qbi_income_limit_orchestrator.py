"""End-to-end regression: Form 8995 income limit must use the taxpayer's
ACTUAL deduction (itemized when itemizing), computed through the orchestrator
stub-building seam. The direct f8995 unit tests supply the stub manually and
cannot catch a bug in what the orchestrator FEEDS to f8995.

All figures are GENERIC/synthetic.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.models import ScheduleK1, ItemizedDeductions, W2

from tests.helpers import make_k1_scenario

REPO_ROOT = Path(__file__).resolve().parents[1]


class QbiIncomeLimitOrchestratorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name),
        )

    def _itemizing_k1_scenario(self, qbi, itemized_total, wages):
        """Single 2025 filer, heavy itemizer, one S-corp K-1 with QBI.

        The K-1's `qbi_amount` alone does NOT flow into AGI -- only
        `ordinary_business_income` does, and it is left at its 0.0 default
        here, so AGI == wages (no adjustments). This mirrors the reference
        scenario's requirement that expected figures be derived from actual
        AGI, not assumed.
        """
        s = make_k1_scenario()
        s.config.year = 2025
        s.config.acknowledges_qbi_below_threshold = False
        # Wages drive AGI; itemized deduction far exceeds standard.
        s.w2s = [
            W2(
                employer="Generic Co",
                wages=wages,
                federal_tax_withheld=0.0,
                ss_wages=wages,
                ss_tax_withheld=0.0,
                medicare_wages=wages,
                medicare_tax_withheld=0.0,
            ),
        ]
        s.schedule_k1s = [ScheduleK1(
            entity_name="Generic S-Corp Inc",
            entity_ein="00-0000000",
            entity_type="s_corp",
            material_participation=True,
            qbi_amount=qbi,
        )]
        s.itemized_deductions = ItemizedDeductions(
            mortgage_interest=itemized_total,  # generic single-source itemized
        )
        return s

    def test_income_limit_binds_for_itemizer(self):
        """Itemized >> standard, and 20%*QBI > 20%*(actual taxable - capgain -
        qualdiv). Line 14 must bind: line 15 == line 14 < line 6.

        Chosen figures (all synthetic):
          wages = 150_000 -> AGI = 150_000 (no adjustments, K-1 contributes
            only qbi_amount, not ordinary_business_income)
          itemized = 90_000  (>> 2025 single standard ~15_750)
          actual taxable-before-QBI = 150_000 - 90_000 = 60_000
          no cap gain / qual div -> line 12 = 0, line 13 = 60_000,
            line 14 = 20% * 60_000 = 12_000
          qbi = 100_000 -> line 6 = 20% * 100_000 = 20_000
          line 15 = min(20_000, 12_000) = 12_000  (limit binds)

        PRE-FIX (bug): the stub fed Form 8995 the STANDARD-deduction-based
        taxable income even though this filer itemizes:
          std-based taxable = 150_000 - 15_750 = 134_250
          line 14 = 20% * 134_250 = 26_850
          line 15 = min(20_000, 26_850) = 20_000  (OVERSTATED -- limit doesn't
            bind at all, taxpayer gets the full uncapped QBI deduction)
        """
        s = self._itemizing_k1_scenario(
            qbi=100_000.0, itemized_total=90_000.0, wages=150_000.0,
        )
        results = self.orch._compute_native_schedules(s)
        f8995 = results["f8995"]
        # f8995_line_11_taxable_income == taxable_income_before_qbi_deduction,
        # which the orchestrator sets to AGI - actual (itemized) deduction.
        # Confirming it equals 60_000 = 150_000 - 90_000 verifies AGI landed
        # at the wages-only 150_000 the docstring assumes, before trusting
        # the downstream line-14/line-15 figures.
        self.assertEqual(f8995["f8995_line_11_taxable_income"], 60_000)
        self.assertEqual(f8995["f8995_line_6_total_before_limit"], 20_000)
        self.assertEqual(f8995["f8995_line_13_subtract"], 60_000)
        self.assertEqual(f8995["f8995_line_14_income_limit"], 12_000)
        self.assertEqual(f8995["f8995_line_15_qbi_deduction"], 12_000)

    def test_standard_filer_unchanged(self):
        """A standard-deduction filer's QBI deduction is unaffected by the fix
        (no itemized_deductions -> deduction = standard, same pre- and
        post-fix, since the fix only changes which deduction feeds the stub
        when the filer itemizes)."""
        s = make_k1_scenario()
        s.config.year = 2025
        s.config.acknowledges_qbi_below_threshold = False
        s.itemized_deductions = None
        s.schedule_k1s = [ScheduleK1(
            entity_name="Generic S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            qbi_amount=10_000.0,
        )]
        results = self.orch._compute_native_schedules(s)
        f8995 = results["f8995"]
        # line 6 = 20% * 10_000 = 2_000; with a standard-deduction filer whose
        # taxable income comfortably exceeds 5x QBI (AGI 100_000 wages from
        # make_k1_scenario, minus 2025 single standard deduction 15_750 =
        # 84_250 >> 50_000 = 5*10_000), line 6 binds (unchanged by the fix).
        self.assertEqual(f8995["f8995_line_6_total_before_limit"], 2_000)
        self.assertEqual(f8995["f8995_line_15_qbi_deduction"], 2_000)

    def test_boundary_line6_equals_line14(self):
        """At the flip point line 6 == line 14, line 15 equals both. Tune
        itemized so actual taxable-before-QBI == 5 * QBI.
          qbi = 40_000 -> line 6 = 20% * 40_000 = 8_000
          need line 13 = 5 * 8_000 = 40_000 -> line 14 = 20% * 40_000 = 8_000
          wages = 130_000, itemized = 90_000 -> taxable = 130_000 - 90_000
            = 40_000
        """
        s = self._itemizing_k1_scenario(
            qbi=40_000.0, itemized_total=90_000.0, wages=130_000.0,
        )
        results = self.orch._compute_native_schedules(s)
        f8995 = results["f8995"]
        self.assertEqual(f8995["f8995_line_13_subtract"], 40_000)
        self.assertEqual(f8995["f8995_line_6_total_before_limit"], 8_000)
        self.assertEqual(f8995["f8995_line_14_income_limit"], 8_000)
        self.assertEqual(f8995["f8995_line_15_qbi_deduction"], 8_000)

    def test_capped_deduction_flows_into_taxable_income(self):
        """The line-14-CAPPED QBI deduction -- not the uncapped line-6 figure
        -- is what reduces taxable income on the 1040. Uses the native spine
        (_compute_1040_pipeline runs compute_spine without the XLSX oracle for
        in-scope single filers).

        Same synthetic figures as test_income_limit_binds_for_itemizer:
          AGI 150_000, itemized 90_000 -> taxable-before-QBI 60_000
          line 6 = 20_000 (uncapped), line 14 = 12_000 (cap) -> line 15 = 12_000
          taxable_income = 60_000 - 12_000 = 48_000
        If the uncapped 20_000 leaked through, taxable_income would be 40_000.
        """
        s = self._itemizing_k1_scenario(
            qbi=100_000.0, itemized_total=90_000.0, wages=150_000.0,
        )
        self.assertTrue(self.orch._scenario_in_spine_scope(s))
        result = self.orch._compute_1040_pipeline(s)
        self.assertEqual(result["total_deductions"], 90_000)
        self.assertEqual(result["taxable_income_before_qbi_deduction"], 60_000)
        self.assertEqual(result["qbi_deduction"], 12_000)
        self.assertEqual(result["taxable_income"], 48_000)


if __name__ == "__main__":
    unittest.main()
