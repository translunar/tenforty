import os
import subprocess
import sys
import unittest


class OracleGateTests(unittest.TestCase):
    def _collect(self, args, with_flag):
        env = {k: v for k, v in os.environ.items() if k != "TENFORTY_ORACLE_OK"}
        if with_flag:
            env["TENFORTY_ORACLE_OK"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "pytest", *args, "--collect-only", "-q"],
            capture_output=True, text=True, env=env)

    def test_oracle_collection_blocked_without_flag(self):
        # No -m filter: the oracle-marked test stays selected -> gate must fire.
        r = self._collect(["tests/test_f1040_spine_oracle.py"], with_flag=False)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("TENFORTY_ORACLE_OK", r.stdout + r.stderr)

    def test_oracle_collection_allowed_with_flag(self):
        r = self._collect(["tests/test_f1040_spine_oracle.py"], with_flag=True)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)

    def test_non_oracle_collection_unaffected(self):
        r = self._collect(["tests/test_years_manifest.py"], with_flag=False)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)

    def test_not_oracle_selector_passes_without_flag(self):
        # -m "not oracle" DESELECTS the oracle test -> no selected oracle item -> gate stays quiet.
        r = self._collect(["tests/test_f1040_spine_oracle.py", "-m", "not oracle"], with_flag=False)
        self.assertEqual(r.returncode, 0, msg=r.stdout + r.stderr)
