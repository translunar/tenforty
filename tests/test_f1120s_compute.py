"""Unit tests for tenforty.forms.f1120s.compute — native Form 1120-S.

Expected values come from manual arithmetic over the IRS 2025 Form 1120-S
instructions. These tests do NOT import or reference any oracle module.
"""

import unittest

from tenforty.forms import f1120s

from tests._scorp_fixtures import _make_v1_scenario


class IncomeSectionTests(unittest.TestCase):
    def test_line_1a_matches_gross_receipts(self):
        s = _make_v1_scenario(gross_receipts=100000.0)
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_1a_gross_receipts"], 100000.0)

    def test_line_1c_equals_1a_minus_1b(self):
        """IRS line 1c = line 1a − line 1b (returns and allowances)."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.returns_and_allowances = 500.0
        out = f1120s.compute(s, upstream={})
        self.assertEqual(out["f1120s_line_1c_net_receipts"], 99500.0)

    def test_line_3_equals_1c_minus_2(self):
        """IRS line 3 gross profit = line 1c − line 2 (COGS)."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.cogs_aggregate = 20000.0
        out = f1120s.compute(s, upstream={})
        # 1c = 100000 - 0 = 100000; 3 = 100000 - 20000 = 80000
        self.assertEqual(out["f1120s_line_3_gross_profit"], 80000.0)

    def test_line_6_total_income_sums_3_4_5(self):
        """IRS line 6 = line 3 + line 4 + line 5."""
        s = _make_v1_scenario(gross_receipts=100000.0)
        s.s_corp_return.income.net_gain_loss_4797 = 2000.0
        s.s_corp_return.income.other_income = 500.0
        out = f1120s.compute(s, upstream={})
        # 3 = 100000; 4 = 2000; 5 = 500; total = 102500
        self.assertEqual(out["f1120s_line_6_total_income"], 102500.0)
