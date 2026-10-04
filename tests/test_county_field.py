"""`county` scenario field: loader reads it; blank stays blank (not a gate)."""
import tempfile
import unittest
from pathlib import Path

from tenforty.scenario import load_scenario
from tests.helpers import REPO_ROOT


class CountyFieldTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.base = REPO_ROOT / "tests" / "fixtures" / "simple_w2.yaml"

    def test_loader_reads_county(self):
        path = self.tmp / "scn.yaml"
        path.write_text(self.base.read_text().replace(
            "config:\n", "config:\n  county: Synthetic County\n", 1))
        self.assertEqual(load_scenario(path).config.county, "Synthetic County")

    def test_absent_county_defaults_blank_and_loads(self):
        self.assertEqual(load_scenario(self.base).config.county, "")


if __name__ == "__main__":
    unittest.main()
