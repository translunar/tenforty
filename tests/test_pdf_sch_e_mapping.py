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

_REQUIRED_PART_II_SCALARS = (
    # Page 2 header
    "taxpayer_name_page2",
    "taxpayer_ssn_page2",
    # Per-row fields for all four K-1 rows
    "sch_e_part_ii_row_a_name",
    "sch_e_part_ii_row_a_ein",
    "sch_e_part_ii_row_a_entity_type_s_corp",
    "sch_e_part_ii_row_a_entity_type_partnership",
    "sch_e_part_ii_row_a_passive_income",
    "sch_e_part_ii_row_a_passive_loss",
    "sch_e_part_ii_row_a_nonpassive_income",
    "sch_e_part_ii_row_a_nonpassive_loss",
    "sch_e_part_ii_row_b_name",
    "sch_e_part_ii_row_b_ein",
    "sch_e_part_ii_row_b_passive_income",
    "sch_e_part_ii_row_b_passive_loss",
    "sch_e_part_ii_row_b_nonpassive_income",
    "sch_e_part_ii_row_b_nonpassive_loss",
    "sch_e_part_ii_row_c_name",
    "sch_e_part_ii_row_c_ein",
    "sch_e_part_ii_row_c_passive_income",
    "sch_e_part_ii_row_c_passive_loss",
    "sch_e_part_ii_row_c_nonpassive_income",
    "sch_e_part_ii_row_c_nonpassive_loss",
    "sch_e_part_ii_row_d_name",
    "sch_e_part_ii_row_d_ein",
    "sch_e_part_ii_row_d_passive_income",
    "sch_e_part_ii_row_d_passive_loss",
    "sch_e_part_ii_row_d_nonpassive_income",
    "sch_e_part_ii_row_d_nonpassive_loss",
    # Line 29 column totals
    "sch_e_line_29a_total_passive_income",
    "sch_e_line_29a_total_nonpassive_income",
    "sch_e_line_29b_total_passive_loss",
    "sch_e_line_29b_total_nonpassive_loss",
    # Line 30, 31, 32 summary
    "sch_e_line_32_total_partnership_scorp",
    # Line 37 (estate/trust, always 0 in Plan D)
    "sch_e_line_37_total_estate_trust",
    # Line 41 (total pass-through)
    "sch_e_line_41_total_pte",
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


class PdfSchEPartIIStructureTests(unittest.TestCase):
    """Tests for Part II (K-1 / pass-through) scalars added for Plan D."""

    def test_2025_has_part_ii_scalars(self):
        m = PdfSchE.get_mapping(2025)
        scalars = set(m["scalars"].keys())
        for k in _REQUIRED_PART_II_SCALARS:
            self.assertIn(k, scalars, f"missing Part II scalar: {k}")

    def test_2025_every_part_ii_value_is_a_real_pdf_field(self):
        if not SCH_E_TEMPLATE.exists():
            self.skipTest(f"Sch E template not available at {SCH_E_TEMPLATE}")
        reader = PdfReader(str(SCH_E_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        m = PdfSchE.get_mapping(2025)
        for key in _REQUIRED_PART_II_SCALARS:
            pdf_field = m["scalars"].get(key)
            self.assertIsNotNone(pdf_field, f"key {key!r} not in scalars")
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040se.pdf",
            )

    def test_2025_scalar_values_are_unique_after_part_ii_extension(self):
        """All scalars (Part I + Part II) must map to distinct PDF fields."""
        values = list(PdfSchE.get_mapping(2025)["scalars"].values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchE mapping has duplicate PDF field targets after Part II extension",
        )


if __name__ == "__main__":
    unittest.main()
