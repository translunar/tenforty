import unittest

from tenforty.forms.f1040_tax import tax_from_schedule
from tenforty.params.federal import load


class TaxFromScheduleTests(unittest.TestCase):
    def setUp(self):
        self.p = load(2025)

    def test_zero_income_zero_tax(self):
        self.assertEqual(tax_from_schedule(0, self.p), 0)

    def test_first_bracket_only(self):
        # 10% of 10,000 = 1,000.
        self.assertEqual(tax_from_schedule(10_000, self.p), 1_000)

    def test_spans_multiple_brackets(self):
        # 100,000 single 2025: 1192.50 + (48475-11925)*.12 + (100000-48475)*.22
        # = 1192.50 + 4386.00 + 11335.50 = 16914.00 -> 16914
        self.assertEqual(tax_from_schedule(100_000, self.p), 16_914)
