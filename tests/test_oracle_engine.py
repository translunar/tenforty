"""Unit tests for SpreadsheetEngine._recalculate reliability guards (issue #23).

All tests patch subprocess.run; no real soffice invocation. Workbook paths
are synthetic empty-bytes placeholders — the tests exercise the engine's
subprocess contract, not any actual LibreOffice recalculation.
"""

import subprocess
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tenforty.oracle import engine as engine_mod
from tenforty.oracle.engine import SpreadsheetEngine


class TestRecalculateVerifiesOutput(unittest.TestCase):
    """soffice can exit 0 without creating output, or create a zero-byte
    output, when the LibreOffice profile lock
    (~/.config/libreoffice/4/.~lock.registrymodifications.xcu#) is held by
    a concurrent headless invocation. _recalculate must detect both at the
    engine boundary, not leak silently into openpyxl three calls downstream."""

    def test_raises_when_returncode_zero_but_output_missing(self) -> None:
        engine = SpreadsheetEngine()
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch("tenforty.oracle.engine.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout="",
                    stderr="Warning: profile locked",
                )
                with self.assertRaises(RuntimeError) as cm:
                    engine._recalculate(workbook, work_dir)
        msg = str(cm.exception)
        self.assertIn("soffice", msg.lower())
        self.assertIn("profile locked", msg)
        self.assertIn(str(work_dir / "recalculated" / "1040.xlsx"), msg)

    def test_raises_when_output_is_zero_bytes(self) -> None:
        """A zero-byte or truncated xlsx passes .exists() but dies in
        openpyxl.load_workbook three calls downstream with a confusing
        BadZipFile error. Catch it at the engine."""
        engine = SpreadsheetEngine()
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")

            def fake_run(cmd, *a, **kw):
                outdir_idx = cmd.index("--outdir") + 1
                outdir = Path(cmd[outdir_idx])
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / "1040.xlsx").write_bytes(b"")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("tenforty.oracle.engine.subprocess.run", side_effect=fake_run):
                with self.assertRaises(RuntimeError) as cm:
                    engine._recalculate(workbook, work_dir)
        self.assertIn("empty", str(cm.exception).lower())

    def test_raises_on_timeout_as_runtimeerror(self) -> None:
        """subprocess.run(..., timeout=60) raises TimeoutExpired on timeout,
        which is NOT a CalledProcessError — it bypasses the returncode check
        and would leak unwrapped. _recalculate must catch it and re-raise as
        RuntimeError so downstream code sees a uniform error type."""
        engine = SpreadsheetEngine()
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch(
                "tenforty.oracle.engine.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd=["soffice"], timeout=60),
            ):
                with self.assertRaises(RuntimeError) as cm:
                    engine._recalculate(workbook, work_dir)
        self.assertNotIsInstance(cm.exception, subprocess.TimeoutExpired)
        self.assertIn("timeout", str(cm.exception).lower())

    def test_raises_with_returncode_in_message_when_nonzero(self) -> None:
        engine = SpreadsheetEngine()
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch("tenforty.oracle.engine.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=77,
                    stdout="",
                    stderr="soffice crashed",
                )
                with self.assertRaises(RuntimeError) as cm:
                    engine._recalculate(workbook, work_dir)
        self.assertIn("77", str(cm.exception))
        self.assertIn("soffice crashed", str(cm.exception))

    def test_success_path_returns_output_path(self) -> None:
        engine = SpreadsheetEngine()
        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")

            def fake_run(cmd, *a, **kw):
                outdir_idx = cmd.index("--outdir") + 1
                outdir = Path(cmd[outdir_idx])
                outdir.mkdir(parents=True, exist_ok=True)
                (outdir / "1040.xlsx").write_bytes(b"recalculated")
                return MagicMock(returncode=0, stdout="", stderr="")

            with patch("tenforty.oracle.engine.subprocess.run", side_effect=fake_run):
                result = engine._recalculate(workbook, work_dir)
            self.assertEqual(result, work_dir / "recalculated" / "1040.xlsx")
            self.assertTrue(result.exists())
            self.assertGreater(result.stat().st_size, 0)
