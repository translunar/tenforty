"""Regression coverage: compute_federal exposes Schedule 1 per-line keys.

These keys are consumed downstream by the Sch CA kernel auto-derive
(sub-plan 3) so that California adjustments fire on the same line
breakdowns the IRS Sch 1 PDF carries. The values come from the XLS
oracle via the f1040 rekey shim; this test pins the contract that
those keys are present in the merged compute_federal result dict.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.models import Form1099G
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import (
    SPREADSHEETS_DIR,
    make_simple_scenario,
    needs_libreoffice,
)


@needs_libreoffice
class ComputeFederalExposesSch1LongFormTotals(unittest.TestCase):
    """Long-form aliases for the existing line 10 / line 26 totals."""

    def test_long_form_line_10_and_line_26_totals_appear(self):
        scenario = make_simple_scenario()
        scenario.form1099_g = [
            Form1099G(payer="State", unemployment_compensation=5000.0),
        ]
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        self.assertIn("sch_1_line_10_total_additional_income", results)
        self.assertIn("sch_1_line_26_total_adjustments", results)
        # The long-form values mirror the short-form aliases.
        self.assertEqual(
            results["sch_1_line_10_total_additional_income"],
            results["sch_1_line_10"],
        )
        self.assertEqual(
            results["sch_1_line_26_total_adjustments"],
            results["sch_1_line_26"],
        )
