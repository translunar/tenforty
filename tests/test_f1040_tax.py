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
        self.assertEqual(tax_from_schedule(0, self.p.for_status(FilingStatus.SINGLE)), 0)

    def test_first_bracket_only(self):
        # 10% of 10,000 = 1,000.
        self.assertEqual(tax_from_schedule(10_000, self.p.for_status(FilingStatus.SINGLE)), 1_000)

    def test_spans_multiple_brackets(self):
        # 100,000 single 2025: 1192.50 + (48475-11925)*.12 + (100000-48475)*.22
        # = 1192.50 + 4386.00 + 11335.50 = 16914.00 -> 16914
        self.assertEqual(tax_from_schedule(100_000, self.p.for_status(FilingStatus.SINGLE)), 16_914)

    def test_reads_the_view_status_column(self):
        # Synthetic sentinel schedule (not a tax value) under the HoH key:
        # 50% up to 1,000, 0% above. The view must read THAT column.
        import dataclasses
        import math
        sentinel = ((1_000.0, 0.5), (math.inf, 0.0))
        params = dataclasses.replace(self.p, ordinary_brackets={
            **self.p.ordinary_brackets,
            FilingStatus.HEAD_OF_HOUSEHOLD.value: sentinel})
        hoh = params.for_status(FilingStatus.HEAD_OF_HOUSEHOLD)
        self.assertEqual(tax_from_schedule(3_000, hoh), 500)
        self.assertNotEqual(
            tax_from_schedule(3_000, params.for_status(FilingStatus.SINGLE)),
            500)

    def test_missing_status_column_refuses(self):
        import dataclasses
        from tenforty.params.status_view import UnsupportedStatusError
        single = FilingStatus.SINGLE.value
        params = dataclasses.replace(self.p, ordinary_brackets={
            single: self.p.ordinary_brackets[single]})
        with self.assertRaises(UnsupportedStatusError):
            tax_from_schedule(
                50_000, params.for_status(FilingStatus.QUALIFYING_WIDOW))

    def test_rejects_raw_params_without_a_status(self):
        with self.assertRaises(TypeError):
            tax_from_schedule(50_000, self.p)


class QdcgtWorksheetTests(unittest.TestCase):
    def setUp(self):
        self.p = load(2025)
        self.single = FilingStatus.SINGLE

    def test_no_preferential_income_equals_ordinary(self):
        # With zero qual div / cap gain, QDCGT == ordinary schedule tax.
        self.assertEqual(
            qdcgt_tax(100_000, 0, 0, self.p, self.single),
            tax_from_schedule(100_000, self.p.for_status(FilingStatus.SINGLE)),
        )

    def test_preferential_slice_taxed_at_15(self):
        # taxable 200,000; preferential 10,000 (all in the 15% band for single).
        # Ordinary portion = 190,000 taxed at schedule; pref 10,000 * 15%.
        ordinary = tax_from_schedule(190_000, self.p.for_status(FilingStatus.SINGLE))
        expected = ordinary + irs_round(10_000 * 0.15)
        self.assertEqual(
            qdcgt_tax(200_000, 4_000, 6_000, self.p, self.single), expected,
        )

    def test_non_single_raises(self):
        with self.assertRaises(NotImplementedError):
            # MFS: never declared on the native grid.
            qdcgt_tax(100_000, 0, 0, self.p, FilingStatus.MARRIED_FILING_SEPARATELY)


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
            tax_from_schedule(100_000.0, params.for_status(FilingStatus.SINGLE)))

    def test_zero_income_is_zero(self):
        params = load(2025)
        self.assertEqual(ordinary_tax(0.0, params, FilingStatus.SINGLE), 0)
