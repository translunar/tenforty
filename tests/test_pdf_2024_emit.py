"""End-to-end test: emit a 2024 federal PDF packet.

Verifies that the 2024 PDF field mappings are wired up and the orchestrator
can produce a filled 1040 PDF for a canonical 2024 wage+investment+rental
scenario.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental_2024


class Emit2024Tests(unittest.TestCase):
    def test_emits_2024_federal_packet(self):
        scenario = build_canonical_wage_investment_rental_2024()
        with tempfile.TemporaryDirectory() as tmp:
            orch = ReturnOrchestrator(
                spreadsheets_dir=REPO_ROOT / "spreadsheets",
                work_dir=Path(tmp),
            )
            results, emitted = orch.run_full_return(scenario, Path(tmp))
            self.assertIn("1040", emitted)
            self.assertTrue(emitted["1040"].exists())
