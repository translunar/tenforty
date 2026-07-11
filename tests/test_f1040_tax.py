import unittest

from tenforty.forms.f1040_tax import tax_from_schedule, qdcgt_tax, ordinary_tax
from tenforty.models import FilingStatus
from tenforty.params.federal import load
from tenforty.rounding import irs_round
from tenforty.tax_table import tax_from_table


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


class QdcgtWorksheetTests(unittest.TestCase):
    def setUp(self):
        self.p = load(2025)
        self.single = FilingStatus.SINGLE

    def test_no_preferential_income_equals_ordinary(self):
        # With zero qual div / cap gain, QDCGT == ordinary schedule tax.
        self.assertEqual(
            qdcgt_tax(100_000, 0, 0, self.p, self.single),
            tax_from_schedule(100_000, self.p),
        )

    def test_preferential_slice_taxed_at_15(self):
        # taxable 200,000; preferential 10,000 (all in the 15% band for single).
        # Ordinary portion = 190,000 taxed at schedule; pref 10,000 * 15%.
        ordinary = tax_from_schedule(190_000, self.p)
        expected = ordinary + irs_round(10_000 * 0.15)
        self.assertEqual(
            qdcgt_tax(200_000, 4_000, 6_000, self.p, self.single), expected,
        )

    def test_non_single_raises(self):
        with self.assertRaises(NotImplementedError):
            qdcgt_tax(100_000, 0, 0, self.p, FilingStatus.MARRIED_JOINTLY)


class OrdinaryTaxTableTests(unittest.TestCase):
    """ordinary_tax routes below-$100k income through the published Tax
    Table (matching what a filer reads off the page) and $100k+ through
    the rate schedule."""

    def test_below_ceiling_uses_table(self):
        params = load(2025)
        self.assertEqual(
            ordinary_tax(75_000.0, params, FilingStatus.SINGLE),
            tax_from_table(75_000.0, 2025, FilingStatus.SINGLE))

    def test_at_ceiling_uses_schedule(self):
        params = load(2025)
        self.assertEqual(
            ordinary_tax(100_000.0, params, FilingStatus.SINGLE),
            tax_from_schedule(100_000.0, params))

    def test_zero_income_is_zero(self):
        params = load(2025)
        self.assertEqual(ordinary_tax(0.0, params, FilingStatus.SINGLE), 0)
