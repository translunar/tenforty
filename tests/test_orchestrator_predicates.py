"""Tests for ReturnOrchestrator conditional-emission predicates."""

import tempfile
import unittest
from pathlib import Path

from datetime import date

from tenforty.forms import f8949 as form_f8949
from tenforty.models import (
    DepreciableAsset, Form1099B, Form1099DIV, Form1099INT, ItemizedDeductions,
    RentalProperty, Scenario, ScheduleK1, TaxReturnConfig, W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import make_k1_scenario, make_simple_scenario, plan_d_attestation_defaults

REPO_ROOT = Path(__file__).resolve().parents[1]


class OrchestratorPredicateTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work_dir = Path(tmp.name)
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.work_dir,
        )

    def test_should_emit_sch_b_false_when_no_interest_or_dividends(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_true_when_interest_over_threshold(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_int.append(
            Form1099INT(payer="Bank A", interest=2000.0)
        )
        self.assertTrue(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_true_when_dividends_over_threshold(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_div.append(
            Form1099DIV(payer="Broker B", ordinary_dividends=2000.0)
        )
        self.assertTrue(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_b_false_when_totals_under_1500_each(self) -> None:
        scenario = make_simple_scenario()
        scenario.form1099_int.append(
            Form1099INT(payer="Bank A", interest=800.0)
        )
        scenario.form1099_div.append(
            Form1099DIV(payer="Broker B", ordinary_dividends=600.0)
        )
        self.assertFalse(self.orchestrator._should_emit_sch_b(scenario, {}))

    def test_should_emit_sch_1_false_when_no_additional_income(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_1(scenario, {}))

    def test_should_emit_sch_1_prefers_oracle_line_10(self) -> None:
        scenario = make_simple_scenario()
        self.assertTrue(self.orchestrator._should_emit_sch_1(
            scenario, {"f1040": {"sch_1_line_10": 15_000, "sch_1_line_26": 0}},
        ))
        self.assertFalse(self.orchestrator._should_emit_sch_1(
            scenario, {"f1040": {"sch_1_line_10": 0, "sch_1_line_26": 0}},
        ))

    def test_should_emit_sch_1_true_when_rental_income_present_no_oracle(self) -> None:
        scenario = make_simple_scenario()
        scenario.rental_properties = [
            RentalProperty(
                address="x", property_type=1, fair_rental_days=365,
                personal_use_days=0, rents_received=24_000.0,
            ),
        ]
        self.assertTrue(self.orchestrator._should_emit_sch_1(scenario, {}))

    def test_should_emit_sch_a_false_when_no_itemized_deductions(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_a(
            scenario, {"f1040": {"agi": 100_000, "magi": 100_000}},
        ))

    def test_should_emit_sch_a_false_when_under_standard_deduction(self) -> None:
        scenario = make_simple_scenario()
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=2_000, property_tax=1_000,
        )
        self.assertFalse(self.orchestrator._should_emit_sch_a(
            scenario, {"f1040": {"agi": 100_000, "magi": 100_000}},
        ))

    def test_should_emit_sch_a_true_when_over_standard_deduction_single(self) -> None:
        scenario = make_simple_scenario()
        scenario.itemized_deductions = ItemizedDeductions(
            state_income_tax=8_000, property_tax=6_000,
            mortgage_interest=18_000, charitable_contributions=3_000,
        )
        self.assertTrue(self.orchestrator._should_emit_sch_a(
            scenario, {"f1040": {"agi": 150_000, "magi": 150_000}},
        ))

    def test_should_emit_sch_d_false_when_no_1099b(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_d(scenario))

    def test_should_emit_sch_e_false_when_no_rental_property(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_e(scenario))

    def test_should_emit_sch_e_fires_for_k1_only(self) -> None:
        scenario = make_k1_scenario()
        scenario.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=50_000.0,
        )]
        self.assertTrue(self.orchestrator._should_emit_sch_e(scenario))
        self.assertTrue(self.orchestrator._should_emit_sch_e_part_ii(scenario))

    def test_should_not_emit_sch_e_part_ii_without_k1(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_sch_e_part_ii(scenario))

    def test_should_emit_8959_false_when_wages_under_threshold(self) -> None:
        scenario = make_simple_scenario()
        # single filer, $100k medicare wages, threshold $200k
        self.assertFalse(self.orchestrator._should_emit_8959(scenario, {}))

    def test_should_emit_8959_prefers_oracle_required_flag(self) -> None:
        scenario = make_simple_scenario()
        # Oracle says required even though wages would be under threshold.
        self.assertTrue(self.orchestrator._should_emit_8959(
            scenario, {"f1040": {"f8959_required": True}},
        ))
        # Oracle says not required even though wages would exceed threshold.
        scenario.w2s = [W2(
            employer="X", wages=300_000, federal_tax_withheld=0,
            ss_wages=168_600, ss_tax_withheld=0,
            medicare_wages=300_000, medicare_tax_withheld=0,
        )]
        self.assertFalse(self.orchestrator._should_emit_8959(
            scenario, {"f1040": {"f8959_required": False}},
        ))

    def test_should_emit_4562_false_when_no_assets(self) -> None:
        scenario = make_simple_scenario()
        self.assertFalse(self.orchestrator._should_emit_4562(scenario, {}))

    def test_should_emit_8995_requires_qbi(self) -> None:
        s = make_k1_scenario()
        s.schedule_k1s = [ScheduleK1(
            entity_name="Fake S-Corp Inc", entity_ein="00-0000000",
            entity_type="s_corp", material_participation=True,
            ordinary_business_income=50_000.0, qbi_amount=0.0,
        )]
        self.assertFalse(self.orchestrator._should_emit_8995(s))
        s.schedule_k1s[0].qbi_amount = 50_000.0
        self.assertTrue(self.orchestrator._should_emit_8995(s))

    def test_should_emit_4562_true_when_any_asset_present(self) -> None:
        scenario = make_simple_scenario()
        scenario.depreciable_assets = [
            DepreciableAsset(
                description="x",
                date_placed_in_service=date(2024, 1, 1),
                basis=1000.0,
                recovery_class="5-year",
                convention="half-year",
            ),
        ]
        self.assertTrue(self.orchestrator._should_emit_4562(scenario, {}))


class TestShouldCompute8949(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name),
        )

    def _scen(self, lots: list) -> Scenario:
        return Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1985-04-20", state="CA",
                **plan_d_attestation_defaults(),
            ),
            form1099_b=list(lots),
        )

    def test_compute_when_any_1099b_lot_present(self) -> None:
        scen = self._scen([
            Form1099B(
                broker="Brokerage Inc", description="Clean",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
        ])
        self.assertTrue(self.orch._should_compute_8949(scen))

    def test_compute_false_when_no_1099b(self) -> None:
        scen = self._scen([])
        self.assertFalse(self.orch._should_compute_8949(scen))


class TestShouldEmit8949Pdf(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(tmp.name),
        )

    def _scen(self, lots: list) -> Scenario:
        return Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1985-04-20", state="CA",
                **plan_d_attestation_defaults(),
            ),
            form1099_b=list(lots),
        )

    def test_emit_true_when_8949_path_lot_present(self) -> None:
        # basis_reported_to_irs=False → Box B → appears in f8949_box_b_total_proceeds
        scen = self._scen([
            Form1099B(
                broker="Brokerage Inc", description="Non-covered lot",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=2000.0, cost_basis=1500.0,
                short_term=True, basis_reported_to_irs=False,
            ),
        ])
        f8949_result = form_f8949.compute(scen, upstream={})
        upstream = {"f8949": f8949_result}
        self.assertTrue(self.orch._should_emit_8949_pdf(scen, upstream))

    def test_emit_false_when_only_aggregate_path_lots(self) -> None:
        # basis_reported_to_irs=True, no adjustments → Box A aggregate path,
        # not on the 8949 path, so per-box totals are all zero.
        scen = self._scen([
            Form1099B(
                broker="Brokerage Inc", description="Covered lot",
                date_acquired="2024-06-01", date_sold="2025-03-15",
                proceeds=5000.0, cost_basis=3000.0,
                short_term=False, basis_reported_to_irs=True,
            ),
        ])
        f8949_result = form_f8949.compute(scen, upstream={})
        upstream = {"f8949": f8949_result}
        self.assertFalse(self.orch._should_emit_8949_pdf(scen, upstream))

    def test_emit_false_when_no_lots_empty_upstream(self) -> None:
        # Empty upstream — no f8949 key at all, or empty dict at "f8949"
        scen = self._scen([])
        upstream: dict = {"f8949": {}}
        self.assertFalse(self.orch._should_emit_8949_pdf(scen, upstream))


if __name__ == "__main__":
    unittest.main()
