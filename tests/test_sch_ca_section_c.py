# tests/test_sch_ca_section_c.py
"""RED-first tests pinning the CORRECT Schedule CA (540) Part I Section C
netting behavior (program bug #11).

The Schedule CA (540) form NETS Section C: Part I line 27 = line 10 (income,
Sections A + B) minus line 26 (Section C adjustments), PER COLUMN A/B/C
(verified on the 2021-2025 editions; see
`.superpowers/sdd/content-audit/cframe-investigate.md`). The pre-fix kernel used
a flat `ca_agi = federal_agi - Sum(all Col B) + Sum(all Col C)`, which
sign-INVERTS every Section C divergence: a §C Column-B (subtraction) entry sits
on line 26, so it REDUCES the netted line-27 Column B and therefore RAISES CA
AGI — the opposite of what the flat formula does.

These tests assert the form-netting behavior and FAIL against the flat compute;
the section-partitioned compute in `sch_ca.py` makes them pass.
"""
import unittest

from tenforty.forms.sch_ca import compute as sch_ca_compute
from tenforty.models import (
    CA540Return,
    CASchCAAdjustment,
    DivergenceDirection,
    DivergenceSource,
)


def _adj(line, direction, amount):
    return CASchCAAdjustment(
        source=DivergenceSource.USER,
        sch_ca_line=line,
        direction=direction,
        amount=amount,
        description="test divergence",
    )


class SectionCNettingTests(unittest.TestCase):
    """Section C entries net against income per Part I line 27 (form arithmetic)."""

    def test_section_c_subtraction_raises_ca_agi(self):
        # A §C (adjustments) Column-B subtraction lands on line 26, which is
        # SUBTRACTED from line 10 to form line 27 -> the netted Col B total goes
        # NEGATIVE, so CA AGI RISES by the amount (opposite of an income-line sub).
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                _adj("Part I §C 14", DivergenceDirection.SUBTRACTION, 5_000.0),
            ]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        # Per-line Col B key is unchanged (raw amount).
        self.assertEqual(result["sch_ca_line_part_i_c_14_subtractions"], 5_000.0)
        # Netted line-27 Col B = line 10 (0) - line 26 (5000) = -5000.
        self.assertEqual(result["sch_ca_total_subtractions"], -5_000.0)
        self.assertEqual(result["sch_ca_total_additions"], 0.0)
        # CA AGI = fed - net_sub + net_add = 100000 - (-5000) + 0 = 105000.
        self.assertEqual(result["sch_ca_ca_agi"], 105_000.0)

    def test_section_c_addition_lowers_ca_agi(self):
        # A §C Column-C addition lands on line 26 Col C, subtracted from line 10
        # Col C -> netted line-27 Col C goes NEGATIVE -> CA AGI FALLS.
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                _adj("Part I §C 14", DivergenceDirection.ADDITION, 5_000.0),
            ]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        self.assertEqual(result["sch_ca_line_part_i_c_14_additions"], 5_000.0)
        self.assertEqual(result["sch_ca_total_additions"], -5_000.0)
        self.assertEqual(result["sch_ca_total_subtractions"], 0.0)
        # CA AGI = 100000 - 0 + (-5000) = 95000.
        self.assertEqual(result["sch_ca_ca_agi"], 95_000.0)


class SectionABIncomeUnchangedTests(unittest.TestCase):
    """Income-line (§A/§B) divergences behave exactly as before the fix."""

    def test_income_subtraction_lowers_ca_agi(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                _adj("Part I §B 8z", DivergenceDirection.SUBTRACTION, 5_000.0),
            ]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        self.assertEqual(result["sch_ca_total_subtractions"], 5_000.0)
        self.assertEqual(result["sch_ca_ca_agi"], 95_000.0)

    def test_income_addition_raises_ca_agi(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                _adj("Part I §A 2", DivergenceDirection.ADDITION, 5_000.0),
            ]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        self.assertEqual(result["sch_ca_total_additions"], 5_000.0)
        self.assertEqual(result["sch_ca_ca_agi"], 105_000.0)


class ZeroSectionCBehaviorPreservationTests(unittest.TestCase):
    """A scenario with NO §C entry is byte-identical to the old flat formula.

    This is the behavior-preservation anchor: when line 26 (§C total) is zero,
    line 27 = line 10, so the netted totals equal the flat Sum-all totals and CA
    AGI is unchanged. Values are hand-computed against the flat formula.
    """

    def test_income_only_scenario_matches_flat_formula(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[
                _adj("Part I §B 8z", DivergenceDirection.SUBTRACTION, 1_500.0),
                _adj("Part I §A 2", DivergenceDirection.ADDITION, 350.0),
            ]),
            federal_results={"agi": 50_000.0},
            year=2025,
        )
        # Flat == netted when §C total is zero.
        self.assertEqual(result["sch_ca_total_subtractions"], 1_500.0)
        self.assertEqual(result["sch_ca_total_additions"], 350.0)
        # 50000 - 1500 + 350 = 48850.
        self.assertEqual(result["sch_ca_ca_agi"], 48_850.0)

    def test_empty_scenario_matches_flat_formula(self):
        result = sch_ca_compute(
            ca540=CA540Return(divergences=[]),
            federal_results={"agi": 100_000.0},
            year=2025,
        )
        self.assertEqual(result["sch_ca_total_subtractions"], 0.0)
        self.assertEqual(result["sch_ca_total_additions"], 0.0)
        self.assertEqual(result["sch_ca_ca_agi"], 100_000.0)


if __name__ == "__main__":
    unittest.main()
