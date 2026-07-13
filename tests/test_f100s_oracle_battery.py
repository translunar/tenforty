import tempfile
import unittest
from pathlib import Path

from tenforty import years
from tenforty.forms import f100s
from tenforty.models import SCorpCAInputs, SCorpShareholder
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.rounding import irs_round
from tests._scorp_fixtures import _example_address, _make_v1_scenario
from tests.oracles import f100s_reference

# Battery of CA net-income probes: losses, zero, the low-income floor band,
# a boundary near where measured tax overtakes the floor, and large incomes.
# Fractional probes discriminate single- vs two-stage whole-dollar rounding:
# the ~$1 divergence between round(net*rate) and round(round(net)*rate) is only
# visible when the $800 floor does NOT mask it, i.e. under first_year=True
# (99.6, 100.5, 5_000.4) or above the floor-crossing (53_499.6) where measured
# tax exceeds $800 for non-first-year too.
NET_INCOMES = [
    -50_000, -1, 0, 1, 500, 5_000, 53_333, 250_000, 4_000_000,
    99.6, 100.5, 5_000.4, 53_499.6,
]

# Probes for the net-income ASSEMBLY path (federal ordinary income + CA
# state-tax addback + CA depreciation adjustment). Every probe carries
# FRACTIONAL, NONZERO addback/depreciation so the two-stage whole-dollar
# rounding is genuinely exercised, and each is chosen to DISCRIMINATE: the
# first three sit above the $800 floor-crossing (measured tax > $800, so the
# minimum-tax floor never masks a dropped term) and the last two use
# first_year=True (no floor at all). One probe carries a negative depreciation
# adjustment. Fractional parts avoid the exact-.5 boundary so float irs_round
# and the Decimal reference agree unambiguously.
# (federal_income, state_tax_addback, depreciation_adjustment, first_year)
ASSEMBLY_PROBES = [
    (250_000, 1234.60, 567.40, False),
    (250_000, 2345.65, 678.20, False),
    (250_000, 1234.60, -567.40, False),
    (50_000, 1234.60, 567.40, True),
    (50_000, 2345.65, 678.20, True),
]

# Uneven multi-shareholder splits (percentages summing to exactly 100, NOT all
# equal) for the Schedule K-1 (100S) allocation path.
K1_SPLITS = [
    (33.33, 33.33, 33.34),
    (58.0, 29.0, 13.0),
]


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

    def test_net_income_assembly_with_addback_and_depreciation(self):
        """Drive f100s.compute with NONZERO state-tax addback and depreciation
        adjustment so the net-income assembly (federal ordinary income + addback
        + depreciation) is exercised, then check the resulting franchise tax
        against reference_franchise_tax fed the raw pre-rounding sum."""
        for year in years.CA_SCORP_YEARS:
            for federal_income, addback, depreciation, first_year in \
                    ASSEMBLY_PROBES:
                with self.subTest(year=year, federal_income=federal_income,
                                  addback=addback, depreciation=depreciation,
                                  first_year=first_year):
                    s = _make_v1_scenario()
                    s.config.year = year
                    s.s_corp_return.ca = SCorpCAInputs(
                        first_year=first_year,
                        estimated_tax_payments=0.0,
                        prior_year_overpayment_applied=0.0,
                        state_tax_deducted_federally=addback,
                        depreciation_adjustment=depreciation,
                        apportionment_ca_only=True,
                    )
                    out = f100s.compute(
                        s,
                        {"f1120s": {
                            "f1120s_ordinary_business_income": federal_income}},
                    )
                    want = f100s_reference.reference_franchise_tax(
                        year, federal_income + addback + depreciation,
                        first_year)
                    self.assertEqual(out["f100s_franchise_tax"], want)

    def test_k1_allocations_match_reference(self):
        """Run the PRODUCTION CA K-1 (100S) allocator end-to-end over an UNEVEN
        multi-shareholder split and check each per-shareholder CA and federal
        ordinary-income share against reference_k1_share.

        The expected ownership fraction is derived independently from the
        ground-truth shareholder percentages the test constructs (NOT from the
        allocator's own output), so a bug in how production derives the fraction
        cannot hide behind a matching fraction in the reference call."""
        orch = ReturnOrchestrator(
            spreadsheets_dir=Path("spreadsheets"),
            work_dir=Path(tempfile.gettempdir()),
        )
        for year in years.CA_SCORP_YEARS:
            for split in K1_SPLITS:
                with self.subTest(year=year, split=split):
                    # gross - officer comp gives OBI = 223_457; the whole-dollar
                    # $5,000 addback lifts CA net income to 228_457 so the CA
                    # and federal bases DIFFER, and every share lands on cents.
                    s = _make_v1_scenario(
                        gross_receipts=253_457.0,
                        compensation_of_officers=30_000.0,
                    )
                    s.config.year = year
                    s.s_corp_return.ca = SCorpCAInputs(
                        first_year=False,
                        estimated_tax_payments=0.0,
                        prior_year_overpayment_applied=0.0,
                        state_tax_deducted_federally=5_000.0,
                        depreciation_adjustment=0.0,
                        apportionment_ca_only=True,
                    )
                    s.s_corp_return.shareholders = [
                        SCorpShareholder(
                            name=f"Shareholder {i}",
                            ssn_or_ein=f"000-00-000{i}",
                            address=_example_address(),
                            ownership_percentage=pct,
                        )
                        for i, pct in enumerate(split, start=1)
                    ]
                    results = orch.compute_california_corporate(s)
                    ca_net = results["f100s_net_income_for_tax"]
                    federal_total = results["f100s_federal_ordinary_income"]
                    allocs = results["f100s_k1_allocations"]

                    self.assertEqual(len(allocs), len(split))
                    ca_shares = []
                    for alloc in allocs:
                        idx = alloc["shareholder_index"]
                        expected_fraction = (
                            s.s_corp_return.shareholders[idx]
                            .ownership_percentage / 100.0
                        )
                        self.assertEqual(
                            irs_round(alloc["ca_ordinary_income"]),
                            f100s_reference.reference_k1_share(
                                ca_net, expected_fraction),
                        )
                        self.assertEqual(
                            irs_round(alloc["federal_ordinary_income"]),
                            f100s_reference.reference_k1_share(
                                federal_total, expected_fraction),
                        )
                        ca_shares.append(irs_round(alloc["ca_ordinary_income"]))
                    # The split is genuinely uneven: the shares are not all
                    # equal, so the test cannot pass by trivial symmetry.
                    self.assertGreater(len(set(ca_shares)), 1)
