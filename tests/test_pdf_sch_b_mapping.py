"""Static structure tests for the Schedule B PDF field mapping.

Sch B 2025 uses flat sequential field names (f1_01..f1_66) rather than
row-grouped names, so the mapping is a plain scalar dict (every
per-row slot is its own key) rather than the {scalars, repeaters}
shape used for forms with indexable row names.
"""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_sch_b import (
    PdfSchB,
    dividend_max_rows,
    interest_max_rows,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental
from tests.helpers import REPO_ROOT

SCH_B_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2025" / "f1040sb.pdf"
)

SCH_B_TEMPLATE_2021 = (
    Path(__file__).resolve().parents[1]
    / "pdfs" / "federal" / "2021" / "f1040sb.pdf"
)


class PdfSchBStructureTests(unittest.TestCase):
    def test_row_counts(self):
        # The paper's capacity: 14 interest rows every year; 16 dividend
        # rows in 2021, 15 from 2022.
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.assertEqual(interest_max_rows(year), 14)
                self.assertEqual(dividend_max_rows(year),
                                 16 if year == 2021 else 15)

    def test_2025_scalars_cover_totals_and_header(self):
        m = PdfSchB.get_mapping(2025)
        for required in (
            "taxpayer_name",
            "taxpayer_ssn",
            "total_interest",
            "excludable_savings_bond",
            "taxable_interest",
            "total_ordinary_dividends",
        ):
            self.assertIn(required, m, f"missing scalar: {required}")

    def test_2025_interest_row_slots(self):
        m = PdfSchB.get_mapping(2025)
        for i in range(1, interest_max_rows(2025) + 1):
            self.assertIn(f"interest_payer_{i}", m)
            self.assertIn(f"interest_amount_{i}", m)

    def test_dividend_row_slots_match_the_paper_each_year(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            m = PdfSchB.get_mapping(year)
            rows = sorted(int(k.rsplit("_", 1)[1]) for k in m
                          if k.startswith("dividend_payer_"))
            with self.subTest(year=year):
                self.assertEqual(rows,
                                 list(range(1, dividend_max_rows(year) + 1)))
                self.assertEqual(
                    sorted(int(k.rsplit("_", 1)[1]) for k in m
                           if k.startswith("dividend_amount_")), rows)

    def test_2022_on_line_6_is_f1_64_and_7b_is_unmapped(self):
        # 2022-2025 templates: f1_64 is the line 6 total box; f1_65 and
        # f1_66 are the Part III line 7b foreign-country fields, which no
        # key serves.
        for year in (2022, 2023, 2024, 2025):
            m = PdfSchB.get_mapping(year)
            with self.subTest(year=year):
                self.assertEqual(m["total_ordinary_dividends"],
                                 "topmostSubform[0].Page1[0].f1_64[0]")
                self.assertEqual(
                    [k for k, v in m.items()
                     if v.endswith(("f1_65[0]", "f1_66[0]"))], [])

    def test_2025_every_value_is_a_real_pdf_field(self):
        if not SCH_B_TEMPLATE.exists():
            self.skipTest(f"Sch B template not available at {SCH_B_TEMPLATE}")
        reader = PdfReader(str(SCH_B_TEMPLATE))
        real_fields = set((reader.get_fields() or {}).keys())
        m = PdfSchB.get_mapping(2025)
        for key, pdf_field in m.items():
            self.assertIn(
                pdf_field, real_fields,
                f"{key}: {pdf_field!r} is not a real PDF field on f1040sb.pdf",
            )

    def test_2025_mapping_values_are_unique(self):
        m = PdfSchB.get_mapping(2025)
        values = list(m.values())
        self.assertEqual(
            len(values), len(set(values)),
            "PdfSchB mapping has duplicate PDF field targets",
        )

    def test_unknown_year_raises(self):
        with self.assertRaisesRegex(ValueError, "Schedule B"):
            PdfSchB.get_mapping(1999)


@unittest.skipUnless(
    SCH_B_TEMPLATE_2021.exists(), "2021 Schedule B template not present"
)
class TestPdfSchB2021EmitRoundTrip(unittest.TestCase):
    """Fill the real 2021 Schedule B template — header, both totals rows, and
    a representative interest/dividend row subset — with distinctive values,
    then read the cells back directly with pypdf. No soffice."""

    def test_distinctive_values_round_trip(self) -> None:
        mapping = PdfSchB.get_mapping(2021)
        field_mapping = {
            "taxpayer_name": mapping["taxpayer_name"],
            "taxpayer_ssn": mapping["taxpayer_ssn"],
            "total_interest": mapping["total_interest"],
            "taxable_interest": mapping["taxable_interest"],
            "total_ordinary_dividends": mapping["total_ordinary_dividends"],
            "interest_payer_1": mapping["interest_payer_1"],
            "interest_amount_1": mapping["interest_amount_1"],
            "interest_payer_14": mapping["interest_payer_14"],
            "interest_amount_14": mapping["interest_amount_14"],
            "dividend_payer_1": mapping["dividend_payer_1"],
            "dividend_amount_1": mapping["dividend_amount_1"],
            "dividend_payer_16": mapping["dividend_payer_16"],
            "dividend_amount_16": mapping["dividend_amount_16"],
        }
        values = {
            "taxpayer_name": "Distinct SchB Filer",
            "taxpayer_ssn": "666-00-2021",
            "total_interest": 12_345,
            "taxable_interest": 12_300,
            "total_ordinary_dividends": 54_321,
            "interest_payer_1": "Distinct Bank Row 1",
            "interest_amount_1": 1_001,
            "interest_payer_14": "Distinct Bank Row 14",
            "interest_amount_14": 1_414,
            "dividend_payer_1": "Distinct Fund Row 1",
            "dividend_amount_1": 2_001,
            "dividend_payer_16": "Distinct Fund Row 16",
            "dividend_amount_16": 2_016,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "sch_b_2021.pdf"
            PdfFiller().fill(
                template_path=SCH_B_TEMPLATE_2021,
                output_path=out,
                field_mapping=field_mapping,
                values=values,
            )
            read = {
                name: (fld.get("/V") or "")
                for name, fld in (PdfReader(str(out)).get_fields() or {}).items()
            }
        for key, expected in values.items():
            with self.subTest(field=key):
                self.assertEqual(read.get(field_mapping[key]), str(expected))



class SchBLineSixEmitTests(unittest.TestCase):
    """The emitted 2022-2025 Schedule B prints the dividend total in the
    line 6 box and leaves the Part III line 7b fields empty."""

    def test_line_6_carries_the_total(self):
        for year in (2022, 2024, 2025):
            with tempfile.TemporaryDirectory() as tmp, \
                    self.subTest(year=year):
                orch = ReturnOrchestrator(
                    spreadsheets_dir=REPO_ROOT / "spreadsheets",
                    work_dir=Path(tmp) / "work")
                scenario = build_canonical_wage_investment_rental(year)
                results = orch.compute_federal(scenario)
                emitted = orch.emit_pdfs(scenario, results, Path(tmp) / "out")
                fields = PdfReader(str(emitted["sch_b"])).get_fields()
                page = "topmostSubform[0].Page1[0]."
                value = {n: str(fields[page + n].get("/V") or "")
                         for n in ("f1_64[0]", "f1_65[0]", "f1_66[0]")}
                self.assertEqual(value["f1_64[0]"], "5000")
                self.assertEqual(value["f1_65[0]"], "")
                self.assertEqual(value["f1_66[0]"], "")


if __name__ == "__main__":
    unittest.main()
