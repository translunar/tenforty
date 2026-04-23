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


class TestRecalculateIsolatesProfile(unittest.TestCase):
    """Each soffice invocation must pass -env:UserInstallation=file://{unique}
    so concurrent invocations don't share ~/.config/libreoffice/4/ and race
    on .~lock.registrymodifications.xcu#. This is the documented LibreOffice
    mechanism for concurrent-safe headless conversion."""

    def _fake_successful_run(self, cmd, *a, **kw):
        outdir_idx = cmd.index("--outdir") + 1
        outdir = Path(cmd[outdir_idx])
        outdir.mkdir(parents=True, exist_ok=True)
        workbook_name = Path(cmd[-1]).name
        (outdir / workbook_name).write_bytes(b"ok")
        return MagicMock(returncode=0, stdout="", stderr="")

    def test_soffice_invocation_includes_userinstallation_flag(self) -> None:
        engine = SpreadsheetEngine()
        captured = []

        def capturing_run(cmd, *a, **kw):
            captured.append(list(cmd))
            return self._fake_successful_run(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch(
                "tenforty.oracle.engine.subprocess.run", side_effect=capturing_run
            ):
                engine._recalculate(workbook, work_dir)

        self.assertEqual(len(captured), 1)
        flags = [
            a for a in captured[0]
            if isinstance(a, str) and a.startswith("-env:UserInstallation=file://")
        ]
        self.assertEqual(
            len(flags), 1, f"expected one UserInstallation flag: {captured[0]}"
        )

    def test_two_invocations_use_distinct_profile_paths(self) -> None:
        engine = SpreadsheetEngine()
        captured = []

        def capturing_run(cmd, *a, **kw):
            captured.append(list(cmd))
            return self._fake_successful_run(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch(
                "tenforty.oracle.engine.subprocess.run", side_effect=capturing_run
            ):
                engine._recalculate(workbook, work_dir)
                engine._recalculate(workbook, work_dir)

        flag_1 = next(a for a in captured[0] if a.startswith("-env:UserInstallation="))
        flag_2 = next(a for a in captured[1] if a.startswith("-env:UserInstallation="))
        self.assertNotEqual(
            flag_1, flag_2,
            "each invocation must get a unique profile dir",
        )

    def test_profile_dir_is_cleaned_up_after_invocation(self) -> None:
        engine = SpreadsheetEngine()
        captured_profiles: list[Path] = []

        def capturing_run(cmd, *a, **kw):
            flag = next(a for a in cmd if a.startswith("-env:UserInstallation=file://"))
            captured_profiles.append(Path(flag.removeprefix("-env:UserInstallation=file://")))
            return self._fake_successful_run(cmd, *a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")
            with patch(
                "tenforty.oracle.engine.subprocess.run", side_effect=capturing_run
            ):
                engine._recalculate(workbook, work_dir)

        self.assertEqual(len(captured_profiles), 1)
        self.assertFalse(
            captured_profiles[0].exists(),
            "profile dir must be cleaned up by the TemporaryDirectory context manager",
        )


class TestRecalculateSerializesSoffice(unittest.TestCase):
    """Belt-and-suspenders on top of profile isolation: the module-level
    _SOFFICE_LOCK serializes soffice invocations so no two overlap in time,
    even if soffice internals expose shared state we haven't cataloged."""

    def test_module_exposes_soffice_lock(self) -> None:
        """_SOFFICE_LOCK must exist at module scope and behave like a lock
        (acquire/release + context-manager). Uses duck typing rather than an
        isinstance check against threading.Lock — the latter returns a
        factory whose concrete type varies by Python implementation."""
        self.assertTrue(hasattr(engine_mod, "_SOFFICE_LOCK"))
        lock = engine_mod._SOFFICE_LOCK
        self.assertTrue(hasattr(lock, "acquire"))
        self.assertTrue(hasattr(lock, "release"))
        with lock:
            pass  # raises if not a context manager

    def test_concurrent_recalculates_do_not_overlap(self) -> None:
        """Four threads each call _recalculate concurrently. With the lock,
        subprocess.run invocations don't overlap in time. Without it,
        max_concurrent would be 2-4."""
        engine_inst = SpreadsheetEngine()
        active = [0]
        max_concurrent = [0]
        counter_lock = threading.Lock()

        def fake_run(cmd, *a, **kw):
            with counter_lock:
                active[0] += 1
                if active[0] > max_concurrent[0]:
                    max_concurrent[0] = active[0]
            # Forces GIL release so a missing _SOFFICE_LOCK would allow
            # observable overlap; without this sleep, GIL scheduling could
            # mask a missing lock and let the test pass incorrectly.
            time.sleep(0.05)
            with counter_lock:
                active[0] -= 1
            outdir_idx = cmd.index("--outdir") + 1
            outdir = Path(cmd[outdir_idx])
            outdir.mkdir(parents=True, exist_ok=True)
            (outdir / Path(cmd[-1]).name).write_bytes(b"ok")
            return MagicMock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            workbook = work_dir / "1040.xlsx"
            workbook.write_bytes(b"")

            with patch(
                "tenforty.oracle.engine.subprocess.run", side_effect=fake_run
            ):
                threads = [
                    threading.Thread(
                        target=engine_inst._recalculate,
                        args=(workbook, work_dir),
                    )
                    for _ in range(4)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()

        self.assertEqual(
            max_concurrent[0], 1,
            "module-level lock must serialize soffice invocations",
        )
