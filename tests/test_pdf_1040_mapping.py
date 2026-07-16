"""Read-back tests for the federal 1040 line-26 (estimated tax payments) cell.

The federal spine emits result key ``estimated_tax_payments`` (line 26,
verbatim). This test locks the pdf_1040 mapping to that same key name for
all four years with committed templates, and verifies the mapped cell is a
real field on each year's template that round-trips a filled value.
"""

import tempfile
import unittest
from pathlib import Path

import pypdf

from tests.helpers import REPO_ROOT
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040

YEAR_CELLS = {
    2022: "topmostSubform[0].Page2[0].f2_15[0]",
    2023: "topmostSubform[0].Page2[0].f2_15[0]",
    2024: "topmostSubform[0].Page2[0].f2_20[0]",
    2025: "topmostSubform[0].Page2[0].f2_21[0]",
}


class TestPdf1040EstimatedTaxPaymentsMapping(unittest.TestCase):
    def test_mapping_keys_on_new_name(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                mapping = Pdf1040.get_mapping(year)
                self.assertEqual(mapping.get("estimated_tax_payments"), cell)
                self.assertNotIn("estimated_payments", mapping)

    def test_mapped_cell_is_real_field_on_template(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                fields = pypdf.PdfReader(template).get_fields()
                self.assertIn(cell, fields)

    def test_readback_distinctive_value(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(
                        template, out, mapping, values={"estimated_tax_payments": 13579}
                    )
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    self.assertEqual(fields[cell].get("/V"), "13579")

    def test_readback_zero_case_renders_zero(self):
        # Per team-lead ruling: a present 0 renders "0" (consistent with line
        # 25d/33 neighbors). The plan's "absent -> blank" means ONLY the case
        # where the results dict LACKS the key entirely (e.g. an old
        # filed-values surface) -- not zero-suppression.
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(
                        template, out, mapping, values={"estimated_tax_payments": 0}
                    )
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    self.assertEqual(fields[cell].get("/V"), "0")

    def test_readback_absent_case_is_blank(self):
        for year, cell in YEAR_CELLS.items():
            with self.subTest(year=year):
                template = REPO_ROOT / "pdfs" / "federal" / str(year) / "f1040.pdf"
                mapping = Pdf1040.get_mapping(year)
                with tempfile.TemporaryDirectory() as tmpdir:
                    out = Path(tmpdir) / "out.pdf"
                    PdfFiller().fill(template, out, mapping, values={})
                    reader = pypdf.PdfReader(out)
                    fields = reader.get_fields()
                    value = fields[cell].get("/V")
                    self.assertTrue(value is None or value == "")


class TestPdf1040_2021EmitRoundTrip(unittest.TestCase):
    """Fill the real 2021 f1040 template via PdfFiller with distinctive values,
    then read the cells back directly with pypdf — no soffice.

    Locks the render-verified 2021 placements, most importantly the wage-line
    regression: `wages` must land in the SINGLE 2021 line-1 box
    (Lines1-11_ReadOrder f1_28), NOT a 1a-1z sub-line (2021 has none). Uses
    plain tokens + integers — no SSN/EIN-shaped sentinels — so the
    personal-data denylist stays clean. If any value fails to land at its
    mapped path the test fails loudly; it must never be weakened.
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        template = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040.pdf"
        mapping = Pdf1040.get_mapping(2021)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040_2021.pdf"
            PdfFiller().fill(template, out, mapping, values=values)
            return {
                name: (fld.get("/V") or "")
                for name, fld in (pypdf.PdfReader(str(out)).get_fields() or {}).items()
            }

    def test_representative_subset_round_trips(self):
        mapping = Pdf1040.get_mapping(2021)
        values = {
            "first_name": "Distinct1040First",
            "last_name": "Distinct1040Last",
            "ssn": "SSN-SENTINEL-2021",
            "wages": 111_028,
            "taxable_interest": 222_030,
            "ordinary_dividends": 333_032,
            "agi": 444_043,
            "taxable_income": 555_049,
            "total_tax": 666_002,
            "total_payments": 777_024,
            "refund": 888_026,
            "combat_pay_election": 999_017,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(mapping[key]), str(expected))

    def test_wages_land_in_single_line1_box_f1_28(self):
        # The wage-line regression: 2021 has a single line-1 wages box; `wages`
        # must land in Lines1-11_ReadOrder f1_28 specifically.
        read = self._fill_and_read({"wages": 123_456})
        self.assertEqual(
            read.get("topmostSubform[0].Page1[0].Lines1-11_ReadOrder[0].f1_28[0]"),
            "123456",
            "wages must land in the single 2021 line-1 box f1_28",
        )

    def test_combat_pay_election_lands_in_f2_17(self):
        read = self._fill_and_read({"combat_pay_election": 42_017})
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].f2_17[0]"),
            "42017",
            "combat_pay_election must land in f2_17 (line 27b)",
        )


if __name__ == "__main__":
    unittest.main()
