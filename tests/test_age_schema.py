"""Schema for the age-65 condition (ruling R-age): the federal aged
additional standard deduction and cutoff, and the California senior
exemption credit and cutoff.

The pending-transcription contract (None in params AND attestation, declared
in PENDING_TRANSCRIPTION) and the ``for_status`` pending refusal are tested
on SYNTHETIC params and attestation doubles, never on the real fields'
current state: a transcription landing must not redden this file. The real
fields' values are guarded by tests/test_params_attestation.py.
"""
import dataclasses
import importlib
import sys
import types
import unittest
from unittest import mock

from tenforty import years
from tenforty.models import FilingStatus
from tenforty.params import california as ca_params
from tenforty.params.california import CaliforniaParams
from tenforty.params.federal import PER_STATUS_FEDERAL_FIELDS, FederalParams
from tenforty.params.federal import load as load_federal
from tenforty.params.status_view import UnsupportedStatusError
from tests.test_params_attestation import _assert_attested, _Probe

_FEDERAL_YEARS = years.FEDERAL_YEARS + years.FEDERAL_COMPUTE_ONLY_YEARS
_CALIFORNIA_YEARS = years.CALIFORNIA_YEARS + years.CALIFORNIA_COMPUTE_ONLY_YEARS

FEDERAL_AGE_FIELDS = ("additional_standard_deduction", "aged_born_before")
CALIFORNIA_AGE_FIELDS = ("senior_exemption_credit", "senior_born_before")

# (jurisdiction, loader, params class, fields, years)
_JURISDICTIONS = (
    ("federal", load_federal, FederalParams, FEDERAL_AGE_FIELDS,
     _FEDERAL_YEARS),
    ("california", ca_params.load, CaliforniaParams, CALIFORNIA_AGE_FIELDS,
     _CALIFORNIA_YEARS),
)


def _attestation(jurisdiction: str, year: int):
    return importlib.import_module(
        f"tests.params_attestations.{jurisdiction}_y{year}")


def _pending_federal(year: int) -> FederalParams:
    """Synthetic: the year's real params with the per-status field pending."""
    return dataclasses.replace(load_federal(year),
                               additional_standard_deduction=None)


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

    def test_every_year_attestation_carries_the_fields(self):
        # State-independent: the key is present whether pending or attested.
        for jurisdiction, _, _, fields, year_list in _JURISDICTIONS:
            for year in year_list:
                module = _attestation(jurisdiction, year)
                for name in fields:
                    with self.subTest(jurisdiction=jurisdiction, year=year,
                                      field=name):
                        self.assertIn(name, module.ATTESTED)


class PendingTranscriptionContractTests(unittest.TestCase):
    """Each age field, pending on SYNTHETIC doubles built from the year's
    real params and attestation, through the real generic attestation gate:
    None on both sides passes; a live params value while pending fails."""

    MODULE = "tests._synthetic_age_attestation"

    def _gate(self, jurisdiction, load, params_cls, year, name, value):
        real = _attestation(jurisdiction, year)
        module = types.ModuleType(self.MODULE)
        module.SOURCES = real.SOURCES
        module.NOT_APPLICABLE = getattr(real, "NOT_APPLICABLE", {})
        module.ATTESTED = {**real.ATTESTED, name: None}
        module.PENDING_TRANSCRIPTION = {
            **getattr(real, "PENDING_TRANSCRIPTION", {}), name: "synthetic"}
        params = dataclasses.replace(load(year), **{name: value})
        with mock.patch.dict(sys.modules, {self.MODULE: module}):
            _assert_attested(_Probe("run_probe"), params, params_cls,
                             self.MODULE)

    def test_pending_none_on_both_sides_passes(self):
        for jurisdiction, load, cls, fields, year_list in _JURISDICTIONS:
            for year in year_list:
                for name in fields:
                    with self.subTest(jurisdiction=jurisdiction, year=year,
                                      field=name):
                        self._gate(jurisdiction, load, cls, year, name, None)

    def test_live_params_value_while_pending_fails(self):
        for jurisdiction, load, cls, fields, year_list in _JURISDICTIONS:
            for year in year_list:
                for name in fields:
                    with self.subTest(jurisdiction=jurisdiction, year=year,
                                      field=name):
                        with self.assertRaisesRegex(AssertionError,
                                                    "pending transcription"):
                            self._gate(jurisdiction, load, cls, year, name,
                                       object())


class PendingPerStatusRefusalTests(unittest.TestCase):
    """``for_status`` on SYNTHETIC params whose per-status field is None."""

    def test_pending_per_status_field_refuses_by_name(self):
        for year in _FEDERAL_YEARS:
            params = _pending_federal(year)
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
                    self.assertTrue(ctx.exception.pending)
                    self.assertIsNone(ctx.exception.__cause__)

    def test_pending_refusal_is_a_not_implemented_refusal(self):
        # Existing fail-closed handling catches NotImplementedError.
        view = _pending_federal(_FEDERAL_YEARS[-1]).for_status(
            FilingStatus.SINGLE)
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
                                    "is not supported") as ctx:
            live.for_status(
                FilingStatus.HEAD_OF_HOUSEHOLD).additional_standard_deduction
        self.assertFalse(ctx.exception.pending)
