"""Schedule C mapping: key coverage, fixed checkboxes, fill round-trip."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import sch_c
from tenforty.mappings.pdf_sch_c import PdfSchC
from tests.helpers import REPO_ROOT

_P1 = "topmostSubform[0].Page1[0]"
_CASH_BOX = f"{_P1}.c1_1[0]"
_MATERIAL_PARTICIPATION_YES_BOX = f"{_P1}.c1_2[0]"
_LINE_32A_BOX = "topmostSubform[0].Page1[0].c1_7[0]"  # literal on purpose


class PdfSchCMappingTests(unittest.TestCase):
    def test_every_expense_field_is_mapped_in_every_year(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            mapping = PdfSchC.get_mapping(year)
            for field_name in sch_c._EXPENSE_FIELDS:
                with self.subTest(year=year, field=field_name):
                    self.assertIn(f"sch_c_expense_{field_name}", mapping)
            # 24 + Part V row 1 (description, amount).
            self.assertEqual(len(mapping), 26)
            self.assertIn("sch_c_part_v_row_1_description", mapping)
            self.assertIn("sch_c_part_v_row_1_amount", mapping)
            for key in ("sch_c_line_1_gross_receipts",
                        "sch_c_line_3_net_receipts",
                        "sch_c_line_5_gross_profit",
                        "sch_c_line_48_total_other_expenses"):
                self.assertIn(key, mapping)

    def test_2021_is_mapped_with_its_own_header_wrapper(self):
        self.assertIn(2021, years.SCHEDULE_C_FAMILY_YEARS)
        m2021 = PdfSchC.get_mapping(2021)
        m2022 = PdfSchC.get_mapping(2022)
        # The 2021 template nests the proprietor name under PgHeader[0];
        # 2022-2023 use Pg1Header[0]. Nothing else differs.
        self.assertEqual(
            m2021["taxpayer_name"], f"{_P1}.PgHeader[0].f1_1[0]")
        self.assertEqual(
            {k for k in m2022 if m2021[k] != m2022[k]}, {"taxpayer_name"})
        self.assertEqual(set(m2021), set(m2022))
        # "Other expenses (from line 48)" is line 27a on the 2021 form.
        self.assertEqual(
            m2021["sch_c_expense_other_expenses"],
            f"{_P1}.Lines18-27[0].f1_39[0]")

    def test_a_year_before_the_family_floor_is_unmapped(self):
        below = years.SCHEDULE_C_FAMILY_YEARS[0] - 1
        with self.assertRaises(ValueError):
            PdfSchC.get_mapping(below)
        with self.assertRaises(ValueError):
            PdfSchC.get_derivations(below)

    def test_fixed_checkboxes_are_cash_and_material_participation_yes(self):
        self.assertEqual(
            {years.POLICY_YEAR_FLOORS[f] for f in ("sch_c", "sch_se", "sch_2")},
            {years.SCHEDULE_C_FAMILY_YEARS[0]})
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                d = PdfSchC.get_derivations(year)
                self.assertEqual(set(d), {_CASH_BOX,
                                          _MATERIAL_PARTICIPATION_YES_BOX,
                                          _LINE_32A_BOX})
                self.assertEqual(d[_CASH_BOX]({}), "/1")
                self.assertEqual(d[_MATERIAL_PARTICIPATION_YES_BOX]({}), "/Yes")

    def test_line_32a_box_is_marked_only_for_a_loss_business(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                box = PdfSchC.get_derivations(year)[_LINE_32A_BOX]
                self.assertEqual(
                    box({"sch_c_line_32a_all_investment_at_risk": True}), "/1")
                self.assertIsNone(box({}))

    def test_fill_round_trip_lands_values_and_checks_boxes(self):
        values = {
            "taxpayer_name": "Example Filer", "taxpayer_ssn": "000-00-0000",
            "sch_c_line_a_description": "Synthetic Consulting",
            "sch_c_line_b_business_code": "541990",
            "sch_c_line_1_gross_receipts": 9000,
            "sch_c_line_3_net_receipts": 9000,
            "sch_c_line_5_gross_profit": 9000,
            "sch_c_line_7_gross_income": 9000,
            "sch_c_expense_supplies": 1000.0,
            "sch_c_line_28_total_expenses": 1000,
            "sch_c_line_29_tentative_profit": 8000,
            "sch_c_line_31_net_profit": 8000,
        }
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "sch_c.pdf"
                mapping = PdfSchC.get_mapping(year)
                PdfFiller().fill(
                    template_path=(REPO_ROOT / "pdfs" / "federal" / str(year)
                                   / "f1040sc.pdf"),
                    output_path=out, field_mapping=mapping, values=values,
                    derivations=PdfSchC.get_derivations(year),
                )
                fields = PdfReader(str(out)).get_fields()

                def v(path):
                    return str(fields[path].get("/V") or "")

                self.assertEqual(v(mapping["taxpayer_name"]), "Example Filer")
                self.assertEqual(v(mapping["taxpayer_ssn"]), "000-00-0000")
                self.assertEqual(v(mapping["sch_c_line_31_net_profit"]), "8000")
                self.assertEqual(v(mapping["sch_c_expense_supplies"]), "1000")
                self.assertEqual(
                    v(mapping["sch_c_line_1_gross_receipts"]), "9000")
                self.assertEqual(
                    v(mapping["sch_c_line_48_total_other_expenses"]), "")
                self.assertEqual(
                    v(mapping["sch_c_line_b_business_code"]), "541990")
                self.assertEqual(v(_CASH_BOX), "/1")
                self.assertEqual(v(_MATERIAL_PARTICIPATION_YES_BOX), "/Yes")
                # An unsupplied expense stays blank.
                self.assertEqual(v(mapping["sch_c_expense_travel"]), "")


if __name__ == "__main__":
    unittest.main()
