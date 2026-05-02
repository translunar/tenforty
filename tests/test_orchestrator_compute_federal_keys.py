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


@needs_libreoffice
class ComputeFederalExposesSch1PartIPerLine(unittest.TestCase):
    """Part I per-line breakdown keys (lines 1, 3, 5, 6, 7).

    Line 4 (other gains) is covered separately in
    ComputeFederalExposesSch1Line4 because it lacks a named range and
    requires a SHEET_MAP entry rather than a named-range OUTPUTS entry.
    """

    def test_unemployment_appears_as_sch_1_line_7(self):
        scenario = make_simple_scenario()
        scenario.form1099_g = [
            Form1099G(payer="State", unemployment_compensation=5000.0),
        ]
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        self.assertEqual(results["sch_1_line_7_unemployment"], 5000)

    def test_part_i_lines_present_for_simple_scenario(self):
        """Even a no-Sch-1-income scenario should expose all Part I keys
        as zero — kernel auto-derive needs the keys to exist before it
        can read them."""
        scenario = make_simple_scenario()
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        for key in [
            "sch_1_line_1_taxable_refunds",
            "sch_1_line_3_business_income",
            "sch_1_line_5_rental_re_royalty",
            "sch_1_line_6_farm_income",
            "sch_1_line_7_unemployment",
        ]:
            self.assertIn(key, results, f"missing Part I key: {key}")
            self.assertEqual(
                results[key], 0,
                f"expected zero for {key} in simple W-2-only scenario",
            )


@needs_libreoffice
class ComputeFederalExposesSch1Line4(unittest.TestCase):
    """Line 4 (other gains) has no named range — direct cell ref via
    SHEET_MAP. The simple-scenario value is zero, but the key must be
    present so kernel auto-derive can read it."""

    def test_line_4_present_in_results(self):
        scenario = make_simple_scenario()
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        self.assertIn("sch_1_line_4_other_gains", results)
        self.assertEqual(results["sch_1_line_4_other_gains"], 0)
