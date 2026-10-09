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
from tenforty.models import AmendmentCase, FilingStatus, TaxReturnConfig
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

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
        # The arbitrary filed figures below net to a balance due, so line 16
        # must be stated; 0 keeps the tail read-back values unchanged.
        original_tax_paid=0.0,
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

    def test_line13_estimated_tax_payments_maps_to_probe_certified_cells(self):
        """Line 13 (estimated tax payments) is now SOURCED — its 3 cells must
        map to the probe-certified Line13 f1_58/59/60 paths under Table_Payments."""
        mapping = get_mapping(_REVISION)
        pm = "topmostSubform[0].Page1[0].Table_Payments[0]."
        self.assertEqual(mapping["f1040x_line13_a"], pm + "Line13[0].f1_58[0]")
        self.assertEqual(mapping["f1040x_line13_b"], pm + "Line13[0].f1_59[0]")
        self.assertEqual(mapping["f1040x_line13_c"], pm + "Line13[0].f1_60[0]")

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


# Literal field names for the page-1 header, read off the template and
# confirmed by rendering a marker fill. NOT read through the mapping: that
# would only fail for a path missing from the template, never a wrong one.
_P1 = "topmostSubform[0].Page1[0]."
_FILING_STATUS_BOXES = {
    FilingStatus.SINGLE: (_P1 + "c1_3[0]", "/1"),
    FilingStatus.MARRIED_JOINTLY: (_P1 + "c1_3[1]", "/2"),
    FilingStatus.MARRIED_SEPARATELY: (_P1 + "c1_3[2]", "/3"),
    FilingStatus.HEAD_OF_HOUSEHOLD: (_P1 + "c1_3[3]", "/4"),
    FilingStatus.QUALIFYING_WIDOW: (_P1 + "c1_3[4]", "/5"),
}


def _config(filing_status: FilingStatus, **spouse) -> TaxReturnConfig:
    return TaxReturnConfig(
        **spouse,
        year=2023, filing_status=filing_status, birthdate="1980-01-01",
        state="CA", first_name="Zelda", middle_initial="Q",
        last_name="Marker", ssn="000-00-0417",
        address="417 Synthetic Blvd", address_city="Faketown",
        address_state="CA", address_zip="90417",
        **scope_out_attestation_defaults(),
    )


class HeaderFillTests(unittest.TestCase):
    """The page-1 header (name, SSN, address, filing status) is filled from
    the scenario config, alongside the assembler's money lines."""

    def _fill(self, filing_status: FilingStatus, **spouse) -> dict:
        values = {
            **_synthetic_assembler_output(),
            **f1040x.presentation_keys(_config(filing_status, **spouse)),
        }
        mapping = {
            **get_mapping(_REVISION),
            **PdfF1040X.get_presentation_mapping(_REVISION),
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040x_filled.pdf"
            PdfFiller().fill(
                _TEMPLATE, out, mapping, values,
                checkbox_states=PdfF1040X.get_checkbox_states(_REVISION))
            return {
                name: str(f.get("/V") or "")
                for name, f in (PdfReader(out).get_fields() or {}).items()}

    def test_each_filing_status_checks_its_own_box_and_no_other(self):
        all_boxes = {box for box, _ in _FILING_STATUS_BOXES.values()}
        for status, (box, on) in _FILING_STATUS_BOXES.items():
            with self.subTest(status=status):
                fields = self._fill(status)
                self.assertEqual(fields[box], on)
                self.assertEqual(
                    {b for b in all_boxes if fields[b] not in ("", "/Off")},
                    {box})

    def test_name_ssn_and_address_cells(self):
        fields = self._fill(FilingStatus.SINGLE)
        addr = _P1 + "Address_ReadOrder[0]."
        self.assertEqual(fields[_P1 + "f1_03[0]"], "Zelda Q")
        self.assertEqual(fields[_P1 + "f1_04[0]"], "Marker")
        self.assertEqual(fields[_P1 + "f1_05[0]"], "000000417")
        self.assertEqual(fields[addr + "f1_09[0]"], "417 Synthetic Blvd")
        self.assertEqual(fields[addr + "f1_11[0]"], "Faketown")
        self.assertEqual(fields[addr + "f1_12[0]"], "CA")
        self.assertEqual(fields[addr + "f1_13[0]"], "90417")
        # The money lines still land: the header is additive.
        self.assertEqual(
            fields[get_mapping(_REVISION)["f1040x_amended_year"]], "2023")

    def test_joint_return_prints_the_spouse_cells(self):
        fields = self._fill(
            FilingStatus.MARRIED_JOINTLY,
            spouse_first_name="Wendell", spouse_middle_initial="R",
            spouse_last_name="Probe", spouse_ssn="000-00-0582")
        self.assertEqual(fields[_P1 + "f1_06[0]"], "Wendell R")
        self.assertEqual(fields[_P1 + "f1_07[0]"], "Probe")
        self.assertEqual(fields[_P1 + "f1_08[0]"], "000000582")
        # The taxpayer's own cells are untouched by the spouse's.
        self.assertEqual(fields[_P1 + "f1_03[0]"], "Zelda Q")
        self.assertEqual(fields[_P1 + "f1_05[0]"], "000000417")

    def test_header_keys_are_disjoint_from_the_assembler_mapping(self):
        self.assertEqual(
            set(get_mapping(_REVISION))
            & set(PdfF1040X.get_presentation_mapping(_REVISION)), set())
        self.assertEqual(
            set(get_mapping(_REVISION).values())
            & set(PdfF1040X.get_presentation_mapping(_REVISION).values()),
            set())


if __name__ == "__main__":
    unittest.main()
