"""Structural tests for the Form 8949 PDF mapping.

Scope: boxes A, B, D, E (the four boxes addressable by the current
Form1099B model). Tests intentionally exclude C/F (no-1099-B) and
the TY2025-new digital-asset boxes G/H/I/J/K/L.
"""

import re
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings import pdf_f8949 as _pdf_f8949_module
from tenforty.mappings.pdf_f8949 import PdfF8949, _BOX_SPECS


class TestPdfF8949Mapping(unittest.TestCase):
    def test_get_mapping_2025_returns_scalars_and_repeaters(self) -> None:
        m = PdfF8949.get_mapping(2025)
        self.assertIn("scalars", m)
        self.assertIn("repeaters", m)

    def test_scalars_contain_header_and_in_scope_totals(self) -> None:
        m = PdfF8949.get_mapping(2025)
        for key in ("taxpayer_name", "taxpayer_ssn"):
            self.assertIn(key, m["scalars"])
        for letter in _BOX_SPECS:
            for kind in ("proceeds", "basis", "adjustment", "gain"):
                self.assertIn(
                    f"f8949_box_{letter.value}_total_{kind}", m["scalars"],
                    f"missing total for box {letter.value.upper()}/{kind}",
                )

    def test_scalars_do_not_cover_out_of_scope_boxes(self) -> None:
        """C/F and digital-asset G/H/I/J/K/L are intentionally excluded —
        the current Form1099B model cannot express them."""
        m = PdfF8949.get_mapping(2025)
        for letter in ("c", "f", "g", "h", "i", "j", "k", "l"):
            for kind in ("proceeds", "basis", "adjustment", "gain"):
                self.assertNotIn(
                    f"f8949_box_{letter}_total_{kind}", m["scalars"],
                    f"box {letter.upper()} should be out of scope",
                )

    def test_repeaters_cover_rows_for_each_in_scope_box(self) -> None:
        m = PdfF8949.get_mapping(2025)
        for letter in _BOX_SPECS:
            self.assertIn(f"box_{letter.value}_rows", m["repeaters"])

    def test_each_box_has_checkbox_in_scalars(self) -> None:
        """The PDF uses one table per page with a checkbox selecting the
        active box — each in-scope box needs its checkbox path mapped so
        emit can mark the correct box."""
        m = PdfF8949.get_mapping(2025)
        for letter in _BOX_SPECS:
            self.assertIn(
                f"f8949_box_{letter.value}_checkbox", m["scalars"],
                f"missing checkbox path for box {letter.value.upper()}",
            )

    def test_no_year_raises(self) -> None:
        with self.assertRaises(ValueError):
            PdfF8949.get_mapping(1999)

    def test_2021_inherits_2022_payload(self) -> None:
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022 (geometry alias).
        self.assertIs(PdfF8949.get_mapping(2021), PdfF8949.get_mapping(2022))


_TEMPLATE_2021 = (
    Path(__file__).resolve().parents[1] / "pdfs" / "federal" / "2021" / "f8949.pdf"
)


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Form 8949 template not present")
class TestPdfF89492021EmitRoundTrip(unittest.TestCase):
    """Fill the real 2021 Form 8949 template — box-A totals scalars plus one
    box-A repeater data row — with distinctive values, then read the cells back
    directly with pypdf. No soffice."""

    def test_distinctive_values_round_trip(self) -> None:
        mapping = PdfF8949.get_mapping(2021)
        row = mapping["repeaters"]["box_a_rows"][0]
        # Merge the scalar totals and one data row into one flat field_mapping;
        # both halves are result-key -> field-path dicts. Checkbox key omitted.
        field_mapping = {
            "taxpayer_name": mapping["scalars"]["taxpayer_name"],
            "taxpayer_ssn": mapping["scalars"]["taxpayer_ssn"],
            "f8949_box_a_total_proceeds": mapping["scalars"]["f8949_box_a_total_proceeds"],
            "f8949_box_a_total_basis": mapping["scalars"]["f8949_box_a_total_basis"],
            "f8949_box_a_total_gain": mapping["scalars"]["f8949_box_a_total_gain"],
            "f8949_box_a_row_1_description": row["f8949_box_a_row_1_description"],
            "f8949_box_a_row_1_proceeds": row["f8949_box_a_row_1_proceeds"],
            "f8949_box_a_row_1_cost_basis": row["f8949_box_a_row_1_cost_basis"],
            "f8949_box_a_row_1_gain_loss": row["f8949_box_a_row_1_gain_loss"],
        }
        values = {
            "taxpayer_name": "Distinct 8949 Filer",
            "taxpayer_ssn": "666-00-2021",
            "f8949_box_a_total_proceeds": 30_000,
            "f8949_box_a_total_basis": 21_000,
            "f8949_box_a_total_gain": 9_000,
            "f8949_box_a_row_1_description": "Distinct Lot ABC",
            "f8949_box_a_row_1_proceeds": 15_500,
            "f8949_box_a_row_1_cost_basis": 10_250,
            "f8949_box_a_row_1_gain_loss": 5_250,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f8949_2021.pdf"
            PdfFiller().fill(
                template_path=_TEMPLATE_2021,
                output_path=out,
                field_mapping=field_mapping,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(field_mapping[key]), str(expected))


class TestPdfF8949NoPlaceholders(unittest.TestCase):
    """Source-tree scan: the shipped mapping must not carry f1_??,
    FILL FROM T11a, or TODO markers left over from pre-probe scaffolding.
    Matches here mean the transcription wasn't finished."""

    def test_module_source_has_no_placeholders(self) -> None:
        src = Path(_pdf_f8949_module.__file__).read_text()
        self.assertNotRegex(
            src, r"f[12]_\?\?",
            "pdf_f8949.py still contains 'f?_??' placeholder",
        )
        self.assertNotIn("FILL FROM T11a", src)
        self.assertFalse(
            re.search(r"\bTODO\b", src),
            "pdf_f8949.py contains a TODO marker",
        )
