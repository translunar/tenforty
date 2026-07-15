"""Structural test for pdf_sch_1 mapping."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tests.helpers import REPO_ROOT

_TEMPLATE_2021 = REPO_ROOT / "pdfs" / "federal" / "2021" / "f1040s1.pdf"


class PdfSch1MappingTests(unittest.TestCase):
    def test_has_expected_scalars_for_2025(self):
        m = PdfSch1.get_mapping(2025)
        s = m["scalars"]
        for k in (
            "taxpayer_name",
            "taxpayer_ssn",
            "sch_1_line_5_rental_re_royalty",
            "sch_1_line_10_total_additional_income",
            "sch_1_line_26_total_adjustments",
        ):
            self.assertIn(k, s, f"missing scalar key: {k}")

    def test_has_empty_repeaters_in_v1(self):
        m = PdfSch1.get_mapping(2025)
        self.assertEqual(m["repeaters"], {})

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "No Schedule 1 PDF mapping"):
            PdfSch1.get_mapping(1999)

    def test_2023_supported_with_probed_renumbered_paths(self):
        # 2023 is a supported year; the IRS renumbered Part I, so the probed
        # 2023 paths differ from 2024's (line 7 unemployment is flat f1_10,
        # not nested in Line8a_ReadOrder; line 10 total is f1_36).
        m = PdfSch1.get_mapping(2023)["scalars"]
        self.assertEqual(m["sch_1_line_7_unemployment"],
                         "form1[0].Page1[0].f1_10[0]")
        self.assertEqual(m["sch_1_line_10_total_additional_income"],
                         "form1[0].Page1[0].f1_36[0]")


@unittest.skipUnless(_TEMPLATE_2021.exists(), "2021 Schedule 1 template not present")
class PdfSch12021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Schedule 1 template via PdfFiller with distinctive
    values, then read the cells back directly with pypdf — no soffice.

    Covers a representative subset spanning both pages, including the divergent
    line-10 total (2021 uses f1_31, not 2022's f1_36) and Part II lines.
    """

    def _fill_and_read(self, values: dict) -> dict[str, str]:
        scalars = PdfSch1.get_mapping(2021)["scalars"]
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f1040s1_2021.pdf"
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
        scalars = PdfSch1.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct Sch1 Filer",
            "taxpayer_ssn": "123-00-2021",
            "sch_1_line_1_taxable_refunds": 1_021,
            "sch_1_line_5_rental_re_royalty": 5_021,
            "sch_1_line_7_unemployment": 7_021,
            "sch_1_line_10_total_additional_income": 10_021,
            "sch_1_line_15_se_tax": 15_021,
            "sch_1_line_26_total_adjustments": 26_021,
        }
        read = self._fill_and_read(values)
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(scalars[key]), str(expected))

    def test_line_10_total_lands_at_f1_31_not_f1_36(self):
        # The divergent field: 2021's line-10 total is f1_31; 2022's f1_36 is
        # absent on the 2021 template. Assert the value lands at f1_31.
        read = self._fill_and_read(
            {"sch_1_line_10_total_additional_income": 10_021}
        )
        self.assertEqual(
            read.get("form1[0].Page1[0].f1_31[0]"),
            "10021",
            "2021 line-10 total must land at f1_31",
        )


if __name__ == "__main__":
    unittest.main()
