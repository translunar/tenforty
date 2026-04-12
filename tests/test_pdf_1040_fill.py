"""Fill-and-reread integration test for the 2025 Form 1040 PDF mapping.

Ground truth (field name -> form line) was transcribed from the probe rendered
by scripts/probe_pdf_fields.py. The 2025 form shifted field numbers relative
to the mapping that was originally committed. Update these assertions whenever
the IRS re-issues the form and field numbers shift again.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.models import (
    FilingStatus,
    Form1099DIV,
    Form1099INT,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator

REPO_ROOT = Path(__file__).parent.parent
F1040_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f1040.pdf"


def _build_synthetic_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            birthdate="1980-01-01",
            state="CA",
            first_name="Alice",
            last_name="Example",
            ssn="000-00-0001",
            address="1 Test Street",
            address_city="Testville",
            address_state="TX",
            address_zip="00001",
        ),
        w2s=[
            W2(
                employer="Tech Corp",
                wages=12350.00,
                federal_tax_withheld=1550.00,
                ss_wages=12350.00,
                ss_tax_withheld=750.00,
                medicare_wages=12350.00,
                medicare_tax_withheld=200.00,
            )
        ],
        form1099_int=[Form1099INT(payer="National Bank", interest=150.00)],
        form1099_div=[
            Form1099DIV(
                payer="Investment Brokerage",
                ordinary_dividends=250.00,
                qualified_dividends=200.00,
            )
        ],
    )


@unittest.skipUnless(F1040_TEMPLATE.exists(), "f1040.pdf template not found")
class TestPdf1040FillGroundTruth(unittest.TestCase):
    """Pin field-name -> value routing against the 2025 form revision."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.mkdtemp()
        out_dir = Path(cls._tmpdir)
        scenario = _build_synthetic_scenario()
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=out_dir / "work",
        )
        cls.results = orch.compute_federal(scenario)
        emitted = orch.emit_pdfs(scenario, cls.results, out_dir)
        reader = pypdf.PdfReader(str(emitted["1040"]))
        fields = reader.get_fields() or {}
        cls.field_values = {
            name: (field.get("/V") or "") for name, field in fields.items()
        }

    def _assert_field(self, field_name: str, expected: str):
        actual = self.field_values.get(field_name, "<missing>")
        self.assertEqual(
            actual, expected,
            f"Field {field_name} expected {expected!r} got {actual!r}",
        )

    # === PAGE 1 ===
    def test_line_1a_wages(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_47[0]", "12350")

    def test_line_2b_taxable_interest(self):
        # Translation: engine `interest_income` -> `taxable_interest`.
        self._assert_field("topmostSubform[0].Page1[0].f1_59[0]", "150")

    def test_line_3b_ordinary_dividends(self):
        # Translation: engine `dividend_income` -> `ordinary_dividends`.
        self._assert_field("topmostSubform[0].Page1[0].f1_61[0]", "250")

    def test_line_9_total_income(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_73[0]", "12750")

    def test_line_11a_agi(self):
        self._assert_field("topmostSubform[0].Page1[0].f1_75[0]", "12750")

    def test_line_7a_capital_gain_left_blank(self):
        # Engine produces no `capital_gain_loss` key for this W-2 scenario;
        # Schedule D line 16 is surfaced as `schd_line16` but no translation
        # rename wires it. Field f1_70 must stay blank — regression guard
        # against accidental routing of total_income here, which is the bug
        # that motivated this fix.
        self._assert_field("topmostSubform[0].Page1[0].f1_70[0]", "")

    # === PAGE 2 ===
    def test_line_25a_federal_withheld_w2(self):
        self._assert_field("topmostSubform[0].Page2[0].f2_16[0]", "1550")


if __name__ == "__main__":
    unittest.main()
