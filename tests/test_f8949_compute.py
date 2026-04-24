"""Unit tests for tenforty.forms.f8949.compute."""

import unittest

from tenforty.forms import f8949
from tenforty.forms.f8949 import Form8949Lot
from tenforty.models import Form1099B, Scenario, TaxReturnConfig
from tests.helpers import plan_d_attestation_defaults

# Per-row PDF-mapping shape contract lives with pdf_f8949 (separate task).


def _make_scenario(lots: list[Form1099B], **config_overrides) -> Scenario:
    kw = plan_d_attestation_defaults()
    kw.update(config_overrides)
    # has_foreign_accounts and prior_year_itemized are already included in
    # plan_d_attestation_defaults(); pass them via **kw only to avoid duplicates.
    cfg = TaxReturnConfig(
        year=2025, filing_status="single",
        birthdate="1985-04-20", state="CA",
        first_name="Taxpayer", last_name="A",
        **kw,
    )
    return Scenario(config=cfg, form1099_b=list(lots))


class TestF8949Compute(unittest.TestCase):
    def test_box_a_clean_lot_flows_to_aggregate_path_only(self) -> None:
        """A single short-term covered no-adjustment lot flows ONLY through
        the aggregate-path totals (sch_d 1a feed) and produces NO Form 8949
        row or box-A subsection total."""
        scenario = _make_scenario([
            Form1099B(
                broker="Brokerage Inc", description="L1",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
        ])
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out["f8949_box_a_total_proceeds"], 0)
        self.assertEqual(out["f8949_box_a_total_basis"], 0)
        self.assertEqual(out["f8949_box_a_total_gain"], 0)
        self.assertEqual(out["f8949_box_a_total_adjustment"], 0)
        self.assertEqual(out["f8949_agg_short_proceeds"], 1000)
        self.assertEqual(out["f8949_agg_short_basis"], 800)
        self.assertEqual(out["f8949_agg_short_gain"], 200)
        self.assertEqual(out["f8949_agg_long_proceeds"], 0)
        self.assertNotIn("f8949_box_a_row_1_description", out)

    def test_wash_sale_adjustment_applied_with_ack(self) -> None:
        """Adjusted Box A lot is 8949-path; wash-sale disallowed loss is
        positive in col (g); col (h) gain = proceeds - basis + adjustment.
        ack=True proceeds (no silent skip)."""
        scenario = _make_scenario(
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
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out["f8949_box_a_total_gain"], 0)
        self.assertEqual(out["f8949_box_a_total_adjustment"], 200)
        self.assertEqual(out["f8949_agg_short_proceeds"], 0)
        self.assertEqual(out["f8949_box_a_row_1_description"], "WS")
        self.assertEqual(out["f8949_box_a_row_1_adjustment_code"], "W")

    def test_wash_sale_without_ack_raises(self) -> None:
        """The attestation's compute-time gate is enforced before compute."""
        scenario = _make_scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="WS",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=1000.0, cost_basis=1200.0,
                    short_term=True, basis_reported_to_irs=True,
                    wash_sale_loss_disallowed=200.0,
                ),
            ],
            acknowledges_no_wash_sale_adjustments=False,
        )
        with self.assertRaises(NotImplementedError):
            f8949.compute(scenario, upstream={})

    def test_combined_wash_sale_and_other_basis_raises(self) -> None:
        """A single lot carrying BOTH wash_sale_loss_disallowed AND
        other_basis_adjustment cannot cleanly emit a single-letter
        adjustment code. Raise at compute time with instructions to split
        into two lots."""
        scenario = _make_scenario(
            [
                Form1099B(
                    broker="Brokerage Inc", description="Combined",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=1000.0, cost_basis=900.0,
                    short_term=True, basis_reported_to_irs=True,
                    wash_sale_loss_disallowed=50.0,
                    other_basis_adjustment=25.0,
                ),
            ],
            acknowledges_no_wash_sale_adjustments=True,
            acknowledges_no_other_basis_adjustments=True,
        )
        with self.assertRaises(NotImplementedError) as ctx:
            f8949.compute(scenario, upstream={})
        self.assertIn("split into two lots", str(ctx.exception))

    def test_28_rate_tag_aggregated(self) -> None:
        """is_28_rate_collectible is an adjustment trigger → 8949-path;
        the gain contributes to the separate 28%-rate aggregate tag
        alongside its normal long-term Box D total."""
        scenario = _make_scenario(
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
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out["f8949_total_28_rate_gain"], 4000)
        self.assertEqual(out["f8949_box_d_total_gain"], 4000)
        self.assertEqual(out["f8949_agg_long_proceeds"], 0)

    def test_section_1250_tag_aggregated(self) -> None:
        scenario = _make_scenario(
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
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out["f8949_total_unrecap_1250"], 3000)
        self.assertEqual(out["f8949_box_d_total_gain"], 3000)
        self.assertEqual(out["f8949_agg_long_proceeds"], 0)

    def test_per_lot_row_fields_emitted_for_8949_path_only(self) -> None:
        """The compute emits per-lot row fields ONLY for 8949-path lots —
        not for aggregate-path lots. All 8 per-row keys must be present and
        match the shape expected by pdf_f8949._row_mapping."""
        scenario = _make_scenario([
            Form1099B(
                broker="Brokerage Inc", description="Clean",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
            Form1099B(
                broker="Brokerage Inc", description="NonCov",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=500.0, cost_basis=300.0,
                short_term=True, basis_reported_to_irs=False,
            ),
        ])
        out = f8949.compute(scenario, upstream={})
        for suffix in (
            "description", "date_acquired", "date_sold",
            "proceeds", "cost_basis",
            "adjustment_code", "adjustment_amount", "gain_loss",
        ):
            self.assertNotIn(f"f8949_box_a_row_1_{suffix}", out)
        self.assertEqual(out["f8949_box_b_row_1_description"], "NonCov")
        self.assertEqual(out["f8949_box_b_row_1_date_acquired"], "2025-01-15")
        self.assertEqual(out["f8949_box_b_row_1_date_sold"], "2025-06-20")
        self.assertEqual(out["f8949_box_b_row_1_proceeds"], 500)
        self.assertEqual(out["f8949_box_b_row_1_cost_basis"], 300)
        self.assertEqual(out["f8949_box_b_row_1_adjustment_code"], "")
        self.assertEqual(out["f8949_box_b_row_1_adjustment_amount"], 0)
        self.assertEqual(out["f8949_box_b_row_1_gain_loss"], 200)

    def test_short_and_long_subtotals_cover_8949_path_only(self) -> None:
        """net_short_term = sum of 8949-path box-a/b/c gains;
        net_long_term = sum of 8949-path box-d/e/f gains."""
        scenario = _make_scenario([
            Form1099B(
                broker="Brokerage Inc", description="CleanST",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1500.0, cost_basis=1000.0,
                short_term=True, basis_reported_to_irs=True,
            ),
            Form1099B(
                broker="Brokerage Inc", description="NonCovST",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=500.0, cost_basis=300.0,
                short_term=True, basis_reported_to_irs=False,
            ),
            Form1099B(
                broker="Brokerage Inc", description="CleanLT",
                date_acquired="2022-01-15", date_sold="2025-06-20",
                proceeds=10000.0, cost_basis=7000.0,
                short_term=False, basis_reported_to_irs=True,
            ),
        ])
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out["f8949_net_short_term"], 200)
        self.assertEqual(out["f8949_net_long_term"], 0)
        self.assertEqual(out["f8949_agg_short_gain"], 500)
        self.assertEqual(out["f8949_agg_long_gain"], 3000)


class TestF8949CheckboxEmission(unittest.TestCase):
    def test_box_a_checkbox_emitted_when_box_a_has_8949_path_lot(self) -> None:
        """A lot routed to Box A (ST, covered, with wash-sale adjustment) must
        cause f8949.compute to emit f8949_box_a_checkbox == 'X'."""
        scenario = _make_scenario(
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
        out = f8949.compute(scenario, upstream={})
        self.assertEqual(out.get("f8949_box_a_checkbox"), "X")
        # Other boxes have no lots → their checkboxes must be absent (key not emitted)
        for letter in ("b", "d", "e"):
            self.assertIsNone(
                out.get(f"f8949_box_{letter}_checkbox"),
                f"Expected f8949_box_{letter}_checkbox to be absent (None), "
                f"got {out.get(f'f8949_box_{letter}_checkbox')!r}",
            )


class TestForm8949Lot(unittest.TestCase):
    """Dataclass sanity — Iron Law 8 (no positional 6-tuples for lot data)."""

    def test_dataclass_is_frozen(self) -> None:
        lot = Form8949Lot(
            box="a", description="X",
            date_acquired="2025-01-15", date_sold="2025-06-20",
            proceeds=1000, basis=800, adjustment_code="",
            adjustment_amount=0, gain=200,
            is_28_rate=False, is_section_1250=False,
        )
        with self.assertRaises(Exception):
            lot.gain = 0  # type: ignore[misc]
