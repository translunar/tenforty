"""The eic_eligibility block (childless-EITC spec §4): loader, trigger, fact
outcomes in the 2025 instructions' order and joint-return wording, the
Worksheet 1 refusal order, and the (2025, single) battery rows computing
natively to the outcome their kind names. All identities synthetic."""
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from tenforty.forms.eic import (
    apply_eligibility_facts,
    compute_eic,
    refuse_worksheet_1_shapes,
)
from tenforty.models import (
    EntityType,
    FilingStatus,
    Scenario,
    ScheduleK1,
)
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.params.federal import load as load_params
from tenforty.scenario import load_scenario
from tests.fixtures import eic_battery
from tests.fixtures.eic_battery import favorable_eligibility, favorable_person
from tests.fixtures.spine_battery import _battery_config
from tests.helpers import REPO_ROOT, SPREADSHEETS_DIR

YEAR = 2025
P = load_params(YEAR)
SINGLE, MFJ = FilingStatus.SINGLE, FilingStatus.MARRIED_FILING_JOINTLY
BASE = REPO_ROOT / "tests" / "fixtures" / "eic_refusals" / (
    "eic_eligibility_missing_2025.yaml")
PERSON = {"main_home_in_us_more_than_half_year": True,
          "can_be_claimed_as_dependent": False,
          "could_be_qualifying_child_of_another": False,
          "ssn_valid_for_employment": True,
          "nonresident_alien_any_part_of_year": False}


def _load(block, **config):
    data = yaml.safe_load(BASE.read_text())
    data["config"].update(config)
    if config.get("filing_status") == "married_filing_jointly":
        for w2 in data["w2s"]:
            w2["owner"] = "taxpayer"
    if block is not None:
        data["eic_eligibility"] = block
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "scenario.yaml"
        path.write_text(yaml.safe_dump(data))
        return load_scenario(path)


def _block(**top):
    return {"taxpayer": dict(PERSON),
            "prior_eic_disallowance_requires_8862": False, **top}


class LoaderTests(unittest.TestCase):

    def test_a_complete_single_block_loads(self):
        s = _load(_block())
        self.assertEqual(s.eic_eligibility, favorable_eligibility())

    def test_absent_block_loads_as_none(self):
        self.assertIsNone(_load(None).eic_eligibility)

    def test_unknown_key_suggests_the_close_one(self):
        with self.assertRaisesRegex(ValueError, "Did you mean 'taxpayer'"):
            _load(_block(taxpayr={}))

    def test_missing_fact_is_named(self):
        person = dict(PERSON)
        del person["ssn_valid_for_employment"]
        with self.assertRaisesRegex(ValueError, "ssn_valid_for_employment"):
            _load(_block(taxpayer=person))

    def test_a_quoted_fact_is_refused_not_coerced(self):
        with self.assertRaisesRegex(ValueError, "true or false"):
            _load(_block(taxpayer={**PERSON,
                                   "ssn_valid_for_employment": "no"}))

    def test_spouse_only_on_a_joint_return(self):
        with self.assertRaisesRegex(ValueError, "only to a married"):
            _load(_block(spouse=dict(PERSON)))

    def test_joint_return_requires_the_spouse(self):
        with self.assertRaisesRegex(ValueError, "spouse is required"):
            _load(_block(), filing_status="married_filing_jointly",
                  spouse_birthdate="1990-06-15")

    def test_2021_only_keys_refuse_in_2025(self):
        for block in (_block(lookback_2019_earned_income=5000.0),
                      _block(taxpayer={**PERSON,
                                       "specified_student_2021": False})):
            with self.subTest(block=sorted(block)):
                with self.assertRaisesRegex(ValueError,
                                            "^year_scoped_eic_fact"):
                    _load(block)


def _eic(scenario, earned=None):
    earned = P.eic_earned_income_amount + 100 if earned is None else earned
    spine = {"wages": earned, "agi": earned, "taxable_interest": 0,
             "ordinary_dividends": 0, "capital_gain_loss": None}
    return compute_eic(scenario, spine, P, {})


def _scenario(status=SINGLE, eligibility="favorable", **top):
    config = _battery_config(YEAR, status)
    if eligibility == "favorable":
        eligibility = favorable_eligibility(status.value)
    return Scenario(config=config, eic_eligibility=eligibility, **top)


class TriggerTests(unittest.TestCase):

    def test_a_positive_tentative_credit_requires_the_block(self):
        with self.assertRaisesRegex(NotImplementedError,
                                    "^eic_eligibility_missing"):
            _eic(_scenario(eligibility=None))

    def test_no_tentative_credit_needs_no_block(self):
        out = _eic(_scenario(eligibility=None),
                   earned=P.eic_completed_phaseout["single"])
        self.assertEqual(out["eic"], 0)

    def test_form_8862_refuses(self):
        with self.assertRaisesRegex(NotImplementedError,
                                    "^prior_eic_disallowance_8862"):
            _eic(_scenario(eligibility=favorable_eligibility(
                prior_eic_disallowance_requires_8862=True)))


class FactOutcomeTests(unittest.TestCase):
    """2025 Form 1040 instructions, line 27a Steps 1 and 4."""

    def _reason(self, status=SINGLE, **who):
        block = favorable_eligibility(status.value, **who)
        out = _eic(_scenario(status, eligibility=block))
        return out["eic"], out["eic_determination"]["reason"]

    def test_each_single_fact_denies_with_its_reason(self):
        for fact, value, reason in (
                ("ssn_valid_for_employment", False, "ssn_not_valid"),
                ("nonresident_alien_any_part_of_year", True,
                 "nonresident_alien"),
                ("main_home_in_us_more_than_half_year", False,
                 "main_home_not_in_us"),
                ("could_be_qualifying_child_of_another", True,
                 "qualifying_child_of_another"),
                ("can_be_claimed_as_dependent", True,
                 "claimable_as_dependent")):
            with self.subTest(fact=fact):
                self.assertEqual(self._reason(
                    taxpayer=favorable_person(**{fact: value})),
                    (0, reason))

    def test_joint_ssn_and_main_home_cover_both_spouses(self):
        for fact, value, reason in (
                ("ssn_valid_for_employment", False, "ssn_not_valid"),
                ("main_home_in_us_more_than_half_year", False,
                 "main_home_not_in_us")):
            with self.subTest(fact=fact):
                self.assertEqual(self._reason(
                    MFJ, spouse=favorable_person(**{fact: value})),
                    (0, reason))

    def test_joint_return_skips_questions_5_and_6(self):
        # Step 4 Q4: "Are you filing a joint return? Yes. Skip questions 5
        # and 6."
        out = _eic(_scenario(MFJ, eligibility=favorable_eligibility(
            MFJ.value, taxpayer=favorable_person(
                could_be_qualifying_child_of_another=True,
                can_be_claimed_as_dependent=True))))
        self.assertGreater(out["eic"], 0)

    def test_a_joint_nonresident_alien_refuses(self):
        # The election to treat a nonresident spouse as resident has no
        # input: undecidable, so refused.
        with self.assertRaisesRegex(NotImplementedError,
                                    "^nonresident_alien_spouse_election"):
            _eic(_scenario(MFJ, eligibility=favorable_eligibility(
                MFJ.value, spouse=favorable_person(
                    nonresident_alien_any_part_of_year=True))))

    def test_facts_apply_in_the_instructions_order(self):
        # SSN (Step 1) is decided before main home (Step 4).
        self.assertEqual(self._reason(taxpayer=favorable_person(
            ssn_valid_for_employment=False,
            main_home_in_us_more_than_half_year=False)),
            (0, "ssn_not_valid"))


class Worksheet1OrderTests(unittest.TestCase):
    """The order is load-bearing: K-1 SE earnings must be checked before
    any K-1, or that refusal is unreachable."""

    def _k1(self, se):
        return ScheduleK1(entity_name="Example Partners LP",
                          entity_ein="00-0000000",
                          entity_type=EntityType.PARTNERSHIP,
                          material_participation=True,
                          partnership_self_employment_earnings=se)

    def test_se_earnings_name_their_own_cause(self):
        with self.assertRaisesRegex(NotImplementedError,
                                    "^k1_self_employment_earnings"):
            refuse_worksheet_1_shapes(_scenario(schedule_k1s=[self._k1(100)]))

    def test_a_k1_without_se_earnings_is_worksheet_1(self):
        with self.assertRaisesRegex(NotImplementedError, "^worksheet_1_k1"):
            refuse_worksheet_1_shapes(_scenario(schedule_k1s=[self._k1(0)]))

    def test_no_k1_and_no_rental_passes(self):
        refuse_worksheet_1_shapes(_scenario())
        self.assertIsNone(apply_eligibility_facts(_scenario(), SINGLE))


class BatteryRowOutcomeTests(unittest.TestCase):
    """Each (2025, single) row computes natively (routing forced native
    until rollout step 6; the workbook path raises) to its kind's outcome."""

    EXPECT_REASON = {
        "over_ceiling": "agi_at_or_over_limit",
        "investment_over_limit": "investment_income_over_limit",
        "age_lower_bound_out": "age_test_not_met",
        "fact_ssn_not_valid": "ssn_not_valid",
        "fact_nonresident_alien": "nonresident_alien",
        "fact_main_home_not_in_us": "main_home_not_in_us",
        "fact_qualifying_child_of_another": "qualifying_child_of_another",
        "fact_claimable_as_dependent": "claimable_as_dependent",
    }

    # 2025: the EIC upper age bound (born after Dec 31 of year - max age)
    # meets the Form 1040 aged cutoff (born before Jan 2 of year - 64), so
    # both rows at that bound are aged filers, refused upstream by the
    # Schedule 1-A seniors-deduction refusal before any credit is figured.
    REFUSED_UPSTREAM = {"age_upper_bound_in": "Schedule 1-A",
                        "age_upper_bound_out": "Schedule 1-A"}

    @classmethod
    def setUpClass(cls):
        cls.out, cls.refused = {}, {}
        rows = eic_battery.battery_for(YEAR, "single")
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
                ReturnOrchestrator, "_compute_1040_via_workbook",
                side_effect=AssertionError("workbook path reached")), \
                mock.patch.object(ReturnOrchestrator,
                                  "_scenario_in_spine_scope",
                                  return_value=True):
            orch = ReturnOrchestrator(spreadsheets_dir=SPREADSHEETS_DIR,
                                      work_dir=Path(tmp))
            for kind, build in rows.items():
                try:
                    cls.out[kind] = orch.compute_federal(build(YEAR))
                except NotImplementedError as exc:
                    cls.refused[kind] = str(exc)

    def test_only_the_upper_age_rows_refuse_upstream(self):
        self.assertEqual(set(self.refused), set(self.REFUSED_UPSTREAM))
        for kind, fragment in self.REFUSED_UPSTREAM.items():
            with self.subTest(kind=kind):
                self.assertIn(fragment, self.refused[kind])

    def test_denied_rows_carry_their_reason(self):
        for kind, reason in self.EXPECT_REASON.items():
            with self.subTest(kind=kind):
                self.assertNotIn("eic", self.out[kind])
                self.assertEqual(
                    self.out[kind]["eic_determination"]["reason"], reason)

    def test_credited_rows_print_a_credit(self):
        for kind in ("plateau", "phase_in", "phase_out", "agi_over_earned",
                     "investment_at_limit", "age_lower_bound_in",
                     "sch_c_worksheet_b", "sch_c_net_loss"):
            with self.subTest(kind=kind):
                self.assertGreater(self.out[kind].get("eic", 0), 0)

    def test_plateau_is_the_max_and_the_shapes_are_below_it(self):
        self.assertEqual(self.out["plateau"]["eic"], P.eic_max_credit)
        for kind in ("phase_in", "phase_out", "agi_over_earned"):
            with self.subTest(kind=kind):
                self.assertLess(self.out[kind]["eic"], P.eic_max_credit)
        self.assertIsNotNone(self.out["agi_over_earned"]["eic_table_agi"])

    def test_worksheet_b_rows_use_worksheet_b(self):
        for kind in ("sch_c_worksheet_b", "sch_c_net_loss"):
            with self.subTest(kind=kind):
                self.assertEqual(
                    self.out[kind]["eic_determination"]["rule"],
                    "Worksheet B")
