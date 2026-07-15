"""Static structure tests for the Schedule E PDF field mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_e import PdfSchE
from tests.helpers import REPO_ROOT

SCH_E_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040se.pdf"
)

_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040se.pdf"

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


class TestPdfSchERowsSnapshot(unittest.TestCase):
    """Snapshot test for pdf_sch_e Part II row mapping (SP1-N9).

    Ensures the loop-based row generator emits the exact same PDF field names
    as the hand-written blocks so the refactor is bit-identical."""

    def test_row_a_through_d_fields(self) -> None:
        m = PdfSchE.get_mapping(2025)
        scalars = m["scalars"]
        expected = {
            # Row A
            "sch_e_part_ii_row_a_name":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].f2_3[0]",
            "sch_e_part_ii_row_a_ein":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].f2_4[0]",
            "sch_e_part_ii_row_a_entity_type_partnership":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].c2_2[0]",
            "sch_e_part_ii_row_a_entity_type_s_corp":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowA[0].c2_3[0]",
            "sch_e_part_ii_row_a_passive_loss":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_15[0]",
            "sch_e_part_ii_row_a_passive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_16[0]",
            "sch_e_part_ii_row_a_nonpassive_loss":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_17[0]",
            "sch_e_part_ii_row_a_nonpassive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowA[0].f2_19[0]",
            # Row D (spot-check stride)
            "sch_e_part_ii_row_d_name":
                "topmostSubform[0].Page2[0].Table_Line28a-f[0].RowD[0].f2_12[0]",
            "sch_e_part_ii_row_d_nonpassive_income":
                "topmostSubform[0].Page2[0].Table_Line28g-k[0].RowD[0].f2_34[0]",
        }
        for k, expected_value in expected.items():
            self.assertEqual(scalars.get(k), expected_value, f"field {k}")


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule E template not present")
class PdfSchE2021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule E template via PdfFiller with distinctive
    values, then read the cells back directly with pypdf — no soffice.

    Locks in the render-verified 2021 placements: row-A name in col (a)
    (f2_3) and EIN in col (d) (f2_5); the four LIVE line-29 totals
    (income-on-29a, loss-on-29b); and a Part I property row amount. If any
    value fails to land at its mapped path the test fails loudly — it must
    never be weakened to match the merged-2022-2025 mapping (which carries a
    separately-tracked line-28 ein/entity-type mismapping bug).
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        scalars = PdfSchE.get_mapping(2021)["scalars"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040se_2021.pdf"
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
        scalars = PdfSchE.get_mapping(2021)["scalars"]
        values = {
            # Part II row-A name (col a → f2_3) + EIN (col d → f2_5)
            "sch_e_part_ii_row_a_name": "Distinct SchE K1 Entity",
            # Non-EIN-shaped sentinel so the personal-data denylist stays clean;
            # the col-(d) cell is a free-text field, so any token round-trips.
            "sch_e_part_ii_row_a_ein": "EIN-SENTINEL-COL-D",
            # The four LIVE line-29 totals (income-on-29a, loss-on-29b)
            "sch_e_line_29a_total_passive_income": 29_101,
            "sch_e_line_29a_total_nonpassive_income": 29_102,
            "sch_e_line_29b_total_passive_loss": 29_201,
            "sch_e_line_29b_total_nonpassive_loss": 29_202,
            # A Part I property-A row field
            "sch_e_property_a_rents": 33_333,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))

    def test_row_a_name_and_ein_land_in_cols_a_and_d(self):
        # Distinct sentinels so a col-a/col-d swap is unambiguous.
        values = {
            "sch_e_part_ii_row_a_name": "NAME-COL-A",
            "sch_e_part_ii_row_a_ein": "EIN-COL-D",
        }
        read = self._fill_and_read(values)
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_3[0]"),
            "NAME-COL-A",
            "row-A name must land in f2_3 (Line 28 col (a))",
        )
        self.assertEqual(
            read.get("topmostSubform[0].Page2[0].Table_Line28a-e[0].RowA[0].f2_5[0]"),
            "EIN-COL-D",
            "row-A EIN must land in f2_5 (Line 28 col (d))",
        )


if __name__ == "__main__":
    unittest.main()
