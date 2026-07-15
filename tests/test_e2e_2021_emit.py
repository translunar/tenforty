"""End-to-end orchestrator emit for a 2021 return (federal-2021-emit Task 4).

A single-filer 2021 battery scenario — wages + interest + qualified dividends +
LTCG + rental — runs the FULL native pipeline (``run_full_return``) and emits a
PDF for every form the scenario should file. The scenario clears the EIC
scope-gate (wages $150k), so ``_compute_1040_pipeline`` routes to the native
spine, NOT the soffice workbook fallback — no LibreOffice needed.

The read-backs reopen the REAL filled PDFs and pull distinctive values:
  - a per-form fill (1040 line 1 wages; Sch B interest/dividend totals), and
  - a CROSS-FORM roll-up (the rental net income lands on Sch E line 26, rolls
    onto Sch 1 line 5, aggregates into Sch 1 line 10, and surfaces on 1040
    line 8) — catching cross-form key WIRING, not just per-form fill.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.mappings.pdf_sch_1 import PdfSch1
from tenforty.mappings.pdf_sch_b import PdfSchB
from tenforty.mappings.pdf_sch_e import PdfSchE
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental

REPO_ROOT = Path(__file__).parent.parent


def _read_v(pdf_path, field_path):
    """Read one AcroForm field's /V, normalizing thousands-comma / dollar."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


class E2E2021EmitTests(unittest.TestCase):
    """2021 canonical scenario → native full-return emit + PDF read-backs."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls._tmp.name)
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=tmp / "work",
        )
        cls.scenario = build_canonical_wage_investment_rental(2021)
        cls.out = tmp / "packet"
        cls.results, cls.emitted = orch.run_full_return(cls.scenario, cls.out)

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_emits_a_pdf_for_every_should_file_form(self):
        """The canonical scenario files 1040 + Sch 1 (rental) + Sch B (interest
        + dividends >= $1,500) + Sch D (1099-B) + Sch E (rental); the always-on
        4868 rides along. Each has a real, non-empty PDF on disk."""
        expected = {
            "f1040_2021.pdf",
            "f1040s1_2021.pdf",
            "f1040sb_2021.pdf",
            "f1040sd_2021.pdf",
            "f1040se_2021.pdf",
            "f4868_2021.pdf",
        }
        for name in sorted(expected):
            with self.subTest(form=name):
                pdf = self.out / name
                self.assertTrue(pdf.exists(), f"missing {name}")
                self.assertGreater(pdf.stat().st_size, 0)
        # The emit map's form set matches what landed on disk.
        self.assertEqual(
            set(self.emitted), {"1040", "4868", "sch_1", "sch_b", "sch_d", "sch_e"})

    def test_reads_back_1040_wage_line(self):
        """1040 line 1 wages (2021 single-box f1_28) carries the $150k W-2 box 1."""
        mapping = Pdf1040.get_mapping(2021)
        self.assertEqual(
            int(float(_read_v(self.out / "f1040_2021.pdf", mapping["wages"]))),
            150_000)

    def test_reads_back_schedule_b_totals(self):
        """Sch B totals round-trip: $2,000 interest and $5,000 ordinary dividends."""
        sb = PdfSchB.get_mapping(2021)
        pdf = self.out / "f1040sb_2021.pdf"
        self.assertEqual(
            int(float(_read_v(pdf, sb["total_interest"]))), 2_000)
        self.assertEqual(
            int(float(_read_v(pdf, sb["total_ordinary_dividends"]))), 5_000)

    def test_rental_net_income_crosses_form_boundaries(self):
        """CROSS-FORM wiring: the rental net income (rents $18,000 − mortgage
        $7,000 − taxes $2,500 − depreciation $4,500 = $4,000) lands on Sch E
        line 26, rolls onto Sch 1 line 5, aggregates into Sch 1 line 10, and
        surfaces on 1040 line 8 — the same $4,000 on all four boxes."""
        se = PdfSchE.get_mapping(2021)["scalars"]
        s1 = PdfSch1.get_mapping(2021)["scalars"]
        m1040 = Pdf1040.get_mapping(2021)

        sch_e_line26 = int(float(_read_v(
            self.out / "f1040se_2021.pdf", se["sch_e_line_26_total"])))
        sch1_line5 = int(float(_read_v(
            self.out / "f1040s1_2021.pdf", s1["sch_1_line_5_rental_re_royalty"])))
        sch1_line10 = int(float(_read_v(
            self.out / "f1040s1_2021.pdf",
            s1["sch_1_line_10_total_additional_income"])))
        f1040_line8 = int(float(_read_v(
            self.out / "f1040_2021.pdf", m1040["sch_1_line_10"])))

        self.assertEqual(sch_e_line26, 4_000)
        # The Sch E total flows onto Sch 1 line 5 (rental/royalty)...
        self.assertEqual(sch1_line5, sch_e_line26)
        # ...aggregates into Sch 1 line 10 (total additional income)...
        self.assertEqual(sch1_line10, sch_e_line26)
        # ...and surfaces on 1040 line 8 (Schedule 1 income).
        self.assertEqual(f1040_line8, sch_e_line26)


if __name__ == "__main__":
    unittest.main()
