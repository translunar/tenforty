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

from tenforty.forms.sch_1 import compute as sch_1_compute
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


@needs_libreoffice
class ComputeFederalExposesSch1PartIIPerLine(unittest.TestCase):
    """Part II per-line breakdown keys (lines 11, 13, 15, 17, 20, 21).

    A simple W-2 scenario doesn't drive any of these; we just assert
    the keys exist and are zero so kernel auto-derive can read them
    without KeyError guards.
    """

    def test_part_ii_lines_present_for_simple_scenario(self):
        scenario = make_simple_scenario()
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        for key in [
            "sch_1_line_11_educator",
            "sch_1_line_13_hsa",
            "sch_1_line_15_se_tax",
            "sch_1_line_17_se_health",
            "sch_1_line_20_ira",
            "sch_1_line_21_student_loan_interest",
        ]:
            self.assertIn(key, results, f"missing Part II key: {key}")
            self.assertEqual(
                results[key], 0,
                f"expected zero for {key} in simple W-2-only scenario",
            )

    def test_student_loan_interest_coerced_from_none_to_zero(self):
        """Line 21's named range points at a raw input cell that
        resolves to None (not 0) for an empty scenario. The rekey
        shim's _NUMERIC_SCH_1_KEYS coercion canonicalizes that to
        a numeric 0 so downstream kernel arithmetic doesn't TypeError.
        """
        scenario = make_simple_scenario()
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)
        self.assertEqual(results["sch_1_line_21_student_loan_interest"], 0)
        self.assertIsNotNone(results["sch_1_line_21_student_loan_interest"])


@needs_libreoffice
class XlsAgreesWithNativeSch1ForNonK1Scenario(unittest.TestCase):
    """Sanity: for a non-K-1 scenario, the XLS-sourced per-line keys in
    compute_federal results agree with what forms/sch_1.compute would
    produce reading the same merged result dict as upstream. This
    pins path (a) and the native compute as consistent for scenarios
    that don't trip the Sch E Part II blind spot.
    """

    def test_unemployment_scenario_xls_matches_native(self):
        scenario = make_simple_scenario()
        scenario.form1099_g = [
            Form1099G(payer="State", unemployment_compensation=4_200.0),
        ]
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=Path(tempfile.mkdtemp()),
        )
        results = orchestrator.compute_federal(scenario)

        # The native compute reads `sch_e_line_26_total` from upstream
        # to drive line 5; results carries `sche_line26` (oracle key)
        # but not the renamed sch_e_line_26_total. Build an upstream
        # snapshot mirroring what the orchestrator's _emit_pdfs_internal
        # synthesizes when it calls sch_1.compute (see orchestrator.py
        # ~line 413: `upstream={**upstream, "sch_e": sch_e_values}`).
        upstream = {
            "f1040": results,
            "sch_e": {
                "sch_e_line_26_total": results.get("sche_line26", 0),
            },
        }
        native = sch_1_compute(scenario, upstream)

        # Path-(a) XLS values must agree with native compute on every
        # per-line key the native module computes. Line 4 (other gains)
        # is intentionally excluded — native sch_1.compute hard-zeros it,
        # so any oracle non-zero would flag a divergence we don't yet
        # have native coverage for.
        for key in [
            "sch_1_line_1_taxable_refunds",
            "sch_1_line_3_business_income",
            "sch_1_line_5_rental_re_royalty",
            "sch_1_line_6_farm_income",
            "sch_1_line_7_unemployment",
            "sch_1_line_11_educator",
            "sch_1_line_13_hsa",
            "sch_1_line_15_se_tax",
            "sch_1_line_17_se_health",
            "sch_1_line_20_ira",
            "sch_1_line_21_student_loan_interest",
            "sch_1_line_10_total_additional_income",
            "sch_1_line_26_total_adjustments",
        ]:
            self.assertEqual(
                results[key],
                native[key],
                f"path-(a)/native disagreement on {key}",
            )
