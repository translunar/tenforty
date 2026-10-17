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
from tenforty.scenario import load_scenario, qp_is_19_or_older
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


if __name__ == "__main__":
    unittest.main()
