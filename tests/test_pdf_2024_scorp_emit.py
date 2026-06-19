"""End-to-end emit test: 2024 S-corp corporate packet.

Verifies that PdfF1120S.get_mapping(2024) and PdfF1120SK1.get_mapping(2024)
are wired and the orchestrator produces a 2024 corporate packet (Form 1120-S
+ Schedule K-1 per shareholder + combined f1120s_2024_complete.pdf).

Reuses the synthetic single-shareholder S-corp scenario from
tests._scorp_fixtures (no real entity or personal data), overriding the
tax year to 2024.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.orchestrator import ReturnOrchestrator
from tenforty import pdf_packet
from tests.helpers import REPO_ROOT
from tests._scorp_fixtures import _make_v1_scenario


def _build_synthetic_2024_scorp_scenario():
    """Reuse the shared v1 S-corp builder, retargeted to tax year 2024.

    `_make_v1_scenario()` already produces a single-shareholder S-corp with
    the full attestation set; it constructs the config with year=2025, so we
    replace the config's year with 2024. `dataclasses.replace` returns fresh
    instances and never mutates the builder's output.
    """
    scenario = _make_v1_scenario()
    return dataclasses.replace(
        scenario,
        config=dataclasses.replace(scenario.config, year=2024),
    )


class Emit2024SCorpTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.output_dir = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.output_dir / "work",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_2024_scorp_emits_corporate_packet(self):
        """run_full_return produces f1120s_2024.pdf and f1120s_k1_1_2024.pdf;
        assemble_all assembles them into f1120s_2024_complete.pdf."""
        scenario = _build_synthetic_2024_scorp_scenario()
        _results, emitted = self.orch.run_full_return(scenario, self.output_dir)

        # The orchestrator must emit the main 1120-S form.
        self.assertIn("1120s", emitted, "emitted must contain '1120s' key")
        self.assertTrue(
            emitted["1120s"].exists(),
            f"f1120s_2024.pdf was not written to {emitted.get('1120s')}",
        )

        # The orchestrator must emit one K-1 (single-shareholder scenario).
        self.assertIn("1120s_k1_1", emitted, "emitted must contain '1120s_k1_1' key")
        self.assertTrue(
            emitted["1120s_k1_1"].exists(),
            f"f1120s_k1_1_2024.pdf was not written to {emitted.get('1120s_k1_1')}",
        )

        # The packet assembler must produce the combined corporate PDF.
        combined = pdf_packet.assemble_all(emitted, self.output_dir, year=2024)
        self.assertIn(
            "federal_corporate", combined,
            "assemble_all must produce the 'federal_corporate' packet",
        )
        packet_path = combined["federal_corporate"]
        self.assertTrue(
            packet_path.exists(),
            f"f1120s_2024_complete.pdf was not written to {packet_path}",
        )
        self.assertEqual(
            packet_path.name, "f1120s_2024_complete.pdf",
            "combined corporate packet must be named f1120s_2024_complete.pdf",
        )
