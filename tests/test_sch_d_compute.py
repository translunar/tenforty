"""Schedule D compute — consumes f8949 totals; preserves 1a/8a aggregate path."""

import unittest

from tenforty.forms import f8949, sch_d
from tenforty.models import (
    Form1099B, K1FanoutData, Scenario, TaxReturnConfig,
)
from tests.helpers import plan_d_attestation_defaults


def _scenario(lots: list[Form1099B], **overrides) -> Scenario:
    kw = plan_d_attestation_defaults()
    kw.update(overrides)
    cfg = TaxReturnConfig(
        year=2025, filing_status="single",
        birthdate="1985-04-20", state="CA",
        first_name="Taxpayer", last_name="A", ssn="000-00-0000",
        **kw,
    )
    return Scenario(config=cfg, form1099_b=list(lots))


class TestSchDAggregateVsForm8949Split(unittest.TestCase):
    def test_no_adjustment_box_a_flows_to_1a_not_1b(self) -> None:
        scen = _scenario([
            Form1099B(
                broker="Brokerage Inc", description="Clean",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
        ])
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        self.assertEqual(out["sch_d_line_1a_proceeds"], 1000)
        self.assertEqual(out["sch_d_line_1a_gain"], 200)
        self.assertEqual(out["sch_d_line_1b_gain"], 0)
        self.assertEqual(out["sch_d_line_1b_proceeds"], 0)

    def test_wash_sale_box_a_flows_to_1b_not_1a(self) -> None:
        scen = _scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="WS",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=1000.0, cost_basis=1200.0,
                    short_term=True, basis_reported_to_irs=True,
                    wash_sale_loss_disallowed=200.0,
                ),
            ],
            acknowledges_no_wash_sale_adjustments=True,
        )
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        self.assertEqual(out["sch_d_line_1a_proceeds"], 0)
        self.assertEqual(out["sch_d_line_1a_gain"], 0)
        self.assertEqual(out["sch_d_line_1b_proceeds"], 1000)
        self.assertEqual(out["sch_d_line_1b_basis"], 1200)
        self.assertEqual(out["sch_d_line_1b_gain"], 0)

    def test_no_double_count_mixed_scenario(self) -> None:
        scen = _scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="Clean",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=1000.0, cost_basis=800.0,
                    short_term=True, basis_reported_to_irs=True,
                ),
                Form1099B(
                    broker="Brokerage Inc", description="WS",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=2000.0, cost_basis=2500.0,
                    short_term=True, basis_reported_to_irs=True,
                    wash_sale_loss_disallowed=500.0,
                ),
                Form1099B(
                    broker="Brokerage Inc", description="NonCov",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=500.0, cost_basis=300.0,
                    short_term=True, basis_reported_to_irs=False,
                ),
            ],
            acknowledges_no_wash_sale_adjustments=True,
        )
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        total_proceeds_across_lines = (
            out["sch_d_line_1a_proceeds"]
            + out["sch_d_line_1b_proceeds"]
            + out["sch_d_line_2_proceeds"]
        )
        self.assertEqual(total_proceeds_across_lines, 1000 + 2000 + 500)

    def test_line_16_combines_short_and_long(self) -> None:
        scen = _scenario([
            Form1099B(
                broker="Brokerage Inc", description="ST",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
            Form1099B(
                broker="Brokerage Inc", description="LT",
                date_acquired="2022-01-15", date_sold="2025-06-20",
                proceeds=5000.0, cost_basis=3000.0,
                short_term=False, basis_reported_to_irs=True,
            ),
        ])
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        self.assertEqual(out["sch_d_line_7_net_short"], 200)
        self.assertEqual(out["sch_d_line_15_net_long"], 2000)
        self.assertEqual(out["sch_d_line_16_total"], 2200)

    def test_28_rate_feeds_line_19(self) -> None:
        scen = _scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="Coin",
                    date_acquired="2020-01-15", date_sold="2025-06-20",
                    proceeds=5000.0, cost_basis=1000.0,
                    short_term=False, basis_reported_to_irs=True,
                    is_28_rate_collectible=True,
                ),
            ],
            acknowledges_no_28_rate_gain=True,
        )
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        self.assertEqual(out["sch_d_line_19_28_rate_gain"], 4000)

    def test_section_1250_feeds_line_18(self) -> None:
        scen = _scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="REIT",
                    date_acquired="2020-01-15", date_sold="2025-06-20",
                    proceeds=10000.0, cost_basis=7000.0,
                    short_term=False, basis_reported_to_irs=True,
                    is_section_1250=True,
                ),
            ],
            acknowledges_no_unrecaptured_section_1250=True,
        )
        f8949_result = f8949.compute(scen, upstream={})
        out = sch_d.compute(scen, upstream={"f8949": f8949_result})
        self.assertEqual(out["sch_d_line_18_unrecap_1250"], 3000)

    def test_k1_cap_gain_adds_to_sch_d(self) -> None:
        scen = _scenario([])
        f8949_result = f8949.compute(scen, upstream={})
        fanout = K1FanoutData(
            sch_b_interest_additions=(),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(150.0,),
            sch_d_long_term_additions=(400.0,),
            qbi_aggregate=0.0,
            qualified_dividends_aggregate=0.0,
            passive_activities=(),
        )
        out = sch_d.compute(
            scen, upstream={"f8949": f8949_result, "k1_fanout": fanout},
        )
        self.assertEqual(out["sch_d_line_5_net_short_k1"], 150)
        self.assertEqual(out["sch_d_line_12_net_long_k1"], 400)
        self.assertEqual(out["sch_d_line_7_net_short"], 150)
        self.assertEqual(out["sch_d_line_15_net_long"], 400)
        self.assertEqual(out["sch_d_line_16_total"], 550)
