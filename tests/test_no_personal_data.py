import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


class TestNoPersonalData(unittest.TestCase):
    def test_verification_script_passes(self):
        """Run the personal data verification script and assert it exits cleanly."""
        result = subprocess.run(
            ["python", str(REPO_ROOT / "scripts" / "verify_no_personal_data.py")],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        self.assertEqual(
            result.returncode, 0,
            f"Personal data check failed:\n{result.stdout}\n{result.stderr}",
        )
