import unittest

from tenforty import years
from tenforty.forms import f100s
from tenforty.models import SCorpCAInputs
from tenforty.params import ca_scorp
from tenforty.rounding import irs_round
from tests._scorp_fixtures import _make_v1_scenario


def _compute_100s(year, federal_ordinary, *, first_year=False,
                  state_addback=0.0, depr_adj=0.0,
                  est_pay=0.0, prior_overpay=0.0):
    """Run f100s.compute for a synthetic scenario: federal ordinary income
    is fed directly via upstream (f100s does not run the federal return),
    config.year drives which attested params load, and the ca sub-block
    carries the CA inputs."""
    s = _make_v1_scenario()
    s.config.year = year
    s.s_corp_return.ca = SCorpCAInputs(
        first_year=first_year,
        estimated_tax_payments=est_pay,
        prior_year_overpayment_applied=prior_overpay,
        state_tax_deducted_federally=state_addback,
        depreciation_adjustment=depr_adj,
        apportionment_ca_only=True,
    )
    upstream = {"f1120s": {"f1120s_ordinary_business_income": federal_ordinary}}
    return f100s.compute(s, upstream)


class F100SComputeTests(unittest.TestCase):
    def test_net_income_equals_federal_plus_adjustments(self):
        out = _compute_100s(2025, 100000, state_addback=5000, depr_adj=2000)
        self.assertEqual(
            out["f100s_net_income_for_tax"],
            out["f100s_federal_ordinary_income"]
            + out["f100s_state_tax_addback"]
            + out["f100s_depreciation_adjustment"])

    def test_minimum_tax_floor_binds_on_low_income(self):
        # net income 500; measured (rate*500) is far below the minimum floor.
        out = _compute_100s(2025, 500, first_year=False)
        p = ca_scorp.load(2025)
        self.assertTrue(out["f100s_minimum_tax_applies"])
        self.assertEqual(out["f100s_franchise_tax"], p.minimum_franchise_tax)

    def test_measured_tax_governs_above_floor(self):
        # net income high enough that measured tax exceeds the minimum floor.
        out = _compute_100s(2025, 100000, first_year=False)
        p = ca_scorp.load(2025)
        self.assertFalse(out["f100s_minimum_tax_applies"])
        self.assertEqual(out["f100s_franchise_tax"], out["f100s_measured_tax"])
        self.assertEqual(
            out["f100s_measured_tax"],
            irs_round(out["f100s_net_income_for_tax"] * p.franchise_tax_rate))

    def test_first_year_exemption_respects_params(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                p = ca_scorp.load(year)
                out = _compute_100s(year, 500, first_year=True)
                if p.first_year_minimum_tax_exempt:
                    # floor waived in year one: measured governs even below floor
                    self.assertFalse(out["f100s_minimum_tax_applies"])
                    self.assertEqual(out["f100s_franchise_tax"],
                                     out["f100s_measured_tax"])
                else:
                    self.assertTrue(out["f100s_minimum_tax_applies"])
                    self.assertEqual(out["f100s_franchise_tax"],
                                     p.minimum_franchise_tax)

    def test_loss_year_still_pays_minimum_when_not_first_year(self):
        out = _compute_100s(2025, -20000, first_year=False)
        p = ca_scorp.load(2025)
        self.assertEqual(out["f100s_measured_tax"], 0)
        self.assertTrue(out["f100s_minimum_tax_applies"])
        self.assertEqual(out["f100s_franchise_tax"], p.minimum_franchise_tax)

    def test_payments_and_balance_arithmetic(self):
        out = _compute_100s(2025, 100000, first_year=False,
                            est_pay=1000, prior_overpay=200)
        self.assertEqual(
            out["f100s_total_payments"],
            out["f100s_estimated_tax_payments"]
            + out["f100s_prior_year_overpayment_applied"])
        tax = out["f100s_franchise_tax"]
        pay = out["f100s_total_payments"]
        self.assertEqual(out["f100s_amount_owed"], max(tax - pay, 0))
        self.assertEqual(out["f100s_overpayment"], max(pay - tax, 0))
