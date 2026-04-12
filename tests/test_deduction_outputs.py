"""E2E tests for deduction outputs that require a fixture not already
exercised by other E2E tests. Single and itemized scenarios have their
deduction assertions folded into test_e2e_simple_w2.py and
test_e2e_itemized.py respectively to avoid redundant LibreOffice recalcs."""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR, needs_libreoffice


@needs_libreoffice
class TestStandardDeductionMFJ(unittest.TestCase):
    """Core fix for issue #2: MFJ standard deduction must be $31,500
    (OBBBA). With the old SD_Single mapping this returned $15,750 —
    wrong by $15,750 for any MFJ filer.
    """

    @classmethod
    def setUpClass(cls):
        cls._work_dir = Path(tempfile.mkdtemp())
        cls._scenario = load_scenario(FIXTURES_DIR / "mfj_simple.yaml")
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=cls._work_dir,
        )
        cls._results = orchestrator.compute_federal(cls._scenario)

    def test_standard_deduction_is_31500(self):
        self.assertEqual(
            int(self._results["standard_deduction"]), 31500,
            "2025 MFJ standard deduction should be $31,500 (OBBBA). "
            "If this test fails, the standard_deduction -> Standard "
            "mapping is not applied or the XLS's Standard cell is "
            "computing the wrong value for the MFJ filing status.",
        )


if __name__ == "__main__":
    unittest.main()
