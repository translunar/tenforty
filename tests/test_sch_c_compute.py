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
    def test_stated_depreciation_refused_without_its_acknowledgment(self):
        # Line 13 is modeled; what refuses now is a stated figure that is not
        # acknowledged as coming from outside the MACRS model. (The computing
        # twin is in tests/test_sch_c_line_13.py.)
        biz = ScheduleCBusiness(
            description="x", gross_receipts=10_000.0, depreciation=100.0)
        with self.assertRaisesRegex(
                ValueError, "states `depreciation` without an asset list"):
            sch_c.compute(_scn(biz), upstream={})

    def test_home_office_refused(self):     self._assert_refused(home_office=100.0)
    def test_vehicle_refused(self):         self._assert_refused(vehicle_expenses=100.0)
    def test_depletion_refused(self):       self._assert_refused(depletion=100.0)
    def test_returns_allowances_refused(self): self._assert_refused(returns_and_allowances=100.0)
    def test_statutory_employee_refused(self): self._assert_refused(statutory_employee=True)


class SchCNetLossRefusalTests(unittest.TestCase):
    def test_net_loss_refused(self):
        # expenses exceed receipts -> line 31 < 0 -> refuse, because the
        # helper scenario does NOT attest all investment is at risk (Form
        # 6198 unmodeled). The attested path is in test_sch_c_net_loss.py.
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


class SchCPrintedChainTests(unittest.TestCase):
    def test_lines_1_3_and_5_carry_the_gross_receipts(self):
        from tenforty.forms import sch_c
        from tenforty.models import ScheduleCBusiness, Scenario
        from tests.helpers import make_simple_scenario
        base = make_simple_scenario()
        scn = Scenario(config=base.config, w2s=base.w2s, schedule_c_businesses=[
            ScheduleCBusiness(description="x", gross_receipts=9_000.4,
                              supplies=1_000.0)])
        lines = sch_c.compute(scn, upstream={})["sch_c_businesses"][0]
        for key in ("sch_c_line_1_gross_receipts", "sch_c_line_3_net_receipts",
                    "sch_c_line_5_gross_profit"):
            with self.subTest(key=key):
                self.assertEqual(lines[key], 9_000)
                self.assertEqual(lines[key], lines["sch_c_line_7_gross_income"])


class SchCEmitValuesTests(unittest.TestCase):
    def _scn(self, **biz_kwargs):
        from tenforty.models import ScheduleCBusiness, Scenario
        from tests.helpers import make_simple_scenario
        base = make_simple_scenario()
        return Scenario(config=base.config, w2s=base.w2s,
                        schedule_c_businesses=[ScheduleCBusiness(**biz_kwargs)])

    def _values(self, scn, index=0):
        from tenforty.forms import sch_c
        lines = sch_c.compute(scn, upstream={})["sch_c_businesses"][index]
        return sch_c.emit_values(scn, index, lines)

    def test_header_description_code_and_line_values(self):
        scn = self._scn(description="Synthetic Consulting",
                        business_code="541990", gross_receipts=9000.0,
                        supplies=1000.0)
        v = self._values(scn)
        self.assertEqual(v["sch_c_line_a_description"], "Synthetic Consulting")
        self.assertEqual(v["sch_c_line_b_business_code"], "541990")
        self.assertEqual(v["sch_c_line_7_gross_income"], 9000)
        self.assertEqual(v["sch_c_line_28_total_expenses"], 1000)
        self.assertEqual(v["sch_c_line_31_net_profit"], 8000)
        self.assertIn("taxpayer_name", v)
        self.assertIn("taxpayer_ssn", v)

    def test_only_nonzero_expenses_are_present(self):
        from tenforty.forms import sch_c
        scn = self._scn(description="x", gross_receipts=9000.0,
                        supplies=1000.0, travel=250.0)
        v = self._values(scn)
        self.assertEqual(v["sch_c_expense_supplies"], 1000.0)
        self.assertEqual(v["sch_c_expense_travel"], 250.0)
        present = {k for k in v if k.startswith("sch_c_expense_")}
        self.assertEqual(present,
                         {"sch_c_expense_supplies", "sch_c_expense_travel"})
        self.assertEqual(len(sch_c._EXPENSE_FIELDS), 12)

    def test_line_48_mirrors_other_expenses_only_when_nonzero(self):
        with_other = self._values(self._scn(
            description="x", gross_receipts=9000.0, other_expenses=640.0,
            other_expenses_description="Synthetic fees"))
        self.assertEqual(with_other["sch_c_line_48_total_other_expenses"], 640.0)
        self.assertEqual(with_other["sch_c_part_v_row_1_amount"], 640.0)
        self.assertEqual(
            with_other["sch_c_part_v_row_1_description"], "Synthetic fees")
        self.assertEqual(with_other["sch_c_expense_other_expenses"], 640.0)
        without = self._values(self._scn(description="x", gross_receipts=9000.0))
        self.assertNotIn("sch_c_line_48_total_other_expenses", without)
        self.assertNotIn("sch_c_part_v_row_1_amount", without)

    def test_blank_description_and_code_are_absent(self):
        v = self._values(self._scn(gross_receipts=100.0))
        self.assertNotIn("sch_c_line_a_description", v)
        self.assertNotIn("sch_c_line_b_business_code", v)

    def test_integer_business_code_prints_its_digits(self):
        # An unquoted YAML code loads as an int.
        v = self._values(self._scn(description="x", business_code=541990,
                                   gross_receipts=100.0))
        self.assertEqual(v["sch_c_line_b_business_code"], "541990")

    def test_index_selects_the_business(self):
        from tenforty.models import ScheduleCBusiness, Scenario
        from tests.helpers import make_simple_scenario
        base = make_simple_scenario()
        scn = Scenario(config=base.config, w2s=base.w2s, schedule_c_businesses=[
            ScheduleCBusiness(description="First", gross_receipts=100.0),
            ScheduleCBusiness(description="Second", gross_receipts=200.0),
        ])
        self.assertEqual(
            self._values(scn, 1)["sch_c_line_a_description"], "Second")
        self.assertEqual(self._values(scn, 1)["sch_c_line_7_gross_income"], 200)
