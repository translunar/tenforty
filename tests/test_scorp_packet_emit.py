"""End-to-end CA S-corp packet emit tests.

Drives ReturnOrchestrator.run_full_california_scorp_return over each supported
CA S-corp year: compute the 100S waterfall, emit Form 100S + one Schedule K-1
(100S) per shareholder, reopen the real filled PDFs, and assert /V read-back of
the distinctive injected + computed values (identity, franchise tax, K-1
ordinary income). Native throughout (no soffice): the 100S/K-1 compute is spine
math and the emit is a straight PdfFiller fill against the committed templates.
"""
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty import years
from tenforty.mappings.pdf_f100s import PdfF100S
from tenforty.mappings.pdf_f100s_k1 import PdfF100SK1
from tenforty.mappings.pdf_f1120s import PdfF1120S
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario


def _with_ca(scenario, first_year=False):
    scenario.s_corp_return.ca = SCorpCAInputs(
        first_year=first_year,
        estimated_tax_payments=0.0,
        prior_year_overpayment_applied=0.0,
        state_tax_deducted_federally=0.0,
        depreciation_adjustment=0.0,
        apportionment_ca_only=True,
    )
    return scenario


def _read_v(pdf_path: Path, field_path: str) -> str:
    """Read one AcroForm field's /V by its full path, normalizing the
    thousands-comma and dollar formatting the filler applies to numerics."""
    fields = PdfReader(str(pdf_path)).get_fields() or {}
    got = fields[field_path].get("/V") or ""
    return str(got).replace(",", "").replace("$", "").strip()


class CaScorpPacketEmitTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_ca_scorp_packet_emits_every_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                s = _with_ca(_make_v1_scenario(
                    gross_receipts=100000.0, compensation_of_officers=30000.0))
                s.config.year = year
                out_dir = Path(self._tmp.name) / f"out_{year}"
                results, emitted = self.orch.run_full_california_scorp_return(
                    s, out_dir)

                f100s_path = out_dir / f"f100s_{year}.pdf"
                k1_path = out_dir / f"f100s_k1_1_{year}.pdf"
                self.assertTrue(f100s_path.exists())
                self.assertTrue(k1_path.exists())
                self.assertEqual(emitted["f100s"], f100s_path)
                self.assertEqual(emitted["f100s_k1_1"], k1_path)

                f100s_map = PdfF100S.get_mapping(year)
                # (1) franchise tax — the computed line-21 amount round-trips.
                self.assertEqual(
                    int(float(_read_v(f100s_path,
                                      f100s_map["f100s_franchise_tax"]))),
                    round(float(results["f100s_franchise_tax"])),
                )
                # (1b) L26/L30 total-tax intermediates round-trip to the
                # line-21 franchise tax (v1: no credits, no other taxes).
                self.assertEqual(
                    int(float(_read_v(f100s_path,
                                      f100s_map["f100s_total_tax"]))),
                    round(float(results["f100s_franchise_tax"])),
                )
                self.assertEqual(
                    int(float(_read_v(
                        f100s_path,
                        f100s_map["f100s_total_tax_after_other_taxes"]))),
                    round(float(results["f100s_franchise_tax"])),
                )
                # (1c) L38 payments balance round-trips to total payments
                # (v1: no use tax, so L38 = L36).
                self.assertEqual(
                    int(float(_read_v(f100s_path,
                                      f100s_map["f100s_payments_balance"]))),
                    round(float(results["f100s_total_payments"])),
                )
                # (2) an identity line — the injected FEIN.
                self.assertEqual(
                    _read_v(f100s_path, f100s_map["f100s_entity_fein"]),
                    "00-0000000",
                )
                # (3) the injected corporation name.
                self.assertEqual(
                    _read_v(f100s_path, f100s_map["f100s_entity_name"]),
                    "Example S-Corp Inc.",
                )

                k1_map = PdfF100SK1.get_mapping(year)
                self.assertEqual(
                    int(float(_read_v(
                        k1_path, k1_map["k1_federal_ordinary_income"]))),
                    70000,
                )
                self.assertEqual(
                    _read_v(k1_path, k1_map["k1_shareholder_name"]),
                    "Taxpayer A",
                )

    def test_no_ca_block_emits_nothing(self):
        # s_corp_return set but no .ca sub-block -> not a CA S-corp packet.
        s = _make_v1_scenario()
        self.assertIsNone(s.s_corp_return.ca)
        out_dir = Path(self._tmp.name) / "no_ca"
        results, emitted = self.orch.run_full_california_scorp_return(s, out_dir)
        self.assertEqual(results, {})
        self.assertEqual(emitted, {})
        self.assertFalse(
            (out_dir / f"f100s_{s.config.year}.pdf").exists())

    def test_federal_2021_slice_emits(self):
        # 2021 is an S-corp-only federal year (spec §4: no 1040 spine), so the
        # corporate set is emitted via the extracted corporate-only method,
        # which does NOT run the individual 1040 pipeline.
        s = _make_v1_scenario(
            gross_receipts=100000.0, compensation_of_officers=30000.0)
        s.config.year = 2021
        corp = self.orch.compute_corporate(s)
        out_dir = Path(self._tmp.name) / "federal_2021"
        emitted = self.orch._emit_federal_corporate_pdfs_internal(
            s, corp, out_dir)

        f1120s_path = out_dir / "f1120s_2021.pdf"
        k1_path = out_dir / "f1120s_k1_1_2021.pdf"
        self.assertTrue(f1120s_path.exists())
        self.assertTrue(k1_path.exists())
        self.assertEqual(emitted["1120s"], f1120s_path)
        self.assertEqual(emitted["1120s_k1_1"], k1_path)

        f1120s_map = PdfF1120S.get_mapping(2021)
        self.assertEqual(
            int(float(_read_v(
                f1120s_path, f1120s_map["f1120s_ordinary_business_income"]))),
            70000,
        )


if __name__ == "__main__":
    unittest.main()
