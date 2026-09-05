"""Task 1 — ScheduleCBusiness input channel: model, Scenario field, load registry,
and load-time negative-amount refusal.

Scope is the INPUT channel only: the dataclass, its attachment to Scenario, its
registration for YAML load, and the load-time validation that refuses a negative
amount. Net-profit / SE-tax COMPUTE and the compute-time refusals of unmodeled
features (COGS, depreciation, home office, ...) belong to later tasks.

All synthetic values.
"""
import unittest

from tenforty.models import ScheduleCBusiness, Scenario, TaxReturnConfig
from tenforty.scenario import (
    _FORM_REGISTRY,
    _KNOWN_TOP_LEVEL_KEYS,
    _validate_schedule_c_businesses,
)
from tests.helpers import make_simple_scenario


class ScheduleCLoadTests(unittest.TestCase):
    def test_default_empty(self):
        sc = make_simple_scenario()
        self.assertEqual(sc.schedule_c_businesses, [])

    def test_business_attaches(self):
        sc = make_simple_scenario()
        biz = ScheduleCBusiness(
            description="consulting", gross_receipts=50_000.0, supplies=1_200.0)
        sc2 = Scenario(config=sc.config, schedule_c_businesses=[biz])
        self.assertEqual(len(sc2.schedule_c_businesses), 1)
        self.assertEqual(sc2.schedule_c_businesses[0].gross_receipts, 50_000.0)
        self.assertEqual(sc2.schedule_c_businesses[0].supplies, 1_200.0)
        self.assertEqual(sc2.schedule_c_businesses[0].description, "consulting")

    def test_registered_for_yaml_load(self):
        # The top-level YAML key must be recognized by the fail-closed loader,
        # and it must route to the ScheduleCBusiness model on the Scenario field.
        self.assertIn("schedule_c_businesses", _FORM_REGISTRY)
        model_cls, field_name = _FORM_REGISTRY["schedule_c_businesses"]
        self.assertIs(model_cls, ScheduleCBusiness)
        self.assertEqual(field_name, "schedule_c_businesses")
        # _KNOWN_TOP_LEVEL_KEYS is derived from _FORM_REGISTRY; confirm the key
        # actually flows through (a YAML file using it must not be rejected as
        # an unknown key).
        self.assertIn("schedule_c_businesses", _KNOWN_TOP_LEVEL_KEYS)


class ScheduleCValidationTests(unittest.TestCase):
    def _scenario_with(self, biz):
        base = make_simple_scenario()
        return Scenario(config=base.config, schedule_c_businesses=[biz])

    def test_valid_business_does_not_raise(self):
        # A well-formed business (all amounts >= 0) must pass validation, so the
        # refusal below is proven to fire on the NEGATIVE amount specifically,
        # not on any business at all.
        biz = ScheduleCBusiness(
            description="ok", gross_receipts=50_000.0, supplies=1_000.0)
        _validate_schedule_c_businesses(self._scenario_with(biz))  # no raise

    def test_negative_gross_receipts_refused(self):
        # A negative synthetic figure must be refused, never clamped.
        biz = ScheduleCBusiness(description="x", gross_receipts=-1.0)
        with self.assertRaises(ValueError) as ctx:
            _validate_schedule_c_businesses(self._scenario_with(biz))
        self.assertIn("gross_receipts", str(ctx.exception))

    def test_negative_expense_refused(self):
        # An expense field is also an amount field; negative is refused.
        biz = ScheduleCBusiness(
            description="y", gross_receipts=10_000.0, supplies=-500.0)
        with self.assertRaises(ValueError) as ctx:
            _validate_schedule_c_businesses(self._scenario_with(biz))
        self.assertIn("supplies", str(ctx.exception))

    def test_refusal_message_names_business_index(self):
        # Two businesses; the negative amount is on index 1. The message must
        # name the offending business index so the filer can find it.
        good = ScheduleCBusiness(description="good", gross_receipts=10_000.0)
        bad = ScheduleCBusiness(description="bad", gross_receipts=20_000.0,
                                travel=-5.0)
        base = make_simple_scenario()
        sc = Scenario(config=base.config, schedule_c_businesses=[good, bad])
        with self.assertRaises(ValueError) as ctx:
            _validate_schedule_c_businesses(sc)
        msg = str(ctx.exception)
        self.assertIn("travel", msg)
        self.assertIn("1", msg)


if __name__ == "__main__":
    unittest.main()
