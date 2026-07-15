"""Static structure tests for the Form 8959 PDF field mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_8959 import Pdf8959

F8959_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f8959.pdf"
)


class Pdf8959StructureTests(unittest.TestCase):
    def test_2025_has_all_24_lines_and_header(self):
        scalars = set(Pdf8959.get_mapping(2025)["scalars"].keys())
        self.assertIn("taxpayer_name", scalars)
        self.assertIn("taxpayer_ssn", scalars)
        for n in range(1, 25):
            self.assertIn(f"f8959_line_{n}", scalars, f"missing line {n}")

    def test_2025_has_empty_repeaters(self):
        self.assertEqual(Pdf8959.get_mapping(2025).get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not F8959_TEMPLATE.exists():
            self.skipTest(f"Form 8959 template not available at {F8959_TEMPLATE}")
        reader = PdfReader(str(F8959_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in Pdf8959.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f8959.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(Pdf8959.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "Pdf8959 mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "8959"):
            Pdf8959.get_mapping(1999)

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022.
        self.assertIs(Pdf8959.get_mapping(2021), Pdf8959.get_mapping(2022))


_TEMPLATE_2021 = (
    Path(__file__).resolve().parents[1] / "pdfs" / "federal" / "2021" / "f8959.pdf"
)


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Form 8959 template not present")
class Pdf89592021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Form 8959 template with distinctive values and read
    the cells back directly with pypdf — no soffice."""

    def test_distinctive_values_round_trip(self):
        scalars = Pdf8959.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct 8959 Filer",
            "taxpayer_ssn": "222-00-2021",
            "f8959_line_1": 71_000,
            "f8959_line_7": 81_000,
            "f8959_line_18": 91_000,
            "f8959_line_24": 12_345,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f8959_2021.pdf"
            PdfFiller().fill(
                template_path=_TEMPLATE_2021,
                output_path=out,
                field_mapping=scalars,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))


if __name__ == "__main__":
    unittest.main()
