"""Year-parameter constants for tax year 2025."""

import unittest

from tenforty.constants import y2025
from tenforty.models import FilingStatus


class StandardDeductionTests(unittest.TestCase):
    def test_all_filing_statuses_present(self):
        sd = y2025.STANDARD_DEDUCTION
        self.assertEqual(sd[FilingStatus.SINGLE], 15_000)
        self.assertEqual(sd[FilingStatus.MARRIED_JOINTLY], 30_000)
        self.assertEqual(sd[FilingStatus.MARRIED_SEPARATELY], 15_000)
        self.assertEqual(sd[FilingStatus.HEAD_OF_HOUSEHOLD], 22_500)
        self.assertEqual(sd[FilingStatus.QUALIFYING_WIDOW], 30_000)


class MedicalAgiFloorTests(unittest.TestCase):
    def test_is_7_5_percent(self):
        self.assertEqual(y2025.MEDICAL_AGI_FLOOR_PCT, 0.075)


class SaltCapObbbaTests(unittest.TestCase):
    def test_starting_values(self):
        """OBBBA (enacted July 2025) raised SALT cap for TY2025-2029.

        Single/MFJ/HoH start at $40,000; MFS starts at $20,000.
        """
        starting = y2025.SALT_CAP_STARTING
        self.assertEqual(starting[FilingStatus.SINGLE], 40_000)
        self.assertEqual(starting[FilingStatus.MARRIED_JOINTLY], 40_000)
        self.assertEqual(starting[FilingStatus.HEAD_OF_HOUSEHOLD], 40_000)
        self.assertEqual(starting[FilingStatus.MARRIED_SEPARATELY], 20_000)

    def test_floor_values(self):
        """Phaseout reduces back toward the pre-OBBBA cap floor."""
        floor = y2025.SALT_CAP_FLOOR
        self.assertEqual(floor[FilingStatus.SINGLE], 10_000)
        self.assertEqual(floor[FilingStatus.MARRIED_JOINTLY], 10_000)
        self.assertEqual(floor[FilingStatus.HEAD_OF_HOUSEHOLD], 10_000)
        self.assertEqual(floor[FilingStatus.MARRIED_SEPARATELY], 5_000)

    def test_phaseout_threshold_and_rate(self):
        self.assertEqual(y2025.SALT_PHASEOUT_THRESHOLD, 500_000)
        self.assertEqual(y2025.SALT_PHASEOUT_RATE, 0.30)


if __name__ == "__main__":
    unittest.main()
