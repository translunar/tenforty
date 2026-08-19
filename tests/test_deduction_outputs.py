"""E2E tests for deduction outputs that require a fixture not already
exercised by other E2E tests. Single and itemized scenarios have their
deduction assertions folded into test_e2e_simple_w2.py and
test_e2e_itemized.py respectively to avoid redundant LibreOffice recalcs."""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.models import TaxReturnConfig
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import FIXTURES_DIR, SPREADSHEETS_DIR, needs_libreoffice
from tests.invariants import assert_4868_fills_correctly


@pytest.mark.xfail(strict=True, reason=(
    "MFJ Deduction-diagnostic refusal fires in setUpClass, before either "
    "assertion runs; spouse-birthdate unit restores reachability"))
@needs_libreoffice
class TestStandardDeductionMFJ(unittest.TestCase):
    """Core fix for issue #2: MFJ standard deduction must be $31,500
    (OBBBA). With the old SD_Single mapping this returned $15,750 —
    wrong by $15,750 for any MFJ filer.

    UNREACHABLE AS OF THE Deduction-DIAGNOSTIC HARVEST, and marked
    ``xfail(strict=True)`` at CLASS level because the refusal lands in
    ``setUpClass``, not in either test body — pytest applies an xfail marker to
    a setup-phase error, so both methods report XFAIL rather than ERROR.

    WHY: this fixture is MARRIED_JOINTLY, so the workbook's ``Birthday_Needed``
    flag is unconditionally TRUE (tenforty has no spouse-birthdate input), the
    ``Deduction`` named range holds "Birthdate(s) needed.", and
    ``f1040.compute`` now refuses instead of harvesting a blanked line 16.
    ``compute_federal`` therefore raises before ``cls._results`` exists.

    NOTE THE COVERAGE THIS COSTS, because it is not nothing and it is not
    obvious: ``standard_deduction`` maps to the ``Standard`` named range, which
    is NOT ``Birthday_Needed``-gated and was still computing $31,500 correctly.
    It is ``Deductions`` (plural — the line-12 APPLIED amount) that the sheet
    zeroes. So the assertion below was passing on its own merits and is being
    parked for an unrelated reason. Strict xfail is what gets it back: when the
    spouse-birthdate unit lands these XPASS, strict-xfail converts that into a
    suite FAILURE, and the marker must be removed. A skip would rot silently.
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

    def test_4868_fills_correctly(self):
        """4868 lines 4/5/6/7 match engine results for MFJ; reuses cached _results."""
        cfg = TaxReturnConfig(
            year=self._scenario.config.year,
            filing_status=self._scenario.config.filing_status,
            birthdate=self._scenario.config.birthdate,
            state=self._scenario.config.state,
            dependents=self._scenario.config.dependents,
            first_name="Alice",
            last_name="Example",
            ssn="000-00-0001",
            spouse_first_name="Bob",
            spouse_last_name="Example",
            spouse_ssn="000-00-0002",
            address="123 Example St",
            address_city="Anywhere",
            address_state="CA",
            address_zip="00000",
        )
        tmp_dir = Path(tempfile.mkdtemp())
        assert_4868_fills_correctly(self, self._results, cfg, tmp_dir)


if __name__ == "__main__":
    unittest.main()
