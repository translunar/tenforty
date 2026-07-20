"""Tests for the argparse subcommand restructure (SP3-T18).

Covers four layers:
  1. In-process parser shape — drive ``_build_parser`` and call
     ``parse_args`` on synthetic argv.
  2. In-process dispatch — call ``main`` with patched ``sys.argv`` and
     verify the right orchestrator method runs.
  3. Subprocess ``--help`` smoke tests for each subcommand.
  4. Backward-compat router tests for ``_route_argv``.
"""

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pypdf

from tenforty.__main__ import _build_parser, _route_argv, main


REPO_ROOT = Path(__file__).parent.parent
SIMPLE_W2 = REPO_ROOT / "tests/fixtures/simple_w2.yaml"


class TestParserShape(unittest.TestCase):
    """Layer 1: in-process parser tests."""

    def setUp(self):
        self.parser = _build_parser()

    def test_federal_just_yaml(self):
        args = self.parser.parse_args(["federal", "foo.yaml"])
        self.assertEqual(args.subcommand, "federal")
        self.assertEqual(args.scenario, Path("foo.yaml"))
        self.assertIsNone(args.output_dir)
        self.assertEqual(args.spreadsheets_dir, Path("spreadsheets"))

    def test_federal_with_output_dir(self):
        args = self.parser.parse_args([
            "federal", "foo.yaml", "--output-dir", "/tmp/out",
        ])
        self.assertEqual(args.output_dir, Path("/tmp/out"))
        self.assertEqual(args.scenario, Path("foo.yaml"))

    def test_federal_with_spreadsheets_dir(self):
        args = self.parser.parse_args([
            "federal", "foo.yaml", "--spreadsheets-dir", "/custom/sheets",
        ])
        self.assertEqual(args.spreadsheets_dir, Path("/custom/sheets"))

    def test_ca_with_both_yamls_and_output_dir(self):
        args = self.parser.parse_args([
            "ca", "fed.yaml", "ca.yaml", "--output-dir", "/tmp/out",
        ])
        self.assertEqual(args.subcommand, "ca")
        self.assertEqual(args.federal_scenario, Path("fed.yaml"))
        self.assertEqual(args.ca_scenario, Path("ca.yaml"))
        self.assertEqual(args.output_dir, Path("/tmp/out"))

    def test_ca_with_only_federal_yaml_defaults_ca_scenario_to_none(self):
        args = self.parser.parse_args([
            "ca", "fed.yaml", "--output-dir", "/tmp/out",
        ])
        self.assertEqual(args.federal_scenario, Path("fed.yaml"))
        self.assertIsNone(args.ca_scenario)
        self.assertEqual(args.output_dir, Path("/tmp/out"))

    def test_ca_without_output_dir_raises_systemexit(self):
        with self.assertRaises(SystemExit):
            # argparse writes its error to stderr; silence it.
            with patch("sys.stderr", io.StringIO()):
                self.parser.parse_args(["ca", "fed.yaml"])

    def test_fods_subcommand_is_retired(self):
        # Part RETIRE (spec §3): the `fods` subcommand was removed along with
        # the .ca.fods worksheet round-trip.
        with self.assertRaises(SystemExit):
            with patch("sys.stderr", io.StringIO()):
                self.parser.parse_args(["fods", "in.yaml"])


class TestDispatch(unittest.TestCase):
    """Layer 2: in-process dispatch tests."""

    def test_federal_no_output_dir_calls_compute_federal(self):
        fake_results = {
            "wages": 60000,
            "standard_deduction": 15000,
            "schedule_a_total": 0,
            "total_deductions": 15000,
        }
        fake_scenario = MagicMock()
        fake_scenario.config.year = 2025
        fake_scenario.config.filing_status = "single"

        with patch.object(sys, "argv", [
            "tenforty", "federal", str(SIMPLE_W2),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario,
        ), patch(
            "tenforty.__main__.ReturnOrchestrator",
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.compute_federal.return_value = fake_results

            with patch("sys.stdout", io.StringIO()):
                result = main()

        self.assertEqual(result, 0)
        mock_orch.compute_federal.assert_called_once_with(fake_scenario)
        mock_orch.run_full_return.assert_not_called()

    def test_federal_with_output_dir_calls_run_full_return(self):
        tmpdir = Path(tempfile.mkdtemp())
        fake_results = {
            "wages": 60000,
            "standard_deduction": 15000,
            "schedule_a_total": 0,
            "total_deductions": 15000,
        }
        fake_scenario = MagicMock()
        fake_scenario.config.year = 2025
        fake_scenario.config.filing_status = "single"
        fake_emitted = {"4868": tmpdir / "f4868_2025.pdf"}

        with patch.object(sys, "argv", [
            "tenforty", "federal", str(SIMPLE_W2),
            "--output-dir", str(tmpdir),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario,
        ), patch(
            "tenforty.__main__.ReturnOrchestrator",
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.run_full_return.return_value = (fake_results, fake_emitted)

            with patch("sys.stdout", io.StringIO()):
                result = main()

        self.assertEqual(result, 0)
        mock_orch.run_full_return.assert_called_once_with(fake_scenario, tmpdir)
        mock_orch.compute_federal.assert_not_called()

    def test_ca_dispatches_to_run_full_california_return(self):
        tmpdir = Path(tempfile.mkdtemp())
        fed_yaml = tmpdir / "alice_2025.yaml"
        ca_yaml = tmpdir / "alice_2025.ca.yaml"
        fed_yaml.write_text("placeholder")
        ca_yaml.write_text("placeholder")
        out_dir = tmpdir / "out"
        out_dir.mkdir()

        fake_scenario = MagicMock()
        fake_scenario.config.year = 2025
        fake_scenario.config.filing_status = "single"
        fake_results = {"f540_total_liability": 0}
        f540_pdf = out_dir / "f540.pdf"
        _writer = pypdf.PdfWriter()
        _writer.add_blank_page(width=72, height=72)
        with open(f540_pdf, "wb") as _f:
            _writer.write(_f)
        _writer.close()
        fake_emitted = {"f540": f540_pdf}

        with patch.object(sys, "argv", [
            "tenforty", "ca", str(fed_yaml),
            "--output-dir", str(out_dir),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario,
        ), patch(
            "tenforty.__main__.ReturnOrchestrator",
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.run_full_california_return.return_value = (
                fake_results, fake_emitted,
            )

            with patch("sys.stdout", io.StringIO()):
                result = main()

        self.assertEqual(result, 0)
        mock_orch.run_full_california_return.assert_called_once()
        kwargs = mock_orch.run_full_california_return.call_args.kwargs
        self.assertEqual(kwargs["scenario"], fake_scenario)
        self.assertEqual(kwargs["ca_yaml_path"], ca_yaml)
        self.assertEqual(kwargs["output_dir"], out_dir)

    def test_ca_inferred_path_missing_returns_1(self):
        tmpdir = Path(tempfile.mkdtemp())
        fed_yaml = tmpdir / "alice_2025.yaml"
        fed_yaml.write_text("placeholder")
        # Note: no alice_2025.ca.yaml created — inferred path must not exist.
        out_dir = tmpdir / "out"
        out_dir.mkdir()

        fake_scenario = MagicMock()

        captured_err = io.StringIO()
        with patch.object(sys, "argv", [
            "tenforty", "ca", str(fed_yaml),
            "--output-dir", str(out_dir),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario,
        ), patch(
            "tenforty.__main__.ReturnOrchestrator",
        ) as MockOrchestrator:
            with patch("sys.stderr", captured_err), patch("sys.stdout", io.StringIO()):
                result = main()

        self.assertEqual(result, 1)
        err_text = captured_err.getvalue()
        inferred = str(fed_yaml.with_suffix(".ca.yaml"))
        self.assertIn(inferred, err_text)
        self.assertIn(str(fed_yaml), err_text)
        self.assertIn("CA YAML not found", err_text)
        # Orchestrator must NOT have run_full_california_return called.
        MockOrchestrator.return_value.run_full_california_return.assert_not_called()


class TestSubprocessHelp(unittest.TestCase):
    """Layer 3: subprocess --help smoke tests (one per subcommand)."""

    def _run(self, *extra_args):
        return subprocess.run(
            [sys.executable, "-m", "tenforty", *extra_args],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )

    def test_federal_help_exits_zero(self):
        result = self._run("federal", "--help")
        self.assertEqual(result.returncode, 0)

    def test_ca_help_exits_zero(self):
        result = self._run("ca", "--help")
        self.assertEqual(result.returncode, 0)


class TestBackwardCompatRouter(unittest.TestCase):
    """Layer 4: backward-compat router tests."""

    def test_top_level_help_lists_subcommands(self):
        result = subprocess.run(
            [sys.executable, "-m", "tenforty", "--help"],
            capture_output=True, text=True, cwd=str(REPO_ROOT),
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("federal", result.stdout)
        self.assertIn("ca", result.stdout)

    def test_bare_yaml_rewrites_to_federal(self):
        rewritten = _route_argv(["python", "foo.yaml"])
        explicit = _route_argv(["python", "federal", "foo.yaml"])
        self.assertEqual(rewritten, explicit)
        self.assertEqual(rewritten, ["python", "federal", "foo.yaml"])

        parser = _build_parser()
        ns_a = parser.parse_args(rewritten[1:])
        ns_b = parser.parse_args(explicit[1:])
        self.assertEqual(vars(ns_a), vars(ns_b))

    def test_explicit_federal_no_double_prepend(self):
        original = ["python", "federal", "foo.yaml"]
        rewritten = _route_argv(original)
        self.assertEqual(rewritten, original)

    def test_flag_before_positional_does_not_route(self):
        # argv[1] starts with "-" → router leaves alone → argparse complains.
        argv_in = ["python", "-o", "/tmp", "foo.yaml"]
        rewritten = _route_argv(argv_in)
        self.assertEqual(rewritten, argv_in)
        # And running through main() with this argv must SystemExit because
        # argparse cannot find a subcommand.
        parser = _build_parser()
        with self.assertRaises(SystemExit):
            with patch("sys.stderr", io.StringIO()):
                parser.parse_args(rewritten[1:])


if __name__ == "__main__":
    unittest.main()
