# tests/test_spine_battery_parameterization.py
"""battery_for(year) generates the parity battery from params — no cloned
per-year builders. Structural checks only; the deep proof is the parity
gate itself (tests/test_f1040_spine_oracle.py) staying green both years."""
import tempfile
import unittest
from pathlib import Path

from tenforty import years as year_manifest
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import battery_for

REPO_ROOT = Path(__file__).parent.parent

_EXPECTED_NAMES = [
    "canonical_wage_investment_rental",
    "qdcgt_15_to_20_boundary",
    "qbi_threshold_boundary",
    "addl_medicare_boundary",
    "zero_tax_refund",
    "owes_tax",
    "tax_table_band",
    "itemizer_with_w2_state_tax",
]


class BatteryParameterizationTests(unittest.TestCase):
    def test_same_seven_scenarios_every_year(self):
        for year in (2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual([n for n, _ in battery_for(year)],
                                 _EXPECTED_NAMES)

    def test_year_threads_into_config(self):
        for year in (2023, 2024, 2025):
            for name, build in battery_for(year):
                with self.subTest(year=year, scenario=name):
                    self.assertEqual(build().config.year, year)

    def test_ss_wage_base_caps_high_wage_scenarios(self):
        # SSA OASDI wage base: 160,200 (2023), 168,600 (2024), 176,100 (2025).
        # The $500k-wage QDCGT scenario must carry ss_wages at exactly the
        # year's base. The 2023 figure is the attested load(2023).ss_wage_base
        # (SSA 2023 OASDI announcement / IRS Pub 15).
        for year, base in ((2023, 160_200.0), (2024, 168_600.0), (2025, 176_100.0)):
            scenario = dict(battery_for(year))["qdcgt_15_to_20_boundary"]()
            self.assertEqual(scenario.w2s[0].ss_wages, base)

    def test_sale_dates_fall_in_tax_year(self):
        for year in (2023, 2024, 2025):
            scenario = dict(battery_for(year))["owes_tax"]()
            self.assertTrue(
                scenario.form1099_b[0].date_sold.startswith(str(year)))

    def test_native_spine_computes_every_scenario_every_year(self):
        # The compute-only tier's promise ("native spine compute") as a machine
        # check: every battery scenario computes through the native 1040 spine —
        # no emit, no workbook, no soffice — for every FULL and COMPUTE-ONLY
        # federal year, producing the core outputs. This is the leg that would
        # catch a spine that crashes or mis-shapes on a newly-backfilled year's
        # params; verifying the inputs pack alone (params/table/attestation)
        # would not. Demand exactly what the tier promises — no less.
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tempfile.mkdtemp()) / "work",
        )
        for year in (year_manifest.FEDERAL_YEARS
                     + year_manifest.FEDERAL_COMPUTE_ONLY_YEARS):
            for name, build in battery_for(year):
                with self.subTest(year=year, scenario=name):
                    results = orch.compute_federal(build())
                    self.assertIn("total_tax", results)
                    self.assertIn("taxable_income", results)
                    self.assertIsInstance(results["total_tax"], (int, float))
