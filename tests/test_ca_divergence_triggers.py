"""Per-predicate unit tests for the closed trigger-predicate registry.

Part TRIGGERS step A (spec §2.4): the code-side ``TRIGGER_PREDICATES`` registry
is the CLOSED vocabulary of named, pure ``Scenario -> bool`` predicates. Each
predicate gets a FIRES case and a DOES-NOT-FIRE case; the registry gets a
shape test (exactly the five keys, every value callable). These tests assert
NOTHING about catalog rows (trigger assignment to catalog YAML is a later step).
"""

import unittest

from tenforty.ca_divergences import TRIGGER_PREDICATES
from tenforty.models import (
    EntityType,
    FilingStatus,
    Form1099DIV,
    Form1099G,
    Form1099INT,
    RentalProperty,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
)

EXPECTED_KEYS = frozenset(
    {
        "has_tax_exempt_interest",
        "has_k1",
        "has_rental_depreciation",
        "has_capital_gain_distributions",
        "has_state_tax_refund",
    }
)


def _config() -> TaxReturnConfig:
    """Smallest valid TaxReturnConfig. The predicates are pure and inspect only
    Scenario list fields, so no scope-out attestations or compute are needed."""
    return TaxReturnConfig(
        year=2021,
        filing_status=FilingStatus.SINGLE,
        birthdate="1985-04-20",
        state="CA",
    )


def _k1(**overrides) -> ScheduleK1:
    kwargs = dict(
        entity_name="Acme LLC",
        entity_ein="00-0000000",
        entity_type=EntityType.S_CORP,
        material_participation=True,
    )
    kwargs.update(overrides)
    return ScheduleK1(**kwargs)


def _rental(**overrides) -> RentalProperty:
    kwargs = dict(
        address="1 Main St",
        property_type=1,
        fair_rental_days=365,
        personal_use_days=0,
        rents_received=12000.0,
    )
    kwargs.update(overrides)
    return RentalProperty(**kwargs)


class TriggerRegistryShapeTest(unittest.TestCase):
    def test_registry_has_exactly_the_five_keys(self):
        self.assertEqual(frozenset(TRIGGER_PREDICATES), EXPECTED_KEYS)

    def test_every_value_is_callable(self):
        for name, predicate in TRIGGER_PREDICATES.items():
            with self.subTest(predicate=name):
                self.assertTrue(callable(predicate))


class HasTaxExemptInterestTest(unittest.TestCase):
    predicate = staticmethod
    name = "has_tax_exempt_interest"

    def test_fires_when_any_1099int_has_tax_exempt_interest(self):
        scenario = Scenario(
            config=_config(),
            form1099_int=[
                Form1099INT(payer="Bank", interest=0.0),
                Form1099INT(payer="Muni", interest=0.0, tax_exempt_interest=500.0),
            ],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_does_not_fire_when_absent_or_zero(self):
        scenario = Scenario(
            config=_config(),
            form1099_int=[Form1099INT(payer="Bank", interest=100.0)],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


class HasK1Test(unittest.TestCase):
    name = "has_k1"

    def test_fires_when_schedule_k1s_non_empty(self):
        scenario = Scenario(config=_config(), schedule_k1s=[_k1()])
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_does_not_fire_when_no_k1s(self):
        scenario = Scenario(config=_config())
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


class HasRentalDepreciationTest(unittest.TestCase):
    name = "has_rental_depreciation"

    def test_fires_when_any_rental_has_depreciation(self):
        scenario = Scenario(
            config=_config(),
            rental_properties=[
                _rental(),
                _rental(address="2 Oak Ave", depreciation=3200.0),
            ],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_does_not_fire_when_absent_or_zero(self):
        scenario = Scenario(
            config=_config(),
            rental_properties=[_rental()],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


class HasCapitalGainDistributionsTest(unittest.TestCase):
    name = "has_capital_gain_distributions"

    def test_fires_when_any_1099div_has_capital_gain_distributions(self):
        scenario = Scenario(
            config=_config(),
            form1099_div=[
                Form1099DIV(payer="Fund A", ordinary_dividends=100.0),
                Form1099DIV(
                    payer="Fund B",
                    ordinary_dividends=200.0,
                    capital_gain_distributions=750.0,
                ),
            ],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_does_not_fire_when_absent_or_zero(self):
        scenario = Scenario(
            config=_config(),
            form1099_div=[Form1099DIV(payer="Fund A", ordinary_dividends=100.0)],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


class HasStateTaxRefundTest(unittest.TestCase):
    name = "has_state_tax_refund"

    def test_fires_when_any_1099g_has_state_tax_refund(self):
        scenario = Scenario(
            config=_config(),
            form1099_g=[
                Form1099G(payer="EDD", unemployment_compensation=1000.0),
                Form1099G(payer="FTB", state_tax_refund=420.0),
            ],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertTrue(result)

    def test_does_not_fire_when_absent_or_zero(self):
        scenario = Scenario(
            config=_config(),
            form1099_g=[Form1099G(payer="EDD", unemployment_compensation=1000.0)],
        )
        result = TRIGGER_PREDICATES[self.name](scenario)
        self.assertIsInstance(result, bool)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
