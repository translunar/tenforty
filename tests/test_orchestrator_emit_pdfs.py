"""Tests for ReturnOrchestrator.emit_pdfs."""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.models import FilingStatus, Scenario, TaxReturnConfig
from tenforty.orchestrator import ReturnOrchestrator


REPO_ROOT = Path(__file__).parent.parent
F4868_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f4868.pdf"


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


if __name__ == "__main__":
    unittest.main()
