"""Flattener dispatch tests for Form 1099-G."""

import unittest

from tenforty.models import Form1099G
from tenforty.oracle.flattener import flatten_scenario

from tests.helpers import make_simple_scenario


class Flatten1099GTests(unittest.TestCase):
    def test_unemployment_box1(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(payer="State", unemployment_compensation=8_000.0)]
        flat = flatten_scenario(s)
        self.assertEqual(flat["g_unemployment_1"], 8_000.0)

    def test_state_refund_box2(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(
            payer="State", state_tax_refund=1_500.0, state_tax_refund_tax_year=2024,
        )]
        flat = flatten_scenario(s)
        self.assertEqual(flat["g_state_refund_1"], 1_500.0)

    def test_federal_withholding_box4(self):
        s = make_simple_scenario()
        s.form1099_g = [Form1099G(payer="State", unemployment_compensation=8_000.0,
                                  federal_tax_withheld=800.0)]
        flat = flatten_scenario(s)
        self.assertEqual(flat["g_fed_withheld_1"], 800.0)


if __name__ == "__main__":
    unittest.main()
