import unittest

from tenforty.models import FilingStatus
from tenforty.forms.f540 import (
    compute_standard_deduction,
    compute_exemption_credit,
    compute_ca_tax,
)


# Verified against FTB Form 540 PDFs (committed in T1; constants in T9a).
# DO NOT modify these values — they are the FTB-published actuals
# extracted from each year's f540.pdf line 18 (standard deduction)
# and lines 7-10 (exemption credit multipliers).
EXPECTED_STANDARD_DEDUCTION: dict[int, dict[FilingStatus, int]] = {
    2025: {
        FilingStatus.SINGLE: 5_706,
        FilingStatus.MARRIED_SEPARATELY: 5_706,
        FilingStatus.MARRIED_JOINTLY: 11_412,
        FilingStatus.HEAD_OF_HOUSEHOLD: 11_412,
        FilingStatus.QUALIFYING_WIDOW: 11_412,
    },
    2024: {
        FilingStatus.SINGLE: 5_540,
        FilingStatus.MARRIED_SEPARATELY: 5_540,
        FilingStatus.MARRIED_JOINTLY: 11_080,
        FilingStatus.HEAD_OF_HOUSEHOLD: 11_080,
        FilingStatus.QUALIFYING_WIDOW: 11_080,
    },
    2023: {
        FilingStatus.SINGLE: 5_363,
        FilingStatus.MARRIED_SEPARATELY: 5_363,
        FilingStatus.MARRIED_JOINTLY: 10_726,
        FilingStatus.HEAD_OF_HOUSEHOLD: 10_726,
        FilingStatus.QUALIFYING_WIDOW: 10_726,
    },
    2022: {
        FilingStatus.SINGLE: 5_202,
        FilingStatus.MARRIED_SEPARATELY: 5_202,
        FilingStatus.MARRIED_JOINTLY: 10_404,
        FilingStatus.HEAD_OF_HOUSEHOLD: 10_404,
        FilingStatus.QUALIFYING_WIDOW: 10_404,
    },
    2021: {
        FilingStatus.SINGLE: 4_803,
        FilingStatus.MARRIED_SEPARATELY: 4_803,
        FilingStatus.MARRIED_JOINTLY: 9_606,
        FilingStatus.HEAD_OF_HOUSEHOLD: 9_606,
        FilingStatus.QUALIFYING_WIDOW: 9_606,
    },
}


EXPECTED_EXEMPTION_CREDIT: dict[int, dict[FilingStatus, int]] = {
    2025: {
        FilingStatus.SINGLE: 153,
        FilingStatus.MARRIED_SEPARATELY: 153,
        FilingStatus.HEAD_OF_HOUSEHOLD: 153,
        FilingStatus.MARRIED_JOINTLY: 306,
        FilingStatus.QUALIFYING_WIDOW: 306,
    },
    2024: {
        FilingStatus.SINGLE: 149,
        FilingStatus.MARRIED_SEPARATELY: 149,
        FilingStatus.HEAD_OF_HOUSEHOLD: 149,
        FilingStatus.MARRIED_JOINTLY: 298,
        FilingStatus.QUALIFYING_WIDOW: 298,
    },
    2023: {
        FilingStatus.SINGLE: 144,
        FilingStatus.MARRIED_SEPARATELY: 144,
        FilingStatus.HEAD_OF_HOUSEHOLD: 144,
        FilingStatus.MARRIED_JOINTLY: 288,
        FilingStatus.QUALIFYING_WIDOW: 288,
    },
    2022: {
        FilingStatus.SINGLE: 140,
        FilingStatus.MARRIED_SEPARATELY: 140,
        FilingStatus.HEAD_OF_HOUSEHOLD: 140,
        FilingStatus.MARRIED_JOINTLY: 280,
        FilingStatus.QUALIFYING_WIDOW: 280,
    },
    2021: {
        FilingStatus.SINGLE: 129,
        FilingStatus.MARRIED_SEPARATELY: 129,
        FilingStatus.HEAD_OF_HOUSEHOLD: 129,
        FilingStatus.MARRIED_JOINTLY: 258,
        FilingStatus.QUALIFYING_WIDOW: 258,
    },
}


class StandardDeductionTests(unittest.TestCase):
    def test_all_years_all_filing_statuses(self):
        for year, expected_by_status in EXPECTED_STANDARD_DEDUCTION.items():
            for filing_status, expected in expected_by_status.items():
                with self.subTest(year=year, filing_status=filing_status):
                    self.assertEqual(
                        compute_standard_deduction(year=year, filing_status=filing_status),
                        expected,
                    )


class ExemptionCreditTests(unittest.TestCase):
    def test_all_years_all_filing_statuses(self):
        for year, expected_by_status in EXPECTED_EXEMPTION_CREDIT.items():
            for filing_status, expected in expected_by_status.items():
                with self.subTest(year=year, filing_status=filing_status):
                    self.assertEqual(
                        compute_exemption_credit(year=year, filing_status=filing_status),
                        expected,
                    )


class UnsupportedYearTests(unittest.TestCase):
    def test_year_not_in_supported_range_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            compute_standard_deduction(year=2020, filing_status=FilingStatus.SINGLE)
        self.assertIn("2020", str(ctx.exception))
        self.assertIn("2021-2025", str(ctx.exception))


# ---------------------------------------------------------------------------
# compute_ca_tax oracles
#
# Oracle 1 (TAX_TABLE_BOUNDARY_ANCHORS_2025): FTB Tax Table boundary anchors
#   for TY2025. Values are PRE-VERIFIED bin midpoint computations against the
#   TY2025 rate schedules extracted from the FTB 540 booklet. Source: FTB-
#   published 2025 Tax Table (TY2025 540 booklet), extracted by team-lead.
#   $50,000 maps to bin $49,951–$50,050 (regular 100-wide bin, midpoint
#   $50,000.5). $100,000 maps to the truncated last bin $99,951–$100,000
#   (midpoint $99,975.5).
#
# Oracle 2 (TRIVIAL_TAX_TABLE_BINS): Status/year-invariant zero-tax incomes
#   ($0, $1, $25, $50). Holds for all years 2021-2025 and all filing statuses.
#
# Oracle 3 (EXPECTED_CHRIS_PAT_MFJ_125K): FTB Personal Income Tax Booklet
#   "How to Figure Your Tax — Example: Chris and Pat Smith" (TY2021-TY2025),
#   MFJ, taxable income $125,000. Source: FTB-published rate-schedule worked
#   examples from each year's booklet.
#
# Oracle 4 (RATE_SCHEDULE_BOUNDARY_ANCHORS_2025): First dollar above the Tax
#   Table ($100,001) for TY2025 using Rate Schedule branch directly. Source:
#   hand-walked rate schedule by team-lead, verified independently by sp3.
# ---------------------------------------------------------------------------

# Oracle 1 — TY2025 Tax Table boundary anchors
# Format: (filing_status, taxable_income) -> expected tax
TAX_TABLE_BOUNDARY_ANCHORS_2025: dict[tuple[FilingStatus, int], int] = {
    # $50,000 — bin $49,951-$50,050 (regular 100-wide bin, midpoint $50,000.5)
    (FilingStatus.SINGLE,             50_000): 1_535,
    (FilingStatus.MARRIED_SEPARATELY, 50_000): 1_535,
    (FilingStatus.MARRIED_JOINTLY,    50_000):   778,
    (FilingStatus.QUALIFYING_WIDOW,   50_000):   778,
    (FilingStatus.HEAD_OF_HOUSEHOLD,  50_000):   778,
    # $100,000 — bin $99,951-$100,000 (TRUNCATED last bin, midpoint $99,975.5)
    (FilingStatus.SINGLE,            100_000): 5_736,
    (FilingStatus.MARRIED_SEPARATELY,100_000): 5_736,
    (FilingStatus.MARRIED_JOINTLY,   100_000): 3_068,
    (FilingStatus.QUALIFYING_WIDOW,  100_000): 3_068,
    (FilingStatus.HEAD_OF_HOUSEHOLD, 100_000): 3_708,
}

# Oracle 2 — trivial bins (status/year invariant)
# These hold for all years 2021-2025 and all filing statuses.
TRIVIAL_TAX_TABLE_BINS: list[int] = [0, 1, 25, 50]

# Oracle 3 — Chris+Pat MFJ $125k rate-schedule worked examples (FTB-published)
EXPECTED_CHRIS_PAT_MFJ_125K: dict[int, int] = {
    2025: 4_768,
    2024: 4_920,
    2023: 5_083,
    2022: 5_231,
    2021: 5_630,
}

# Oracle 4 — Rate Schedule branch boundary at $100,001 (TY2025, hand-walked)
RATE_SCHEDULE_BOUNDARY_ANCHORS_2025: dict[FilingStatus, int] = {
    # $100,001 — first dollar above the Tax Table; uses Rate Schedule branch
    FilingStatus.SINGLE:          5_739,
    FilingStatus.MARRIED_JOINTLY: 3_070,
}


class TaxTableBoundaryAnchors2025Tests(unittest.TestCase):
    """Oracle 1: TY2025 Tax Table boundary anchors at $50k and $100k."""

    def test_tax_table_boundary_anchors_2025(self):
        for (filing_status, taxable_income), expected in TAX_TABLE_BOUNDARY_ANCHORS_2025.items():
            with self.subTest(filing_status=filing_status, taxable_income=taxable_income):
                self.assertEqual(
                    compute_ca_tax(2025, filing_status, taxable_income),
                    expected,
                )


class TrivialTaxTableBinsTests(unittest.TestCase):
    """Oracle 2: Status/year-invariant zero-tax incomes."""

    def test_trivial_bins_all_years_all_statuses(self):
        all_statuses = list(FilingStatus)
        for year in range(2021, 2026):
            for status in all_statuses:
                for income in TRIVIAL_TAX_TABLE_BINS:
                    with self.subTest(year=year, status=status, income=income):
                        self.assertEqual(
                            compute_ca_tax(year, status, income),
                            0,
                        )


class ChrisPatMFJ125KTests(unittest.TestCase):
    """Oracle 3: FTB-published MFJ $125k rate-schedule worked examples."""

    def test_chris_pat_mfj_125k_all_years(self):
        for year, expected in EXPECTED_CHRIS_PAT_MFJ_125K.items():
            with self.subTest(year=year):
                self.assertEqual(
                    compute_ca_tax(year, FilingStatus.MARRIED_JOINTLY, 125_000),
                    expected,
                )


class RateScheduleBoundaryAnchors2025Tests(unittest.TestCase):
    """Oracle 4: Rate Schedule branch at $100,001 (TY2025)."""

    def test_rate_schedule_boundary_100001(self):
        for filing_status, expected in RATE_SCHEDULE_BOUNDARY_ANCHORS_2025.items():
            with self.subTest(filing_status=filing_status):
                self.assertEqual(
                    compute_ca_tax(2025, filing_status, 100_001),
                    expected,
                )


class ComputeCaTaxUnsupportedYearTests(unittest.TestCase):
    """Oracle 5: NotImplementedError contract for unsupported years."""

    def test_year_not_in_supported_range_raises_not_implemented(self):
        with self.assertRaises(NotImplementedError) as ctx:
            compute_ca_tax(year=2020, filing_status=FilingStatus.SINGLE, taxable_income=50_000)
        self.assertIn("2020", str(ctx.exception))
        self.assertIn("2021-2025", str(ctx.exception))
