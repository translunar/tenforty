"""Schedule SE mapping: a line the compute does not produce stays blank."""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.filing.pdf import PdfFiller
from tenforty.forms import sch_se
from tenforty.mappings.pdf_sch_se import PdfSchSe
from tests.helpers import REPO_ROOT, make_simple_scenario

# Lines the compute omits when net earnings are under $400.
_OMITTED_UNDER_THRESHOLD = (
    "sch_se_line_8a_ss_wages_and_tips",
    "sch_se_line_8d_wages_subject_to_ss",
    "sch_se_line_9_ss_earnings_remaining",
    "sch_se_line_10_ss_portion",
    "sch_se_line_11_medicare_portion",
)


class PdfSchSeBlankLineTests(unittest.TestCase):
    def test_line_7_is_never_mapped(self):
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            self.assertNotIn(
                "sch_se_line_7_ss_wage_base", PdfSchSe.get_mapping(year))

    def test_2021_shares_the_zero_padded_2022_field_tree(self):
        self.assertIn(2021, years.SCHEDULE_C_FAMILY_YEARS)
        m2021 = PdfSchSe.get_mapping(2021)
        self.assertEqual(m2021, PdfSchSe.get_mapping(2022))
        self.assertEqual(
            m2021["sch_se_line_2_net_profit"],
            "topmostSubform[0].Page1[0].f1_05[0]")
        # Read off the 2021 template itself, not inferred from 2022: the
        # zero-padded leaves exist and the unpadded ones do not.
        on_template = set(PdfReader(str(
            REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040sse.pdf"
        )).get_fields())
        self.assertIn("topmostSubform[0].Page1[0].f1_05[0]", on_template)
        self.assertNotIn("topmostSubform[0].Page1[0].f1_5[0]", on_template)

    def test_line_7_field_is_read_only_on_every_template(self):
        # The reason line 7 is unmapped: the wage base is pre-printed in a
        # read-only field (f1_13). Checked per year on the template.
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year):
                fields = PdfReader(str(
                    REPO_ROOT / "pdfs" / "federal" / str(year)
                    / "f1040sse.pdf")).get_fields()
                line_7 = fields["topmostSubform[0].Page1[0].f1_13[0]"]
                self.assertTrue(int(line_7.get("/Ff", 0)) & 1)
                self.assertNotIn(
                    "topmostSubform[0].Page1[0].f1_13[0]",
                    set(PdfSchSe.get_mapping(year).values()))

    def test_lines_absent_from_the_compute_leave_their_fields_empty(self):
        values = sch_se.compute(
            make_simple_scenario(),
            {"sch_c": {"sch_c_line_31_net_profit_total": 350.0}})
        for key in _OMITTED_UNDER_THRESHOLD:
            self.assertNotIn(key, values)
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "sch_se.pdf"
                mapping = PdfSchSe.get_mapping(year)
                PdfFiller().fill(
                    template_path=(REPO_ROOT / "pdfs" / "federal" / str(year)
                                   / "f1040sse.pdf"),
                    output_path=out, field_mapping=mapping, values=values)
                fields = PdfReader(str(out)).get_fields()
                for key in _OMITTED_UNDER_THRESHOLD:
                    self.assertFalse(
                        fields[mapping[key]].get("/V"),
                        f"{year}: {key} printed a value; expected blank")
                self.assertEqual(
                    str(fields[mapping["sch_se_line_3_net_profit"]].get("/V")),
                    "350")

    def test_line_8a_fills_its_own_field_beside_8d(self):
        from dataclasses import replace
        base = make_simple_scenario()
        scn = replace(base, w2s=[replace(base.w2s[0], ss_wages=50_000)])
        values = sch_se.compute(
            scn, {"sch_c": {"sch_c_line_31_net_profit_total": 4_100.0}})
        for year in years.SCHEDULE_C_FAMILY_YEARS:
            with self.subTest(year=year), tempfile.TemporaryDirectory() as d:
                out = Path(d) / "sch_se.pdf"
                mapping = PdfSchSe.get_mapping(year)
                PdfFiller().fill(
                    template_path=(REPO_ROOT / "pdfs" / "federal" / str(year)
                                   / "f1040sse.pdf"),
                    output_path=out, field_mapping=mapping, values=values)
                fields = PdfReader(str(out)).get_fields()
                for key in ("sch_se_line_8a_ss_wages_and_tips",
                            "sch_se_line_8d_wages_subject_to_ss"):
                    self.assertEqual(
                        str(fields[mapping[key]].get("/V")), "50000", key)


if __name__ == "__main__":
    unittest.main()
