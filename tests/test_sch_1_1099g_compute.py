"""1099-G fan-out through Schedule 1."""

import unittest

from tenforty.forms import sch_1 as form_sch_1
from tenforty.models import Form1099G

from tests.helpers import make_simple_scenario


class Sch1UnemploymentTests(unittest.TestCase):
    def test_box1_to_line_7(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(payer="State", unemployment_compensation=8_000.0)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_7_unemployment"], 8_000)

    def test_multiple_1099g_summed(self):
        s = make_simple_scenario()
        s.form1099_g = [
            Form1099G(payer="State A", unemployment_compensation=3_000.0),
            Form1099G(payer="State B", unemployment_compensation=5_000.0),
        ]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_7_unemployment"], 8_000)


class Sch1OtherIncomeTests(unittest.TestCase):
    def test_rtaa_to_line_8z(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(
            payer="State", rtaa_payments=500.0, taxable_grants=1_000.0,
            agriculture_payments=2_000.0, market_gain=150.0,
        )]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_8z_other_income"], 3_650)


if __name__ == "__main__":
    unittest.main()
