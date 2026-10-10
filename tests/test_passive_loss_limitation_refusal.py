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
