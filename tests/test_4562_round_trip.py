"""End-to-end: fill a 4562 PDF, reread it, assert every filled field matches.

Exercises forms.f4562.compute → Pdf4562 mapping → PdfFiller round-trip.
Covers the one concrete v1 scenario (single 27.5-yr rental) and a
multi-class scenario (rental + laptop) that hits two different 19x rows.
"""

import unittest
from datetime import date
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.forms import f4562 as form_f4562
from tenforty.mappings.pdf_4562 import Pdf4562
from tenforty.models import DepreciableAsset
from tests.helpers import make_simple_scenario


REPO_ROOT = Path(__file__).resolve().parents[1]
PDF_TEMPLATE = REPO_ROOT / "pdfs" / "federal" / "2025" / "f4562.pdf"


def _one_rental_scenario():
    s = make_simple_scenario()
    s.config.first_name = "Round"
    s.config.last_name = "Trip"
    s.config.ssn = "000-00-0000"
    s.config.year = 2025
    s.depreciable_assets = [
        DepreciableAsset(
            description="Evans Ave",
            date_placed_in_service=date(2025, 1, 15),
            basis=200_000.0,
            recovery_class="27.5-year",
            convention="mid-month",
        ),
    ]
    return s


class F4562RoundTripTests(unittest.TestCase):
    def test_one_rental_fills_19i_and_line_22(self):
        import tempfile
        scenario = _one_rental_scenario()
        values = form_f4562.compute(scenario, upstream={})
        mapping = Pdf4562.get_mapping(2025)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f4562_round_trip.pdf"
            PdfFiller().fill_with_repeaters(
                template_path=PDF_TEMPLATE,
                output_path=out,
                mapping=mapping,
                values=values,
            )
            self.assertTrue(out.exists())

            fields = PdfReader(str(out)).get_fields()
            s = mapping["scalars"]
            self.assertEqual(fields[s["taxpayer_name"]]["/V"], "Round Trip")
            self.assertEqual(fields[s["taxpayer_ssn"]]["/V"], "000-00-0000")
            self.assertEqual(
                fields[s["f4562_line_22_total_depreciation"]]["/V"], "6970",
            )
            self.assertEqual(
                fields[s["f4562_line_19i_date_placed_in_service"]]["/V"],
                "01/2025",
            )
            self.assertEqual(
                fields[s["f4562_line_19i_basis"]]["/V"], "200000",
            )
            self.assertEqual(
                fields[s["f4562_line_19i_recovery_period"]]["/V"], "27.5 yrs.",
            )
            self.assertEqual(
                fields[s["f4562_line_19i_convention"]]["/V"], "MM",
            )
            self.assertEqual(fields[s["f4562_line_19i_method"]]["/V"], "S/L")
            self.assertEqual(
                fields[s["f4562_line_19i_deduction"]]["/V"], "6970",
            )

    def test_rental_plus_laptop_fills_19b_and_19i(self):
        import tempfile
        scenario = _one_rental_scenario()
        scenario.depreciable_assets.append(
            DepreciableAsset(
                description="Laptop",
                date_placed_in_service=date(2025, 3, 1),
                basis=2_500.0,
                recovery_class="5-year",
                convention="half-year",
            ),
        )
        values = form_f4562.compute(scenario, upstream={})
        mapping = Pdf4562.get_mapping(2025)

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f4562_round_trip_multi.pdf"
            PdfFiller().fill_with_repeaters(
                template_path=PDF_TEMPLATE,
                output_path=out,
                mapping=mapping,
                values=values,
            )
            fields = PdfReader(str(out)).get_fields()
            s = mapping["scalars"]
            self.assertEqual(fields[s["f4562_line_19b_basis"]]["/V"], "2500")
            self.assertEqual(fields[s["f4562_line_19b_deduction"]]["/V"], "500")
            self.assertEqual(fields[s["f4562_line_19b_method"]]["/V"], "200DB")
            self.assertEqual(fields[s["f4562_line_19i_basis"]]["/V"], "200000")
            self.assertEqual(
                fields[s["f4562_line_22_total_depreciation"]]["/V"], "7470",
            )


if __name__ == "__main__":
    unittest.main()
