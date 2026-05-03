import unittest
from pathlib import Path

from tenforty.forms.sch_ca_fods import FodsDivergences, import_fods_divergences

FIXTURES = Path(__file__).parent / "fixtures" / "sch_ca_fods"


class ImportFodsDivergencesEmptyTests(unittest.TestCase):
    def test_empty_fods_returns_empty_dataclass(self):
        result = import_fods_divergences(FIXTURES / "empty.fods")
        self.assertEqual(result, FodsDivergences(sch_ca=[], sch_d_540=[]))
