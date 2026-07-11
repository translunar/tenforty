# tests/test_spine_battery_parameterization.py
"""battery_for(year) generates the parity battery from params — no cloned
per-year builders. Structural checks only; the deep proof is the parity
gate itself (tests/test_f1040_spine_oracle.py) staying green both years."""
import unittest

from tests.fixtures.spine_battery import battery_for

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
        for year in (2024, 2025):
            with self.subTest(year=year):
                self.assertEqual([n for n, _ in battery_for(year)],
                                 _EXPECTED_NAMES)

    def test_year_threads_into_config(self):
        for year in (2024, 2025):
            for name, build in battery_for(year):
                with self.subTest(year=year, scenario=name):
                    self.assertEqual(build().config.year, year)

    def test_ss_wage_base_caps_high_wage_scenarios(self):
        # SSA OASDI wage base: 168,600 (2024), 176,100 (2025). The $500k-wage
        # QDCGT scenario must carry ss_wages at exactly the year's base.
        for year, base in ((2024, 168_600.0), (2025, 176_100.0)):
            scenario = dict(battery_for(year))["qdcgt_15_to_20_boundary"]()
            self.assertEqual(scenario.w2s[0].ss_wages, base)

    def test_sale_dates_fall_in_tax_year(self):
        for year in (2024, 2025):
            scenario = dict(battery_for(year))["owes_tax"]()
            self.assertTrue(
                scenario.form1099_b[0].date_sold.startswith(str(year)))
