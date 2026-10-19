"""Shape tests for the Schedule C verification battery's inputs and native
per-line extractor. Asserts SHAPE ONLY -- no expected tax values live here.
Synthetic inputs only."""
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures import sch_c_battery
from tests.helpers import REPO_ROOT

NAMES = (
    "sole-trade-basic", "two-trades", "day-job-plus-consulting",
    "base-maxed-day-job", "under-threshold-sideline", "big-sole-trade",
    "qbi-interplay",
)
SCH_C_KEYS = {"1", "3", "5", "7", "28", "29", "31"}
REQUIRED_FORMS = ("sch_se", "sch_2", "sch_1", "f8995", "f1040")


class SchCBatteryHarnessTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def test_battery_names_and_years(self):
        self.assertEqual(tuple(sch_c_battery.SCENARIOS), NAMES)
        self.assertEqual(sch_c_battery.YEARS, (2022, 2023, 2024, 2025))

    def test_two_trades_inputs_transcribed(self):
        scn = sch_c_battery.SCENARIOS["two-trades"](2023)
        self.assertEqual(scn.config.year, 2023)
        self.assertEqual(scn.config.filing_status.value, "single")
        self.assertEqual(scn.w2s, [])
        self.assertEqual([b.description for b in scn.schedule_c_businesses],
                         ["Harbor Tutoring", "Pinewood Crafts"])
        second = scn.schedule_c_businesses[1]
        self.assertEqual(second.gross_receipts, 14_500.0)
        self.assertEqual(second.utilities, 500.0)
        self.assertEqual(second.other_expenses, 1_000.0)

    def test_base_maxed_day_job_inputs_transcribed(self):
        scn = sch_c_battery.SCENARIOS["base-maxed-day-job"](2025)
        (w2,) = scn.w2s
        self.assertEqual(w2.employer, "Granite Peak Labs")
        self.assertEqual(w2.ss_wages, 180_000.0)
        self.assertEqual(w2.medicare_wages, 180_000.0)

    def test_refusing_set_is_exactly_the_documented_one(self):
        self.assertEqual(sch_c_battery.REFUSING, frozenset({
            ("day-job-plus-consulting", 2022),
            ("base-maxed-day-job", 2022), ("base-maxed-day-job", 2023),
            ("base-maxed-day-job", 2024), ("base-maxed-day-job", 2025),
        }))

    def test_refusing_scenario_years_raise_the_threshold_refusal(self):
        for name, year in sorted(sch_c_battery.REFUSING):
            with self.subTest(name=name, year=year):
                scn = sch_c_battery.SCENARIOS[name](year)
                with self.assertRaises(NotImplementedError) as ctx:
                    sch_c_battery.native_lines(self.orch, scn)
                self.assertIn(sch_c_battery.REFUSAL_TEXT, str(ctx.exception))
                self.assertIn("Form 8995-A", str(ctx.exception))

    def test_non_refusing_scenario_years_extract_whole_dollar_lines(self):
        for name in NAMES:
            for year in sch_c_battery.YEARS:
                if (name, year) in sch_c_battery.REFUSING:
                    continue
                with self.subTest(name=name, year=year):
                    scn = sch_c_battery.SCENARIOS[name](year)
                    lines = sch_c_battery.native_lines(self.orch, scn)
                    self.assertEqual(set(lines["sch_c_1"]), SCH_C_KEYS)
                    for form in REQUIRED_FORMS:
                        self.assertIn(form, lines)
                    self.assertEqual(set(lines["f1040"]),
                                     {"agi", "taxable_income"})
                    for form, form_lines in lines.items():
                        for line, value in form_lines.items():
                            self.assertIsInstance(value, int, (form, line))

    def test_second_business_yields_a_second_schedule_c_only_when_present(self):
        scn = sch_c_battery.SCENARIOS["two-trades"](2024)
        lines = sch_c_battery.native_lines(self.orch, scn)
        self.assertIn("sch_c_2", lines)
        self.assertNotIn("sch_c_3", lines)

    def test_every_scenario_is_in_spine_scope(self):
        for name in NAMES:
            for year in sch_c_battery.YEARS:
                with self.subTest(name=name, year=year):
                    scn = sch_c_battery.SCENARIOS[name](year)
                    self.assertTrue(self.orch._scenario_in_spine_scope(scn))
