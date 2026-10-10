"""Form 8582 limitation computed but not applied to the return: refuse.

Schedule 1 line 5 reads Schedule E line 26 (every rental loss in full) plus
Part II line 32 (every K-1 loss in full, no prior-year carryforward). Form
8582's allowed loss is computed beside that and never applied. The return is
right only when the limitation does not bind, so it refuses when it does:

  * any passive loss is suspended (deducted in full though not allowed), or
  * any prior-year unallowed loss is present (allowed in part or whole by
    Form 8582, never deducted).

All figures invented.
"""

import tempfile
import unittest
from pathlib import Path

from tenforty.attestations import enforce_scoped_refusals
from tenforty.models import (
    RentalProperty, Scenario, ScheduleK1, TaxReturnConfig, W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.scenario import load_scenario
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults

_REFUSAL = r"Form 8582 limitation.*not applied to the return"

_K1_GATES = (
    "acknowledges_qbi_below_threshold", "acknowledges_unlimited_at_risk",
    "basis_tracked_externally", "acknowledges_no_partnership_se_earnings",
    "acknowledges_no_section_1231_gain", "acknowledges_no_more_than_four_k1s",
    "acknowledges_no_k1_credits", "acknowledges_no_section_179",
    "acknowledges_no_estate_trust_k1",
)


def _scenario(*, wages: int, rentals=(), k1s=(), year: int = 2024) -> Scenario:
    config = TaxReturnConfig(
        year=year, filing_status="single", birthdate="1990-06-15",
        state="TX", digital_assets=False,
        **scope_out_attestation_defaults(),
    )
    for name in _K1_GATES:
        setattr(config, name, True)
    return Scenario(
        config=config,
        w2s=[W2(employer="Acme Corp", wages=wages,
                federal_tax_withheld=15_000, ss_wages=wages,
                ss_tax_withheld=6_200, medicare_wages=wages,
                medicare_tax_withheld=1_450)],
        rental_properties=list(rentals), schedule_k1s=list(k1s),
    )


def _loss_rental(loss: int = 15_000) -> RentalProperty:
    return RentalProperty(
        address="1 Test Way", property_type=1, fair_rental_days=365,
        personal_use_days=0, rents_received=10_000.0,
        mortgage_interest=10_000.0 + loss)


def _passive_k1(income: float, carryforward: float = 0.0) -> ScheduleK1:
    return ScheduleK1(
        entity_name="Fake LP", entity_ein="00-0000000",
        entity_type="partnership", material_participation=False,
        ordinary_business_income=income,
        prior_year_passive_loss_carryforward=carryforward)


class _Case(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work")


class LimitationBindsRefusalTests(_Case):
    def test_suspended_rental_loss_refuses_and_allowed_twin_computes(self):
        # Twin: wages 100,000 -> the full 25,000 special allowance covers the
        # 15,000 loss; nothing is suspended and the return computes.
        allowed = self.orch.compute_federal(
            _scenario(wages=100_000, rentals=[_loss_rental()]))
        self.assertEqual(allowed["f8582_line_11_oracle"], 15_000)
        self.assertEqual(allowed["agi"], 85_000)
        # Wages 200,000 -> modified AGI over 150,000 -> allowance 0 -> the
        # whole 15,000 is suspended, yet Schedule 1 would deduct it.
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            self.orch.compute_federal(
                _scenario(wages=200_000, rentals=[_loss_rental()]))

    def test_partly_suspended_rental_loss_refuses(self):
        # Loss 35,000 against a 25,000 allowance: 10,000 suspended.
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            self.orch.compute_federal(
                _scenario(wages=60_000, rentals=[_loss_rental(35_000)]))

    def test_suspended_passive_k1_loss_refuses(self):
        # A non-rental passive K-1 loss has no special allowance.
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            self.orch.compute_federal(
                _scenario(wages=100_000, k1s=[_passive_k1(-8_000.0)]))

    def test_passive_k1_rental_loss_beyond_income_plus_allowance_refuses(self):
        # The shape the Form 8582 oracle and emit tests carried before they
        # were reshaped: an income rental (net 3,000) and a passive K-1 rental
        # real estate loss of 30,000. Allowed: 3,000 + 25,000 = 28,000 of
        # 30,000 -> 2,000 suspended. Native path; fires before any workbook.
        def shaped(k1_loss: float) -> Scenario:
            return _scenario(
                wages=100_000,
                rentals=[RentalProperty(
                    address="1 Test St", property_type=1,
                    fair_rental_days=365, personal_use_days=0,
                    rents_received=5_000.0, mortgage_interest=2_000.0)],
                k1s=[ScheduleK1(
                    entity_name="Example LLC", entity_ein="00-0000000",
                    entity_type="partnership", material_participation=False,
                    net_rental_real_estate=k1_loss)])
        twin = self.orch.compute_federal(shaped(-28_000.0))
        self.assertEqual(twin["f8582_line_11_oracle"], 28_000)
        with self.assertRaisesRegex(
                NotImplementedError, _REFUSAL + r": 2,000 of passive loss"):
            self.orch.compute_federal(shaped(-30_000.0))

    def test_allowed_but_undeducted_carryforward_refuses(self):
        # Passive income 9,000 lets Form 8582 allow the whole 3,000 prior-year
        # loss -- nothing suspended -- but the return never deducts it.
        self.orch.compute_federal(
            _scenario(wages=100_000, k1s=[_passive_k1(9_000.0)]))  # twin
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            self.orch.compute_federal(_scenario(
                wages=100_000, k1s=[_passive_k1(9_000.0, 3_000.0)]))

    def test_passive_income_alone_does_not_refuse(self):
        r = self.orch.compute_federal(
            _scenario(wages=100_000, k1s=[_passive_k1(9_000.0)]))
        self.assertEqual(r["agi"], 109_000)

    def test_refusal_fires_in_every_supported_year(self):
        for year in (2021, 2022, 2023, 2024, 2025):
            with self.subTest(year=year):
                self.orch.compute_federal(_scenario(
                    wages=100_000, rentals=[_loss_rental()], year=year))
                with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
                    self.orch.compute_federal(_scenario(
                        wages=200_000, rentals=[_loss_rental()], year=year))


class ShippedFixtureTests(_Case):
    """tests/fixtures/k1_partnership_passive.yaml produced a return before
    this refusal existed (passive K-1, prior-year carryforward 2,000). It now
    lives under fixtures/refusals/ as a firing case."""

    def test_passive_carryforward_fixture_loads_but_refuses_to_compute(self):
        scenario = load_scenario(
            REPO_ROOT / "tests" / "fixtures" / "refusals"
            / "k1_partnership_passive.yaml")
        self.assertEqual(
            scenario.schedule_k1s[0].prior_year_passive_loss_carryforward,
            2_000.0)
        with self.assertRaisesRegex(
                NotImplementedError,
                _REFUSAL + r": a prior-year unallowed loss of 2,000"):
            self.orch.compute_federal(scenario)
        with self.assertRaisesRegex(
                NotImplementedError, r"Schedule E line 27.*'Example LLC'"):
            enforce_scoped_refusals(scenario, "emit")


class LedgerEntryTests(unittest.TestCase):
    """The entry itself, over a Form 8582 result (stage "schedules")."""

    @staticmethod
    def _f8582(loss, carryforward, allowed) -> dict:
        return {"f8582": {
            "f8582_line_1b_activities_with_loss": loss,
            "f8582_line_1c_prior_year_unallowed_loss": carryforward,
            "f8582_line_11_allowed_loss": allowed,
        }}

    def test_fires_on_a_suspended_loss(self):
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            enforce_scoped_refusals(self._f8582(15_000, 0, 5_000), "schedules")

    def test_fires_on_a_carryforward_even_when_fully_allowed(self):
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            enforce_scoped_refusals(self._f8582(0, 3_000, 3_000), "schedules")

    def test_silent_when_the_whole_current_year_loss_is_allowed(self):
        enforce_scoped_refusals(self._f8582(15_000, 0, 15_000), "schedules")

    def test_silent_with_no_form_8582_result(self):
        enforce_scoped_refusals({}, "schedules")
        enforce_scoped_refusals(self._f8582(0, 0, 0), "schedules")

    def test_message_names_the_gap_and_the_follow_up(self):
        with self.assertRaises(NotImplementedError) as caught:
            enforce_scoped_refusals(self._f8582(15_000, 0, 5_000), "schedules")
        text = str(caught.exception)
        self.assertIn("10,000", text)          # the suspended amount
        self.assertIn("follow-up", text)


    def test_suspended_amount_counts_the_prior_year_loss(self):
        # 10,000 current + 4,000 prior against 5,000 allowed: 9,000 suspended.
        with self.assertRaises(NotImplementedError) as caught:
            enforce_scoped_refusals(
                self._f8582(10_000, 4_000, 5_000), "schedules")
        text = str(caught.exception)
        self.assertIn("9,000 of passive loss", text)
        self.assertIn("prior-year unallowed loss of 4,000", text)


class UnknownMagiRefusalTests(_Case):
    """Form 8582's special allowance turns on modified AGI. A results dict
    with no ``magi`` key (the workbook path's) must not be read as 0 -- that
    grants the maximum allowance. With something to limit, it refuses."""

    _UNKNOWN = r"modified adjusted gross income is unknown"

    def test_form_8582_flags_a_missing_magi_and_not_a_present_one(self):
        from tenforty.forms import f8582 as form_f8582
        from tenforty.forms import sch_e as form_sch_e
        scenario = _scenario(wages=100_000, rentals=[_loss_rental()])
        sch_e = form_sch_e.compute(scenario, upstream={})
        missing = form_f8582.compute(
            scenario, upstream={"f1040": {"wages": 100_000}, "sch_e": sch_e})
        self.assertIs(missing["f8582_magi_unknown"], True)
        absent = form_f8582.compute(scenario, upstream={"sch_e": sch_e})
        self.assertIs(absent["f8582_magi_unknown"], True)
        present = form_f8582.compute(
            scenario, upstream={"f1040": {"magi": 0}, "sch_e": sch_e})
        self.assertNotIn("f8582_magi_unknown", present)

    def test_ledger_refuses_an_unknown_magi_with_a_loss_to_limit(self):
        with self.assertRaisesRegex(NotImplementedError, self._UNKNOWN):
            enforce_scoped_refusals({"f8582": {
                "f8582_magi_unknown": True,
                "f8582_line_1b_activities_with_loss": 15_000,
                "f8582_line_1c_prior_year_unallowed_loss": 0,
                "f8582_line_11_allowed_loss": 15_000,
            }}, "schedules")

    def test_ledger_refuses_an_unknown_magi_with_a_carryforward(self):
        with self.assertRaisesRegex(NotImplementedError, self._UNKNOWN):
            enforce_scoped_refusals({"f8582": {
                "f8582_magi_unknown": True,
                "f8582_line_1b_activities_with_loss": 0,
                "f8582_line_1c_prior_year_unallowed_loss": 2_000,
                "f8582_line_11_allowed_loss": 2_000,
            }}, "schedules")

    def test_ledger_is_silent_on_an_unknown_magi_with_nothing_to_limit(self):
        enforce_scoped_refusals({"f8582": {
            "f8582_magi_unknown": True,
            "f8582_line_1b_activities_with_loss": 0,
            "f8582_line_1c_prior_year_unallowed_loss": 0,
            "f8582_line_11_allowed_loss": 0,
        }}, "schedules")

    def test_ledger_is_silent_on_a_known_magi_with_the_loss_allowed(self):
        enforce_scoped_refusals({"f8582": {
            "f8582_line_1b_activities_with_loss": 15_000,
            "f8582_line_1c_prior_year_unallowed_loss": 0,
            "f8582_line_11_allowed_loss": 15_000,
        }}, "schedules")

    def test_emit_refuses_a_results_dict_without_magi(self):
        # The firing case end to end: a loss rental, and a results dict
        # shaped like the workbook path's (no `magi`). Read as 0 it would
        # grant the full allowance and print.
        scenario = _scenario(wages=100_000, rentals=[_loss_rental()])
        results = self.orch.compute_federal(scenario)
        self.orch._federal_individual_emit_specs(scenario, results)  # twin
        without = {k: v for k, v in results.items() if k != "magi"}
        self.assertNotIn("magi", without)
        with self.assertRaisesRegex(NotImplementedError, self._UNKNOWN):
            self.orch._federal_individual_emit_specs(scenario, without)

    def test_emit_without_magi_still_prints_an_income_rental(self):
        income = RentalProperty(
            address="1 Test Way", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=10_000.0,
            mortgage_interest=4_000.0)
        scenario = _scenario(wages=100_000, rentals=[income])
        results = self.orch.compute_federal(scenario)
        without = {k: v for k, v in results.items() if k != "magi"}
        specs = self.orch._federal_individual_emit_specs(scenario, without)
        self.assertIn("sch_e", {s.name for s in specs})


class EmitPathRefusalTests(_Case):
    """The emit chokepoint re-checks with the Form 8582 it is about to print,
    so a results dict that did not come through the native compute (the
    workbook path) is covered too."""

    def test_emit_refuses_when_the_printed_form_8582_binds(self):
        scenario = _scenario(wages=100_000, rentals=[_loss_rental()])
        results = self.orch.compute_federal(scenario)
        self.orch._federal_individual_emit_specs(scenario, results)  # twin
        # The same return handed a results dict whose modified AGI puts the
        # special allowance at 0: the Form 8582 about to print binds.
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            self.orch._federal_individual_emit_specs(
                scenario, {**results, "magi": 200_000})


if __name__ == "__main__":
    unittest.main()
