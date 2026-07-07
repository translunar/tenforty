# tests/test_params_load_manifest.py
"""Both params load() functions gate on the manifest and discover modules
by name — adding a year must touch zero lines of load()."""
import unittest

from tenforty import years as year_manifest
from tenforty.params import california as ca_params
from tenforty.params.federal import load as load_federal


class FederalParamsLoadTests(unittest.TestCase):
    def test_every_manifest_year_loads_and_selfidentifies(self):
        for year in year_manifest.FEDERAL_YEARS:
            with self.subTest(year=year):
                self.assertEqual(load_federal(year).year, year)

    def test_unsupported_year_error_names_request_and_supported_set(self):
        with self.assertRaises(ValueError) as ctx:
            load_federal(2019)
        message = str(ctx.exception)
        self.assertIn("2019", message)
        for year in year_manifest.FEDERAL_YEARS:
            self.assertIn(str(year), message)


class CaliforniaParamsLoadTests(unittest.TestCase):
    def test_every_manifest_year_loads_and_selfidentifies(self):
        for year in (year_manifest.CALIFORNIA_YEARS
                     + year_manifest.CALIFORNIA_COMPUTE_ONLY_YEARS):
            with self.subTest(year=year):
                self.assertEqual(ca_params.load(year).year, year)

    def test_unsupported_year_error_names_request_and_supported_set(self):
        with self.assertRaises(NotImplementedError) as ctx:
            ca_params.load(2019)
        message = str(ctx.exception)
        self.assertIn("2019", message)
        self.assertIn("2021", message)
        self.assertIn("2025", message)
