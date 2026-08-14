"""Unit tests for the shared deduction-resolution helper."""

import unittest

from tenforty.forms.f1040_spine import resolve_deductions
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_simple_scenario
from tenforty.models import ItemizedDeductions
import dataclasses


class ResolveDeductionsTests(unittest.TestCase):
    def _params(self, year=2025):
        return load_federal_params(year)

    def test_standard_deduction_selected_when_no_itemized(self):
        s = make_simple_scenario()  # single, 2025, no itemized
        params = self._params()
        std = params.standard_deduction[s.config.filing_status.value]
        agi = 100_000
        res = resolve_deductions(s, params, agi, sch_a={})
        self.assertTrue(res.standard_deduction_applied)
        self.assertEqual(res.total_deductions, std)
        self.assertEqual(res.standard_deduction_amount, std)
        self.assertEqual(res.schedule_a_total, 0)
        self.assertEqual(res.taxable_income_before_qbi, agi - std)

    def test_itemized_selected_when_exceeds_standard(self):
        s = make_simple_scenario()
        params = self._params()
        std = params.standard_deduction[s.config.filing_status.value]
        itemized = std + 40_000
        agi = 200_000
        res = resolve_deductions(
            s, params, agi, sch_a={"sch_a_line_17_total": itemized},
        )
        self.assertFalse(res.standard_deduction_applied)
        self.assertEqual(res.total_deductions, itemized)
        self.assertEqual(res.standard_deduction_amount, 0)
        self.assertEqual(res.taxable_income_before_qbi, agi - itemized)

    def test_taxable_income_before_qbi_floored_at_zero(self):
        s = make_simple_scenario()
        params = self._params()
        std = params.standard_deduction[s.config.filing_status.value]
        agi = std - 5_000  # deduction exceeds AGI
        res = resolve_deductions(s, params, agi, sch_a={})
        self.assertEqual(res.taxable_income_before_qbi, 0)
