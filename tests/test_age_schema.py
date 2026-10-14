"""Schema for the age-65 condition (ruling R-age): the federal aged
additional standard deduction and cutoff, and the California senior
exemption credit and cutoff.

Every field is pending transcription (age-65-params): None in params AND in
the attestation, and declared in the attestation's PENDING_TRANSCRIPTION.
Reading the per-status pending field through ``for_status`` refuses with the
named UnsupportedStatusError, never a TypeError or KeyError off the None.
"""
import dataclasses
import importlib
import unittest

from tenforty import years
from tenforty.models import FilingStatus
from tenforty.params import california as ca_params
from tenforty.params.california import CaliforniaParams
from tenforty.params.federal import PER_STATUS_FEDERAL_FIELDS, FederalParams
from tenforty.params.federal import load as load_federal
from tenforty.params.status_view import UnsupportedStatusError

_FEDERAL_YEARS = years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS
_CALIFORNIA_YEARS = years.CALIFORNIA_YEARS + years.CALIFORNIA_COMPUTE_ONLY_YEARS

FEDERAL_AGE_FIELDS = ("additional_standard_deduction", "aged_born_before")
CALIFORNIA_AGE_FIELDS = ("senior_exemption_credit", "senior_born_before")


def _attestation(jurisdiction: str, year: int):
    return importlib.import_module(
        f"tests.params_attestations.{jurisdiction}_y{year}")


class AgeSchemaTests(unittest.TestCase):
    def test_federal_fields_declared(self):
        names = {f.name for f in dataclasses.fields(FederalParams)}
        for name in FEDERAL_AGE_FIELDS:
            self.assertIn(name, names)

    def test_california_fields_declared(self):
        names = {f.name for f in dataclasses.fields(CaliforniaParams)}
        for name in CALIFORNIA_AGE_FIELDS:
            self.assertIn(name, names)

    def test_additional_standard_deduction_is_per_status(self):
        self.assertIn("additional_standard_deduction",
                      PER_STATUS_FEDERAL_FIELDS)
        # The cutoff is one date for every status, not a status column.
        self.assertNotIn("aged_born_before", PER_STATUS_FEDERAL_FIELDS)

    def test_federal_fields_pending_on_both_sides_every_year(self):
        for year in _FEDERAL_YEARS:
            params = load_federal(year)
            module = _attestation("federal", year)
            for name in FEDERAL_AGE_FIELDS:
                with self.subTest(year=year, field=name):
                    self.assertIsNone(getattr(params, name))
                    self.assertIsNone(module.ATTESTED[name])
                    self.assertIn(name, module.PENDING_TRANSCRIPTION)

    def test_california_fields_pending_on_both_sides_every_year(self):
        for year in _CALIFORNIA_YEARS:
            params = ca_params.load(year)
            module = _attestation("california", year)
            for name in CALIFORNIA_AGE_FIELDS:
                with self.subTest(year=year, field=name):
                    self.assertIsNone(getattr(params, name))
                    self.assertIsNone(module.ATTESTED[name])
                    self.assertIn(name, module.PENDING_TRANSCRIPTION)

    def test_pending_per_status_field_refuses_by_name(self):
        for year in _FEDERAL_YEARS:
            params = load_federal(year)
            for status in FilingStatus:
                view = params.for_status(status)
                with self.subTest(year=year, status=status):
                    with self.assertRaisesRegex(
                            UnsupportedStatusError,
                            r"additional_standard_deduction.*pending "
                            r"transcription") as ctx:
                        view.additional_standard_deduction
                    self.assertEqual(ctx.exception.field,
                                     "additional_standard_deduction")
                    self.assertEqual(ctx.exception.year, year)
                    self.assertIsNone(ctx.exception.__cause__)

    def test_pending_refusal_is_a_not_implemented_refusal(self):
        # Existing fail-closed handling catches NotImplementedError.
        view = load_federal(_FEDERAL_YEARS[-1]).for_status(FilingStatus.SINGLE)
        with self.assertRaises(NotImplementedError):
            view.additional_standard_deduction

    def test_present_per_status_field_still_reads(self):
        # The pending guard fires on None only; a transcribed column reads.
        params = load_federal(_FEDERAL_YEARS[-1])
        column = object()
        live = dataclasses.replace(
            params, additional_standard_deduction={
                FilingStatus.SINGLE.value: column})
        self.assertIs(
            live.for_status(FilingStatus.SINGLE).additional_standard_deduction,
            column)
        with self.assertRaisesRegex(UnsupportedStatusError,
                                    "is not supported"):
            live.for_status(
                FilingStatus.HEAD_OF_HOUSEHOLD).additional_standard_deduction
