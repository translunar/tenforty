"""Schedule D native-Python summary-path compute tests."""

import unittest

from tenforty.forms.sch_d import compute
from tenforty.models import Form1099B

from tests.helpers import make_simple_scenario


def _lot(
    *,
    short_term: bool = True,
    proceeds: float = 1000.0,
    basis: float = 600.0,
    basis_reported_to_irs: bool = True,
    wash_sale_loss_disallowed: float = 0.0,
) -> Form1099B:
    return Form1099B(
        broker="Schwab",
        description="100 ACME",
        date_acquired="2024-01-01",
        date_sold="2025-06-01",
        proceeds=proceeds,
        cost_basis=basis,
        short_term=short_term,
        basis_reported_to_irs=basis_reported_to_irs,
        wash_sale_loss_disallowed=wash_sale_loss_disallowed,
    )


class SchDShortTermTests(unittest.TestCase):
    def test_single_short_term_summary_line(self):
        scenario = make_simple_scenario()
        scenario.form1099_b = [_lot(proceeds=1500.0, basis=1000.0)]
        result = compute(scenario, upstream={})
        self.assertEqual(result["sch_d_line_1a_proceeds"], 1500)
        self.assertEqual(result["sch_d_line_1a_basis"], 1000)
        self.assertEqual(result["sch_d_line_1a_gain"], 500)
        self.assertEqual(result["sch_d_line_7_net_short"], 500)
        self.assertEqual(result["sch_d_line_8a_gain"], 0)
        self.assertEqual(result["sch_d_line_15_net_long"], 0)

    def test_short_term_netting(self):
        scenario = make_simple_scenario()
        scenario.form1099_b = [
            _lot(proceeds=1000.0, basis=600.0),   # +400
            _lot(proceeds=500.0, basis=700.0),    # -200
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["sch_d_line_7_net_short"], 200)


class SchDLongTermTests(unittest.TestCase):
    def test_long_term_netting(self):
        scenario = make_simple_scenario()
        scenario.form1099_b = [
            _lot(short_term=False, proceeds=5000.0, basis=2000.0),  # +3000
            _lot(short_term=False, proceeds=1000.0, basis=1500.0),  # -500
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["sch_d_line_15_net_long"], 2500)


class SchDMixedTests(unittest.TestCase):
    def test_mixed_terms_produce_two_summary_lines(self):
        scenario = make_simple_scenario()
        scenario.form1099_b = [
            _lot(short_term=True, proceeds=1500.0, basis=1000.0),
            _lot(short_term=False, proceeds=5000.0, basis=2000.0),
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(result["sch_d_line_1a_gain"], 500)
        self.assertEqual(result["sch_d_line_8a_gain"], 3000)
        self.assertEqual(result["sch_d_line_16_total"], 3500)

    def test_line_16_is_sum_of_7_and_15(self):
        scenario = make_simple_scenario()
        scenario.form1099_b = [
            _lot(short_term=True, proceeds=1500.0, basis=1000.0),
            _lot(short_term=False, proceeds=5000.0, basis=2000.0),
        ]
        result = compute(scenario, upstream={})
        self.assertEqual(
            result["sch_d_line_16_total"],
            result["sch_d_line_7_net_short"]
            + result["sch_d_line_15_net_long"],
        )


class SchDEmptyTests(unittest.TestCase):
    def test_empty_scenario_yields_zero_totals(self):
        scenario = make_simple_scenario()
        result = compute(scenario, upstream={})
        for key in (
            "sch_d_line_1a_proceeds", "sch_d_line_1a_basis",
            "sch_d_line_1a_gain", "sch_d_line_7_net_short",
            "sch_d_line_8a_proceeds", "sch_d_line_8a_basis",
            "sch_d_line_8a_gain", "sch_d_line_15_net_long",
            "sch_d_line_16_total",
        ):
            self.assertEqual(result[key], 0, key)


class SchDTaxpayerHeaderTests(unittest.TestCase):
    def test_taxpayer_header_from_config(self):
        scenario = make_simple_scenario()
        scenario.config.first_name = "Alex"
        scenario.config.last_name = "Rivera"
        scenario.config.ssn = "000-12-3456"
        scenario.form1099_b = [_lot()]
        result = compute(scenario, upstream={})
        self.assertEqual(result["taxpayer_name"], "Alex Rivera")
        self.assertEqual(result["taxpayer_ssn"], "000-12-3456")


if __name__ == "__main__":
    unittest.main()
