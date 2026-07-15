import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.helpers import REPO_ROOT

SCANNER_PATH = REPO_ROOT / "scripts" / "verify_no_personal_data.py"


def _run_scanner(config_path: Path) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    env["TENFORTY_PII_CONFIG"] = str(config_path)
    return subprocess.run(
        [sys.executable, str(SCANNER_PATH)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env=env,
    )


class TestNoPersonalData(unittest.TestCase):
    def test_verification_script_passes(self):
        """Run the personal data verification script and assert it exits cleanly."""
        result = subprocess.run(
            [sys.executable, str(SCANNER_PATH)],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            result.returncode, 0,
            f"Personal data check failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_missing_config_fails_closed(self):
        """A missing config file must fail the scan, not warn-and-pass."""
        with tempfile.TemporaryDirectory() as tmp:
            missing_path = Path(tmp) / "does_not_exist.yaml"
            result = _run_scanner(missing_path)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                result.returncode, 0,
                f"Missing config should fail closed:\n{combined}",
            )
            self.assertIn(str(missing_path), combined)
            self.assertIn("cp ", combined)
            self.assertIn(str(missing_path), combined.split("cp ", 1)[1])

    def test_empty_config_fails_closed(self):
        """A 0-byte config file must fail the scan."""
        with tempfile.TemporaryDirectory() as tmp:
            empty_path = Path(tmp) / "empty.yaml"
            empty_path.write_text("")
            result = _run_scanner(empty_path)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                result.returncode, 0,
                f"Empty config should fail closed:\n{combined}",
            )
            self.assertIn(str(empty_path), combined)

    def test_malformed_config_fails_closed(self):
        """Malformed YAML in the config must fail the scan."""
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "malformed.yaml"
            bad_path.write_text("denylist_patterns: [unterminated\n  - foo\n:::bad")
            result = _run_scanner(bad_path)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                result.returncode, 0,
                f"Malformed config should fail closed:\n{combined}",
            )
            self.assertIn(str(bad_path), combined)

    def test_non_mapping_config_fails_closed(self):
        """Config that parses to a non-mapping (e.g. a YAML list) must fail closed."""
        with tempfile.TemporaryDirectory() as tmp:
            list_path = Path(tmp) / "list.yaml"
            list_path.write_text("- one\n- two\n")
            result = _run_scanner(list_path)
            combined = result.stdout + result.stderr
            self.assertNotEqual(
                result.returncode, 0,
                f"Non-mapping config should fail closed:\n{combined}",
            )
            self.assertIn(str(list_path), combined)

    def test_valid_empty_denylist_passes(self):
        """A present, parseable config with an empty denylist_patterns list must pass."""
        with tempfile.TemporaryDirectory() as tmp:
            valid_path = Path(tmp) / "valid.yaml"
            valid_path.write_text("denylist_patterns: []\n")
            result = _run_scanner(valid_path)
            combined = result.stdout + result.stderr
            self.assertEqual(
                result.returncode, 0,
                f"Valid config with empty denylist should pass:\n{combined}",
            )
