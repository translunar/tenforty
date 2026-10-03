"""Production-vs-oracle comparison battery for Form 1120-S, 2021-2025.

Drives `tenforty.forms.f1120s.compute` and the air-gapped reference
`tests/oracles/f1120s_reference.py` over the same synthetic scenarios and
compares every numeric output key. The oracle reports UNROUNDED amounts;
production rounds each line to whole dollars. Per tests/oracles/README.md
rule 3, the comparison applies production's `irs_round` to the ORACLE side at
the boundary; tolerance is never added.

Interface notes honoured here (not divergences):
  * refundable_credits is only meaningful 2023+ (oracle raises 2021-2022).
  * Schedule K separately-stated items have no production inputs, so line 18
    equals line 1 at top level.
  * Section 453 interest is refused by production (shareholder-level), so it
    is always zero in this battery.

All data is synthetic; amounts are $50 multiples except where cents are the
point.
"""

import unittest

from tenforty.forms import f1120s
from tenforty.models import SCorp199AInfo
from tenforty.rounding import irs_round
from tests._scorp_fixtures import _make_v1_scenario
from tests.oracles import f1120s_reference as oracle

YEARS = (2021, 2022, 2023, 2024, 2025)

_ZERO_DED = dict(
    compensation_of_officers=0.0, salaries_wages=0.0, repairs_maintenance=0.0,
    bad_debts=0.0, rents=0.0, taxes_licenses=0.0, interest=0.0,
    depreciation=0.0, depletion=0.0, advertising=0.0,
    pension_profit_sharing_plans=0.0, employee_benefits=0.0,
    other_deductions=0.0,
)

# name -> dict(income=..., deductions=..., scope_outs=..., payments=...,
#              pcts=..., s199a=...)
# `payments` may carry refundable_credits; it is stripped for 2021-2022.
SCENARIOS = {
    "small_modest_profit": dict(
        income=dict(gross_receipts=60_000.0),
        deductions=dict(compensation_of_officers=20_000.0, rents=6_000.0),
    ),
    "zero_activity": dict(income=dict(gross_receipts=0.0)),
    "loss_year": dict(
        income=dict(gross_receipts=40_000.0),
        deductions=dict(compensation_of_officers=30_000.0,
                        salaries_wages=25_000.0, rents=12_000.0),
    ),
    "mid_all_income_lines": dict(
        income=dict(gross_receipts=500_000.0, returns_and_allowances=20_000.0,
                    cogs_aggregate=150_000.0, net_gain_loss_4797=5_000.0,
                    other_income=2_500.0),
        deductions=dict(compensation_of_officers=80_000.0),
    ),
    "negative_4797_and_other": dict(
        income=dict(gross_receipts=200_000.0, net_gain_loss_4797=-7_500.0,
                    other_income=-1_000.0),
        deductions=dict(salaries_wages=50_000.0),
    ),
    "all_deduction_categories": dict(
        income=dict(gross_receipts=900_000.0, returns_and_allowances=10_000.0,
                    cogs_aggregate=200_000.0),
        deductions=dict(
            compensation_of_officers=100_000.0, salaries_wages=150_000.0,
            repairs_maintenance=3_000.0, bad_debts=1_000.0, rents=24_000.0,
            taxes_licenses=9_000.0, interest=2_000.0, depreciation=12_000.0,
            depletion=500.0, advertising=4_000.0,
            pension_profit_sharing_plans=6_000.0, employee_benefits=5_000.0,
            other_deductions=10_500.0),
    ),
    "large": dict(
        income=dict(gross_receipts=12_500_000.0,
                    returns_and_allowances=250_000.0,
                    cogs_aggregate=4_000_000.0, net_gain_loss_4797=50_000.0,
                    other_income=25_000.0),
        deductions=dict(compensation_of_officers=1_000_000.0,
                        salaries_wages=3_000_000.0, depreciation=400_000.0,
                        other_deductions=1_500_000.0),
    ),
    "cents_everywhere": dict(
        income=dict(gross_receipts=100_000.60, returns_and_allowances=500.30,
                    cogs_aggregate=20_000.25, net_gain_loss_4797=100.45,
                    other_income=50.55),
        deductions=dict(compensation_of_officers=30_000.40,
                        salaries_wages=10_000.35, rents=5_000.50,
                        depreciation=1_000.25, other_deductions=250.65),
    ),
    "cents_half_boundaries": dict(
        income=dict(gross_receipts=10_000.50, cogs_aggregate=0.50),
        deductions=dict(compensation_of_officers=2_000.50,
                        salaries_wages=1_000.50),
    ),
    "cents_loss": dict(
        income=dict(gross_receipts=1_000.40),
        deductions=dict(compensation_of_officers=3_000.60,
                        rents=500.20),
    ),
    "split_60_40_cents": dict(
        income=dict(gross_receipts=253_457.35),
        deductions=dict(compensation_of_officers=30_000.15),
        pcts=[60.0, 40.0],
    ),
    "split_three_way": dict(
        income=dict(gross_receipts=300_000.0),
        deductions=dict(compensation_of_officers=50_000.0),
        pcts=[50.0, 30.0, 20.0],
    ),
    "split_thirds_uneven_cents": dict(
        income=dict(gross_receipts=211_111.11),
        deductions=dict(salaries_wages=11_111.11),
        pcts=[33.33, 33.33, 33.34],
    ),
    "split_loss": dict(
        income=dict(gross_receipts=20_000.0),
        deductions=dict(compensation_of_officers=50_000.0),
        pcts=[75.0, 25.0],
    ),
    "section_199a_default_qbi": dict(
        income=dict(gross_receipts=400_000.0),
        deductions=dict(compensation_of_officers=100_000.0),
        pcts=[60.0, 40.0],
        s199a=dict(w2_wages=100_000.0, ubia=50_000.0),
    ),
    "section_199a_override_qbi": dict(
        income=dict(gross_receipts=400_000.0),
        deductions=dict(compensation_of_officers=100_000.0),
        pcts=[50.0, 30.0, 20.0],
        s199a=dict(qbi_override=250_000.0, w2_wages=100_000.0, ubia=50_000.0),
    ),
    # Tax / payments / balance branches.
    "tax_owed_no_payments": dict(
        income=dict(gross_receipts=500_000.0),
        scope_outs=dict(net_passive_income_tax=1_000.0,
                        built_in_gains_tax=2_500.0),
    ),
    "tax_partly_paid_owed": dict(
        income=dict(gross_receipts=500_000.0),
        scope_outs=dict(net_passive_income_tax=1_000.0,
                        built_in_gains_tax=2_500.0),
        payments=dict(estimated_tax_payments=1_000.0,
                      prior_year_overpayment_credited=500.0),
    ),
    "tax_fully_paid_exact": dict(
        income=dict(gross_receipts=500_000.0),
        scope_outs=dict(built_in_gains_tax=3_000.0),
        payments=dict(estimated_tax_payments=1_000.0,
                      tax_deposited_with_7004=1_500.0,
                      credit_for_federal_excise_tax=500.0),
    ),
    "overpayment_all_payment_lines": dict(
        income=dict(gross_receipts=500_000.0),
        scope_outs=dict(net_passive_income_tax=500.0),
        payments=dict(estimated_tax_payments=1_000.0,
                      prior_year_overpayment_credited=250.0,
                      tax_deposited_with_7004=300.0,
                      credit_for_federal_excise_tax=150.0,
                      refundable_credits=200.0),
    ),
    "overpayment_no_tax": dict(
        income=dict(gross_receipts=100_000.0),
        payments=dict(estimated_tax_payments=800.0),
    ),
    "refundable_credits_creates_overpayment": dict(
        income=dict(gross_receipts=100_000.0),
        scope_outs=dict(built_in_gains_tax=1_000.0),
        payments=dict(estimated_tax_payments=1_000.0,
                      refundable_credits=350.0),
    ),
    "cents_tax_and_payments": dict(
        income=dict(gross_receipts=100_000.0),
        scope_outs=dict(net_passive_income_tax=1_000.40,
                        built_in_gains_tax=2_000.40),
        payments=dict(estimated_tax_payments=1_500.20,
                      prior_year_overpayment_credited=700.20,
                      tax_deposited_with_7004=300.20),
    ),
    "cents_overpayment": dict(
        income=dict(gross_receipts=100_000.0),
        scope_outs=dict(net_passive_income_tax=100.40),
        payments=dict(estimated_tax_payments=500.30,
                      tax_deposited_with_7004=200.20),
    ),
}

_SCALAR_KEYS_SKIP = {"f1120s_sch_k1_allocations"}

# Recorded production-vs-oracle DIVERGENCES (see the expectedFailure tests
# below; each is compared strictly there, never loosened). The main
# comparisons skip exactly these so the rest of the surface stays enforced.
#  D1: Sch K line 18 -- production emits the v1 zero placeholder; oracle = line 1.
#  D2: line 21 / Sch K line 1 / K-1 box 1 -- production computes line 6(rounded)
#      minus line 20(raw) then rounds; oracle rounds the raw difference.
#  D3: line 26 overpayment -- production subtracts rounded line 22c from RAW
#      line 23 sum then rounds; oracle rounds the raw difference.
D1_KEY = "f1120s_sch_k_income_loss_reconciliation"
D2_SCENARIO = "cents_loss"
D2_KEYS = {"f1120s_ordinary_business_income",
           "f1120s_sch_k_ordinary_business_income"}
D3_SCENARIO = "cents_overpayment"
D3_KEY = "f1120s_overpayment"


def _known_divergence(scenario, key):
    return (key == D1_KEY
            or (scenario == D2_SCENARIO and key in D2_KEYS)
            or (scenario == D3_SCENARIO and key == D3_KEY))


def build(year, spec):
    s = _make_v1_scenario(shareholder_pcts=spec.get("pcts"))
    s.config.year = year
    r = s.s_corp_return
    for group, fields in (("income", spec.get("income", {})),
                          ("deductions", spec.get("deductions", {})),
                          ("scope_outs", spec.get("scope_outs", {})),
                          ("payments", spec.get("payments", {}))):
        target = getattr(r, group)
        if group == "income":
            target.returns_and_allowances = 0.0
            target.cogs_aggregate = 0.0
            target.net_gain_loss_4797 = 0.0
            target.other_income = 0.0
        if group == "deductions":
            for k, v in _ZERO_DED.items():
                setattr(target, k, v)
        for k, v in fields.items():
            if group == "payments" and k == "refundable_credits" \
                    and year < 2023:
                continue
            setattr(target, k, v)
    if "gross_receipts" not in spec.get("income", {}):
        r.income.gross_receipts = 0.0
    if "s199a" in spec:
        r.section_199a = SCorp199AInfo(**spec["s199a"])
    return s


class F1120SOracleBattery(unittest.TestCase):
    def test_scalar_outputs_match_oracle(self):
        for year in YEARS:
            for name, spec in SCENARIOS.items():
                s = build(year, spec)
                got = f1120s.compute(s, upstream={})
                want = oracle.reference_f1120s(year, s.s_corp_return)
                for key in sorted(want):
                    if key in _SCALAR_KEYS_SKIP \
                            or _known_divergence(name, key):
                        continue
                    with self.subTest(year=year, scenario=name, key=key):
                        self.assertIn(key, got)
                        w = want[key]
                        if isinstance(w, float):
                            w = irs_round(w)
                        self.assertEqual(got[key], w)

    def test_k1_allocations_match_oracle(self):
        for year in YEARS:
            for name, spec in SCENARIOS.items():
                s = build(year, spec)
                got = f1120s.compute(s, upstream={})["f1120s_sch_k1_allocations"]
                want = oracle.reference_f1120s(
                    year, s.s_corp_return)["f1120s_sch_k1_allocations"]
                with self.subTest(year=year, scenario=name, part="count"):
                    self.assertEqual(len(got), len(want))
                for i, (g, w) in enumerate(zip(got, want)):
                    if name == D2_SCENARIO:
                        continue  # D2: box 1 inherits the line 21 divergence
                    with self.subTest(year=year, scenario=name, holder=i):
                        self.assertEqual(g.shareholder.name, w["name"])
                        self.assertEqual(g.ownership_percentage,
                                         w["ownership_percentage"])
                        self.assertEqual(
                            irs_round(g.box_1_ordinary_business_income),
                            irs_round(w["ordinary_business_income"]))
                        sec = w["section_199a"]
                        if sec is None:
                            continue  # see test_no_statement_a_*
                        else:
                            self.assertEqual(g.box_17v_qbi,
                                             irs_round(sec["qbi"]))
                            self.assertEqual(g.box_17v_w2_wages,
                                             irs_round(sec["w2_wages"]))
                            self.assertEqual(g.box_17v_ubia,
                                             irs_round(sec["ubia"]))

    @unittest.expectedFailure
    def test_no_statement_a_when_section_199a_is_none(self):
        """DIVERGENCE (oracle FLAG-6): with section_199a None the oracle
        reports NO Statement A (``section_199a: None``); production emits
        box 17V QBI = the holder's share of Sch K line 1 (default-QBI
        statement, zero wages/UBIA). Recorded, not reshaped; awaiting
        team-lead adjudication."""
        for year in YEARS:
            for name, spec in SCENARIOS.items():
                if "s199a" in spec:
                    continue
                s = build(year, spec)
                got = f1120s.compute(s, upstream={})["f1120s_sch_k1_allocations"]
                for g in got:
                    with self.subTest(year=year, scenario=name):
                        self.assertEqual(
                            (g.box_17v_qbi, g.box_17v_w2_wages,
                             g.box_17v_ubia), (0, 0, 0))

    def _strict_scalar(self, key, scenarios):
        for year in YEARS:
            for name in scenarios:
                s = build(year, SCENARIOS[name])
                got = f1120s.compute(s, upstream={})[key]
                want = irs_round(oracle.reference_f1120s(
                    year, s.s_corp_return)[key])
                with self.subTest(year=year, scenario=name, key=key):
                    self.assertEqual(got, want)

    @unittest.expectedFailure
    def test_d1_line_18_reconciliation_matches_oracle(self):
        """DIVERGENCE D1: production emits 0 for Sch K line 18; oracle (no
        separately stated items) reports line 18 == line 1."""
        self._strict_scalar(D1_KEY, SCENARIOS)

    @unittest.expectedFailure
    def test_d2_line_21_from_rounded_line_6_matches_oracle(self):
        """DIVERGENCE D2: cents_loss -- production line 21 = -2501
        (round(1000.40) - round(3500.80)); oracle round(-2500.40) = -2500."""
        for key in sorted(D2_KEYS):
            self._strict_scalar(key, [D2_SCENARIO])

    @unittest.expectedFailure
    def test_d3_line_26_overpayment_matches_oracle(self):
        """DIVERGENCE D3: cents_overpayment -- production 601
        (701 - 100 from rounded lines); oracle round(700.50 - 100.40) = 600."""
        self._strict_scalar(D3_KEY, [D3_SCENARIO])

    def test_line_18_equals_line_1_at_top_level(self):
        for year in YEARS:
            for name, spec in SCENARIOS.items():
                with self.subTest(year=year, scenario=name):
                    out = oracle.reference_f1120s(
                        year, build(year, spec).s_corp_return)
                    self.assertEqual(
                        out["f1120s_sch_k_income_loss_reconciliation"],
                        out["f1120s_sch_k_ordinary_business_income"])

    def test_every_deduction_category_nonzero_somewhere(self):
        fields = set(_ZERO_DED)
        covered = {k for spec in SCENARIOS.values()
                   for k, v in spec.get("deductions", {}).items() if v}
        self.assertEqual(fields - covered, set())

    def test_oracle_rejects_refundable_credits_before_2023(self):
        s = build(2023, SCENARIOS["overpayment_all_payment_lines"])
        for year in (2021, 2022):
            with self.subTest(year=year):
                with self.assertRaises(NotImplementedError):
                    oracle.reference_f1120s(year, s.s_corp_return)


if __name__ == "__main__":
    unittest.main()
