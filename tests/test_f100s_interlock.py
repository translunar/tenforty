import tempfile
import unittest
from pathlib import Path

from tenforty import years
from tenforty.models import SCorpCAInputs
from tenforty.orchestrator import ReturnOrchestrator
from tests._scorp_fixtures import _make_v1_scenario


def _with_ca(scenario, first_year=False):
    scenario.s_corp_return.ca = SCorpCAInputs(
        first_year=first_year,
        estimated_tax_payments=0.0,
        prior_year_overpayment_applied=0.0,
        state_tax_deducted_federally=0.0,
        depreciation_adjustment=0.0,
        apportionment_ca_only=True,
    )
    return scenario


class F100SInterlockTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(self._tmp.name),
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_ca_income_base_equals_federal_line(self):
        s = _with_ca(_make_v1_scenario(gross_receipts=100000.0,
                                       compensation_of_officers=30000.0))
        corp = self.orch.compute_corporate(s)
        ca = self.orch.compute_california_corporate(s)
        self.assertEqual(ca["f100s_federal_ordinary_income"],
                         corp["f1120s_ordinary_business_income"])

    def test_k1_totals_foot_across_jurisdictions(self):
        s = _with_ca(_make_v1_scenario(gross_receipts=100000.0,
                                       compensation_of_officers=30000.0))
        ca = self.orch.compute_california_corporate(s)
        corp = self.orch.compute_corporate(s)
        allocs = ca["f100s_k1_allocations"]
        self.assertAlmostEqual(
            sum(a["ca_ordinary_income"] for a in allocs),
            ca["f100s_net_income_for_tax"])
        self.assertAlmostEqual(
            sum(a["federal_ordinary_income"] for a in allocs),
            corp["f1120s_sch_k_ordinary_business_income"])

    def test_no_ca_block_means_no_ca_corporate_keys(self):
        s = _make_v1_scenario()  # s_corp_return set but no .ca
        self.assertEqual(self.orch.compute_california_corporate(s), {})
        s2 = _make_v1_scenario()
        s2.s_corp_return = None
        self.assertEqual(self.orch.compute_california_corporate(s2), {})

    def test_every_ca_scorp_year_computes(self):
        for year in years.CA_SCORP_YEARS:
            with self.subTest(year=year):
                s = _with_ca(_make_v1_scenario(
                    gross_receipts=100000.0, compensation_of_officers=30000.0))
                s.config.year = year
                ca = self.orch.compute_california_corporate(s)
                self.assertIn("f100s_franchise_tax", ca)
                self.assertEqual(ca["f100s_federal_ordinary_income"], 70000.0)
