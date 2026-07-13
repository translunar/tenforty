import unittest

from tenforty import years
from tenforty.forms import f100s
from tenforty.models import SCorpCAInputs
from tests._scorp_fixtures import _make_v1_scenario
from tests.oracles import f100s_reference

# Battery of CA net-income probes: losses, zero, the low-income floor band,
# a boundary near where measured tax overtakes the floor, and large incomes.
NET_INCOMES = [-50_000, -1, 0, 1, 500, 5_000, 53_333, 250_000, 4_000_000]


class F100SOracleBattery(unittest.TestCase):
    def _franchise_tax(self, year, net, first_year):
        s = _make_v1_scenario()
        s.config.year = year
        s.s_corp_return.ca = SCorpCAInputs(
            first_year=first_year,
            estimated_tax_payments=0.0,
            prior_year_overpayment_applied=0.0,
            state_tax_deducted_federally=0.0,
            depreciation_adjustment=0.0,
            apportionment_ca_only=True,
        )
        out = f100s.compute(
            s, {"f1120s": {"f1120s_ordinary_business_income": net}})
        return out["f100s_franchise_tax"]

    def test_franchise_tax_matches_reference(self):
        for year in years.CA_SCORP_YEARS:
            for net in NET_INCOMES:
                for first_year in (False, True):
                    with self.subTest(year=year, net=net,
                                      first_year=first_year):
                        got = self._franchise_tax(year, net, first_year)
                        want = f100s_reference.reference_franchise_tax(
                            year, net, first_year)
                        self.assertEqual(got, want)
