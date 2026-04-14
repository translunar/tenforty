"""Round-trip unit tests for Form 4868 PDF emission.

Synthesizes results + Scenario in memory, calls emit_pdfs, re-reads the
filled PDF with pypdf, and asserts each 4868 line matches the expected value.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.models import FilingStatus, Scenario, TaxReturnConfig
from tenforty.orchestrator import ReturnOrchestrator


REPO_ROOT = Path(__file__).parent.parent
F4868_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f4868.pdf"

# PDF field names for 4868 lines (from Pdf4868._MAPPINGS[2025])
FIELD_FULL_NAME = "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_4[0]"
FIELD_SSN = "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_9[0]"
FIELD_SPOUSE_SSN = "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_10[0]"
FIELD_LINE4 = "topmostSubform[0].Page1[0].f1_11[0]"   # estimated_total_tax
FIELD_LINE5 = "topmostSubform[0].Page1[0].f1_12[0]"   # total_payments
FIELD_LINE6 = "topmostSubform[0].Page1[0].f1_13[0]"   # balance_due
FIELD_LINE7 = "topmostSubform[0].Page1[0].f1_14[0]"   # amount_paying_with_extension
FIELD_VOUCHER = "topmostSubform[0].Page3[0].Col4[0].f3_1[0]"


def _read_fields(pdf_path: Path) -> dict[str, str]:
    """Return a flat {field_name: value_str} dict from a filled PDF."""
    reader = pypdf.PdfReader(str(pdf_path))
    raw = reader.get_fields() or {}
    return {name: (field.get("/V") or "") for name, field in raw.items()}


def _make_orchestrator(tmp: Path) -> ReturnOrchestrator:
    return ReturnOrchestrator(
        spreadsheets_dir=REPO_ROOT / "spreadsheets",
        work_dir=tmp / "work",
    )


def _emit(orchestrator: ReturnOrchestrator, scenario: Scenario,
          results: dict, tmp: Path) -> dict[str, str]:
    output_dir = tmp / "out"
    emitted = orchestrator.emit_pdfs(scenario, results, output_dir)
    return _read_fields(emitted["4868"])


@unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
class TestBalanceDueSingle(unittest.TestCase):
    """Balance-due scenario for a single filer."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orchestrator = _make_orchestrator(self._tmp)
        config = TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1990-01-01",
            state="TX",
            first_name="Alice",
            last_name="Example",
            ssn="000-00-0001",
            address="100 Main St",
            address_city="Austin",
            address_state="TX",
            address_zip="78701",
        )
        scenario = Scenario(config=config)
        results = {"total_tax": 15000, "total_payments": 12000, "wages": 90000}
        self._fields = _emit(self._orchestrator, scenario, results, self._tmp)

    def test_line4_estimated_total_tax(self):
        self.assertEqual(self._fields.get(FIELD_LINE4), "15000")

    def test_line5_total_payments(self):
        self.assertEqual(self._fields.get(FIELD_LINE5), "12000")

    def test_line6_balance_due(self):
        self.assertEqual(self._fields.get(FIELD_LINE6), "3000")

    def test_line7_amount_paying(self):
        self.assertEqual(self._fields.get(FIELD_LINE7), "0")

    def test_voucher_amount(self):
        self.assertEqual(self._fields.get(FIELD_VOUCHER), "3000")

    def test_ssn_populated(self):
        self.assertEqual(self._fields.get(FIELD_SSN), "000-00-0001")

    def test_spouse_ssn_blank(self):
        # Single filer: spouse_ssn defaults to "" → PdfFiller writes ""
        self.assertEqual(self._fields.get(FIELD_SPOUSE_SSN, ""), "")

    def test_full_name(self):
        self.assertEqual(self._fields.get(FIELD_FULL_NAME), "Alice Example")


@unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
class TestRefundCase(unittest.TestCase):
    """Line 6 is floored to 0 when total_payments exceeds total_tax."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orchestrator = _make_orchestrator(self._tmp)
        config = TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1985-06-15",
            state="CA",
            first_name="Bob",
            last_name="Refund",
            ssn="000-00-0002",
            address="200 Oak Ave",
            address_city="Los Angeles",
            address_state="CA",
            address_zip="90001",
        )
        scenario = Scenario(config=config)
        results = {"total_tax": 10000, "total_payments": 12500}
        self._fields = _emit(self._orchestrator, scenario, results, self._tmp)

    def test_line4_estimated_total_tax(self):
        self.assertEqual(self._fields.get(FIELD_LINE4), "10000")

    def test_line5_total_payments(self):
        self.assertEqual(self._fields.get(FIELD_LINE5), "12500")

    def test_line6_floored_to_zero(self):
        self.assertEqual(self._fields.get(FIELD_LINE6), "0")

    def test_voucher_amount_zero(self):
        self.assertEqual(self._fields.get(FIELD_VOUCHER), "0")


@unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
class TestMFJSpouseSSN(unittest.TestCase):
    """MFJ filing: both names and spouse SSN are populated."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orchestrator = _make_orchestrator(self._tmp)
        config = TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.MARRIED_JOINTLY,
            birthdate="1982-03-10",
            state="NY",
            first_name="Carol",
            last_name="Joint",
            ssn="000-00-0003",
            spouse_first_name="Dave",
            spouse_last_name="Joint",
            spouse_ssn="000-00-0004",
            address="300 Pine Rd",
            address_city="New York",
            address_state="NY",
            address_zip="10001",
        )
        scenario = Scenario(config=config)
        results = {"total_tax": 20000, "total_payments": 18000}
        self._fields = _emit(self._orchestrator, scenario, results, self._tmp)

    def test_spouse_ssn_populated(self):
        self.assertEqual(self._fields.get(FIELD_SPOUSE_SSN), "000-00-0004")

    def test_primary_ssn_populated(self):
        self.assertEqual(self._fields.get(FIELD_SSN), "000-00-0003")

    def test_full_name_uses_primary(self):
        # forms.f4868.compute uses first_name + last_name (primary only)
        self.assertEqual(self._fields.get(FIELD_FULL_NAME), "Carol Joint")

    def test_line6_balance_due(self):
        self.assertEqual(self._fields.get(FIELD_LINE6), "2000")


@unittest.skipUnless(F4868_TEMPLATE.exists(), "f4868.pdf template not found")
class TestSingleFilerSpouseFieldsBlank(unittest.TestCase):
    """Single filer: spouse_ssn field is empty in the filled PDF."""

    def setUp(self):
        self._tmp = Path(tempfile.mkdtemp())
        self._orchestrator = _make_orchestrator(self._tmp)
        config = TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1995-11-20",
            state="WA",
            first_name="Eve",
            last_name="Solo",
            ssn="000-00-0005",
            spouse_ssn="",
            address="400 Birch Ln",
            address_city="Seattle",
            address_state="WA",
            address_zip="98101",
        )
        scenario = Scenario(config=config)
        results = {"total_tax": 5000, "total_payments": 4000}
        self._fields = _emit(self._orchestrator, scenario, results, self._tmp)

    def test_spouse_ssn_absent_or_empty(self):
        # PdfFiller writes "" for spouse_ssn="" (not None, so not skipped)
        # get returns "" either because it was written as "" or field is absent
        value = self._fields.get(FIELD_SPOUSE_SSN, "")
        self.assertEqual(value, "")

    def test_primary_ssn_present(self):
        self.assertEqual(self._fields.get(FIELD_SSN), "000-00-0005")


if __name__ == "__main__":
    unittest.main()
