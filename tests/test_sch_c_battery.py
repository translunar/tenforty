"""Schedule C verification battery gate: native compute must equal the
air-gapped hand-derived values, per line, for every scenario and year.

The expected values come from tests/fixtures/sch_c_battery_expected.py, which
is derived from the IRS form instructions by a deriver who never saw tenforty
source. A mismatch here is a STOP-and-reconcile at team-lead level: never
edit an expected value or the compute to make this pass."""
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import sch_c as form_sch_c
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import sch_c_battery as battery
from tests.fixtures.sch_c_battery_expected import EXPECTED
from tests.helpers import REPO_ROOT


def _multi_business(name, year):
    """Whether the scenario has two or more Schedule C businesses with
    nonzero net profit: Form 8995 refuses it until phase C of the f8995
    per-source-rows lane (the half-SE-tax allocation ruling)."""
    scenario = battery.SCENARIOS[name](year)
    return sum(1 for biz in scenario.schedule_c_businesses
               if form_sch_c.net_profit_estimate(biz, year, mid_quarter=False)
               ) >= 2


class SchCBatteryGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def test_fixture_covers_the_value_scenario_years_and_only_valid_refusals(self):
        every = {(name, year) for name in battery.SCENARIOS
                 for year in battery.YEARS}
        value_keys = {k for k, v in EXPECTED.items() if "refuses" not in v}
        refusal_keys = {k for k, v in EXPECTED.items() if "refuses" in v}
        self.assertEqual(len(every - set(battery.REFUSING)), 23)
        self.assertEqual(value_keys, every - set(battery.REFUSING))
        self.assertLessEqual(refusal_keys, set(battery.REFUSING))

    def test_refusal_scenario_years_refuse(self):
        for name, year in sorted(battery.REFUSING):
            with self.subTest(scenario=name, year=year):
                with self.assertRaises(NotImplementedError) as ctx:
                    battery.native_lines(
                        self.orch, battery.SCENARIOS[name](year))
                self.assertIn(battery.REFUSAL_TEXT, str(ctx.exception))
                fixture_entry = EXPECTED.get((name, year))
                if fixture_entry is not None:
                    self.assertIn(
                        fixture_entry["refuses"], str(ctx.exception))

    def test_native_compute_equals_the_derived_values(self):
        for (name, year), expected in sorted(EXPECTED.items()):
            if "refuses" in expected:
                continue   # asserted by test_refusal_scenario_years_refuse
            if _multi_business(name, year):
                continue   # refused until phase C; pinned below
            native = battery.native_lines(
                self.orch, battery.SCENARIOS[name](year))
            for form, by_line in expected.items():
                for line, value in by_line.items():
                    with self.subTest(scenario=name, year=year, form=form,
                                      line=line):
                        self.assertIn(
                            form, native, f"native produced no {form}")
                        if value is None:
                            # Expected blank: no native value, or zero.
                            self.assertFalse(
                                native[form].get(line),
                                f"{form} line {line} expected blank")
                            continue
                        self.assertIn(
                            line, native[form],
                            f"native has no value for {form} line {line}")
                        self.assertEqual(native[form][line], value)

    def test_multi_business_value_years_refuse_until_phase_c(self):
        # The value scenario-years the gate above skips: two or more
        # Schedule C businesses, which Form 8995 refuses until phase C of
        # the f8995 per-source-rows lane lands. When it does, this goes red
        # and the skip above is removed.
        skipped = sorted(key for key, expected in EXPECTED.items()
                         if "refuses" not in expected
                         and _multi_business(*key))
        self.assertEqual(skipped, [("two-trades", year)
                                   for year in (2022, 2023, 2024, 2025)])
        for name, year in skipped:
            with self.subTest(scenario=name, year=year):
                with self.assertRaises(NotImplementedError) as ctx:
                    battery.native_lines(
                        self.orch, battery.SCENARIOS[name](year))
                self.assertIn("Form 8995 per-source rows", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
