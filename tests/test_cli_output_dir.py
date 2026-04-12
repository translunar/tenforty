"""Tests for the --output-dir CLI flag and argparse wiring."""

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tenforty.__main__ import main


REPO_ROOT = Path(__file__).parent.parent


class TestArgparseWiring(unittest.TestCase):
    """Verify argparse arg parsing without hitting the engine."""

    def test_missing_scenario_exits_nonzero(self):
        with patch.object(sys, "argv", ["tenforty"]):
            with self.assertRaises(SystemExit) as ctx:
                main()
            self.assertNotEqual(ctx.exception.code, 0)

    def test_scenario_not_found_returns_1(self):
        with patch.object(sys, "argv", ["tenforty", "/nonexistent/path/scenario.yaml"]):
            result = main()
        self.assertEqual(result, 1)

    def test_output_dir_flag_calls_emit_pdfs(self):
        """When --output-dir is passed, emit_pdfs should be called."""
        tmpdir = Path(tempfile.mkdtemp())
        fake_results = {
            "total_tax": 5000,
            "total_payments": 4000,
            "wages": 60000,
            "standard_deduction": 15000,
            "schedule_a_total": 0,
            "total_deductions": 15000,
        }
        fake_scenario = MagicMock()
        fake_scenario.config.year = 2025
        fake_scenario.config.filing_status = "single"

        fake_emitted = {"4868": tmpdir / "f4868_2025.pdf"}

        # Create a dummy file so the path exists for output verification
        fake_emitted["4868"].write_bytes(b"dummy")

        with patch.object(sys, "argv", [
            "tenforty",
            str(REPO_ROOT / "tests/fixtures/simple_w2.yaml"),
            "--spreadsheets-dir", str(REPO_ROOT / "spreadsheets"),
            "--output-dir", str(tmpdir),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario
        ), patch(
            "tenforty.__main__.ReturnOrchestrator"
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.compute_federal.return_value = fake_results
            mock_orch.emit_pdfs.return_value = fake_emitted

            captured = io.StringIO()
            with patch("sys.stdout", captured):
                result = main()

        self.assertEqual(result, 0)
        mock_orch.emit_pdfs.assert_called_once()
        output = captured.getvalue()
        self.assertIn("=== Emitted PDFs ===", output)
        self.assertIn("4868", output)

    def test_no_output_dir_skips_emit_pdfs(self):
        """When --output-dir is not passed, emit_pdfs should NOT be called."""
        fake_results = {
            "total_tax": 5000,
            "total_payments": 4000,
            "wages": 60000,
            "standard_deduction": 15000,
            "schedule_a_total": 0,
            "total_deductions": 15000,
        }
        fake_scenario = MagicMock()
        fake_scenario.config.year = 2025
        fake_scenario.config.filing_status = "single"

        with patch.object(sys, "argv", [
            "tenforty",
            str(REPO_ROOT / "tests/fixtures/simple_w2.yaml"),
        ]), patch(
            "tenforty.__main__.load_scenario", return_value=fake_scenario
        ), patch(
            "tenforty.__main__.ReturnOrchestrator"
        ) as MockOrchestrator:
            mock_orch = MockOrchestrator.return_value
            mock_orch.compute_federal.return_value = fake_results

            with patch("sys.stdout", io.StringIO()):
                result = main()

        self.assertEqual(result, 0)
        mock_orch.emit_pdfs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
