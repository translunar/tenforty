import shutil
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator

REPO_ROOT = Path(__file__).parent.parent
TEMPLATE = REPO_ROOT / "tests" / "fixtures" / "sch_ca_fods" / "single_tab_subtraction.fods"


class AutoDiscoverFodsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_basename_ca_fods_is_loaded_when_present(self):
        federal_yaml = self.tmp / "main.yaml"
        federal_yaml.write_text("# placeholder; not loaded for this unit test\n")
        ca_fods = self.tmp / "main.ca.fods"
        shutil.copy(TEMPLATE, ca_fods)
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )
        result = orchestrator.discover_fods_divergences(federal_yaml)
        self.assertEqual(len(result.sch_ca), 1)
        self.assertEqual(result.sch_ca[0].sch_ca_line, "Part I §A 2")
        self.assertEqual(result.sch_d_540, [])

    def test_no_fods_returns_empty_dataclass(self):
        federal_yaml = self.tmp / "main.yaml"
        federal_yaml.write_text("# placeholder\n")
        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )
        result = orchestrator.discover_fods_divergences(federal_yaml)
        self.assertEqual(result.sch_ca, [])
        self.assertEqual(result.sch_d_540, [])
