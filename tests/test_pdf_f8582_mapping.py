"""PDF field mapping for Form 8582 — scalars in v1."""

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_f8582 import PdfF8582
from tenforty.models import RentalProperty, ScheduleK1
from tenforty.orchestrator import ReturnOrchestrator

from tests.helpers import REPO_ROOT, make_k1_scenario, needs_libreoffice, needs_pdf


class PdfF8582MappingTests(unittest.TestCase):
    def test_has_2025_mapping(self):
        mapping = PdfF8582.get_mapping(2025)
        self.assertIn("scalars", mapping)
        for key in (
            "f8582_line_1a_activities_with_income",
            "f8582_line_1b_activities_with_loss",
            "f8582_line_1c_prior_year_unallowed_loss",
            "f8582_line_1d_combine",
            "f8582_line_11_allowed_loss",
            "taxpayer_name",
            "taxpayer_ssn",
        ):
            self.assertIn(key, mapping["scalars"])

    def test_raises_for_unknown_year(self):
        with self.assertRaises(ValueError):
            PdfF8582.get_mapping(1999)

    def test_2021_inherits_2022_payload(self):
        # 2021 field tree is diff_pdf_fields-IDENTICAL to 2022.
        self.assertIs(PdfF8582.get_mapping(2021), PdfF8582.get_mapping(2022))


@unittest.skipUnless(
    (REPO_ROOT / "pdfs/federal/2021/f8582.pdf").exists(),
    "2021 Form 8582 template not present",
)
class PdfF85822021EmitRoundTripTests(unittest.TestCase):
    """Fill the real 2021 Form 8582 template with distinctive values and read
    the cells back directly with pypdf — no soffice."""

    def test_distinctive_values_round_trip(self):
        scalars = PdfF8582.get_mapping(2021)["scalars"]
        values = {
            "taxpayer_name": "Distinct 8582 Filer",
            "taxpayer_ssn": "333-00-2021",
            "f8582_line_1a_activities_with_income": 15_000,
            "f8582_line_1b_activities_with_loss": 26_000,
            "f8582_line_11_allowed_loss": 37_000,
        }
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "f8582_2021.pdf"
            PdfFiller().fill(
                template_path=REPO_ROOT / "pdfs/federal/2021/f8582.pdf",
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


@needs_libreoffice
class PdfF8582RoundTripTests(unittest.TestCase):
    @unittest.skipUnless(
        (REPO_ROOT / "pdfs/federal/2025/f8582.pdf").exists(),
        "f8582 template not present",
    )
    def test_emit_produces_nonempty_pdf(self):
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Example LLC", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
            net_rental_real_estate=-30_000.0,
        )]
        s.rental_properties = [RentalProperty(
            address="1 Test St", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=5_000.0, mortgage_interest=2_000.0,
        )]
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results = orch.compute_federal(s)
            emitted = orch.emit_pdfs(s, results, Path(tmp))
            self.assertIn("f8582", emitted)
            self.assertGreater(emitted["f8582"].stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
