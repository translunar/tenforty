"""Structural tests for the Form 8949 PDF mapping.

Scope: boxes A, B, D, E (the four boxes addressable by the current
Form1099B model). Tests intentionally exclude C/F (no-1099-B) and
the TY2025-new digital-asset boxes G/H/I/J/K/L.
"""

import re
import unittest
from pathlib import Path

from tenforty.mappings.pdf_f8949 import PdfF8949


_IN_SCOPE_BOXES = ("a", "b", "d", "e")


class TestPdfF8949Mapping(unittest.TestCase):
    def test_get_mapping_2025_returns_scalars_and_repeaters(self) -> None:
        m = PdfF8949.get_mapping(2025)
        self.assertIn("scalars", m)
        self.assertIn("repeaters", m)

    def test_scalars_contain_header_and_in_scope_totals(self) -> None:
        m = PdfF8949.get_mapping(2025)
        for key in ("taxpayer_name", "taxpayer_ssn"):
            self.assertIn(key, m["scalars"])
        for letter in _IN_SCOPE_BOXES:
            for kind in ("proceeds", "basis", "adjustment", "gain"):
                self.assertIn(
                    f"f8949_box_{letter}_total_{kind}", m["scalars"],
                    f"missing total for box {letter.upper()}/{kind}",
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
        for letter in _IN_SCOPE_BOXES:
            self.assertIn(f"box_{letter}_rows", m["repeaters"])

    def test_each_box_has_checkbox_in_scalars(self) -> None:
        """The PDF uses one table per page with a checkbox selecting the
        active box — each in-scope box needs its checkbox path mapped so
        emit can mark the correct box."""
        m = PdfF8949.get_mapping(2025)
        for letter in _IN_SCOPE_BOXES:
            self.assertIn(
                f"f8949_box_{letter}_checkbox", m["scalars"],
                f"missing checkbox path for box {letter.upper()}",
            )

    def test_no_year_raises(self) -> None:
        with self.assertRaises(ValueError):
            PdfF8949.get_mapping(1999)


class TestPdfF8949NoPlaceholders(unittest.TestCase):
    """Source-tree scan: the shipped mapping must not carry f1_??,
    FILL FROM T11a, or TODO markers left over from pre-probe scaffolding.
    Matches here mean the transcription wasn't finished."""

    def test_module_source_has_no_placeholders(self) -> None:
        src = Path("tenforty/mappings/pdf_f8949.py").read_text()
        self.assertNotRegex(
            src, r"f[12]_\?\?",
            "pdf_f8949.py still contains 'f?_??' placeholder",
        )
        self.assertNotIn("FILL FROM T11a", src)
        self.assertFalse(
            re.search(r"\bTODO\b", src),
            "pdf_f8949.py contains a TODO marker",
        )
