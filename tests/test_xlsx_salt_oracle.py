"""XLSX oracle sanity check: the reference workbook implements OBBBA SALT.

Verifies that spreadsheets/federal/2025/1040.xlsx Sch. A encodes the
OBBBA §164(b)(6) cap structure (TY2025-2029):

  - Starting caps: $40,000 single/MFJ/HoH (P17), $20,000 MFS (P16)
  - Phaseout: threshold $500,000 MAGI (T21), rate 30% (T18)
  - Floors: $10,000 single/MFJ/HoH (T16), $5,000 MFS (T15)

Matches the constants in tenforty.constants.y2025. Without this check,
a later Sch A oracle diff could be silently wrong on both sides.
"""

import unittest
from pathlib import Path

import pytest
from openpyxl import load_workbook

from tenforty.constants import y2025
from tenforty.models import FilingStatus


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKBOOK_PATH = REPO_ROOT / "spreadsheets" / "federal" / "2025" / "1040.xlsx"


@pytest.mark.oracle
class XlsxSaltOracleTests(unittest.TestCase):
    """Cell-level check; does not require LibreOffice (fast)."""

    @classmethod
    def setUpClass(cls):
        cls.wb = load_workbook(WORKBOOK_PATH, data_only=False)
        cls.sch_a = cls.wb["Sch. A"]

    def test_salt_deduct_limit_named_range_resolves_to_p22(self):
        dn = self.wb.defined_names.get("SALT_Deduct_Limit")
        self.assertIsNotNone(dn, "SALT_Deduct_Limit named range missing")
        destinations = list(dn.destinations)
        self.assertEqual(destinations, [("Sch. A", "$P$22")])

    def test_starting_caps_match_constants(self):
        # P17: single/MFJ/HoH starting cap; P16: MFS starting cap.
        self.assertEqual(
            self.sch_a["P17"].value,
            y2025.SALT_CAP_STARTING[FilingStatus.SINGLE],
        )
        self.assertEqual(
            self.sch_a["P16"].value,
            y2025.SALT_CAP_STARTING[FilingStatus.MARRIED_SEPARATELY],
        )

    def test_floors_match_constants(self):
        # T16: single/MFJ/HoH floor; T15: MFS floor.
        self.assertEqual(
            self.sch_a["T16"].value,
            y2025.SALT_CAP_FLOOR[FilingStatus.SINGLE],
        )
        self.assertEqual(
            self.sch_a["T15"].value,
            y2025.SALT_CAP_FLOOR[FilingStatus.MARRIED_SEPARATELY],
        )

    def test_phaseout_threshold_and_rate_match_constants(self):
        self.assertEqual(self.sch_a["T21"].value, y2025.SALT_PHASEOUT_THRESHOLD)
        self.assertEqual(self.sch_a["T18"].value, y2025.SALT_PHASEOUT_RATE)

    def test_p22_formula_is_obbba_shaped(self):
        # Sanity-check the formula structure so a silent revert of the OBBBA
        # math in the workbook (e.g., someone hard-codes P22 back to 10000)
        # is caught here instead of downstream in Sch A compute.
        formula = self.sch_a["P22"].value
        self.assertTrue(
            formula.startswith("=IF(AND(File_Marr_Sep"),
            f"P22 no longer looks OBBBA-shaped: {formula!r}",
        )
        self.assertIn("ModAdjGrossInc", formula)
        self.assertIn("$T$21", formula)  # phaseout threshold
        self.assertIn("$T$18", formula)  # phaseout rate


if __name__ == "__main__":
    unittest.main()
