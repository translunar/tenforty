"""Probe-certified verification for the Form 1040-X (Rev. Dec 2025) mapping.

Three classes, mirroring tests/test_pdf_f100s_mapping.py:
  1. Payload-key coverage — every forms/f1040x.assemble output key maps EXCEPT
     the three documented, intentionally-unmapped duplicate aliases.
  2. Fields-on-template — every mapped path is a real get_fields() key on the
     actual Dec-2025 template.
  3. Filled-emit read-back — fill the real template through PdfFiller and reopen
     with pypdf, asserting distinctive values read back from the filled PDF
     (native pypdf, no soffice).
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f1040x
from tenforty.mappings.pdf_f1040x import PdfF1040X, get_mapping
from tenforty.models import AmendmentCase
from tests.helpers import REPO_ROOT

_REVISION = "rev-2025-12"
_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "amendments" / "f1040x.pdf"

# The three DUPLICATE aliases the assembler emits alongside their bare line
# keys. They carry the SAME value as f1040x_line18 / line20 / line22 and are
# INTENTIONALLY absent from the mapping — mapping both an alias and its bare
# key would double-fill one field. See pdf_f1040x module docstring.
_INTENTIONALLY_UNMAPPED = frozenset({
    "f1040x_line18_overpayment_on_original",
    "f1040x_line20_amount_owed",
    "f1040x_line22_refund",
})


def _synthetic_case() -> AmendmentCase:
    return AmendmentCase(
        year=2023,
        explanation="SYNTHETIC-AMENDMENT-EXPLANATION-9F3",
        original_refund_received=20.0,
        original_refund_applied=0.0,
    )


def _synthetic_assembler_output() -> dict:
    """A real forms/f1040x.assemble output built from arbitrary synthetic
    filed/corrected figures (not tax data). Chosen so the tail lands in the
    REFUND branch (corrected total_tax < net payments) and the distinctive
    read-back values are mutually distinct.

    ``f8962_repayment`` and ``f8959_tax_total`` (lines 6 / 10 sourced
    components) are set on BOTH filed and corrected so lines 6/8/10/11 carry
    distinctive, nonzero, column-dependent values. ``nonrefundable_credits``
    (line 7) is set on ``corrected`` ONLY — a nonzero value on ``filed``
    would trip the out-of-scope guard, so Column A of line 7 is legitimately
    0 in this scenario."""
    filed = {
        "agi": 1000.0, "total_deductions": 200.0, "_qbi_deduction_1040": 50.0,
        "taxable_income": 750.0, "total_tax": 80.0, "federal_withheld": 100.0,
        "total_payments": 100.0,
        "f8962_repayment": 15.0, "f8959_tax_total": 7.0,
    }
    corrected = {
        "agi": 1200.0, "total_deductions": 200.0, "_qbi_deduction_1040": 60.0,
        "taxable_income": 940.0, "total_tax": 30.0, "federal_withheld": 100.0,
        "total_payments": 100.0,
        "f8962_repayment": 25.0, "nonrefundable_credits": 8.0, "f8959_tax_total": 12.0,
    }
    return f1040x.assemble(filed, corrected, _synthetic_case())


class PayloadCoverageTests(unittest.TestCase):
    def test_every_assembler_key_maps_except_documented_aliases(self):
        mapping = get_mapping(_REVISION)
        output_keys = set(_synthetic_assembler_output())
        # The three aliases are the ONLY output keys that must not map.
        self.assertEqual(output_keys - set(mapping), _INTENTIONALLY_UNMAPPED)
        # And the mapping introduces no key the assembler does not emit.
        self.assertEqual(set(mapping) - output_keys, set())

    def test_aliases_are_absent_from_mapping(self):
        mapping = get_mapping(_REVISION)
        for alias in _INTENTIONALLY_UNMAPPED:
            with self.subTest(alias=alias):
                self.assertNotIn(alias, mapping)

    def test_class_and_module_accessor_agree(self):
        self.assertIs(get_mapping(_REVISION), PdfF1040X.get_mapping(_REVISION))

    def test_unknown_revision_raises(self):
        with self.assertRaises(ValueError):
            get_mapping("rev-1999-01")


class FieldsOnTemplateTests(unittest.TestCase):
    def test_every_mapped_path_is_a_real_pdf_field(self):
        real = set(PdfReader(_TEMPLATE).get_fields() or {})
        bad = sorted(p for p in get_mapping(_REVISION).values() if p not in real)
        self.assertEqual(bad, [])


class FilledEmitReadBackTests(unittest.TestCase):
    def test_distinctive_values_read_back_from_filled_pdf(self):
        mapping = get_mapping(_REVISION)
        values = _synthetic_assembler_output()
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040x_filled.pdf"
            PdfFiller().fill(_TEMPLATE, out, mapping, values)
            fields = PdfReader(out).get_fields() or {}

        def read(key: str) -> str:
            got = fields[mapping[key]].get("/V") or ""
            return str(got).replace(",", "").replace("$", "").strip()

        # A Column-B delta: line 5_b = corrected 940 - filed 750 = 190.
        self.assertEqual(read("f1040x_line5_b"), "190")
        # Tax-computation section (lines 6/7/8/10/11), distinctive per column:
        #   L6  = total_tax + f8962_repayment:            A=95   B=-40  C=55
        #   L7  = nonrefundable_credits (filed guarded 0): A=0    B=8    C=8
        #   L8  = L6 - L7 (on-form subtotal):              A=95   B=-48  C=47
        #   L10 = f8959_tax_total:                         A=7    B=5    C=12
        #   L11 = L8 + L10 (on-form subtotal):             A=102  B=-43  C=59
        self.assertEqual(read("f1040x_line6_a"), "95")
        self.assertEqual(read("f1040x_line6_b"), "-40")
        self.assertEqual(read("f1040x_line6_c"), "55")
        self.assertEqual(read("f1040x_line10_c"), "12")
        # Printed-arithmetic check on the RENDERED integers (not the Python
        # floats): L8 == L6 - L7 and L11 == L8 + L10, per column, confirming
        # the mapped fields land on the correct on-form cells.
        for col in ("a", "b", "c"):
            with self.subTest(col=col):
                l6 = int(read(f"f1040x_line6_{col}"))
                l7 = int(read(f"f1040x_line7_{col}"))
                l8 = int(read(f"f1040x_line8_{col}"))
                l10 = int(read(f"f1040x_line10_{col}"))
                l11 = int(read(f"f1040x_line11_{col}"))
                self.assertEqual(l8, l6 - l7)
                self.assertEqual(l11, l8 + l10)
        # Refund tail: line11 col C = 59, line19 (net original payments) = 80,
        # so line 21 = 80 - 59 = 21, and line 22 refunds all of it.
        self.assertEqual(read("f1040x_line22"), "21")
        # Part II explanation text.
        self.assertEqual(read("f1040x_explanation"),
                         "SYNTHETIC-AMENDMENT-EXPLANATION-9F3")
        # Year write-in carries case.year.
        self.assertEqual(read("f1040x_amended_year"), "2023")


if __name__ == "__main__":
    unittest.main()
