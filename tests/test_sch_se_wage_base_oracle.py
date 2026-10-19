"""Schedule SE line 8a wage-base cases against the air-gapped oracle.

Oracle: tests/oracles/sch_se_wage_base_cases.md -- 15 hand-derived cases
(2021-2025 x at the wage base / $10,000 above it / $20,000 below it), every
line in exact cents, from the official IRS forms and instructions only. That
file stays cents-exact; it is never edited.

Each case runs the REAL pipeline (run_full_return, single filer) and reads
the Schedule SE the emit RECORDED. Single, because a married-filing-jointly
return with Schedule C is refused outright (orchestrator.
refuse_joint_schedule_c: Schedule SE is figured per person). Only Schedule SE
lines are asserted: as a single filer, wages plus line 6 cross Form 8959's
$200,000 Additional Medicare threshold in five of these runs (2023 case 2,
2024 cases 1-2, 2025 cases 1-2; the oracle's flag 3), so Form 8959 is real,
modeled computation there, outside this file's lines. Case 2's two W-2s are
the oracle's: one employer's box 3 cannot exceed the base.

Rounding: tenforty prints each line in whole dollars, rounded half up (the
Form 1040 general instructions' round-off option; Schedule SE's own sources
are silent on rounding), so each oracle line is compared as its exact cents
rounded half up. The oracle's flag 1 names the path-dependence that rounding
introduces -- rounding line 12 first and then halving it, versus rounding
line 13 at the end -- and on these inputs both paths agree (both land on a
.5 that rounds up). The FOOTING assertion is the check that bites if the
path-dependence ever does: printed line 12 equals printed line 10 plus
printed line 11 (a skipped line 10 counts as 0, as the oracle states).

On the skip branch ("If $<base> or more, skip lines 8b through 10") the
oracle marks 8b, 8c, 8d, 9 and 10 SKIPPED: the record must carry no value for
any of them -- the defect this lane fixes.
"""
import json
import re
import tempfile
import unittest
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from tenforty.models import W2, ScheduleCBusiness
from tenforty.verification import emit_manifest
from tests.fixtures.sch_c_battery import _build

_ORACLE = (Path(__file__).parent / "oracles" / "sch_se_wage_base_cases.md")
SCH_SE = ("federal", "sch_se")
# Oracle line -> the Schedule SE compute key that prints it. Lines the
# oracle leaves without entry (1a, 1b, 4b, 5a, 5b; 8b, 8c below the base)
# have no compute key: tenforty models none of those inputs.
KEYS = {
    "2": "sch_se_line_2_net_profit",
    "3": "sch_se_line_3_net_profit",
    "4a": "sch_se_line_4a_net_earnings",
    "4c": "sch_se_line_4c_net_earnings",
    "6": "sch_se_line_6_total_net_earnings",
    "7": "sch_se_line_7_ss_wage_base",
    "8a": "sch_se_line_8a_ss_wages_and_tips",
    "8d": "sch_se_line_8d_wages_subject_to_ss",
    "9": "sch_se_line_9_ss_earnings_remaining",
    "10": "sch_se_line_10_ss_portion",
    "11": "sch_se_line_11_medicare_portion",
    "12": "sch_se_line_12_se_tax",
    "13": "sch_se_line_13_half_deduction",
}
UNMODELED = ("1a", "1b", "4b", "5a", "5b", "8b", "8c")


def _cases():
    text = _ORACLE.read_text()
    return json.loads(re.search(r"```json\n(.*?)\n```", text, re.S).group(1))


def _dollars(amount: str) -> int:
    """The oracle's exact amount, rounded half up to the dollar."""
    return int(Decimal(amount).quantize(Decimal(1), rounding=ROUND_HALF_UP))


# Box 1 excludes a pre-tax 401(k) elective deferral at the year's 402(g)
# limit (boxes 3 and 5 include it); one employer only, the limit is per person.
_ELECTIVE_DEFERRAL_LIMIT = {2021: 19_500.0, 2022: 20_500.0, 2023: 22_500.0,
                            2024: 23_000.0, 2025: 23_500.0}


def _w2(employer: str, ss_wages: float, deferral: float) -> W2:
    return W2(employer=employer, wages=ss_wages - deferral,
              federal_tax_withheld=0.0, ss_wages=ss_wages,
              ss_tax_withheld=0.0, medicare_wages=ss_wages,
              medicare_tax_withheld=0.0)


def _scenario(case):
    year = case["tax_year"]
    wages = case["w2_box3_social_security_wages"]
    return _build(year, [ScheduleCBusiness(
        description="Example Oracle Sideline",
        gross_receipts=float(case["schedule_c_line_31_net_profit"]))],
        w2s=[_w2(f"Example Employer {i + 1}", float(w),
                 _ELECTIVE_DEFERRAL_LIMIT[year] if i == 0 else 0.0)
             for i, w in enumerate(wages)])


def _recorded_schedule_se(case) -> dict:
    out = Path(tempfile.mkdtemp()) / "out"
    orch = emit_manifest._orchestrator(out.parent / "work")
    with emit_manifest._no_workbook():
        _, emitted = orch.run_full_return(_scenario(case), out)
    (record,) = [r for r in emitted.record if r.form == SCH_SE]
    return dict(record.values)


class SchSeWageBaseOracleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = _cases()
        cls.recorded = {(c["tax_year"], c["case"]): _recorded_schedule_se(c)
                        for c in cls.cases}

    @pytest.mark.oracle
    def test_the_oracle_has_fifteen_cases(self):
        self.assertEqual(sorted((c["tax_year"], c["case"]) for c in self.cases),
                         sorted((y, k) for y in range(2021, 2026)
                                for k in ("1_at_base", "2_above_base",
                                          "3_below_base")))

    @pytest.mark.oracle
    def test_every_printed_line_matches_the_oracle(self):
        for case in self.cases:
            values = self.recorded[(case["tax_year"], case["case"])]
            for line, expected in sorted(case["lines"].items()):
                with self.subTest(year=case["tax_year"], case=case["case"],
                                  line=line):
                    if line in UNMODELED:
                        self.assertIn(expected, (None, "SKIPPED"))
                    elif expected == "SKIPPED":
                        # The paper leaves the line blank: no value recorded.
                        self.assertIsNone(values.get(KEYS[line]))
                    else:
                        self.assertEqual(values.get(KEYS[line]),
                                         _dollars(expected))

    @pytest.mark.oracle
    def test_line_12_foots_on_the_printed_page(self):
        for case in self.cases:
            values = self.recorded[(case["tax_year"], case["case"])]
            with self.subTest(year=case["tax_year"], case=case["case"]):
                self.assertEqual(
                    values[KEYS["12"]],
                    (values.get(KEYS["10"]) or 0) + values[KEYS["11"]])
