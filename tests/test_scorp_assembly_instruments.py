"""CA S-corp packet spec (Part A) and the ``scorp`` CLI subcommand (Part B).

All data synthetic. Emit is native (PdfFiller against committed templates);
no LibreOffice.
"""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pypdf

from tenforty import pdf_packet, years
from tenforty.__main__ import _build_parser, _route_argv, main
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario, set_tax_year

REPO_ROOT = Path(__file__).parent.parent


def _make_pdf(path: Path, num_pages: int) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)
    writer.close()
    return path


def _ca_scorp_scenario(year: int, pcts=None):
    s = _make_v1_scenario(shareholder_pcts=pcts)
    s.s_corp_return.ca = SCorpCAInputs(
        first_year=False,
        estimated_tax_payments=0.0,
        prior_year_overpayment_applied=0.0,
        state_tax_deducted_federally=0.0,
        depreciation_adjustment=0.0,
        apportionment_ca_only=True,
    )
    return set_tax_year(s, year)


class CaCorporatePacketSpecTests(unittest.TestCase):
    def test_f100s_main_form_is_claimed_by_ca_corporate(self):
        self.assertEqual(
            pdf_packet.classify_key("f100s"), "california_corporate")

    def test_k1_family_keys_are_claimed_by_ca_corporate(self):
        for key in ("f100s_k1_1", "f100s_k1_2", "f100s_k1_10"):
            with self.subTest(key=key):
                self.assertEqual(
                    pdf_packet.classify_key(key), "california_corporate")

    def test_federal_corporate_claims_are_undisturbed(self):
        # Neighbouring-namespace control: federal keys keep their packet.
        self.assertEqual(
            pdf_packet.classify_key("1120s_k1_1"), "federal_corporate")
        self.assertEqual(pdf_packet.classify_key("f540"), "california")

    def test_order_is_100s_first_then_k1s_numerically(self):
        emitted = {
            "f100s_k1_10": Path("/x/k1_10.pdf"),
            "f100s_k1_2": Path("/x/k1_2.pdf"),
            "f100s": Path("/x/f100s.pdf"),
            "f100s_k1_1": Path("/x/k1_1.pdf"),
        }
        packet = next(p for p in pdf_packet.PACKETS
                      if p.name == "california_corporate")
        self.assertEqual(
            [p.name for p in pdf_packet.ordered_members(emitted, packet)],
            ["f100s.pdf", "k1_1.pdf", "k1_2.pdf", "k1_10.pdf"])

    def test_assemble_all_builds_the_ca_corporate_packet(self):
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            emitted = {
                "f100s": _make_pdf(d / "a.pdf", 4),
                "f100s_k1_1": _make_pdf(d / "b.pdf", 1),
                "f100s_k1_2": _make_pdf(d / "c.pdf", 1),
            }
            combined = pdf_packet.assemble_all(emitted, d, 2025)
            self.assertEqual(list(combined), ["california_corporate"])
            self.assertEqual(
                combined["california_corporate"].name,
                "f100s_2025_complete.pdf")
            self.assertEqual(
                len(pypdf.PdfReader(str(combined["california_corporate"])).pages),
                6)

    def test_every_key_the_real_ca_scorp_emit_produces_is_claimed(self):
        with tempfile.TemporaryDirectory() as td:
            orch = ReturnOrchestrator(
                spreadsheets_dir=Path("spreadsheets"), work_dir=Path(td))
            for year in years.CA_SCORP_YEARS:
                with self.subTest(year=year):
                    s = _ca_scorp_scenario(year, pcts=[60.0, 40.0])
                    _, emitted = orch.run_full_california_scorp_return(
                        s, Path(td) / f"out_{year}")
                    # positive control: the emit really produced the keys.
                    self.assertEqual(
                        sorted(emitted), ["f100s", "f100s_k1_1", "f100s_k1_2"])
                    for key in emitted:
                        self.assertEqual(
                            pdf_packet.classify_key(key),
                            "california_corporate", key)


class ScorpParserTests(unittest.TestCase):
    def test_scorp_parses_scenario_and_output_dir(self):
        args = _build_parser().parse_args(
            ["scorp", "foo.yaml", "--output-dir", "/tmp/out"])
        self.assertEqual(args.subcommand, "scorp")
        self.assertEqual(args.scenario, Path("foo.yaml"))
        self.assertEqual(args.output_dir, Path("/tmp/out"))
        self.assertEqual(args.spreadsheets_dir, Path("spreadsheets"))

    def test_scorp_requires_output_dir(self):
        parser = _build_parser()
        # positive control: same argv plus the flag parses.
        parser.parse_args(["scorp", "foo.yaml", "--output-dir", "/tmp/out"])
        with self.assertRaises(SystemExit):
            with patch("sys.stderr", io.StringIO()):
                parser.parse_args(["scorp", "foo.yaml"])

    def test_router_leaves_scorp_alone(self):
        argv = ["python", "scorp", "foo.yaml", "--output-dir", "o"]
        self.assertEqual(_route_argv(argv), argv)

    def test_scorp_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "tenforty", "scorp", "--help"],
            capture_output=True, text=True, cwd=str(REPO_ROOT))
        self.assertEqual(result.returncode, 0)
        self.assertIn("S-corp", result.stdout)


class ScorpDispatchTests(unittest.TestCase):
    def _run(self, scenario, out_dir, fed_emitted=None, ca_emitted=None):
        with patch.object(sys, "argv", [
            "tenforty", "scorp", "s.yaml", "--output-dir", str(out_dir),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=scenario,
        ), patch("tenforty.__main__.ReturnOrchestrator") as Orch:
            orch = Orch.return_value
            orch.run_full_federal_scorp_return.return_value = (
                {}, fed_emitted or {})
            orch.run_full_california_scorp_return.return_value = (
                {}, ca_emitted or {})
            out = io.StringIO()
            with patch("sys.stdout", out), patch("sys.stderr", out):
                rc = main()
        return rc, orch, out.getvalue()

    def _scenario(self, with_ca):
        sc = MagicMock()
        sc.config.year = 2025
        sc.config.filing_status = "single"
        sc.source_documents = ()
        sc.s_corp_return.ca = MagicMock() if with_ca else None
        return sc

    def test_scorp_with_ca_drives_both_entry_points(self):
        out_dir = Path(tempfile.mkdtemp())
        sc = self._scenario(with_ca=True)
        rc, orch, _ = self._run(sc, out_dir)
        self.assertEqual(rc, 0)
        orch.run_full_federal_scorp_return.assert_called_once_with(sc, out_dir)
        orch.run_full_california_scorp_return.assert_called_once_with(
            sc, out_dir)

    def test_scorp_without_ca_block_skips_the_ca_entry_point(self):
        out_dir = Path(tempfile.mkdtemp())
        # positive control: with a CA block, the CA entry IS called.
        rc_ca, orch_ca, _ = self._run(self._scenario(True), out_dir)
        orch_ca.run_full_california_scorp_return.assert_called_once()
        sc = self._scenario(with_ca=False)
        rc, orch, _ = self._run(sc, out_dir)
        self.assertEqual(rc, 0)
        orch.run_full_federal_scorp_return.assert_called_once_with(sc, out_dir)
        orch.run_full_california_scorp_return.assert_not_called()

    def test_non_scorp_scenario_returns_1_without_emitting(self):
        out_dir = Path(tempfile.mkdtemp())
        sc = self._scenario(True)
        sc.s_corp_return = None
        rc, orch, text = self._run(sc, out_dir)
        self.assertEqual(rc, 1)
        self.assertIn("s_corp_return", text)
        orch.run_full_federal_scorp_return.assert_not_called()
        orch.run_full_california_scorp_return.assert_not_called()

    def test_both_packets_are_assembled_and_loose_files_pruned(self):
        out_dir = Path(tempfile.mkdtemp())
        fed = {
            "1120s": _make_pdf(out_dir / "f1120s_2025.pdf", 3),
            "1120s_k1_1": _make_pdf(out_dir / "f1120s_k1_1_2025.pdf", 1),
        }
        ca = {
            "f100s": _make_pdf(out_dir / "f100s_2025.pdf", 2),
            "f100s_k1_1": _make_pdf(out_dir / "f100s_k1_1_2025.pdf", 1),
        }
        rc, _, text = self._run(
            self._scenario(True), out_dir, fed_emitted=fed, ca_emitted=ca)
        self.assertEqual(rc, 0)
        fed_pkt = out_dir / "f1120s_2025_complete.pdf"
        ca_pkt = out_dir / "f100s_2025_complete.pdf"
        self.assertEqual(len(pypdf.PdfReader(str(fed_pkt)).pages), 4)
        self.assertEqual(len(pypdf.PdfReader(str(ca_pkt)).pages), 3)
        self.assertIn("federal_corporate", text)
        self.assertIn("california_corporate", text)
        # loose members consumed (positive control: they existed above).
        for path in (*fed.values(), *ca.values()):
            self.assertFalse(path.exists(), path)


class ScorpEndToEndTests(unittest.TestCase):
    """Real orchestrator + real templates through the CLI (no mocks past
    load_scenario)."""

    def test_cli_emits_both_corporate_packets(self):
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "out"
            sc = _ca_scorp_scenario(2025, pcts=[60.0, 40.0])
            with patch.object(sys, "argv", [
                "tenforty", "scorp", "s.yaml", "--output-dir", str(out_dir),
            ]), patch("tenforty.__main__.load_scenario", return_value=sc):
                with patch("sys.stdout", io.StringIO()):
                    rc = main()
            self.assertEqual(rc, 0)
            names = sorted(p.name for p in out_dir.glob("*.pdf"))
            self.assertEqual(
                names, ["f100s_2025_complete.pdf", "f1120s_2025_complete.pdf"])
            ca_pages = len(pypdf.PdfReader(
                str(out_dir / "f100s_2025_complete.pdf")).pages)
            self.assertGreaterEqual(ca_pages, 3)  # 100S + 2 K-1s


if __name__ == "__main__":
    unittest.main()
