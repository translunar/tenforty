"""Emit-time gate: every W-2 needs a source document, or an attestation.

The gate lives at the packet-emit entry points ONLY. compute_federal and
load_scenario stay ungated so the compute-only corpus is unaffected.
Per the attestation-audit norm the refusal is proved to FIRE via the real
entry points — fast-tier, because the gate raises before any workbook /
LibreOffice work begins. The flag-clears / pdf-rides-along end-to-end
positive paths need the full pipeline and are oracle-tier
(@needs_libreoffice), run by the controller at acceptance.
"""

import dataclasses
import tempfile
import unittest
from pathlib import Path

import pypdf

from tenforty.models import W2
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental
from tests.helpers import REPO_ROOT, needs_libreoffice


def _make_pdf(path: Path, num_pages: int = 1) -> Path:
    writer = pypdf.PdfWriter()
    for _ in range(num_pages):
        writer.add_blank_page(width=72, height=72)
    with open(path, "wb") as f:
        writer.write(f)
    writer.close()
    return path


def _orchestrator() -> ReturnOrchestrator:
    return ReturnOrchestrator(
        spreadsheets_dir=REPO_ROOT / "spreadsheets",
        work_dir=Path(tempfile.mkdtemp()),
    )


def _no_pdf_scenario(year: int = 2024):
    scenario = build_canonical_wage_investment_rental(year)
    # The battery config carries acknowledges_no_source_documents=True after
    # the Task-3 sweep; clear it here so the gate is actually under test.
    scenario.config = dataclasses.replace(
        scenario.config, acknowledges_no_source_documents=None)
    return scenario


class GateRefusalTests(unittest.TestCase):
    """Fast tier: the gate raises before any LibreOffice work."""

    def test_refusal_fires_for_w2_without_pdf(self):
        scenario = _no_pdf_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                _orchestrator().run_full_return(scenario, Path(tmp))
        msg = str(ctx.exception)
        self.assertIn("Synthetic Employer A", msg)
        self.assertIn("acknowledges_no_source_documents", msg)

    def test_refusal_fires_for_zero_withholding_w2(self):
        # Copy B attaches for EVERY W-2 — withholding is irrelevant.
        scenario = _no_pdf_scenario()
        scenario.w2s = [
            dataclasses.replace(w2, federal_tax_withheld=0.0)
            for w2 in scenario.w2s
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                _orchestrator().run_full_return(scenario, Path(tmp))

    def test_refusal_names_every_missing_employer(self):
        scenario = _no_pdf_scenario()
        scenario.w2s = scenario.w2s + [
            dataclasses.replace(scenario.w2s[0], employer="Synthetic Employer B")
        ]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                _orchestrator().run_full_return(scenario, Path(tmp))
        msg = str(ctx.exception)
        self.assertIn("Synthetic Employer A", msg)
        self.assertIn("Synthetic Employer B", msg)

    def test_ca_entry_point_is_gated(self):
        scenario = _no_pdf_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError) as ctx:
                _orchestrator().run_full_california_return(
                    scenario=scenario,
                    ca_yaml_path=Path(tmp) / "does-not-matter.ca.yaml",
                    output_dir=Path(tmp),
                )
        self.assertIn("acknowledges_no_source_documents", str(ctx.exception))

    def test_attestation_suppresses_the_gate(self):
        # Helper-level: with the flag set the gate helper is a no-op. The
        # end-to-end positive path is oracle-tier below.
        scenario = build_canonical_wage_investment_rental(2024)
        scenario.config = dataclasses.replace(
            scenario.config, acknowledges_no_source_documents=True)
        _orchestrator()._refuse_missing_source_documents(scenario)  # no raise

    def test_pdf_on_every_w2_suppresses_the_gate(self):
        scenario = _no_pdf_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = _make_pdf(Path(tmp) / "w2.pdf")
            scenario.w2s = [
                dataclasses.replace(w2, pdf=str(pdf_path))
                for w2 in scenario.w2s
            ]
            _orchestrator()._refuse_missing_source_documents(scenario)  # no raise

    def test_compute_federal_is_ungated(self):
        # compute_federal must not consult the gate at all. It runs the
        # native compute pipeline (no LibreOffice); if THIS test errors on
        # missing spreadsheets or similar environment grounds, STOP and
        # report — do not decorate or reshape it.
        scenario = _no_pdf_scenario()
        results = _orchestrator().compute_federal(scenario)
        self.assertIn("agi", results)


@needs_libreoffice
class GateEndToEndTests(unittest.TestCase):
    """Oracle tier (controller-run): the doc actually rides along."""

    def test_w2_pdf_rides_into_the_assembled_packet(self):
        from tenforty import pdf_packet

        scenario = _no_pdf_scenario()
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = _make_pdf(Path(tmp) / "w2.pdf")
            scenario.w2s = [
                dataclasses.replace(w2, pdf=str(pdf_path))
                for w2 in scenario.w2s
            ]
            # Normalize the way load_scenario would.
            from tenforty.scenario import _load_source_documents
            scenario.source_documents = _load_source_documents(
                scenario.w2s, Path(tmp))

            results, emitted = _orchestrator().run_full_return(
                scenario, Path(tmp))
            with_docs = pdf_packet.assemble_all(
                emitted, Path(tmp), scenario.config.year,
                source_documents=scenario.source_documents)
            (Path(tmp) / "no-docs-out").mkdir(exist_ok=True)
            without = pdf_packet.assemble_all(
                emitted, Path(tmp) / "no-docs-out", scenario.config.year)
            n_with = len(pypdf.PdfReader(
                str(with_docs["federal_individual"])).pages)
            n_without = len(pypdf.PdfReader(
                str(without["federal_individual"])).pages)
            self.assertEqual(n_with, n_without + 1)


if __name__ == "__main__":
    unittest.main()
