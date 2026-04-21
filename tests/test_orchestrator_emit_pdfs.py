"""Tests for ReturnOrchestrator.emit_pdfs."""

import tempfile
import unittest
from pathlib import Path

import pypdf

from datetime import date

from tenforty.models import (
    DepreciableAsset, FilingStatus, Form1099B, Form1099DIV, Form1099INT,
    ItemizedDeductions, RentalProperty, Scenario, TaxReturnConfig, W2,
)
from tenforty.orchestrator import ReturnOrchestrator


REPO_ROOT = Path(__file__).parent.parent
F4868_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f4868.pdf"
SCH_B_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040sb.pdf"
SCH_D_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040sd.pdf"
SCH_E_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040se.pdf"
SCH_1_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040s1.pdf"
SCH_A_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040sa.pdf"
F8959_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f8959.pdf"


def make_scenario_with_identity() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1990-01-01",
            state="TX",
            first_name="Sam",
            last_name="Doe",
            ssn="000-11-2222",
            address="789 Elm St",
            address_city="Houston",
            address_state="TX",
            address_zip="77001",
            has_foreign_accounts=False,
            acknowledges_no_wash_sale_adjustments=False,
            acknowledges_no_other_basis_adjustments=False,
            acknowledges_no_28_rate_gain=False,
            acknowledges_no_unrecaptured_section_1250=False,
        ),
    )


SAMPLE_RESULTS = {
    "total_tax": 15000,
    "total_payments": 12000,
    "wages": 90000,
}


class TestEmitPdfs(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
    def test_4868_pdf_emitted(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(scenario, SAMPLE_RESULTS, self.output_dir)
        self.assertIn("4868", emitted)
        path = emitted["4868"]
        self.assertTrue(path.exists(), f"Expected {path} to exist")
        self.assertGreater(path.stat().st_size, 0)

    @unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
    def test_4868_output_filename(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(scenario, SAMPLE_RESULTS, self.output_dir)
        self.assertEqual(emitted["4868"].name, "f4868_2025.pdf")

    @unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
    def test_output_dir_created_if_missing(self):
        nested = self.output_dir / "nested" / "subdir"
        scenario = make_scenario_with_identity()
        self.orchestrator.emit_pdfs(scenario, SAMPLE_RESULTS, nested)
        self.assertTrue(nested.exists())

    @unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
    def test_4868_fields_written(self):
        """Check that key fields were written into the filled PDF."""
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(scenario, SAMPLE_RESULTS, self.output_dir)
        reader = pypdf.PdfReader(str(emitted["4868"]))
        fields = reader.get_fields() or {}

        # Collect all field values into a flat dict keyed by field name
        field_values = {name: (field.get("/V") or "") for name, field in fields.items()}

        # Line 4 — estimated_total_tax (total_tax = 15000)
        estimated_tax_field = "topmostSubform[0].Page1[0].f1_11[0]"
        self.assertEqual(field_values.get(estimated_tax_field), "15000")

        # Line 6 — balance_due = max(0, 15000 - 12000) = 3000
        balance_due_field = "topmostSubform[0].Page1[0].f1_13[0]"
        self.assertEqual(field_values.get(balance_due_field), "3000")

    def test_emit_pdfs_emits_both_forms(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(scenario, SAMPLE_RESULTS, self.output_dir)
        self.assertIn("1040", emitted)
        self.assertIn("4868", emitted)
        self.assertTrue(emitted["1040"].exists())
        self.assertTrue(emitted["4868"].exists())


class EmitPdfsSchBTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(SCH_B_TEMPLATE.exists(), "f1040sb.pdf template not found")
    def test_emits_sch_b_when_interest_over_threshold(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_int = [Form1099INT(payer="Bank", interest=2000.0)]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("sch_b", emitted)
        self.assertEqual(emitted["sch_b"].name, "f1040sb_2025.pdf")
        self.assertTrue(emitted["sch_b"].exists())
        self.assertGreater(emitted["sch_b"].stat().st_size, 0)

    @unittest.skipUnless(SCH_B_TEMPLATE.exists(), "f1040sb.pdf template not found")
    def test_emits_sch_b_when_dividends_over_threshold(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_div = [
            Form1099DIV(payer="Broker", ordinary_dividends=1600.0),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("sch_b", emitted)

    def test_omits_sch_b_when_under_threshold(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_int = [Form1099INT(payer="Bank", interest=100.0)]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("sch_b", emitted)

    @unittest.skipUnless(SCH_B_TEMPLATE.exists(), "f1040sb.pdf template not found")
    def test_emitted_sch_b_has_payer_rows_filled(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_int = [
            Form1099INT(payer="Bank A", interest=900.0),
            Form1099INT(payer="Bank B", interest=800.0),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["sch_b"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        # Row 1 payer is inside Line1_ReadOrder; amount is at Page1 scope.
        row1_payer = "topmostSubform[0].Page1[0].Line1_ReadOrder[0].f1_03[0]"
        row1_amount = "topmostSubform[0].Page1[0].f1_04[0]"
        row2_payer = "topmostSubform[0].Page1[0].f1_05[0]"
        total_interest = "topmostSubform[0].Page1[0].f1_31[0]"
        self.assertEqual(field_values.get(row1_payer), "Bank A")
        self.assertEqual(field_values.get(row1_amount), "900")
        self.assertEqual(field_values.get(row2_payer), "Bank B")
        self.assertEqual(field_values.get(total_interest), "1700")


def _lot(**overrides) -> Form1099B:
    defaults = dict(
        broker="Schwab",
        description="100 ACME",
        date_acquired="2024-01-01",
        date_sold="2025-06-01",
        proceeds=1500.0,
        cost_basis=1000.0,
        short_term=True,
        basis_reported_to_irs=True,
    )
    defaults.update(overrides)
    return Form1099B(**defaults)


class EmitPdfsSchDTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(SCH_D_TEMPLATE.exists(), "f1040sd.pdf template not found")
    def test_emits_sch_d_when_1099b_present(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_b = [_lot()]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("sch_d", emitted)
        self.assertEqual(emitted["sch_d"].name, "f1040sd_2025.pdf")
        self.assertTrue(emitted["sch_d"].exists())
        self.assertGreater(emitted["sch_d"].stat().st_size, 0)

    def test_omits_sch_d_when_no_1099b(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("sch_d", emitted)

    @unittest.skipUnless(SCH_D_TEMPLATE.exists(), "f1040sd.pdf template not found")
    def test_emitted_sch_d_has_summary_totals(self):
        scenario = make_scenario_with_identity()
        scenario.form1099_b = [
            _lot(short_term=True, proceeds=1500.0, cost_basis=1000.0),
            _lot(short_term=False, proceeds=5000.0, cost_basis=2000.0),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["sch_d"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        line_1a_gain = "topmostSubform[0].Page1[0].Table_PartI[0].Row1a[0].f1_6[0]"
        line_8a_gain = "topmostSubform[0].Page1[0].Table_PartII[0].Row8a[0].f1_26[0]"
        line_16_total = "topmostSubform[0].Page2[0].f2_1[0]"
        self.assertEqual(field_values.get(line_1a_gain), "500")
        self.assertEqual(field_values.get(line_8a_gain), "3000")
        self.assertEqual(field_values.get(line_16_total), "3500")


class EmitPdfsSchETests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(SCH_E_TEMPLATE.exists(), "f1040se.pdf template not found")
    def test_emits_sch_e_when_rental_property_present(self):
        scenario = make_scenario_with_identity()
        scenario.rental_properties = [
            RentalProperty(
                address="123 Main St",
                property_type=1,
                fair_rental_days=365,
                personal_use_days=0,
                rents_received=24000.0,
                mortgage_interest=8000.0,
                taxes=3000.0,
                depreciation=5000.0,
            ),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("sch_e", emitted)
        self.assertEqual(emitted["sch_e"].name, "f1040se_2025.pdf")
        self.assertTrue(emitted["sch_e"].exists())
        self.assertGreater(emitted["sch_e"].stat().st_size, 0)

    def test_omits_sch_e_when_no_rental(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("sch_e", emitted)

    @unittest.skipUnless(SCH_E_TEMPLATE.exists(), "f1040se.pdf template not found")
    def test_emitted_sch_e_fills_property_a_fields(self):
        scenario = make_scenario_with_identity()
        scenario.rental_properties = [
            RentalProperty(
                address="456 Oak Ln",
                property_type=2,
                fair_rental_days=300,
                personal_use_days=30,
                rents_received=18000.0,
                mortgage_interest=6000.0,
                taxes=2000.0,
            ),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["sch_e"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        addr = "topmostSubform[0].Page1[0].Table_Line1a[0].RowA[0].f1_3[0]"
        type_code = "topmostSubform[0].Page1[0].Table_Line1b[0].RowA[0].f1_6[0]"
        rents = "topmostSubform[0].Page1[0].Table_Income[0].Line3[0].f1_16[0]"
        total_exp = "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_68[0]"
        income = "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_71[0]"
        self.assertEqual(field_values.get(addr), "456 Oak Ln")
        self.assertEqual(field_values.get(type_code), "2")
        self.assertEqual(field_values.get(rents), "18000")
        self.assertEqual(field_values.get(total_exp), "8000")
        self.assertEqual(field_values.get(income), "10000")


class EmitPdfsSch1Tests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(SCH_1_TEMPLATE.exists(), "f1040s1.pdf template not found")
    def test_emits_sch_1_when_rental_income_present(self):
        scenario = make_scenario_with_identity()
        scenario.rental_properties = [
            RentalProperty(
                address="123 Main St", property_type=1,
                fair_rental_days=365, personal_use_days=0,
                rents_received=24000.0, mortgage_interest=8000.0,
                taxes=3000.0, depreciation=5000.0,
            ),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("sch_1", emitted)
        self.assertEqual(emitted["sch_1"].name, "f1040s1_2025.pdf")
        self.assertTrue(emitted["sch_1"].exists())
        self.assertGreater(emitted["sch_1"].stat().st_size, 0)

    def test_omits_sch_1_when_no_additional_income(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("sch_1", emitted)

    @unittest.skipUnless(SCH_1_TEMPLATE.exists(), "f1040s1.pdf template not found")
    def test_emitted_sch_1_fills_line_5_and_line_10(self):
        scenario = make_scenario_with_identity()
        scenario.rental_properties = [
            RentalProperty(
                address="123 Main St", property_type=1,
                fair_rental_days=365, personal_use_days=0,
                rents_received=24000.0, mortgage_interest=8000.0,
                taxes=3000.0, depreciation=5000.0,
            ),
        ]
        results = {**SAMPLE_RESULTS, "sche_line26": 8000}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["sch_1"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        line_5 = "topmostSubform[0].Page1[0].f1_09[0]"
        line_10 = "topmostSubform[0].Page1[0].f1_37[0]"
        self.assertEqual(field_values.get(line_5), "8000")
        self.assertEqual(field_values.get(line_10), "8000")


class EmitPdfsSchATests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(SCH_A_TEMPLATE.exists(), "f1040sa.pdf template not found")
    def test_emits_sch_a_when_itemizing_beats_standard(self):
        scenario = make_scenario_with_identity()
        scenario.config.state = "CA"
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=8_000, property_tax=6_000,
            mortgage_interest=18_000, charitable_contributions=3_000,
        )
        results = {**SAMPLE_RESULTS, "agi": 150_000, "magi": 150_000}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        self.assertIn("sch_a", emitted)
        self.assertEqual(emitted["sch_a"].name, "f1040sa_2025.pdf")
        self.assertTrue(emitted["sch_a"].exists())
        self.assertGreater(emitted["sch_a"].stat().st_size, 0)

    def test_omits_sch_a_when_no_itemized_deductions(self):
        scenario = make_scenario_with_identity()
        results = {**SAMPLE_RESULTS, "agi": 150_000, "magi": 150_000}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        self.assertNotIn("sch_a", emitted)

    def test_omits_sch_a_when_under_standard_deduction(self):
        scenario = make_scenario_with_identity()
        scenario.config.state = "CA"
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=2_000, property_tax=1_000,
        )
        results = {**SAMPLE_RESULTS, "agi": 150_000, "magi": 150_000}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        self.assertNotIn("sch_a", emitted)

    @unittest.skipUnless(SCH_A_TEMPLATE.exists(), "f1040sa.pdf template not found")
    def test_emitted_sch_a_fills_salt_and_total(self):
        scenario = make_scenario_with_identity()
        scenario.config.state = "CA"
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=8_000, property_tax=6_000,
            mortgage_interest=18_000, charitable_contributions=3_000,
        )
        results = {**SAMPLE_RESULTS, "agi": 150_000, "magi": 150_000}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["sch_a"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        line_5e = "form1[0].Page1[0].f1_11[0]"
        line_17 = "form1[0].Page1[0].f1_30[0]"
        line_8a = "form1[0].Page1[0].f1_15[0]"
        # 8k + 6k = 14k SALT, well under cap
        self.assertEqual(field_values.get(line_5e), "14000")
        # 14k SALT + 18k mortgage + 3k charity = 35k (medical 0 at 150k AGI)
        self.assertEqual(field_values.get(line_17), "35000")
        self.assertEqual(field_values.get(line_8a), "18000")


def _w2_over_threshold(medicare_wages: float) -> W2:
    return W2(
        employer="Acme", wages=medicare_wages, federal_tax_withheld=0,
        ss_wages=168_600, ss_tax_withheld=0,
        medicare_wages=medicare_wages,
        medicare_tax_withheld=round(medicare_wages * 0.0145),
    )


class EmitPdfs8959Tests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        self.output_dir = Path(self._tmpdir)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    @unittest.skipUnless(F8959_TEMPLATE.exists(), "f8959.pdf template not found")
    def test_emits_8959_when_wages_over_threshold(self):
        scenario = make_scenario_with_identity()
        scenario.w2s = [_w2_over_threshold(300_000)]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("8959", emitted)
        self.assertEqual(emitted["8959"].name, "f8959_2025.pdf")
        self.assertTrue(emitted["8959"].exists())

    def test_omits_8959_when_wages_under_threshold(self):
        scenario = make_scenario_with_identity()
        scenario.w2s = [_w2_over_threshold(150_000)]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("8959", emitted)

    def test_omits_8959_when_oracle_says_not_required(self):
        scenario = make_scenario_with_identity()
        scenario.w2s = [_w2_over_threshold(300_000)]
        results = {**SAMPLE_RESULTS, "f8959_required": False}
        emitted = self.orchestrator.emit_pdfs(
            scenario, results, self.output_dir,
        )
        self.assertNotIn("8959", emitted)

    @unittest.skipUnless(F8959_TEMPLATE.exists(), "f8959.pdf template not found")
    def test_emitted_8959_fills_key_totals(self):
        scenario = make_scenario_with_identity()
        scenario.w2s = [_w2_over_threshold(300_000)]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        reader = pypdf.PdfReader(str(emitted["8959"]))
        field_values = {
            name: (f.get("/V") or "")
            for name, f in (reader.get_fields() or {}).items()
        }
        line_1 = "topmostSubform[0].Page1[0].f1_3[0]"   # line 1: Medicare wages
        line_18 = "topmostSubform[0].Page1[0].f1_20[0]"  # line 18: total
        name_field = "topmostSubform[0].Page1[0].f1_1[0]"
        self.assertEqual(field_values.get(name_field), "Sam Doe")
        self.assertEqual(field_values.get(line_1), "300000")
        self.assertEqual(field_values.get(line_18), "900")

    def test_emits_4562_when_depreciable_asset_present(self):
        scenario = make_scenario_with_identity()
        scenario.depreciable_assets = [
            DepreciableAsset(
                description="Evans Ave",
                date_placed_in_service=date(2025, 1, 15),
                basis=200_000.0,
                recovery_class="27.5-year",
                convention="mid-month",
            ),
        ]
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertIn("f4562", emitted)
        self.assertEqual(emitted["f4562"].name, "f4562_2025.pdf")
        self.assertTrue(emitted["f4562"].exists())
        self.assertGreater(emitted["f4562"].stat().st_size, 0)

    def test_omits_4562_when_no_depreciable_assets(self):
        scenario = make_scenario_with_identity()
        emitted = self.orchestrator.emit_pdfs(
            scenario, SAMPLE_RESULTS, self.output_dir,
        )
        self.assertNotIn("f4562", emitted)


if __name__ == "__main__":
    unittest.main()
