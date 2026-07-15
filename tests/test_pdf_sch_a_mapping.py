"""Structural test for pdf_sch_a mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_a import PdfSchA
from tests.helpers import REPO_ROOT


class PdfSchAMappingTests(unittest.TestCase):
    def test_has_expected_scalars_for_2025(self):
        s = PdfSchA.get_mapping(2025)["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "sch_a_line_1_medical_gross",
            "sch_a_line_4_medical_deductible",
            "sch_a_line_5a_state_income_tax",
            "sch_a_line_5b_property_tax",
            "sch_a_line_5e_salt_capped",
            "sch_a_line_7_taxes_total",
            "sch_a_line_8a_mortgage_interest",
            "sch_a_line_10_interest_total",
            "sch_a_line_11_charity_cash",
            "sch_a_line_14_charity_total",
            "sch_a_line_17_total",
        ):
            self.assertIn(k, s, f"missing scalar key: {k}")

    def test_has_empty_repeaters_in_v1(self):
        self.assertEqual(PdfSchA.get_mapping(2025)["repeaters"], {})

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022; the mapping
        # inherits the 2022 payload by reference.
        self.assertIs(PdfSchA.get_mapping(2021), PdfSchA.get_mapping(2022))


_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040sa.pdf"


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule A template not present")
class PdfSchA2021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule A template with distinctive values via the
    same mapping the orchestrator uses, then read the cells back — no soffice,
    the AcroForm is filled and re-read directly with pypdf."""

    def test_distinctive_values_round_trip(self):
        scalars = PdfSchA.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct SchA Filer",
            "taxpayer_ssn": "111-00-2021",
            "sch_a_line_1_medical_gross": 11_111,
            "sch_a_line_5b_property_tax": 22_222,
            "sch_a_line_8a_mortgage_interest": 33_333,
            "sch_a_line_17_total": 44_444,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040sa_2021.pdf"
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

    def test_unknown_year_raises(self):
        # 2023 is now supported (inherits 2024's identical field tree); use a
        # genuinely unsupported year to exercise the fail-closed path.
        with self.assertRaisesRegex(ValueError, "No Schedule A PDF mapping"):
            PdfSchA.get_mapping(1999)


if __name__ == "__main__":
    unittest.main()
