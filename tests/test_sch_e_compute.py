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
            depreciation=5000.0, acknowledges_depreciation_stated_outside_macrs=True,
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
            depreciation=5000.0, acknowledges_depreciation_stated_outside_macrs=True,
        )]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(result["sch_e_property_a_total_expenses"], 16000)
        self.assertEqual(result["sch_e_property_a_income_loss"], 8000)


class SchEPrintedChainTests(unittest.TestCase):
    """printed-chain ruling (SE line 12 lineage), 2026-10-04: the filed page
    must foot from its own printed (whole-dollar) lines."""

    def test_line_20_sums_rounded_categories_and_page_foots(self):
        # Cents sum = 100.40 + 100.40 + 100.40 = 301.20 -> 301; printed
        # addends 100 + 100 + 100 = 300. Old convention printed 301 (page
        # does not foot); the ruling prints 300.
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=1000.30, advertising=100.40, insurance=100.40,
            repairs=100.40,
        )]
        r = compute(scenario, upstream={"f1040": {}})
        printed = [r[k] for k in (
            "sch_e_property_a_advertising", "sch_e_property_a_insurance",
            "sch_e_property_a_repairs")]
        self.assertEqual(printed, [100, 100, 100])
        self.assertEqual(r["sch_e_property_a_rents"], 1000)
        self.assertEqual(r["sch_e_property_a_total_expenses"], sum(printed))
        self.assertEqual(r["sch_e_property_a_total_expenses"], 300)
        self.assertEqual(
            r["sch_e_property_a_income_loss"],
            r["sch_e_property_a_rents"] - r["sch_e_property_a_total_expenses"],
        )
        self.assertEqual(r["sch_e_property_a_income_loss"], 700)
        self.assertEqual(r["sch_e_line_26_total"], 700)

    def test_line_26_follows_printed_line_21_even_if_oracle_cents_differ(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=1000.30, advertising=100.40, insurance=100.40,
            repairs=100.40,
        )]
        # Workbook cents figure rounds to 699 (1000.30 - 301.20 = 699.10).
        with self.assertLogs("tenforty.forms.sch_e", level=logging.WARNING):
            r = compute(scenario, upstream={"f1040": {"sche_line26": 699.10}})
        self.assertEqual(r["sch_e_line_26_total"], 700)


class SchELine26OracleTests(unittest.TestCase):
    def test_line_26_passed_through_from_oracle(self):
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0, mortgage_interest=8000.0,
            taxes=3000.0, depreciation=5000.0,
            acknowledges_depreciation_stated_outside_macrs=True,
        )]
        result = compute(scenario, upstream={"f1040": {"sche_line26": 8000}})
        self.assertEqual(result["sch_e_line_26_total"], 8000)

    def test_line_26_falls_back_to_locally_summed_when_oracle_missing(self):
        """Plan C shift: native compute is authoritative. When the oracle
        doesn't expose line 26 (e.g. Sch 1 predicate path), use the locally
        summed single-property line 21."""
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental()]
        result = compute(scenario, upstream={"f1040": {}})
        self.assertEqual(
            result["sch_e_line_26_total"],
            result["sch_e_property_a_income_loss"],
        )

    def test_line_26_divergence_warns_and_uses_printed_chain(self):
        # Moved under the printed-chain ruling (SE line 12 lineage),
        # 2026-10-04: line 26 is arithmetic over printed line 21, so a
        # diverging workbook figure is logged but NOT adopted. Local line
        # 21 = 24000 - 8000 = 16000.
        scenario = make_simple_scenario()
        scenario.rental_properties = [_rental(
            rents_received=24000.0, mortgage_interest=8000.0,
        )]
        with self.assertLogs("tenforty.forms.sch_e", level=logging.WARNING) as cm:
            result = compute(
                scenario, upstream={"f1040": {"sche_line26": 9999}},
            )
        self.assertEqual(result["sch_e_line_26_total"], 16000)
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
