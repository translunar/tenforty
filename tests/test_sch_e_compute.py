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


def _stated(address: str, **amounts) -> RentalProperty:
    return _rental(
        address=address,
        acknowledges_depreciation_stated_outside_macrs=True, **amounts)


def _three_rentals(**overrides) -> list[RentalProperty]:
    """Three invented rentals. Per column -- A: rents 24,000, line 12 8,000,
    line 16 3,000, line 18 5,000 -> line 20 16,000, line 21 8,000.
    B: rents 12,000, line 16 2,000, line 18 14,000 -> line 20 16,000,
    line 21 (4,000). C: rents 9,000, line 12 4,000, line 16 1,000 ->
    line 20 5,000, line 21 4,000. ``overrides`` maps a column letter to
    field overrides for that property."""
    columns = {
        "a": dict(address="100 Example Street", rents_received=24_000.0,
                  mortgage_interest=8_000.0, taxes=3_000.0,
                  depreciation=5_000.0),
        "b": dict(address="200 Example Street", rents_received=12_000.0,
                  taxes=2_000.0, depreciation=14_000.0),
        "c": dict(address="300 Example Street", rents_received=9_000.0,
                  mortgage_interest=4_000.0, taxes=1_000.0),
    }
    for letter, fields in overrides.items():
        columns[letter].update(fields)
    return [_stated(**columns[letter]) for letter in "abc"]


def _columns_scenario(rentals):
    scenario = make_simple_scenario()
    scenario.rental_properties = list(rentals)
    return scenario


class PropertyColumnsComputeTests(unittest.TestCase):
    def test_each_property_fills_its_own_column_in_order(self):
        r = compute(_columns_scenario(_three_rentals()), upstream={})
        self.assertEqual(
            [r[f"sch_e_property_{x}_address"] for x in "abc"],
            ["100 Example Street", "200 Example Street",
             "300 Example Street"])
        self.assertEqual(
            [r[f"sch_e_property_{x}_rents"] for x in "abc"],
            [24_000, 12_000, 9_000])
        self.assertEqual(
            [r[f"sch_e_property_{x}_total_expenses"] for x in "abc"],
            [16_000, 16_000, 5_000])
        self.assertEqual(
            [r[f"sch_e_property_{x}_income_loss"] for x in "abc"],
            [8_000, -4_000, 4_000])
        # Zero lines print nothing; column A's line 12 is the twin.
        self.assertNotIn("sch_e_property_b_mortgage_interest", r)
        self.assertNotIn("sch_e_property_c_depreciation", r)
        self.assertEqual(r["sch_e_property_a_mortgage_interest"], 8_000)

    def test_totals_sum_the_printed_columns(self):
        r = compute(_columns_scenario(_three_rentals()), upstream={})
        self.assertEqual(r["sch_e_line_23a_total_rents"], 45_000)
        self.assertEqual(r["sch_e_line_23c_total_mortgage_interest"], 12_000)
        self.assertEqual(r["sch_e_line_23d_total_depreciation"], 19_000)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 37_000)
        self.assertEqual(r["sch_e_property_b_deductible_loss"], 4_000)
        self.assertNotIn("sch_e_property_a_deductible_loss", r)
        self.assertNotIn("sch_e_property_c_deductible_loss", r)
        self.assertEqual(r["sch_e_line_24_income"], 12_000)
        self.assertEqual(r["sch_e_line_25_losses"], 4_000)
        self.assertEqual(r["sch_e_line_26_total"], 8_000)

    def test_totals_sum_rounded_lines_not_raw_inputs(self):
        # Line 16 prints 3,001 in column A and 2,001 in column B (each half
        # dollar rounds up), so each line 20 prints 16,001. Line 23e is the
        # sum of the printed line 20s: 16,001 + 16,001 + 5,000 -- one more
        # than the 37,001 the raw amounts (37,001.00) would round to.
        r = compute(_columns_scenario(_three_rentals(
            a=dict(taxes=3_000.50), b=dict(taxes=2_000.50))), upstream={})
        self.assertEqual(r["sch_e_property_a_total_expenses"], 16_001)
        self.assertEqual(r["sch_e_property_b_total_expenses"], 16_001)
        self.assertEqual(r["sch_e_line_23e_total_expenses"], 37_002)
        line_21s = [r[f"sch_e_property_{x}_income_loss"] for x in "abc"]
        self.assertEqual(line_21s, [7_999, -4_001, 4_000])
        self.assertEqual(r["sch_e_line_26_total"], sum(line_21s))
        self.assertEqual(r["sch_e_line_26_total"], 7_998)

    def test_three_break_even_properties_leave_24_and_25_blank(self):
        even = [_stated(f"{n}00 Example Street", rents_received=5_000.0,
                        taxes=5_000.0) for n in (1, 2, 3)]
        r = compute(_columns_scenario(even), upstream={})
        self.assertEqual(
            [r[f"sch_e_property_{x}_income_loss"] for x in "abc"], [0, 0, 0])
        self.assertNotIn("sch_e_line_24_income", r)
        self.assertNotIn("sch_e_line_25_losses", r)
        self.assertEqual(r["sch_e_line_26_total"], 0)
        # Twin: the mixed-sign scenario prints both.
        mixed = compute(_columns_scenario(_three_rentals()), upstream={})
        self.assertIn("sch_e_line_24_income", mixed)
        self.assertIn("sch_e_line_25_losses", mixed)

    def test_line_25_sums_the_losses_of_two_columns(self):
        # Line 21 per column: A (3,000), B 9,000, C (5,000). Line 25 is
        # both losses, 8,000 -- not the last loss column's 5,000.
        rentals = [
            _stated("100 Example Street", rents_received=10_000.0,
                    taxes=13_000.0),
            _stated("200 Example Street", rents_received=20_000.0,
                    taxes=11_000.0),
            _stated("300 Example Street", rents_received=6_000.0,
                    taxes=11_000.0),
        ]
        r = compute(_columns_scenario(rentals), upstream={})
        self.assertEqual(
            [r[f"sch_e_property_{x}_income_loss"] for x in "abc"],
            [-3_000, 9_000, -5_000])
        self.assertEqual(r["sch_e_property_a_deductible_loss"], 3_000)
        self.assertNotIn("sch_e_property_b_deductible_loss", r)
        self.assertEqual(r["sch_e_property_c_deductible_loss"], 5_000)
        self.assertEqual(r["sch_e_line_24_income"], 9_000)
        self.assertEqual(r["sch_e_line_25_losses"], 8_000)
        self.assertEqual(r["sch_e_line_26_total"], 1_000)

    def test_an_empty_second_property_prints_its_row_and_changes_no_total(self):
        first = _three_rentals()[0]
        alone = compute(_columns_scenario([first]), upstream={})
        r = compute(_columns_scenario([first, _rental(
            address="200 Example Street", rents_received=0.0)]), upstream={})
        self.assertEqual(r["sch_e_property_b_address"], "200 Example Street")
        self.assertEqual(r["sch_e_property_b_income_loss"], 0)
        for key, expected in (
                ("sch_e_line_23a_total_rents", 24_000),
                ("sch_e_line_23e_total_expenses", 16_000),
                ("sch_e_line_24_income", 8_000),
                ("sch_e_line_26_total", 8_000)):
            with self.subTest(key=key):
                self.assertEqual(r[key], expected)
                self.assertEqual(r[key], alone[key])

    def test_a_fourth_property_refuses_rather_than_truncating(self):
        four = _three_rentals() + [_stated(
            "400 Example Street", rents_received=1_000.0)]
        compute(_columns_scenario(four[:3]), upstream={})  # twin: three print
        with self.assertRaisesRegex(NotImplementedError, r"rental_3"):
            compute(_columns_scenario(four), upstream={})

    def test_line_26_cross_check_compares_the_summed_total(self):
        # Property C's rents are 10,000 here, so C nets 5,000 and the three
        # columns total 9,000 -- a figure that differs from column A's own
        # line 21 (8,000). With the unmodified table the two coincide and
        # the check could not tell the summed total from column A.
        scenario = _columns_scenario(_three_rentals(
            c=dict(rents_received=10_000.0)))
        with self.assertNoLogs("tenforty.forms.sch_e", level="WARNING"):
            r = compute(scenario, upstream={"f1040": {"sche_line26": 9_000}})
        self.assertEqual(r["sch_e_line_26_total"], 9_000)
        # Twin: column A's line 21 is not the page total, so it diverges.
        with self.assertLogs("tenforty.forms.sch_e", level="WARNING") as cm:
            r = compute(scenario, upstream={"f1040": {"sche_line26": 8_000}})
        self.assertTrue(
            any("diverges" in rec.getMessage() for rec in cm.records))
        self.assertEqual(r["sch_e_line_26_total"], 9_000)

if __name__ == "__main__":
    unittest.main()
