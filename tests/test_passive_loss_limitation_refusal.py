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


def _block(loss, carryforward, allowed, *, income=0, non_rental=0,
           **extra) -> dict:
    """A complete Form 8582 result block, as the ledger predicates read it."""
    return {
        "f8582_line_1a_activities_with_income": income,
        "f8582_line_1b_activities_with_loss": loss,
        "f8582_line_1c_prior_year_unallowed_loss": carryforward,
        "f8582_line_11_allowed_loss": allowed,
        "f8582_non_rental_passive_loss": non_rental,
        **extra,
    }


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

    # --- Non-rental passive losses -------------------------------------
    # Form 8582's compute applies the rental real estate special allowance to
    # the WHOLE passive-loss pool whenever any rental exists, so by its own
    # figure a non-rental passive loss looks "allowed in full". The allowance
    # may only excuse rental real estate losses: a non-rental passive loss is
    # deductible only against passive income. The return refuses whenever
    # non-rental passive losses exceed passive income.

    @staticmethod
    def _business_k1(income: float, name: str = "Fake LP") -> ScheduleK1:
        return ScheduleK1(
            entity_name=name, entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
            ordinary_business_income=income)

    @staticmethod
    def _rental(rents: float, interest: float) -> RentalProperty:
        return RentalProperty(
            address="1 Test Way", property_type=1, fair_rental_days=365,
            personal_use_days=0, rents_received=rents,
            mortgage_interest=interest)

    def test_non_rental_loss_beside_a_profitable_rental_refuses(self):
        # Passive partnership business loss 20,000; rental nets +3,000. Only
        # 3,000 of passive income exists to absorb the 20,000.
        scenario = _scenario(
            wages=60_000, rentals=[self._rental(5_000.0, 2_000.0)],
            k1s=[self._business_k1(-20_000.0)])
        with self.assertRaisesRegex(
                NotImplementedError,
                _REFUSAL + r".*non-rental passive losses of 20,000 exceed "
                r"passive income of 3,000"):
            self.orch.compute_federal(scenario)

    def test_non_rental_loss_beside_a_rental_loss_refuses(self):
        # Rental loss 5,000 and a non-rental passive loss of 15,000, with no
        # passive income at all.
        scenario = _scenario(
            wages=60_000, rentals=[self._rental(5_000.0, 10_000.0)],
            k1s=[self._business_k1(-15_000.0)])
        with self.assertRaisesRegex(
                NotImplementedError,
                _REFUSAL + r".*non-rental passive losses of 15,000 exceed "
                r"passive income of 0"):
            self.orch.compute_federal(scenario)

    def test_non_rental_loss_absorbed_by_passive_income_computes(self):
        # Twin: the non-rental loss (2,000) fits inside the rental's passive
        # income (3,000), so nothing is suspended and the return computes.
        scenario = _scenario(
            wages=60_000, rentals=[self._rental(5_000.0, 2_000.0)],
            k1s=[self._business_k1(-2_000.0)])
        r = self.orch.compute_federal(scenario)
        self.assertEqual(r["f8582_line_11_oracle"], 2_000)
        self.assertEqual(r["agi"], 61_000)

    def test_non_rental_loss_equal_to_passive_income_computes(self):
        scenario = _scenario(
            wages=60_000, rentals=[self._rental(5_000.0, 2_000.0)],
            k1s=[self._business_k1(-3_000.0)])
        self.assertEqual(self.orch.compute_federal(scenario)["agi"], 60_000)

    def test_k1_with_any_non_rental_box_counts_as_non_rental(self):
        # Conservative classification, no box split: a passive K-1 is rental
        # real estate only when that is its ONLY nonzero business box. This
        # one nets to a 10,000 loss across an ordinary and a rental box.
        mixed = ScheduleK1(
            entity_name="Fake LP", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
            ordinary_business_income=-4_000.0,
            net_rental_real_estate=-6_000.0)
        with self.assertRaisesRegex(
                NotImplementedError,
                r"non-rental passive losses of 10,000 exceed"):
            self.orch.compute_federal(_scenario(wages=60_000, k1s=[mixed]))
        # A K-1 whose only box is rental real estate stays a rental: the
        # allowance covers its 10,000 loss and the return computes.
        pure = ScheduleK1(
            entity_name="Fake LP", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False,
            net_rental_real_estate=-10_000.0)
        r = self.orch.compute_federal(_scenario(wages=60_000, k1s=[pure]))
        self.assertEqual(r["f8582_line_11_oracle"], 10_000)

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


class RentalRealEstateClassificationTests(unittest.TestCase):
    """Which passive K-1s reach Form 8582 as rental real estate: only those
    whose rental real estate box is their ONLY nonzero business box."""

    @staticmethod
    def _flag(**boxes) -> bool:
        from tenforty.forms import sch_e_part_ii
        k1 = ScheduleK1(
            entity_name="Fake LP", entity_ein="00-0000000",
            entity_type="partnership", material_participation=False, **boxes)
        _fields, fanout = sch_e_part_ii.compute(
            _scenario(wages=60_000, k1s=[k1]), upstream={})
        (activity,) = fanout.passive_activities
        return activity.rental_real_estate_only

    def test_only_a_pure_rental_real_estate_k1_is_rental(self):
        self.assertIs(self._flag(net_rental_real_estate=-10_000.0), True)
        self.assertIs(self._flag(net_rental_real_estate=4_000.0), True)
        for other in ("ordinary_business_income", "other_net_rental",
                      "royalties", "other_income"):
            with self.subTest(other_box=other):
                self.assertIs(self._flag(
                    net_rental_real_estate=-10_000.0, **{other: 1.0}), False)
                self.assertIs(self._flag(**{other: -5_000.0}), False)

    def test_k1_with_no_business_box_is_not_rental(self):
        self.assertIs(self._flag(interest_income=100.0), False)


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
    def _f8582(loss, carryforward, allowed, *, income=0, non_rental=0) -> dict:
        return {"f8582": _block(
            loss, carryforward, allowed, income=income, non_rental=non_rental)}

    def test_fires_on_a_suspended_loss(self):
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            enforce_scoped_refusals(self._f8582(15_000, 0, 5_000), "schedules")

    def test_fires_on_a_carryforward_even_when_fully_allowed(self):
        with self.assertRaisesRegex(NotImplementedError, _REFUSAL):
            enforce_scoped_refusals(self._f8582(0, 3_000, 3_000), "schedules")

    def test_silent_when_the_whole_current_year_loss_is_allowed(self):
        enforce_scoped_refusals(self._f8582(15_000, 0, 15_000), "schedules")

    def test_silent_with_no_form_8582_result(self):
        # No block at all (a return with no Form 8582): nothing to check.
        enforce_scoped_refusals({}, "schedules")
        enforce_scoped_refusals({"f8582": None}, "schedules")
        enforce_scoped_refusals(self._f8582(0, 0, 0), "schedules")

    def test_fires_when_non_rental_losses_exceed_passive_income(self):
        # Nothing "suspended" by the form's own figure (20,000 allowed of
        # 20,000), but 20,000 of non-rental loss against 3,000 of income.
        with self.assertRaisesRegex(
                NotImplementedError, r"non-rental passive losses of 20,000 "
                r"exceed passive income of 3,000"):
            enforce_scoped_refusals(self._f8582(
                20_000, 0, 20_000, income=3_000, non_rental=20_000),
                "schedules")

    def test_silent_when_passive_income_covers_non_rental_losses(self):
        enforce_scoped_refusals(self._f8582(
            2_000, 0, 2_000, income=3_000, non_rental=2_000), "schedules")
        enforce_scoped_refusals(self._f8582(
            3_000, 0, 3_000, income=3_000, non_rental=3_000), "schedules")

    def test_present_block_missing_an_expected_key_fails_loudly(self):
        # A Form 8582 block that IS present but lacks a figure the predicates
        # read is a wiring defect; reading it as 0 would wave the return
        # through. Every expected key, one at a time.
        complete = _block(15_000, 0, 15_000)
        for key in complete:
            with self.subTest(missing=key):
                block = {k: v for k, v in complete.items() if k != key}
                with self.assertRaisesRegex(ValueError, key):
                    enforce_scoped_refusals({"f8582": block}, "schedules")

    def test_present_but_empty_block_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, "f8582_line_11_allowed_loss"):
            enforce_scoped_refusals({"f8582": {}}, "schedules")

    def test_real_form_8582_result_carries_every_expected_key(self):
        from tenforty.forms import f8582 as form_f8582
        from tenforty.forms import sch_e as form_sch_e
        scenario = _scenario(wages=100_000, rentals=[_loss_rental()])
        sch_e = form_sch_e.compute(scenario, upstream={})
        result = form_f8582.compute(
            scenario, upstream={"f1040": {"magi": 100_000}, "sch_e": sch_e})
        self.assertLessEqual(set(_block(0, 0, 0)), set(result))
        enforce_scoped_refusals({"f8582": result}, "schedules")

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
    with no ``magi`` key must not be read as 0 -- that grants the maximum
    allowance. With something to limit, it refuses.

    A defensive guard: both compute paths supply ``magi`` today (the native
    spine computes it; the workbook mapping harvests it), so this fires only
    on a results dict assembled without one."""

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
            enforce_scoped_refusals({"f8582": _block(
                15_000, 0, 15_000, f8582_magi_unknown=True)}, "schedules")

    def test_ledger_refuses_an_unknown_magi_with_a_carryforward(self):
        with self.assertRaisesRegex(NotImplementedError, self._UNKNOWN):
            enforce_scoped_refusals({"f8582": _block(
                0, 2_000, 2_000, f8582_magi_unknown=True)}, "schedules")

    def test_ledger_is_silent_on_an_unknown_magi_with_nothing_to_limit(self):
        enforce_scoped_refusals({"f8582": _block(
                0, 0, 0, f8582_magi_unknown=True)}, "schedules")

    def test_ledger_is_silent_on_a_known_magi_with_the_loss_allowed(self):
        enforce_scoped_refusals(
            {"f8582": _block(15_000, 0, 15_000)}, "schedules")

    def test_emit_refuses_a_results_dict_without_magi(self):
        # The firing case end to end: a loss rental, and a results dict with
        # its `magi` removed. Read as 0 it would grant the full allowance
        # and print.
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
