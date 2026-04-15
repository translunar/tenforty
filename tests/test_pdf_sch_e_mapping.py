"""Static structure tests for the Schedule E PDF field mapping."""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_sch_e import PdfSchE

SCH_E_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040se.pdf"
)

_REQUIRED_SCALARS = (
    "taxpayer_name", "taxpayer_ssn",
    "sch_e_property_a_address",
    "sch_e_property_a_type_code",
    "sch_e_property_a_fair_rental_days",
    "sch_e_property_a_personal_use_days",
    "sch_e_property_a_rents",
    "sch_e_property_a_total_expenses",
    "sch_e_property_a_income_loss",
)


class PdfSchEStructureTests(unittest.TestCase):
    def test_2025_has_property_a_scalars(self):
        m = PdfSchE.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_SCALARS:
            self.assertIn(k, scalars, f"missing scalar: {k}")

    def test_2025_has_empty_repeaters_v1(self):
        m = PdfSchE.get_mapping(2025)
        self.assertEqual(m.get("repeaters", {}), {})

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_E_TEMPLATE.exists():
            self.skipTest(f"Sch E template not available at {SCH_E_TEMPLATE}")
        reader = PdfReader(str(SCH_E_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        for key, pdf_field in PdfSchE.get_mapping(2025)["scalars"].items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040se.pdf",
            )

    def test_2025_scalar_values_are_unique(self):
        values = list(PdfSchE.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchE mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule E"):
            PdfSchE.get_mapping(1999)


if __name__ == "__main__":
    unittest.main()
