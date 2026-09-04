import unittest

from tenforty.forms import sch_c
from tenforty.models import ScheduleCBusiness, Scenario
from tests.helpers import make_simple_scenario


def _scn(*biz):
    base = make_simple_scenario()
    return Scenario(config=base.config, schedule_c_businesses=list(biz))


class SchCNetProfitTests(unittest.TestCase):
    def test_net_profit_is_receipts_minus_expenses(self):
        biz = ScheduleCBusiness(description="consult", gross_receipts=80_000.0,
                                supplies=2_000.0, utilities=1_000.0, wages=10_000.0)
        out = sch_c.compute(_scn(biz), upstream={})
        # 80,000 gross - (2,000 + 1,000 + 10,000) expenses = 67,000
        self.assertEqual(out["sch_c_line_31_net_profit_total"], 67_000)
        self.assertEqual(out["sch_c_businesses"][0]["sch_c_line_28_total_expenses"], 13_000)

    def test_multiple_businesses_sum(self):
        b1 = ScheduleCBusiness(description="a", gross_receipts=40_000.0, supplies=5_000.0)
        b2 = ScheduleCBusiness(description="b", gross_receipts=20_000.0, rent_lease=2_000.0)
        out = sch_c.compute(_scn(b1, b2), upstream={})
        self.assertEqual(out["sch_c_line_31_net_profit_total"], 53_000)  # 35,000 + 18,000

    def test_empty_returns_empty(self):
        self.assertEqual(sch_c.compute(make_simple_scenario(), upstream={}), {})


class SchCRefusalTests(unittest.TestCase):
    def _assert_refused(self, **kw):
        biz = ScheduleCBusiness(description="x", gross_receipts=10_000.0, **kw)
        with self.assertRaises(NotImplementedError):
            sch_c.compute(_scn(biz), upstream={})

    def test_cogs_refused(self):            self._assert_refused(cost_of_goods_sold=100.0)
    def test_inventory_refused(self):       self._assert_refused(inventory=100.0)
    def test_depreciation_refused(self):    self._assert_refused(depreciation=100.0)
    def test_home_office_refused(self):     self._assert_refused(home_office=100.0)
    def test_vehicle_refused(self):         self._assert_refused(vehicle_expenses=100.0)
    def test_depletion_refused(self):       self._assert_refused(depletion=100.0)
    def test_returns_allowances_refused(self): self._assert_refused(returns_and_allowances=100.0)
    def test_statutory_employee_refused(self): self._assert_refused(statutory_employee=True)


class SchCNetLossRefusalTests(unittest.TestCase):
    def test_net_loss_refused(self):
        # expenses exceed receipts -> line 31 < 0 -> refuse (at-risk / QBI-loss /
        # 461(l) unmodeled).
        biz = ScheduleCBusiness(description="loss", gross_receipts=10_000.0,
                                supplies=15_000.0)   # net profit = -5,000
        with self.assertRaises(NotImplementedError):
            sch_c.compute(_scn(biz), upstream={})

    def test_zero_net_profit_allowed(self):
        # exactly break-even (line 31 == 0) is NOT a loss -> computes.
        biz = ScheduleCBusiness(description="flat", gross_receipts=10_000.0,
                                supplies=10_000.0)
        out = sch_c.compute(_scn(biz), upstream={})
        self.assertEqual(out["sch_c_line_31_net_profit_total"], 0)
