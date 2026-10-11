"""`depreciation_audit_unbuildable`: a return whose audit workbook cannot be
built does not emit.

Two triggers. The MIRROR MISMATCH: a formula cell, evaluated in Python over
the cells as written, differs from the engine's figure for that cell. And an
UNWRITABLE output file. Each has a firing proof and a twin that emits.

Two shapes that are NOT refusals, by ruling: a fully depreciated asset (it
renders with no rate), and a table the workbook has no rates for (there is
none: `EngineTableCoverageTests` enumerates every table the engine can read).
"""
import dataclasses
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import openpyxl

from tenforty.attestations import enforce_scoped_refusals
from tenforty.audit import depreciation_workbook as dw
from tenforty.forms.depreciation import macrs, resolver
from tenforty.models import (
    PERSONAL_PROPERTY_CLASSES, REAL_PROPERTY_CLASSES, DepreciableAsset,
)
from tests import _audit_workbook_fixtures as fx

# The engine takes the acknowledged prior as whole dollars (9,501), leaving
# 499 of the 10,000 basis; the workbook's formula reads the stated cell
# (10,000 - 9,500.50 = 499.50, which rounds to 500).
FRACTIONAL_PRIOR = dataclasses.replace(
    fx.APPLIANCE, prior_depreciation=9_500.5,
    acknowledges_prior_depreciation_as_stated=True)
WHOLE_PRIOR = dataclasses.replace(FRACTIONAL_PRIOR, prior_depreciation=9_500.0)


class UnbuildableRefusalTests(unittest.TestCase):
    def test_mirror_mismatch_fires(self):
        scenario = fx.scenario(rental_assets=(FRACTIONAL_PRIOR,))
        # The engine itself has a figure: only the workbook is the problem.
        self.assertEqual(resolver.audit_trail(scenario)[0].engine_amount, 499)
        with self.assertRaises(NotImplementedError) as caught:
            enforce_scoped_refusals(scenario, "emit")
        message = str(caught.exception)
        self.assertIn("depreciation audit workbook", message)
        self.assertIn("asset 'Appliance set' on rental property #0", message)
        self.assertIn("Assets!K2", message)
        self.assertIn("gives 500", message)
        self.assertIn("engine's figure is 499", message)
        self.assertIn("`prior_depreciation`", message)

    def test_whole_dollar_prior_twin_is_silent(self):
        scenario = fx.scenario(rental_assets=(WHOLE_PRIOR,))
        self.assertEqual(resolver.audit_trail(scenario)[0].engine_amount, 500)
        enforce_scoped_refusals(scenario, "emit")
        self.assertEqual(dw.unbuildable_reasons(scenario), [])

    def test_default_fixture_is_silent(self):
        enforce_scoped_refusals(fx.scenario(), "emit")
        self.assertEqual(dw.unbuildable_reasons(fx.scenario()), [])

    def test_stated_mode_return_is_silent(self):
        scenario = fx.scenario(rental_assets=(), rental_stated=4_000.0)
        enforce_scoped_refusals(scenario, "emit")
        self.assertEqual(dw.unbuildable_reasons(scenario), [])

    def test_prior_above_basis_is_silent(self):
        over = dataclasses.replace(WHOLE_PRIOR, prior_depreciation=10_500.0)
        enforce_scoped_refusals(fx.scenario(rental_assets=(over,)), "emit")

    def test_fully_depreciated_asset_is_silent(self):
        old = DepreciableAsset(
            description="Old computer", date_placed_in_service=date(2015, 4, 1),
            basis=3_000.0, recovery_class="5-year", prior_depreciation=3_000.0,
            no_bonus_or_section_179_history=True, convention="half-year")
        enforce_scoped_refusals(fx.scenario(rental_assets=(old,)), "emit")

    def test_each_mismatched_cell_is_named(self):
        scenario = fx.scenario(
            rental_assets=(fx.BUILDING, FRACTIONAL_PRIOR))
        reasons = dw.unbuildable_reasons(scenario)
        # The asset's own cell, and the activity total that sums it.
        self.assertEqual(len(reasons), 2)
        self.assertIn("Assets!K3", reasons[0])
        self.assertIn("Tie-outs!B2", reasons[1])
        self.assertNotIn("Rental building", reasons[0])


class WriterRefusalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "audit.xlsx"

    def test_write_refuses_an_unbuildable_trail(self):
        trail = resolver.audit_trail(
            fx.scenario(rental_assets=(FRACTIONAL_PRIOR,)))
        with self.assertRaisesRegex(NotImplementedError, r"Assets!K2"):
            dw.write_depreciation_audit(trail, dw.PrintedFigures(), self.out)
        self.assertFalse(self.out.exists())

    def test_write_emits_the_twin(self):
        trail = resolver.audit_trail(
            fx.scenario(rental_assets=(WHOLE_PRIOR,)))
        dw.write_depreciation_audit(trail, dw.PrintedFigures(), self.out)
        self.assertTrue(self.out.is_file())

    def test_unwritable_output_refuses(self):
        trail = resolver.audit_trail(fx.scenario())
        with mock.patch.object(
                openpyxl.Workbook, "save",
                side_effect=PermissionError("read-only directory")):
            with self.assertRaises(NotImplementedError) as caught:
                dw.write_depreciation_audit(
                    trail, dw.PrintedFigures(), self.out)
        message = str(caught.exception)
        self.assertIn("depreciation audit workbook", message)
        self.assertIn("audit.xlsx could not be written", message)
        self.assertIn("read-only directory", message)
        self.assertFalse(self.out.exists())

    def test_a_missing_directory_refuses(self):
        # The real thing, unpatched: openpyxl cannot open the path.
        trail = resolver.audit_trail(fx.scenario())
        missing = self.out.parent / "no_such_dir" / "audit.xlsx"
        with self.assertRaisesRegex(
                NotImplementedError, r"audit\.xlsx could not be written"):
            dw.write_depreciation_audit(trail, dw.PrintedFigures(), missing)

    def test_an_existing_file_is_overwritten(self):
        self.out.write_bytes(b"stale")
        dw.write_depreciation_audit(
            resolver.audit_trail(fx.scenario()), dw.PrintedFigures(), self.out)
        self.assertEqual(
            openpyxl.load_workbook(self.out).sheetnames[0], "Tie-outs")


class MirrorIsFailClosedTests(unittest.TestCase):
    """A formula the Python mirror cannot read is a refusal, never a cell
    it skips -- including the cells that have no engine figure to compare
    (differences, verdicts, running totals)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.out = Path(tmp.name) / "audit.xlsx"
        self.trail = resolver.audit_trail(fx.scenario())

    def test_unrecognized_function_in_a_verdict_cell_refuses(self):
        # The verdict column has no engine figure; it is still evaluated.
        with mock.patch.object(
                dw, "VERDICT_FORMULA", '=IFERROR(E{row},"PASS")'):
            with self.assertRaises(NotImplementedError) as caught:
                dw.write_depreciation_audit(
                    self.trail, dw.PrintedFigures(), self.out)
        message = str(caught.exception)
        self.assertIn("Tie-outs!F2", message)
        self.assertIn("unsupported function IFERROR", message)
        self.assertFalse(self.out.exists())

    def test_unreadable_text_in_a_verdict_cell_refuses(self):
        with mock.patch.object(dw, "VERDICT_FORMULA", "=E{row}^2"):
            with self.assertRaisesRegex(
                    NotImplementedError, r"Tie-outs!F2.*cannot read formula"):
                dw.write_depreciation_audit(
                    self.trail, dw.PrintedFigures(), self.out)
        self.assertFalse(self.out.exists())

    def test_the_predicate_reports_it_before_any_form_is_prepared(self):
        with mock.patch.object(
                dw, "VERDICT_FORMULA", '=IFERROR(E{row},"PASS")'):
            reasons = dw.unbuildable_reasons(fx.scenario())
            with self.assertRaisesRegex(NotImplementedError, "IFERROR"):
                enforce_scoped_refusals(fx.scenario(), "emit")
        self.assertEqual(len(reasons), 1)
        self.assertIn("Tie-outs!F2", reasons[0])

    def test_every_formula_cell_is_evaluated(self):
        # The mirror walks the workbook, not a list of expected cells: its
        # count is the count of formula cells on the sheets.
        workbook, reasons = dw._build(self.trail, dw.PrintedFigures())
        on_sheets = sum(
            1 for sheet in workbook.worksheets for row in sheet.iter_rows()
            for cell in row if cell.data_type == "f")
        self.assertEqual(reasons, [])
        # Assets 3 x (H, K, L); Year-by-year 11 x (A, E, F); Tie-outs one
        # activity row x (B, E, F).
        self.assertEqual(on_sheets, 9 + 33 + 3)
        self.assertEqual(len(dw.formula_cells(workbook)), on_sheets)


class EngineTableCoverageTests(unittest.TestCase):
    """Every Pub 946 table the engine can read is one the workbook renders.
    (An engine table added without workbook support fails here.)"""

    def test_every_engine_table_has_a_grid(self):
        seen = set()
        for cls in REAL_PROPERTY_CLASSES:
            asset = DepreciableAsset(
                description="Probe", date_placed_in_service=date(2020, 6, 1),
                basis=1.0, recovery_class=cls)
            seen.add(macrs.table_identity(
                asset, return_year=2025, mid_quarter=False))
        for cls in PERSONAL_PROPERTY_CLASSES:
            stated = [("half-year", None)] + [
                ("mid-quarter", q) for q in (1, 2, 3, 4)]
            for convention, quarter in stated:
                month = 6 if quarter is None else quarter * 3 - 1
                asset = DepreciableAsset(
                    description="Probe",
                    date_placed_in_service=date(2020, month, 1), basis=1.0,
                    recovery_class=cls, convention=convention,
                    quarter=quarter)
                seen.add(macrs.table_identity(
                    asset, return_year=2025, mid_quarter=False))
            # Placed in the return year: computed, under either 40% answer.
            for mid_quarter in (False, True):
                for month in (2, 5, 8, 11):
                    asset = DepreciableAsset(
                        description="Probe",
                        date_placed_in_service=date(2025, month, 1),
                        basis=1.0, recovery_class=cls)
                    seen.add(macrs.table_identity(
                        asset, return_year=2025, mid_quarter=mid_quarter))
        self.assertEqual(
            seen, {"A-1", "A-2", "A-3", "A-4", "A-5", "A-6", "A-7a"})
        self.assertEqual(seen - dw.GRID_TABLES, set())
        self.assertEqual(dw.GRID_TABLES, seen)


if __name__ == "__main__":
    unittest.main()
