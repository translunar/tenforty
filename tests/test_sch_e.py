"""Tests for forms.sch_e helpers."""

import unittest

from tenforty.forms import sch_e as form_sch_e
from tenforty.models import RentalProperty
from tests.helpers import make_simple_scenario


class TestHasAnyNetLossUsesExpenseFields(unittest.TestCase):
    def test_breakeven_is_not_a_loss(self) -> None:
        scenario = make_simple_scenario()
        scenario.rental_properties = [RentalProperty(
            address="123 Example St",
            property_type=1, fair_rental_days=365, personal_use_days=0,
            rents_received=12000.0, mortgage_interest=6000.0, taxes=6000.0,
        )]
        self.assertFalse(form_sch_e.has_any_net_loss(scenario))

    def test_net_loss_returns_true(self) -> None:
        scenario = make_simple_scenario()
        scenario.rental_properties = [RentalProperty(
            address="123 Example St",
            property_type=1, fair_rental_days=365, personal_use_days=0,
            rents_received=6000.0, mortgage_interest=9000.0,
        )]
        self.assertTrue(form_sch_e.has_any_net_loss(scenario))

    def test_body_does_not_hand_enumerate(self) -> None:
        """The implementation must iterate _EXPENSE_FIELDS, not maintain a
        parallel list of attribute names (SP1-M5)."""
        import inspect
        src = inspect.getsource(form_sch_e.has_any_net_loss)
        self.assertNotIn("p.advertising", src)
        self.assertNotIn("p.cleaning_and_maintenance", src)
        self.assertNotIn("p.mortgage_interest", src)
        self.assertIn("_EXPENSE_FIELDS", src)
