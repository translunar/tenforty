"""Cross-check Schedule A native compute against the XLSX oracle.

The XLSX engine consumes state income tax via W2 state withholding and
mortgage/property tax via Form 1098 — so these scenarios populate both
the upstream inputs and a mirrored ItemizedDeductions so both compute
paths see the same totals. Charitable and medical are not flattened by
the XLSX input path in v1, so the oracle test confirms line 5e (SALT
capped) only — the OBBBA-sensitive field.
"""

import tempfile
import unittest
from pathlib import Path

import pytest

from tenforty.forms import sch_a as form_sch_a
from tenforty.models import FilingStatus, Form1098, ItemizedDeductions
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round

from tests.helpers import REPO_ROOT, needs_libreoffice, make_simple_scenario


@needs_libreoffice
class SchAOracleTests(unittest.TestCase):
    @pytest.mark.oracle
    def test_line_5e_matches_xlsx_below_cap(self):
        scenario = make_simple_scenario()
        scenario.config.filing_status = FilingStatus.SINGLE
        scenario.w2s[0].wages = 150_000.0
        scenario.w2s[0].medicare_wages = 150_000.0
        scenario.w2s[0].state_wages = 150_000.0
        scenario.w2s[0].state_tax_withheld = 8_000.0
        scenario.form1098s = [
            Form1098(lender="Bank", mortgage_interest=18_000.0, property_tax=6_000.0),
        ]
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=8_000,
            property_tax=6_000,
            mortgage_interest=18_000,
        )

        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(scenario)

        sch_a = form_sch_a.compute(scenario, upstream={"f1040": f1040})
        self.assertEqual(
            sch_a["sch_a_line_5e_salt_capped"],
            irs_round(f1040["sch_a_line_5e_salt_capped"]),
        )

    @pytest.mark.oracle
    def test_line_5e_at_40k_cap_matches_xlsx(self):
        scenario = make_simple_scenario()
        scenario.config.filing_status = FilingStatus.SINGLE
        scenario.w2s[0].wages = 200_000.0
        scenario.w2s[0].medicare_wages = 200_000.0
        scenario.w2s[0].state_wages = 200_000.0
        scenario.w2s[0].state_tax_withheld = 30_000.0
        scenario.form1098s = [
            Form1098(lender="Bank", mortgage_interest=0.0, property_tax=20_000.0),
        ]
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=30_000,
            property_tax=20_000,
        )

        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            f1040 = orch.compute_federal(scenario)

        sch_a = form_sch_a.compute(scenario, upstream={"f1040": f1040})
        self.assertEqual(sch_a["sch_a_line_5e_salt_capped"], 40_000)
        self.assertEqual(irs_round(f1040["sch_a_line_5e_salt_capped"]), 40_000)


if __name__ == "__main__":
    unittest.main()
