"""Form 8995 line 1: one row per QBI source (Juno's ruling; phase K).

Each QBI source gets its own row i-v: its name in (a), its TIN in (b), its
OWN qualified business income in (c). Line 2 combines the rows as printed:
the sum of each row's whole-dollar QBI (ruled; the vendor workbook's own
line-2 formula). The aggregate key f8995_line_1_qbi stays as line 2's feed.

Phase K serves K-1 sources (pure re-exposure of each K-1's qbi_amount) and a
single Schedule C business (its row is exactly today's Schedule C QBI
component). Two or more Schedule C businesses need the half-SE-tax allocated
across them, which is pending a ruling: refused. More than five sources need
an attached statement, not built yet: refused.

All identities and amounts are fully synthetic (TINs are placeholder
tokens, deliberately not EIN-shaped).
"""
import unittest

from tenforty.forms import f8995
from tenforty.models import K1FanoutData, ScheduleCBusiness, ScheduleK1
from tenforty.rounding import irs_round

from tests.helpers import make_k1_scenario

ROWS = ("i", "ii", "iii", "iv", "v")
SSN = "000-00-1111"


def _k1(n, qbi):
    return ScheduleK1(entity_name=f"Example Entity {n}",
                      entity_ein=f"EX-EIN-{n}", entity_type="s_corp",
                      material_participation=True, qbi_amount=qbi)


def _case(k1_qbis=(), businesses=(), half_se=0.0, se_health=0.0,
          fanout_qbi=None):
    """A scenario whose upstream agrees with its source objects (as the
    production producers guarantee), unless ``fanout_qbi`` overrides the
    K-1 aggregate."""
    s = make_k1_scenario()
    s.config.ssn = SSN
    s.config.self_employed_health_insurance_deduction = se_health
    s.schedule_k1s = [_k1(n, q) for n, q in enumerate(k1_qbis, start=1)]
    s.schedule_c_businesses = [ScheduleCBusiness(description=desc)
                               for desc, _ in businesses]
    nets = [net for _, net in businesses]
    upstream = {
        "f1040": {"taxable_income_before_qbi_deduction": 100_000.0,
                  "net_capital_gain": 0.0, "qualified_dividends": 0.0},
        "k1_fanout": K1FanoutData(
            sch_b_interest_additions=(), sch_b_dividend_additions=(),
            sch_d_short_term_additions=(), sch_d_long_term_additions=(),
            qbi_aggregate=(sum(k1_qbis) if fanout_qbi is None
                           else fanout_qbi),
            qualified_dividends_aggregate=0.0, passive_activities=()),
        "sch_c": {"sch_c_businesses": [{"sch_c_line_31_net_profit": net}
                                       for net in nets],
                  "sch_c_line_31_net_profit_total": sum(nets)},
        "sch_se": {"sch_se_line_13_half_deduction": half_se},
    }
    return s, upstream


def _rows(out):
    """{row: (name, tin, qbi)} for every row the computation emitted."""
    return {r: (out[f"f8995_line_1{r}_name"], out[f"f8995_line_1{r}_tin"],
                out[f"f8995_line_1{r}_qbi"])
            for r in ROWS if f"f8995_line_1{r}_qbi" in out}


class SingleScheduleCIdentityTests(unittest.TestCase):
    """One Schedule C business: its row is exactly today's Schedule C QBI
    component (net profit - half-SE-tax - SE-health), the identity the
    single-row form printed."""

    def test_row_i_is_todays_sch_c_qbi(self):
        for net, half_se, se_health in ((60_000.0, 4_000.0, 0.0),
                                        (60_000.0, 4_000.0, 6_000.0),
                                        (-40.0, 0.0, 0.0)):
            s, up = _case(businesses=[("Example Bindery", net)],
                          half_se=half_se, se_health=se_health)
            out = f8995.compute(s, up)
            todays = irs_round(net - half_se - se_health)
            with self.subTest(net=net, half_se=half_se, se_health=se_health):
                self.assertEqual(_rows(out),
                                 {"i": ("Example Bindery", SSN, todays)})
                self.assertEqual(out["f8995_line_1_qbi"], todays)
                self.assertEqual(out["f8995_line_2_total_qbi"], todays)


class PerSourceRowTests(unittest.TestCase):
    def test_each_k1_gets_its_own_row(self):
        s, up = _case(k1_qbis=(12_000.0, 3_000.0, 500.0))
        out = f8995.compute(s, up)
        self.assertEqual(_rows(out), {
            "i": ("Example Entity 1", "EX-EIN-1", 12_000),
            "ii": ("Example Entity 2", "EX-EIN-2", 3_000),
            "iii": ("Example Entity 3", "EX-EIN-3", 500)})
        self.assertEqual(out["f8995_line_2_total_qbi"], 15_500)

    def test_a_zero_qbi_k1_takes_no_row(self):
        s, up = _case(k1_qbis=(12_000.0, 0.0, 500.0))
        out = f8995.compute(s, up)
        self.assertEqual(_rows(out), {
            "i": ("Example Entity 1", "EX-EIN-1", 12_000),
            "ii": ("Example Entity 3", "EX-EIN-3", 500)})

    def test_schedule_c_rows_come_first(self):
        s, up = _case(k1_qbis=(2_000.0,),
                      businesses=[("Example Bindery", 30_000.0)],
                      half_se=2_000.0)
        out = f8995.compute(s, up)
        self.assertEqual(_rows(out), {
            "i": ("Example Bindery", SSN, 28_000),
            "ii": ("Example Entity 1", "EX-EIN-1", 2_000)})
        self.assertEqual(out["f8995_line_1_qbi"], 30_000)

    def test_five_sources_fill_the_grid(self):
        s, up = _case(k1_qbis=(1_000.0, 2_000.0, 3_000.0, 4_000.0),
                      businesses=[("Example Bindery", 10_000.0)])
        self.assertEqual(sorted(_rows(f8995.compute(s, up)), key=ROWS.index),
                         list(ROWS))

    def test_a_zero_profit_business_takes_no_row_and_does_not_refuse(self):
        s, up = _case(businesses=[("Example Bindery", 10_000.0),
                                  ("Example Idle Shop", 0.0)])
        self.assertEqual(_rows(f8995.compute(s, up)),
                         {"i": ("Example Bindery", SSN, 10_000)})


class LineTwoFootingTests(unittest.TestCase):
    """Line 2 = the sum of each row's whole-dollar QBI (ruled)."""

    def test_line_2_sums_the_printed_rows(self):
        # 10.6 + 10.6: the rows print 11 and 11, so line 2 is 22, where one
        # round of the unrounded sum (21.2) would give 21.
        s, up = _case(k1_qbis=(10.6, 10.6))
        out = f8995.compute(s, up)
        self.assertEqual([q for _, _, q in _rows(out).values()], [11, 11])
        self.assertEqual(out["f8995_line_2_total_qbi"], 22)
        self.assertEqual(out["f8995_line_1_qbi"], 22)


class RefusalTests(unittest.TestCase):
    def test_two_schedule_c_businesses_are_refused(self):
        # The half-SE-tax allocation across businesses is pending a ruling.
        s, up = _case(businesses=[("Example Bindery", 10_000.0),
                                  ("Example Kiln", -500.0)])
        with self.assertRaises(NotImplementedError) as ctx:
            f8995.compute(s, up)
        self.assertIn("per-source rows", str(ctx.exception))
        self.assertIn("allocat", str(ctx.exception))

    def test_more_than_five_sources_are_refused(self):
        s, up = _case(k1_qbis=(1_000.0,) * 6)
        with self.assertRaises(NotImplementedError) as ctx:
            f8995.compute(s, up)
        self.assertIn("statement", str(ctx.exception))

    def test_an_upstream_aggregate_disagreeing_with_the_sources_raises(self):
        # The rows are the sources; a K-1 aggregate that does not equal them
        # would make line 2 contradict the printed rows.
        s, up = _case(k1_qbis=(1_000.0,), fanout_qbi=11_000.0)
        with self.assertRaises(ValueError):
            f8995.compute(s, up)


if __name__ == "__main__":
    unittest.main()
