"""Schedule E native-Python compute tests (scenario-sourced property A)."""

import logging
import unittest

from tenforty.forms.sch_e import compute
from tenforty.models import RentalProperty

from tests.helpers import make_simple_scenario


def _rental(**overrides) -> RentalProperty:
    defaults = dict(
        address="123 Main St",
        property_type=1,
        fair_rental_days=365,
        personal_use_days=0,
        rents_received=24000.0,
    )
    defaults.update(overrides)
    return RentalProperty(**defaults)


class SchEHeaderTests(unittest.TestCase):
    def test_taxpayer_header_from_config(self):
        scenario = make_simple_scenario()
        scenario.config.first_name = "Alex"
        scenario.config.last_name = "Rivera"
        scenario.config.ssn = "000-12-3456"
        scenario.rental_properties = [_rental()]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["taxpayer_name"], "Alex Rivera")
        self.assertEqual(result["taxpayer_ssn"], "000-12-3456")


class SchEPropertyAFieldsTests(unittest.TestCase):
    def test_property_a_scenario_fields(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            address="123 Main St",
            property_type=1,
            fair_rental_days=365,
            personal_use_days=0,
        )]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["sch_e_property_a_address"], "123 Main St")
        self.assertEqual(result["sch_e_property_a_type_code"], "1")
        self.assertEqual(result["sch_e_property_a_fair_rental_days"], 365)
        self.assertEqual(result["sch_e_property_a_personal_use_days"], 0)

    def test_expenses_passed_through_only_when_nonzero(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0,
            mortgage_interest=8000.0,
            taxes=3000.0,
            depreciation=5000.0,
        )]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["sch_e_property_a_rents"], 24000)
        self.assertEqual(result["sch_e_property_a_mortgage_interest"], 8000)
        self.assertEqual(result["sch_e_property_a_taxes"], 3000)
        self.assertEqual(result["sch_e_property_a_depreciation"], 5000)
        # Zero-valued expenses stay out of the result dict entirely so the
        # PDF skips those cells rather than stamping "0" into every line.
        self.assertNotIn("sch_e_property_a_advertising", result)
        self.assertNotIn("sch_e_property_a_repairs", result)


class SchEComputedTotalsTests(unittest.TestCase):
    def test_line_20_and_21_are_summed_locally(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0,
            mortgage_interest=8000.0,
            taxes=3000.0,
            depreciation=5000.0,
        )]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["sch_e_property_a_total_expenses"], 16000)
        self.assertEqual(result["sch_e_property_a_income_loss"], 8000)


class SchELine26OracleTests(unittest.TestCase):
    def test_line_26_passed_through_from_oracle(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0, mortgage_interest=8000.0,
            taxes=3000.0, depreciation=5000.0,
        )]
        result = compute(scenario, upstream={"f1040": {"sche_line26": 8000}})
        self.assertEqual(result["sch_e_line_26_total"], 8000)

    def test_line_26_missing_is_skipped(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental()]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertNotIn("sch_e_line_26_total", result)

    def test_line_26_divergence_warns_and_uses_oracle(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0, mortgage_interest=8000.0,
        )]
        with self.assertLogs("tenforty.forms.sch_e", level=logging.WARNING) as cm:
            result = compute(
                scenario, upstream={"f1040": {"sche_line26": 9999}},
            )
        self.assertEqual(result["sch_e_line_26_total"], 9999)
        self.assertTrue(
            any("diverges" in rec.getMessage() for rec in cm.records),
            "expected a divergence WARNING",
        )


class SchEEmptyTests(unittest.TestCase):
    def test_empty_scenario_returns_header_only(self):
        scenario = make_simple_scenario()
        result = compute(scenario, upstream={"f1040": {}})
        self.assertIn("taxpayer_name", result)
        self.assertNotIn("sch_e_property_a_address", result)
        self.assertNotIn("sch_e_line_26_total", result)


if __name__ == "__main__":
    unittest.main()
