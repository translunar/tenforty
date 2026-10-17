"""Schedule SE line 8a's skip branch prints lines 8d, 9 and 10 BLANK.

Line 8a reads (every year 2021-2025, verified on each year's printed page):
"If $<wage base> or more, skip lines 8b through 10, and go to line 11" --
the amount is that year's Social Security wage base, line 7. On that branch
the paper leaves 8d, 9 and 10 blank, so the computation emits no key for
them (absent, as line 6 is absent past line 4c's $400 stop). The branch is
INCLUSIVE: 8a exactly at the base skips.

The tax itself is unchanged: on the branch line 10's Social Security
portion is already 0, so lines 12 and 13 are what the code produced before
the fix. Before-values (tests/fixtures/sch_se_skip_branch_before.json) were
captured once from the untouched merge commit 264b07d -- values the code
produced, never hand-derived -- at the base less $1, at the base, and at
the base plus $10,000, every year.
"""
import json
import unittest
from pathlib import Path

from tenforty.forms import sch_c, sch_se
from tenforty.models import ScheduleCBusiness
from tenforty.params.federal import load as load_federal_params
from tests.fixtures.sch_c_battery import _build, _w2

_BEFORE = Path(__file__).parent / "fixtures" / "sch_se_skip_branch_before.json"
_YEARS = (2021, 2022, 2023, 2024, 2025)
SKIPPED = ("sch_se_line_8d_wages_subject_to_ss",
           "sch_se_line_9_ss_earnings_remaining",
           "sch_se_line_10_ss_portion")
_OFFSETS = {"below": -1, "at": 0, "above": 10_000}


def _schedule_se(year: int, wages: float) -> dict:
    scenario = _build(year, [ScheduleCBusiness(
        description="Example Sideline", gross_receipts=12_000.0,
        supplies=500.0)], w2s=[_w2("Example Employer", wages)])
    return sch_se.compute(scenario,
                          {"sch_c": sch_c.compute(scenario, upstream={})})


class _Rows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before = json.loads(_BEFORE.read_text())

    def rows(self, *tags):
        for year in _YEARS:
            base = load_federal_params(year).ss_wage_base
            for tag in tags:
                yield year, tag, _schedule_se(year, float(base + _OFFSETS[tag]))


class SkipBranchBlanksTests(_Rows):
    def test_at_and_above_the_base_8d_9_10_are_absent(self):
        for year, tag, out in self.rows("at", "above"):
            with self.subTest(year=year, wages=tag):
                self.assertEqual([k for k in SKIPPED if k in out], [])

    def test_every_other_line_is_unchanged_on_the_branch(self):
        # Line 8a still prints the wages; lines 11-13 (the tax) and the
        # rest are exactly the pre-fix values.
        for year, tag, out in self.rows("at", "above"):
            before = {k: v for k, v in self.before[f"{tag}__{year}"].items()
                      if k not in SKIPPED}
            with self.subTest(year=year, wages=tag):
                self.assertEqual(out, before)

    def test_below_the_base_nothing_changes(self):
        # One dollar under the base, 8d / 9 / 10 print (9 = 1, 10 = 0 as a
        # value): the branch is exactly "or more".
        for year, tag, out in self.rows("below"):
            with self.subTest(year=year):
                self.assertEqual(out, self.before[f"below__{year}"])
                for key in SKIPPED:
                    self.assertIn(key, out)

    def test_the_before_values_cover_every_point(self):
        self.assertEqual(sorted(self.before), sorted(
            f"{tag}__{year}" for year in _YEARS for tag in _OFFSETS))


if __name__ == "__main__":
    unittest.main()
