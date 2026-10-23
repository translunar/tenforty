"""Catalog #10 / ruling R-S8-11, oracle tier: production's 2022 workbook
path, BOTH sides in one run.

* Without the restored Q4 answer (write suppressed), a 2022 return whose
  taxable interest exceeds the investment limit prints the table credit:
  Q4 unanswered starves E48:E50, so the sheet never declares "no credit".
* With it, the same return REFUSES (R-S7-10, exact prefix): Q4 answered,
  the interest counts, the Step 2 gate fires, H64 answers Form 4797 "No",
  NoEICredit turns TRUE beside a positive line 27.
* A credited 2022 row (no investment income) prints the same credit either
  way: the restored answer changes nothing else.

The limit is read from the 2022 template (N57); nothing is typed in. All
identities synthetic.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import openpyxl

from tenforty.mappings import f1040 as f1040_mapping
from tenforty.models import FilingStatus, Form1099INT
from tenforty.orchestrator import ReturnOrchestrator, WorkbookEicInconsistent
from tests.fixtures import eic_battery
from tests.helpers import SPREADSHEETS_DIR, needs_libreoffice

YEAR = 2022
STATUSES = (FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY)
REFUSAL = "workbook_eic_inconsistent: "


def _limit() -> int:
    return openpyxl.load_workbook(
        SPREADSHEETS_DIR / "federal" / str(YEAR) / "1040.xlsx",
        read_only=True)["Line 27 (EIC)"]["N57"].value


def _investment_row(status, limit):
    """Low wages beside taxable interest one dollar over the limit."""
    scenario = eic_battery._eic_row(YEAR, 2000.0, status=status.value)
    scenario.form1099_int = [Form1099INT(payer="Example Bank",
                                         interest=float(limit + 1))]
    return scenario


def _credited_row(status):
    return eic_battery._eic_row(YEAR, 9000.0, status=status.value)


def _n(value) -> int:
    return int(round(value or 0))


@needs_libreoffice
class Q4AnswerOnThe2022WorkbookPathTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        limit = _limit()
        cls.unfixed, cls.fixed, cls.refusals = {}, {}, {}
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for status in STATUSES:
                for kind, scenario in (
                        ("investment", _investment_row(status, limit)),
                        ("credited", _credited_row(status))):
                    eff, _ = orch._build_effective_scenario(scenario)
                    key = (status.value, kind)
                    with mock.patch.dict(f1040_mapping.EIC_Q4_NO_CELL,
                                         clear=True):
                        cls.unfixed[key] = orch._compute_1040_via_workbook(
                            eff)
                    try:
                        cls.fixed[key] = orch._compute_1040_via_workbook(eff)
                    except WorkbookEicInconsistent as refusal:
                        cls.refusals[key] = str(refusal)

    def test_without_the_answer_the_table_credit_prints(self):
        for status in STATUSES:
            with self.subTest(status=status.value):
                self.assertGreater(
                    _n(self.unfixed[(status.value, "investment")].get("eic")),
                    0)

    def test_with_the_answer_the_return_refuses(self):
        for status in STATUSES:
            with self.subTest(status=status.value):
                self.assertTrue(self.refusals.get(
                    (status.value, "investment"), "").startswith(REFUSAL),
                    self.refusals.get((status.value, "investment")))

    def test_a_credited_row_is_unchanged(self):
        for status in STATUSES:
            key = (status.value, "credited")
            with self.subTest(status=status.value):
                self.assertNotIn(key, self.refusals)
                expected = _n(self.unfixed[key].get("eic"))
                self.assertGreater(expected, 0)
                self.assertEqual(_n(self.fixed[key].get("eic")), expected)
