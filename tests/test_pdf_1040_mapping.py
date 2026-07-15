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


if __name__ == "__main__":
    unittest.main()
