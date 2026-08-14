"""Regression guard: ``compute_spine``'s ``taxable_income_before_qbi`` is UNFLOORED.

``compute_spine`` computes its own local::

    taxable_income_before_qbi = irs_round(agi - total_deductions)   # NO max(0, ...)

while the shared ``resolve_deductions`` helper's ``DeductionResolution`` field of
the same name IS floored at zero::

    taxable_income_before_qbi = max(0, irs_round(agi - total_deductions))

The two agree for every filer whose deduction is at most their AGI, so the rest
of the suite cannot tell them apart. This module pins the difference:
substituting ``resolve_deductions``' floored ``taxable_income_before_qbi`` field
for ``compute_spine``'s own local would emit 0 here instead of the negative
figure and break this test.

All figures are synthetic.
"""

import dataclasses
import unittest

from tenforty.forms.f1040_spine import compute_spine
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_simple_scenario


# Synthetic wages chosen to sit well below the single-filer standard deduction,
# so AGI − deduction is reliably negative.
_LOW_WAGES = 5_000


def _low_income_scenario():
    """make_simple_scenario() with wages reduced so the standard deduction
    exceeds AGI. Withholding is zeroed too so the scenario stays coherent."""
    scenario = make_simple_scenario()
    w2 = dataclasses.replace(
        scenario.w2s[0],
        wages=_LOW_WAGES,
        federal_tax_withheld=0,
        ss_wages=_LOW_WAGES,
        ss_tax_withheld=0,
        medicare_wages=_LOW_WAGES,
        medicare_tax_withheld=0,
    )
    return dataclasses.replace(scenario, w2s=[w2])


class UnflooredTaxableIncomeBeforeQBITests(unittest.TestCase):
    """Pin that ``taxable_income_before_qbi_deduction`` may go NEGATIVE."""

    def test_taxable_income_before_qbi_is_negative_and_unfloored(self):
        """AGI − standard deduction is emitted verbatim, with no zero floor.

        Substituting ``resolve_deductions``' floored
        ``taxable_income_before_qbi`` field for ``compute_spine``'s own local
        would emit 0 here and fail this test.

        Also pins where the floor DOES live: ``taxable_income`` (1040 line 15)
        is separately floored by ``max(0, ...)`` and comes out 0, while the
        line feeding it stays negative. That asymmetry is the point.
        """
        scenario = _low_income_scenario()
        params = load_federal_params(2025)
        out = compute_spine(
            scenario, params, {"sch_a": {"sch_a_line_17_total": 0}}
        )
        std = params.standard_deduction[scenario.config.filing_status.value]

        # Preconditions: the standard deduction was applied and it exceeds AGI,
        # so the subtraction is genuinely negative (not a vacuous assertion).
        self.assertEqual(out["standard_deduction"], std)
        self.assertEqual(out["total_deductions"], std)
        self.assertLess(out["agi"], std)

        # The unfloored value: negative, exact.
        expected = out["agi"] - std
        self.assertLess(expected, 0)
        self.assertEqual(out["taxable_income_before_qbi_deduction"], expected)

        # The floor applies one step later, at taxable income.
        self.assertEqual(out["taxable_income"], 0)


if __name__ == "__main__":
    unittest.main()
