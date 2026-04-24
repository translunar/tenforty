import unittest

from tenforty.oracle.flattener import flatten_scenario
from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    RentalProperty,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tests.helpers import plan_d_attestation_defaults


def _simple_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        ),
        w2s=[
            W2(
                employer="Acme",
                wages=100000,
                federal_tax_withheld=15000,
                ss_wages=100000,
                ss_tax_withheld=6200,
                medicare_wages=100000,
                medicare_tax_withheld=1450,
                state_wages=100000,
                state_tax_withheld=5000,
            ),
        ],
        form1099_int=[Form1099INT(payer="Bank", interest=250)],
        form1098s=[Form1098(lender="Mortgage Co", mortgage_interest=8400)],
    )


class TestFlattenScenario(unittest.TestCase):
    def test_filing_status_single(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["filing_status_single"], "X")
        self.assertNotIn("filing_status_married_jointly", flat)

    def test_birthdate_split(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["birthdate_month"], 6)
        self.assertEqual(flat["birthdate_day"], 15)
        self.assertEqual(flat["birthdate_year"], 1990)

    def test_w2_fields(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["w2_wages_1"], 100000)
        self.assertEqual(flat["w2_fed_withheld_1"], 15000)
        self.assertEqual(flat["w2_ss_wages_1"], 100000)
        self.assertEqual(flat["w2_state_wages_1"], 100000)
        self.assertEqual(flat["w2_state_withheld_1"], 5000)

    def test_1099_int_fields(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["interest_1"], 250)

    def test_1098_mortgage(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertEqual(flat["mortgage_interest"], 8400)

    def test_1099_div_capital_gain_distributions(self):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            form1099_div=[Form1099DIV(
                payer="Brokerage Inc",
                ordinary_dividends=500,
                qualified_dividends=500,
                capital_gain_distributions=5000,
            )],
        )
        flat = flatten_scenario(scenario)
        self.assertEqual(flat["capital_gain_distributions_1"], 5000)

    def test_multiple_1098s_summed(self):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            form1098s=[
                Form1098(lender="Mortgage Co", mortgage_interest=8000, property_tax=3000),
                Form1098(lender="Home Mortgage Co", mortgage_interest=4000, property_tax=1500),
            ],
        )
        flat = flatten_scenario(scenario)
        self.assertEqual(flat["mortgage_interest"], 12000)
        self.assertEqual(flat["property_tax"], 4500)

    def test_empty_forms_produce_no_keys(self):
        flat = flatten_scenario(_simple_scenario())
        self.assertNotIn("ordinary_dividends_1", flat)
        self.assertNotIn("sche_rents_a", flat)


class TestFlattenRentalProperty(unittest.TestCase):
    def _make_rental_scenario(self) -> Scenario:
        return Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1990-06-15", state="CA",
            ),
            rental_properties=[RentalProperty(
                address="42 Test Blvd, Faketown TX 99999",
                property_type=2,
                fair_rental_days=350,
                personal_use_days=15,
                rents_received=24000,
                auto_and_travel=800,
                cleaning_and_maintenance=550,
                insurance=1600,
                legal_and_professional_fees=300,
                mortgage_interest=7500,
                repairs=950,
                supplies=350,
                taxes=8500,
                depreciation=5500,
            )],
        )

    def test_rental_rents_received(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_rents_a"], 24000)

    def test_rental_metadata(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_property_type_a"], 2)
        self.assertEqual(flat["sche_fair_rental_days_a"], 350)
        self.assertEqual(flat["sche_personal_use_days_a"], 15)

    def test_rental_all_expenses(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertEqual(flat["sche_insurance_a"], 1600)
        self.assertEqual(flat["sche_mortgage_interest_a"], 7500)
        self.assertEqual(flat["sche_repairs_a"], 950)
        self.assertEqual(flat["sche_taxes_a"], 8500)
        self.assertEqual(flat["sche_depreciation_a"], 5500)
        self.assertEqual(flat["sche_auto_and_travel_a"], 800)
        self.assertEqual(flat["sche_cleaning_and_maintenance_a"], 550)
        self.assertEqual(flat["sche_legal_and_professional_fees_a"], 300)
        self.assertEqual(flat["sche_supplies_a"], 350)

    def test_rental_zero_expenses_not_included(self):
        flat = flatten_scenario(self._make_rental_scenario())
        self.assertNotIn("sche_advertising_a", flat)
        self.assertNotIn("sche_commissions_a", flat)
        self.assertNotIn("sche_management_fees_a", flat)
        self.assertNotIn("sche_other_interest_a", flat)
        self.assertNotIn("sche_utilities_a", flat)
        self.assertNotIn("sche_other_expenses_a", flat)


class TestFlatten1099B(unittest.TestCase):
    """Flattener emits per-lot 8949 row keys per box/subsection."""

    def _scenario_with_lots(self, lots):
        return self._scenario_with_lots_ack(lots)

    def _scenario_with_lots_ack(self, lots, **ack_overrides):
        """Build a Scenario with attestation overrides passed directly into
        TaxReturnConfig (no post-construction mutation)."""
        kw = plan_d_attestation_defaults()
        kw.update(ack_overrides)
        return Scenario(
            config=TaxReturnConfig(
                year=2025, filing_status="single",
                birthdate="1985-04-20", state="CA",
                **kw,
            ),
            form1099_b=list(lots),
        )

    def test_short_term_box_a_lot(self) -> None:
        """Box A: short_term + basis_reported + no adjustments."""
        s = self._scenario_with_lots([
            Form1099B(
                broker="Brokerage Inc", description="10 sh X",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0, short_term=True,
                basis_reported_to_irs=True,
            ),
        ])
        flat = flatten_scenario(s)
        self.assertEqual(flat.get("f8949_box_a_lot_1_proceeds"), 1000.0)
        self.assertEqual(flat.get("f8949_box_a_lot_1_basis"), 800.0)
        self.assertEqual(flat.get("f8949_box_a_lot_1_description"), "10 sh X")

    def test_long_term_box_d_lot(self) -> None:
        """Box D: long_term + basis_reported + no adjustments."""
        s = self._scenario_with_lots([
            Form1099B(
                broker="Brokerage Inc", description="100 sh Y",
                date_acquired="2022-01-15", date_sold="2025-06-20",
                proceeds=15000.0, cost_basis=10000.0, short_term=False,
                basis_reported_to_irs=True,
            ),
        ])
        flat = flatten_scenario(s)
        self.assertEqual(flat.get("f8949_box_d_lot_1_proceeds"), 15000.0)
        self.assertEqual(flat.get("f8949_box_d_lot_1_basis"), 10000.0)

    def test_short_term_box_b_when_basis_not_reported(self) -> None:
        s = self._scenario_with_lots([
            Form1099B(
                broker="Brokerage Inc", description="50 sh Z",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=500.0, cost_basis=700.0, short_term=True,
                basis_reported_to_irs=False,
            ),
        ])
        flat = flatten_scenario(s)
        self.assertIn("f8949_box_b_lot_1_proceeds", flat)
        self.assertNotIn("f8949_box_a_lot_1_proceeds", flat)

    def test_wash_sale_lot_carries_adjustment(self) -> None:
        """Lot with wash_sale_loss_disallowed is routed to adjusted-basis
        box (A if basis reported, B if not) and its column-(g) adjustment
        amount is keyed for the engine."""
        s = self._scenario_with_lots_ack(
            lots=[
                Form1099B(
                    broker="Brokerage Inc", description="W sh",
                    date_acquired="2025-01-15", date_sold="2025-06-20",
                    proceeds=500.0, cost_basis=700.0, short_term=True,
                    basis_reported_to_irs=True,
                    wash_sale_loss_disallowed=100.0,
                ),
            ],
            acknowledges_no_wash_sale_adjustments=True,
        )
        flat = flatten_scenario(s)
        self.assertEqual(flat.get("f8949_box_a_lot_1_adjustment_amount"), 100.0)
        self.assertEqual(flat.get("f8949_box_a_lot_1_adjustment_code"), "W")

    def test_multiple_lots_enumerate(self) -> None:
        s = self._scenario_with_lots([
            Form1099B(
                broker="Brokerage Inc", description="L1",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=1000.0, cost_basis=800.0,
                short_term=True, basis_reported_to_irs=True,
            ),
            Form1099B(
                broker="Brokerage Inc", description="L2",
                date_acquired="2025-02-15", date_sold="2025-07-20",
                proceeds=1500.0, cost_basis=1200.0,
                short_term=True, basis_reported_to_irs=True,
            ),
        ])
        flat = flatten_scenario(s)
        self.assertEqual(flat["f8949_box_a_lot_1_description"], "L1")
        self.assertEqual(flat["f8949_box_a_lot_2_description"], "L2")

    def test_reject_unhandled_no_longer_blocks_1099_b(self) -> None:
        """The pre-existing _reject_unhandled gate for form1099_b is gone."""
        s = self._scenario_with_lots([
            Form1099B(
                broker="Brokerage Inc", description="X",
                date_acquired="2025-01-15", date_sold="2025-06-20",
                proceeds=100.0, cost_basis=80.0,
            ),
        ])
        flatten_scenario(s)  # must not raise NotImplementedError
