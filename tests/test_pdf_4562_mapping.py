"""mappings.pdf_4562 — Form 4562 PDF field mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_4562 import Pdf4562
from tests.helpers import REPO_ROOT


PDF_PATH = "pdfs/federal/2025/f4562.pdf"

_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f4562.pdf"


class Pdf4562MappingTests(unittest.TestCase):
    def test_has_expected_header_and_total_scalars(self):
        m = Pdf4562.get_mapping(2025)
        s = m["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "f4562_line_22_total_depreciation",
        ):
            self.assertIn(k, s)

    def test_has_all_section_b_row_scalars(self):
        s = Pdf4562.get_mapping(2025)["scalars"]
        for label in ("a", "b", "c", "d", "e", "f", "g", "h", "i", "j"):
            for col in (
                "date_placed_in_service", "basis", "recovery_period",
                "convention", "method", "deduction",
            ):
                self.assertIn(f"f4562_line_19{label}_{col}", s)

    def test_no_repeaters_in_v1(self):
        m = Pdf4562.get_mapping(2025)
        self.assertEqual(m["repeaters"], {})

    def test_every_mapped_field_exists_in_pdf(self):
        s = Pdf4562.get_mapping(2025)["scalars"]
        fields = PdfReader(PDF_PATH).get_fields()
        for key, pdf_path in s.items():
            self.assertIn(
                pdf_path, fields,
                f"mapping {key!r} → {pdf_path!r} not found in {PDF_PATH}",
            )

    def test_unknown_year_raises(self):
        # 2023 is now supported (inherits 2024's identical field tree); use a
        # genuinely unsupported year to exercise the fail-closed path.
        with self.assertRaisesRegex(ValueError, "No Form 4562 PDF mapping"):
            Pdf4562.get_mapping(1999)


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Form 4562 template not present")
class Pdf45622021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Form 4562 template via PdfFiller with distinctive
    values, then read the cells back directly with pypdf — no soffice.

    Covers a representative Section B subset including the two offset rows:
    the compute's line_19i (residential 27.5yr) lands in the 2021 form's
    residential container Line19h_1, and line_19j (nonresidential 39yr) lands
    in the nonresidential container Line19i_1. The 2021 form has no 50-year
    (19h) row, so there is no such key.
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        scalars = Pdf4562.get_mapping(2021)["scalars"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f4562_2021.pdf"
            PdfFiller().fill(
                template_path=_TEMPLATE_2021,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            return {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }

    def test_representative_subset_round_trips(self):
        scalars = Pdf4562.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct 4562 Filer",
            "taxpayer_ssn": "222-00-2021",
            "f4562_line_22_total_depreciation": 22_022,
            # A full 19a row (3-year).
            "f4562_line_19a_date_placed_in_service": "01/2021",
            "f4562_line_19a_basis": 19_001,
            "f4562_line_19a_recovery_period": "3",
            "f4562_line_19a_convention": "HY",
            "f4562_line_19a_deduction": 19_003,
            # A full 19f row (20-year).
            "f4562_line_19f_date_placed_in_service": "06/2021",
            "f4562_line_19f_basis": 19_601,
            "f4562_line_19f_recovery_period": "20",
            "f4562_line_19f_convention": "MM",
            "f4562_line_19f_deduction": 19_603,
            # Offset row: residential-rental 27.5yr → 2021 container Line19h_1.
            "f4562_line_19i_basis": 27_500,
            "f4562_line_19i_deduction": 27_501,
            # Offset row: nonresidential-real 39yr → 2021 container Line19i_1.
            "f4562_line_19j_basis": 39_000,
            "f4562_line_19j_deduction": 39_001,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))

    def test_offset_rows_land_in_2021_containers(self):
        # Distinct sentinels so a mis-route to the wrong container is unambiguous.
        values = {
            "f4562_line_19i_basis": 27_500,
            "f4562_line_19j_basis": 39_000,
        }
        read = self._fill_and_read(values)
        self.assertEqual(
            read.get("topmostSubform[0].Page1[0].SectionBTable[0].Line19h_1[0].f1_62[0]"),
            "27500",
            "residential 27.5yr basis (line_19i) must land in Line19h_1",
        )
        self.assertEqual(
            read.get("topmostSubform[0].Page1[0].SectionBTable[0].Line19i_1[0].f1_74[0]"),
            "39000",
            "nonresidential 39yr basis (line_19j) must land in Line19i_1",
        )


if __name__ == "__main__":
    unittest.main()
