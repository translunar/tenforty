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


if __name__ == "__main__":
    unittest.main()
