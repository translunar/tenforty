# tests/test_battery_param_coverage.py
"""Layer-3 coverage gate: every FederalParams field is either exercised by
a battery scenario at its boundary, or consciously waived with a reason.
A field in neither map fails — adding a params field forces this
conversation instead of silently shipping untested."""
import dataclasses
import unittest

from tenforty.params.federal import FederalParams
from tests.fixtures.spine_battery import battery_for

# field -> battery scenario names that exercise it at a boundary.
EXERCISED: dict[str, tuple[str, ...]] = {
    "year": ("canonical_wage_investment_rental",),          # threads everywhere
    "standard_deduction": ("zero_tax_refund", "tax_table_band"),
    "ordinary_brackets": ("zero_tax_refund", "tax_table_band"),
    "qdcgt_breakpoints": ("qdcgt_15_to_20_boundary",),
    "addl_medicare_threshold": ("addl_medicare_boundary",),
    "ss_wage_base": ("qdcgt_15_to_20_boundary",),           # wages above base
    "qbi_threshold": ("qbi_threshold_boundary",),
    "salt_cap_starting": ("itemizer_with_w2_state_tax",),   # cap binds in 2024
    "salt_cap_floor": ("itemizer_with_w2_state_tax",),
    "salt_phaseout_threshold": ("itemizer_with_w2_state_tax",),  # consulted every itemizer
}

# field -> reason it is consciously NOT exercised. Shrinking this map is
# progress; growing it is a decision that belongs in review.
WAIVED: dict[str, str] = {
    "salt_phaseout_rate": "OBBBA >$500k phaseout math is scoped out "
                          "(sch_a raises NotImplementedError above threshold)",
    "medical_agi_floor_pct": "no medical-expense battery scenario yet; "
                             "add one when a medical itemizer enters scope",
    "prior_year_salt_cap": "battery pins prior_year_itemized=False, "
                           "short-circuiting the Sch 1 tax-benefit rule",
    "eic_income_ceiling": "exercised as the routing guard (scope gate), "
                          "not as a computed value",
    "nonitemizer_charitable_cap": "load-time-only field so far (params + "
                          "scenario channel + negative/one-year-provision "
                          "guards); the compute-time field>cap and "
                          "itemizer-status checks that would consume it "
                          "ship in a later task",
}


class BatteryParamCoverageTests(unittest.TestCase):
    def test_every_field_exercised_or_waived(self):
        fields = {f.name for f in dataclasses.fields(FederalParams)}
        placed = set(EXERCISED) | set(WAIVED)
        self.assertEqual(set(EXERCISED) & set(WAIVED), set(),
                         "a field cannot be both exercised and waived")
        self.assertEqual(fields - placed, set(),
                         "params fields with no coverage decision")
        self.assertEqual(placed - fields, set(),
                         "coverage maps name nonexistent fields")

    def test_exercising_scenarios_exist(self):
        names = {n for n, _ in battery_for(2025)}
        for field, scenarios in EXERCISED.items():
            for scenario in scenarios:
                with self.subTest(field=field, scenario=scenario):
                    self.assertIn(scenario, names)
