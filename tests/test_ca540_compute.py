import unittest

from tenforty.models import FilingStatus
from tenforty.forms.f540 import (
    compute_standard_deduction,
    compute_exemption_credit,
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
