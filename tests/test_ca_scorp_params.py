# tests/test_ca_scorp_params.py
"""CA S-corp params load/gating — structural only (no tax figures here;
values are proven by the air-gapped attestation gate, test_params_attestation)."""
import dataclasses
import unittest

from tenforty import years
from tenforty.params import ca_scorp


class CAScorpParamsTests(unittest.TestCase):
    def test_loads_every_declared_year(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                p = ca_scorp.load(year)
                self.assertEqual(p.year, year)
                self.assertGreater(p.franchise_tax_rate, 0.0)
                self.assertLess(p.franchise_tax_rate, 0.1)
                self.assertGreater(p.minimum_franchise_tax, 0)

    def test_undeclared_year_raises(self):
        with self.assertRaises(NotImplementedError):
            ca_scorp.load(1999)

    def test_no_field_defaults(self):
        for f in dataclasses.fields(ca_scorp.CAScorpParams):
            self.assertIs(f.default, dataclasses.MISSING, f.name)
            self.assertIs(f.default_factory, dataclasses.MISSING, f.name)
