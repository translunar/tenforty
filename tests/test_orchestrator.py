import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tenforty.forms import sch_e_part_ii as form_sch_e_part_ii
from tenforty.models import EntityType, Scenario, ScheduleK1, TaxReturnConfig, W2
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import SPREADSHEETS_DIR, make_simple_scenario, needs_libreoffice, needs_pdf


@needs_libreoffice
class TestReturnOrchestrator(unittest.TestCase):
    def test_federal_return(self):
        tmp_path = Path(tempfile.mkdtemp())
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
            ),
            w2s=[
                W2(
                    employer="Test Corp",
                    wages=80000,
                    federal_tax_withheld=12000,
                    ss_wages=80000,
                    ss_tax_withheld=4960,
                    medicare_wages=80000,
                    medicare_tax_withheld=1160,
                ),
            ],
        )

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=tmp_path,
        )
        results = orchestrator.compute_federal(scenario)

        self.assertEqual(results["wages"], 80000)
        self.assertEqual(results["agi"], 80000)
        # 80000 - 15750 = 64250
        self.assertEqual(results["taxable_income"], 64250)
        self.assertEqual(results["federal_withheld"], 12000)


class TestShouldEmit8582AcceptsUpstream(unittest.TestCase):
    """_should_emit_8582 gains an `upstream: UpstreamState` parameter in
    Task 8 — signature-only, so its body is unchanged and still iterates
    `scenario.schedule_k1s`. Task 9 rewrites the body to read upstream."""

    def test_signature_accepts_upstream(self) -> None:
        sig = inspect.signature(ReturnOrchestrator._should_emit_8582)
        self.assertIn("upstream", sig.parameters)


class TestComputeOnceDiscipline(unittest.TestCase):
    """emit_pdfs must invoke form_sch_e_part_ii.compute at most once per call."""

    @needs_libreoffice
    @needs_pdf
    def test_part_ii_called_at_most_once_across_emit_pdfs(self) -> None:
        scenario = make_simple_scenario()
        scenario.schedule_k1s = [
            ScheduleK1(
                entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
                entity_type=EntityType.S_CORP,
                material_participation=True,
                ordinary_business_income=50000.0, qbi_amount=50000.0,
                interest_income=100.0,  # triggers Sch B
                net_long_term_capital_gain=500.0,  # triggers Sch D
            ),
        ]
        scenario.config.acknowledges_unlimited_at_risk = True
        scenario.config.basis_tracked_externally = True
        scenario.config.acknowledges_no_k1_credits = True

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path("/tmp/tenforty-test-compute-once"),
        )
        results = orchestrator.compute_federal(scenario)

        real_compute = form_sch_e_part_ii.compute
        with patch(
            "tenforty.orchestrator.form_sch_e_part_ii.compute",
            side_effect=real_compute,
        ) as spy:
            orchestrator.emit_pdfs(
                scenario, results,
                output_dir=Path("/tmp/tenforty-test-compute-once-pdfs"),
            )

        self.assertLessEqual(
            spy.call_count, 1,
            f"sch_e_part_ii.compute was called {spy.call_count} times in "
            "one emit_pdfs; SP1-M1 requires at most once per compute stage.",
        )
