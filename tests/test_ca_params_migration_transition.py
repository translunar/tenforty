# tests/test_ca_params_migration_transition.py
"""Transition-only migration gate: params.california must equal the legacy
constants modules field-for-field, every year, every filing status.

DELETE this file in the same commit that deletes tenforty/constants/ —
its job ends when the legacy modules are gone (the permanent oracle tests
in tests/test_ca540_compute.py keep validating the values themselves).
"""
import importlib
import unittest

from tenforty.models import FilingStatus
from tenforty.params import california as ca_params

_YEARS = (2021, 2022, 2023, 2024, 2025)


class CaParamsMigrationEquivalenceTests(unittest.TestCase):
    def test_params_equal_legacy_constants(self):
        for year in _YEARS:
            legacy = importlib.import_module(
                f"tenforty.constants.california_y{year}")
            params = ca_params.load(year)
            self.assertEqual(params.year, year)
            self.assertEqual(params.dependent_exemption_amount,
                             legacy.DEPENDENT_EXEMPTION_AMOUNT)
            self.assertEqual(params.agi_phaseout_threshold,
                             legacy.AGI_PHASEOUT_THRESHOLD)
            for status in FilingStatus:
                with self.subTest(year=year, status=status):
                    self.assertEqual(
                        params.standard_deduction[status.value],
                        legacy.STANDARD_DEDUCTION[status])
                    self.assertEqual(
                        params.exemption_credit[status.value],
                        legacy.EXEMPTION_CREDIT[status])
                    self.assertEqual(
                        params.rate_schedule[status.value],
                        tuple(tuple(b) for b in legacy.RATE_SCHEDULE[status]))
                    self.assertEqual(
                        params.renter_credit_agi_threshold[status.value],
                        legacy.RENTER_CREDIT_AGI_THRESHOLD[status])
                    self.assertEqual(
                        params.renter_credit_amount[status.value],
                        legacy.RENTER_CREDIT_AMOUNT[status])
