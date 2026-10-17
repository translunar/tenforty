"""The head-of-household block: the qualifying person and marital facts that
FTB 3532 (Head of Household Filing Status Schedule) prints.

California denies head-of-household status to a filer who does not attach a
completed FTB 3532, so every head_of_household scenario must carry
`config.head_of_household`, and no other status may. These tests drive the
real YAML loader (`load_scenario`) and pin the load-time contract: the block's
requiredness by status and its structural rules (spec
docs/plans/2026-10-16-ftb3532-spec.md §4.2-§4.3, rules 1-9 and 2b).

Synthetic values only.
"""
import dataclasses
import datetime
import tempfile
import unittest
from pathlib import Path

import yaml

from tenforty.models import (
    HeadOfHouseholdFacts,
    HohMaritalStatus,
    HohQualifyingPerson,
    HohRelationship,
    LivedTogetherPeriod,
    SeparationDecreeKind,
)
from tenforty.scenario import (
    load_scenario, qp_is_19_or_older, qp_on_qualifying_child_path)
from tests.helpers import scope_out_attestation_defaults

_YEAR = 2025
_DEFAULT = object()


def _qp(year=_YEAR, **overrides) -> dict:
    """A valid qualifying person: a child, 10 in the tax year, all year home."""
    qp = {
        "first_name": "Example",
        "last_name": "Child",
        "ssn": "000-00-0005",
        "birthdate": f"{year - 10}-03-07",
        "relationship": "child_or_stepchild",
        "full_time_student": None,
        "permanently_disabled": None,
        "gross_income": 0,
        "days_lived_with_you": 365,
    }
    qp.update(overrides)
    return qp


def _block(year=_YEAR, qp=None, **overrides) -> dict:
    block = {
        "marital_status": "unmarried",
        "lived_with_spouse_periods": [],
        "separation_decree_kind": None,
        "qualifying_person": qp if qp is not None else _qp(year),
    }
    block.update(overrides)
    return block


def _hoh_yaml(*, year=_YEAR, status="head_of_household", block=_DEFAULT,
              **config_extra) -> str:
    """A minimal synthetic scenario YAML. `block=None` omits the
    head_of_household block; the default is a valid block."""
    config = {
        "year": year,
        "filing_status": status,
        "birthdate": "1985-03-01",
        "state": "CA",
        "first_name": "Example",
        "last_name": "Filer",
        "ssn": "000-00-0000",
        "digital_assets": False,
        **scope_out_attestation_defaults(),
    }
    if status in ("married_filing_jointly", "married_filing_separately"):
        config.update(spouse_first_name="Example", spouse_last_name="Spouse",
                      spouse_ssn="000-00-0002")
    if status == "married_filing_jointly":
        config["spouse_birthdate"] = "1986-04-02"
    if status == "married_filing_separately":
        config["mfs_lived_with_spouse_any_time"] = False
    if block is _DEFAULT:
        block = _block(year)
    if block is not None:
        config["head_of_household"] = block
    config.update(config_extra)
    return yaml.safe_dump({"config": config}, sort_keys=False)


class _LoaderCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def load(self, text: str):
        path = self.dir / "scenario.yaml"
        path.write_text(text)
        return load_scenario(path)

    def refuses(self, text: str, *fragments: str) -> str:
        """Assert the load refuses with ValueError whose message contains
        every fragment; return the message."""
        with self.assertRaises(ValueError) as ctx:
            self.load(text)
        message = str(ctx.exception)
        for fragment in fragments:
            self.assertIn(fragment, message)
        return message


class HohBlockRequirednessTests(_LoaderCase):
    def test_hoh_without_block_refuses_naming_ftb3532(self):
        self.refuses(_hoh_yaml(block=None), "head_of_household", "FTB 3532")

    def test_other_statuses_with_block_refuse(self):
        for status in ("single", "married_filing_jointly",
                       "married_filing_separately"):
            with self.subTest(status=status):
                message = self.refuses(_hoh_yaml(status=status),
                                       "head_of_household")
                self.assertIn(f"`{status}`", message)

    def test_other_statuses_without_block_load(self):
        # Positive control for the refusal above: the same configs, block
        # removed, load.
        for status in ("single", "married_filing_jointly",
                       "married_filing_separately"):
            with self.subTest(status=status):
                cfg = self.load(_hoh_yaml(status=status, block=None)).config
                self.assertIsNone(cfg.head_of_household)

    def test_valid_default_loads_and_normalizes_the_ssn(self):
        cfg = self.load(_hoh_yaml()).config
        facts = cfg.head_of_household
        self.assertIsInstance(facts, HeadOfHouseholdFacts)
        self.assertIs(facts.marital_status, HohMaritalStatus.UNMARRIED)
        self.assertEqual(facts.lived_with_spouse_periods, ())
        self.assertIsNone(facts.separation_decree_kind)
        qp = facts.qualifying_person
        self.assertIsInstance(qp, HohQualifyingPerson)
        self.assertEqual(qp.ssn, "000000005")
        self.assertIs(qp.relationship, HohRelationship.CHILD_OR_STEPCHILD)
        self.assertEqual(qp.birthdate, f"{_YEAR - 10}-03-07")
        self.assertEqual(qp.days_lived_with_you, 365)
        self.assertEqual(qp.gross_income, 0)

    def test_undashed_ssn_loads_unchanged(self):
        qp = self.load(_hoh_yaml(block=_block(qp=_qp(ssn="000000005")))
                       ).config.head_of_household.qualifying_person
        self.assertEqual(qp.ssn, "000000005")


class StructuralRuleTests(_LoaderCase):
    # --- rule 1: known keys and enum members -------------------------------
    def test_unknown_block_key_refuses(self):
        self.refuses(_hoh_yaml(block=_block(nickname="x")),
                     "Unknown key", "nickname")

    def test_unknown_qualifying_person_key_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(nickname="x"))),
                     "Unknown key", "nickname")

    def test_unknown_period_key_refuses(self):
        periods = [{"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-02-28",
                    "note": "x"}]
        self.refuses(_hoh_yaml(block=_block(
            marital_status="married_lived_together_part_of_year",
            lived_with_spouse_periods=periods)), "Unknown key", "note")

    def test_unknown_marital_status_refuses(self):
        self.refuses(_hoh_yaml(block=_block(marital_status="widowed")),
                     "marital_status", "widowed")

    def test_unknown_relationship_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(relationship="cousin"))),
                     "relationship", "cousin")

    def test_missing_required_qualifying_person_key_refuses(self):
        for key in ("first_name", "last_name", "ssn", "birthdate",
                    "relationship", "gross_income", "days_lived_with_you"):
            with self.subTest(key=key):
                qp = _qp()
                del qp[key]
                self.refuses(_hoh_yaml(block=_block(qp=qp)), key)

    def test_missing_qualifying_person_refuses(self):
        block = _block()
        del block["qualifying_person"]
        self.refuses(_hoh_yaml(block=block), "qualifying_person")

    # --- rule 2: lived-with-spouse periods (Part I line 1f) ------------------
    def _together(self, periods):
        return _hoh_yaml(block=_block(
            marital_status="married_lived_together_part_of_year",
            lived_with_spouse_periods=periods))

    def test_1f_with_no_periods_refuses(self):
        self.refuses(self._together([]), "lived_with_spouse_periods",
                     "line 1f")

    def test_1f_with_two_periods_loads(self):
        facts = self.load(self._together([
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-02-28"},
            {"from": f"{_YEAR}-04-01", "to": f"{_YEAR}-05-31"},
        ])).config.head_of_household
        self.assertEqual(facts.lived_with_spouse_periods, (
            LivedTogetherPeriod(start=f"{_YEAR}-01-01", end=f"{_YEAR}-02-28"),
            LivedTogetherPeriod(start=f"{_YEAR}-04-01", end=f"{_YEAR}-05-31"),
        ))

    def test_1f_with_three_periods_refuses_naming_the_two_slots(self):
        self.refuses(self._together([
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-01-31"},
            {"from": f"{_YEAR}-03-01", "to": f"{_YEAR}-03-31"},
            {"from": f"{_YEAR}-05-01", "to": f"{_YEAR}-05-31"},
        ]), "lived_with_spouse_periods", "two")

    def test_period_on_another_marital_status_refuses(self):
        self.refuses(_hoh_yaml(block=_block(lived_with_spouse_periods=[
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-02-28"}])),
            "lived_with_spouse_periods", "must be empty")

    def test_period_from_after_to_refuses(self):
        self.refuses(self._together([
            {"from": f"{_YEAR}-03-01", "to": f"{_YEAR}-02-01"}]),
            "is after its `to`")

    def test_period_outside_the_tax_year_refuses(self):
        self.refuses(self._together([
            {"from": f"{_YEAR - 1}-12-01", "to": f"{_YEAR}-01-31"}]),
            f"outside tax year {_YEAR}")

    def test_overlapping_periods_refuse(self):
        self.refuses(self._together([
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-03-31"},
            {"from": f"{_YEAR}-03-15", "to": f"{_YEAR}-05-31"},
        ]), "overlap")

    def test_out_of_order_periods_refuse(self):
        self.refuses(self._together([
            {"from": f"{_YEAR}-04-01", "to": f"{_YEAR}-05-31"},
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-02-28"},
        ]), "order")

    def test_unquoted_period_date_refuses(self):
        self.refuses(self._together([
            {"from": datetime.date(_YEAR, 1, 1), "to": f"{_YEAR}-02-28"}]),
            "quoted ISO")

    # --- rule 2b: separation_decree_kind (Part I line 1d) --------------------
    def test_1d_without_decree_kind_refuses(self):
        self.refuses(_hoh_yaml(block=_block(
            marital_status="divorced_or_legally_separated")),
            "separation_decree_kind", "is required")

    def test_1d_with_each_decree_kind_loads(self):
        for kind in SeparationDecreeKind:
            with self.subTest(kind=kind.value):
                facts = self.load(_hoh_yaml(block=_block(
                    marital_status="divorced_or_legally_separated",
                    separation_decree_kind=kind.value))).config.head_of_household
                self.assertIs(facts.separation_decree_kind, kind)

    def test_decree_kind_on_another_marital_status_refuses(self):
        self.refuses(_hoh_yaml(block=_block(
            separation_decree_kind="divorce_or_dissolution")),
            "separation_decree_kind", "only for")

    def test_unknown_decree_kind_refuses(self):
        self.refuses(_hoh_yaml(block=_block(
            marital_status="divorced_or_legally_separated",
            separation_decree_kind="annulment")),
            "separation_decree_kind", "annulment")

    # --- rule 3: names -------------------------------------------------------
    def test_blank_names_refuse(self):
        for key in ("first_name", "last_name"):
            with self.subTest(key=key):
                self.refuses(_hoh_yaml(block=_block(qp=_qp(**{key: "  "}))),
                             key, "blank")

    # --- rules 4 and 5: SSN --------------------------------------------------
    def test_eight_digit_ssn_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(ssn="00000005"))),
                     "ssn", "9 digits")

    def test_died_refuses_naming_the_certificates(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(ssn="Died"))),
                     "certificates", "by hand")

    def test_blank_ssn_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(ssn=""))),
                     "ssn", "applied for")

    def test_qualifying_person_ssn_equal_to_the_filers_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(ssn="000000000"))),
                     "your own qualifying person")

    def test_space_separated_filer_ssn_equal_to_the_qualifying_persons_refuses(self):
        # The federal 1040 prints any-shape filer SSNs digits-only, so rule 5
        # compares digits, not the normalized NNN-NN-NNNN shape.
        self.refuses(_hoh_yaml(ssn="000 00 0001", block=_block(
            qp=_qp(ssn="000000001"))), "same as the filer's own SSN")

    # --- rule 6: birthdate ---------------------------------------------------
    def test_birthdate_after_the_tax_year_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(
            birthdate=f"{_YEAR + 1}-01-01"))), "birthdate",
            f"after the end of tax year {_YEAR}")

    def test_birthdate_on_the_last_day_of_the_tax_year_loads(self):
        qp = self.load(_hoh_yaml(block=_block(qp=_qp(
            birthdate=f"{_YEAR}-12-31")))).config.head_of_household \
            .qualifying_person
        self.assertEqual(qp.birthdate, f"{_YEAR}-12-31")

    def test_unquoted_birthdate_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(
            birthdate=datetime.date(_YEAR - 10, 3, 7)))),
            "birthdate", "quoted ISO")

    def test_non_iso_birthdate_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(
            birthdate=f"03/07/{_YEAR - 10}"))), "birthdate", "ISO")

    # --- rule 8: gross income ------------------------------------------------
    def test_negative_gross_income_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(gross_income=-1))),
                     "gross_income", ">= 0")

    def test_non_numeric_gross_income_refuses(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(gross_income="0"))),
                     "gross_income", "number")

    # --- rule 9: days lived with you ----------------------------------------
    def test_days_above_the_days_in_the_year_refuse(self):
        self.refuses(_hoh_yaml(year=2023, block=_block(
            2023, qp=_qp(2023, days_lived_with_you=366))),
            "days_lived_with_you", "365")

    def test_leap_year_accepts_366_days(self):
        qp = self.load(_hoh_yaml(year=2024, block=_block(
            2024, qp=_qp(2024, days_lived_with_you=366)))
        ).config.head_of_household.qualifying_person
        self.assertEqual(qp.days_lived_with_you, 366)

    def test_non_integer_days_refuse(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(
            days_lived_with_you=300.5))), "days_lived_with_you", "whole number")

    def test_negative_days_refuse(self):
        self.refuses(_hoh_yaml(block=_block(qp=_qp(days_lived_with_you=-1))),
                     "days_lived_with_you")


class AgeBranchTests(_LoaderCase):
    """Rule 7: lines 3a/3b are answered iff the person is 19 or older in the
    tax year ("If not, go to line 4"). The reading is
    tax_year - birth_year >= 19 (spec §8 Q5)."""

    def _aged(self, age, **answers):
        return _hoh_yaml(block=_block(qp=_qp(
            birthdate=f"{_YEAR - age}-06-15", **answers)))

    def test_qp_is_19_or_older_at_both_edges(self):
        def person(birth_year):
            return HohQualifyingPerson(
                first_name="Example", last_name="Child", ssn="000000005",
                birthdate=f"{birth_year}-01-01",
                relationship=HohRelationship.CHILD_OR_STEPCHILD,
                full_time_student=None, permanently_disabled=None,
                gross_income=0.0, days_lived_with_you=365)
        self.assertTrue(qp_is_19_or_older(person(_YEAR - 19), _YEAR))
        self.assertFalse(qp_is_19_or_older(person(_YEAR - 18), _YEAR))
        # December 31 birthday in the year-19 birth year still counts as 19.
        late = dataclasses.replace(person(_YEAR - 19),
                                   birthdate=f"{_YEAR - 19}-12-31")
        self.assertTrue(qp_is_19_or_older(late, _YEAR))

    def test_at_19_missing_answers_refuse(self):
        for missing in ("full_time_student", "permanently_disabled"):
            with self.subTest(missing=missing):
                answers = {"full_time_student": True,
                           "permanently_disabled": False}
                answers[missing] = None
                self.refuses(self._aged(19, **answers), missing, "19")

    def test_at_19_answered_loads(self):
        qp = self.load(self._aged(19, full_time_student=True,
                                  permanently_disabled=False)
                       ).config.head_of_household.qualifying_person
        self.assertIs(qp.full_time_student, True)
        self.assertIs(qp.permanently_disabled, False)

    def test_at_18_any_answer_refuses_citing_go_to_line_4(self):
        for key in ("full_time_student", "permanently_disabled"):
            for value in (True, False):
                with self.subTest(key=key, value=value):
                    self.refuses(self._aged(18, **{key: value}), key,
                                 "go to line 4")

    def test_at_18_unanswered_loads(self):
        qp = self.load(self._aged(18)).config.head_of_household \
            .qualifying_person
        self.assertIsNone(qp.full_time_student)
        self.assertIsNone(qp.permanently_disabled)

    def test_string_answer_refuses(self):
        self.refuses(self._aged(19, full_time_student="yes",
                                permanently_disabled=False),
                     "full_time_student", "true or false")


def _days_in_year(year: int) -> int:
    return (datetime.date(year, 12, 31) - datetime.date(year, 1, 1)).days + 1


class DaysThresholdTests(_LoaderCase):
    """Rule 10 (FTB 3532 line 5 instructions): the qualifying person lived
    with the filer more than half the year."""

    def test_more_than_half_the_year_boundary(self):
        for year in (2023, 2024):
            half = _days_in_year(year) // 2
            with self.subTest(year=year, days=half):
                self.refuses(_hoh_yaml(year=year, block=_block(
                    year, qp=_qp(year, days_lived_with_you=half))),
                    "days_lived_with_you", "more than half the year")
            with self.subTest(year=year, days=half + 1):
                qp = self.load(_hoh_yaml(year=year, block=_block(
                    year, qp=_qp(year, days_lived_with_you=half + 1)))
                ).config.head_of_household.qualifying_person
                self.assertEqual(qp.days_lived_with_you, half + 1)


_BIRTH_OR_DEATH = ("In the event of a birth or death of your qualifying "
                   "person during the year, enter 365 days.")


class BirthInYearDaysTests(_LoaderCase):
    """FTB 3532 line 5 instructions: "In the event of a birth or death of
    your qualifying person during the year, enter 365 days. Note: A year is
    365 days, a leap year is 366 days." A qualifying person born in the tax
    year enters the year's full day count."""

    def _born_in_year(self, year, days):
        return _hoh_yaml(year=year, block=_block(year, qp=_qp(
            year, birthdate=f"{year}-11-10", days_lived_with_you=days)))

    def test_born_in_year_with_the_full_year_loads(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                qp = self.load(self._born_in_year(year, _days_in_year(year))
                               ).config.head_of_household.qualifying_person
                self.assertEqual(qp.days_lived_with_you, _days_in_year(year))

    def test_born_in_year_with_fewer_days_refuses_citing_the_birth_rule(self):
        for year, days in ((2024, 45), (2025, 45), (2024, 365)):
            with self.subTest(year=year, days=days):
                self.refuses(
                    self._born_in_year(year, days), "days_lived_with_you",
                    _BIRTH_OR_DEATH,
                    f"enter {_days_in_year(year)} days per the FTB 3532 "
                    "line 5 instructions")

    def test_under_threshold_refusal_names_the_birth_or_death_rule(self):
        # Not born in the year: rule 10's refusal still tells a filer whose
        # qualifying person died during the year what to enter.
        message = self.refuses(_hoh_yaml(block=_block(qp=_qp(
            days_lived_with_you=45))), "more than half the year")
        self.assertIn(_BIRTH_OR_DEATH, message)
        self.assertIn(f"enter {_days_in_year(_YEAR)} days", message)


class LivedTogetherBoundaryTests(_LoaderCase):
    """Rule 11: a married filer who lived with the spouse at any time in the
    last six months of the year cannot qualify."""

    def _ending(self, end):
        return _hoh_yaml(block=_block(
            marital_status="married_lived_together_part_of_year",
            lived_with_spouse_periods=[
                {"from": f"{_YEAR}-05-01", "to": f"{_YEAR}-{end}"}]))

    def test_period_ending_june_30_loads(self):
        facts = self.load(self._ending("06-30")).config.head_of_household
        self.assertEqual(facts.lived_with_spouse_periods[0].end,
                         f"{_YEAR}-06-30")

    def test_period_ending_july_1_refuses(self):
        self.refuses(self._ending("07-01"), "lived_with_spouse_periods",
                     "last six months")


class ConsideredUnmarriedRelationshipTests(_LoaderCase):
    """Rule 12: a married filer (1e, 1f) is "considered unmarried" only if
    the qualifying person is the filer's child, stepchild, adopted child or
    eligible foster child (2a, 2c)."""

    _MARRIED = {
        "married_lived_apart_all_year": [],
        "married_lived_together_part_of_year": [
            {"from": f"{_YEAR}-01-01", "to": f"{_YEAR}-02-28"}],
    }

    def _married(self, marital, relationship):
        return _hoh_yaml(block=_block(
            marital_status=marital,
            lived_with_spouse_periods=self._MARRIED[marital],
            qp=_qp(relationship=relationship)))

    def test_married_with_a_grandchild_sibling_niece_or_nephew_refuses(self):
        for marital in self._MARRIED:
            with self.subTest(marital=marital):
                self.refuses(self._married(
                    marital, "grandchild_sibling_niece_or_nephew"),
                    "relationship", "eligible foster child")

    def test_married_with_a_child_or_foster_child_loads(self):
        for marital in self._MARRIED:
            for relationship in ("child_or_stepchild", "eligible_foster_child"):
                with self.subTest(marital=marital, relationship=relationship):
                    qp = self.load(self._married(marital, relationship)
                                   ).config.head_of_household.qualifying_person
                    self.assertEqual(qp.relationship.value, relationship)

    def test_unmarried_with_a_grandchild_loads(self):
        qp = self.load(_hoh_yaml(block=_block(qp=_qp(
            relationship="grandchild_sibling_niece_or_nephew")))
        ).config.head_of_household.qualifying_person
        self.assertIs(qp.relationship,
                      HohRelationship.GRANDCHILD_SIBLING_NIECE_OR_NEPHEW)


class QualifyingChildOnlyTests(_LoaderCase):
    """Rule 13: until 0.2.1, the qualifying person must be on the
    qualifying-child path (2a-2c, and under 19, a full-time student, or
    permanently disabled)."""

    def _person(self, relationship, age, **answers):
        return _qp(relationship=relationship,
                   birthdate=f"{_YEAR - age}-06-15", **answers)

    def _assert_path(self, qp_dict, expected):
        person = HohQualifyingPerson(**{
            **qp_dict, "ssn": "000000005",
            "relationship": HohRelationship(qp_dict["relationship"]),
            "gross_income": float(qp_dict["gross_income"])})
        self.assertIs(qp_on_qualifying_child_path(person, _YEAR), expected)

    def test_parent_and_other_relative_refuse_naming_the_release(self):
        # Permanently disabled, so the age test is met: only the Part II
        # relationship (2d, 2e) takes them off the qualifying-child path.
        for relationship in ("parent_or_stepparent", "other_relative"):
            with self.subTest(relationship=relationship):
                qp = self._person(relationship, 60, full_time_student=False,
                                  permanently_disabled=True)
                self._assert_path(qp, False)
                self.refuses(_hoh_yaml(block=_block(qp=qp)),
                             "qualifying relative", "0.2.1")

    def test_child_at_20_neither_student_nor_disabled_refuses(self):
        qp = self._person("child_or_stepchild", 20, full_time_student=False,
                          permanently_disabled=False)
        self._assert_path(qp, False)
        self.refuses(_hoh_yaml(block=_block(qp=qp)), "0.2.1")

    def test_child_at_20_student_loads(self):
        qp = self._person("child_or_stepchild", 20, full_time_student=True,
                          permanently_disabled=False)
        self._assert_path(qp, True)
        self.load(_hoh_yaml(block=_block(qp=qp)))

    def test_child_at_30_disabled_loads(self):
        qp = self._person("child_or_stepchild", 30, full_time_student=False,
                          permanently_disabled=True)
        self._assert_path(qp, True)
        self.load(_hoh_yaml(block=_block(qp=qp)))

    def test_student_at_birth_year_age_23_loads(self):
        # FTB 3532 Part III line 3 instructions: "a full-time student under
        # 24 years of age". Birth-year age, as qp_is_19_or_older reads it.
        qp = self._person("child_or_stepchild", 23, full_time_student=True,
                          permanently_disabled=False)
        self._assert_path(qp, True)
        self.load(_hoh_yaml(block=_block(qp=qp)))

    def test_student_at_24_or_older_refuses_naming_the_student_age_limit(self):
        for age in (24, 26):
            with self.subTest(age=age):
                qp = self._person("child_or_stepchild", age,
                                  full_time_student=True,
                                  permanently_disabled=False)
                self._assert_path(qp, False)
                self.refuses(_hoh_yaml(block=_block(qp=qp)),
                             "not on the qualifying-child path",
                             "a full-time student under 24")

    def test_disabled_student_at_26_loads(self):
        # Permanently and totally disabled meets the age test at any age.
        qp = self._person("child_or_stepchild", 26, full_time_student=True,
                          permanently_disabled=True)
        self._assert_path(qp, True)
        self.load(_hoh_yaml(block=_block(qp=qp)))

    def test_each_child_relationship_under_19_is_on_the_path(self):
        for relationship in ("child_or_stepchild",
                             "grandchild_sibling_niece_or_nephew",
                             "eligible_foster_child"):
            with self.subTest(relationship=relationship):
                qp = self._person(relationship, 10)
                self._assert_path(qp, True)
                self.load(_hoh_yaml(block=_block(qp=qp)))


if __name__ == "__main__":
    unittest.main()
