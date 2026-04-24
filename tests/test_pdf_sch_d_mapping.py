"""Static structure tests for the Schedule D PDF field mapping."""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_sch_d import PdfSchD

SCH_D_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040sd.pdf"
)

_REQUIRED_SCALARS = (
    "taxpayer_name", "taxpayer_ssn",
    "sch_d_line_1a_proceeds", "sch_d_line_1a_basis", "sch_d_line_1a_gain",
    "sch_d_line_7_net_short",
    "sch_d_line_8a_proceeds", "sch_d_line_8a_basis", "sch_d_line_8a_gain",
    "sch_d_line_15_net_long",
    "sch_d_line_16_total",
)


class PdfSchDStructureTests(unittest.TestCase):
    def test_2025_has_summary_scalars(self):
        m = PdfSchD.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_SCALARS:
            self.assertIn(k, scalars, f"missing scalar: {k}")

    def test_2025_has_empty_repeaters_v1(self):
        m = PdfSchD.get_mapping(2025)
        self.assertEqual(m.get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_D_TEMPLATE.exists():
            self.skipTest(f"Sch D template not available at {SCH_D_TEMPLATE}")
        reader = PdfReader(str(SCH_D_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in PdfSchD.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040sd.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(PdfSchD.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchD mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule D"):
            PdfSchD.get_mapping(1999)


class TestPdfSchDFullLineGrid(unittest.TestCase):
    """Verify the full Part I / Part II line grid plus page-2 lines 18/19."""

    def test_all_new_lines_present(self) -> None:
        m = PdfSchD.get_mapping(2025)
        for line, kind in [
            ("1b", "proceeds"), ("1b", "basis"), ("1b", "gain"),
            ("2",  "proceeds"), ("2",  "basis"), ("2",  "gain"),
            ("3",  "proceeds"), ("3",  "basis"), ("3",  "gain"),
            ("5",  "net_short_k1"),
            ("8b", "proceeds"), ("8b", "basis"), ("8b", "gain"),
            ("9",  "proceeds"), ("9",  "basis"), ("9",  "gain"),
            ("10", "proceeds"), ("10", "basis"), ("10", "gain"),
            ("12", "net_long_k1"),
        ]:
            self.assertIn(f"sch_d_line_{line}_{kind}", m["scalars"])
        self.assertIn("sch_d_line_18_unrecap_1250", m["scalars"])
        self.assertIn("sch_d_line_19_28_rate_gain", m["scalars"])


if __name__ == "__main__":
    unittest.main()
