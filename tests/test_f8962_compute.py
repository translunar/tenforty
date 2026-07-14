import unittest

from tenforty.forms.f8962 import compute
from tenforty.models import Form1095A, Form1095AMonth
from tenforty.params.f8962 import F8962Params


def _params(unemployment_rule=False, line5_400_boundary_inclusive=False):
    return F8962Params(
        year=2021 if unemployment_rule else 2024,
        fpl_single_48=10_000,
        applicable_figures={100: 0.0, 133: 0.0, 150: 0.0, 200: 0.02,
                            250: 0.04, 300: 0.06, 400: 0.085, 500: 0.085},
        applicable_figure_floor_pct=100,
        applicable_figure_ceiling_pct=500,
        repayment_caps_single=((200, 350), (300, 900), (400, 1500)),
        unemployment_rule=unemployment_rule,
        line5_400_boundary_inclusive=line5_400_boundary_inclusive,
    )


def _block(months, ui=False):
    rows = [Form1095AMonth() for _ in range(12)]
    for i, row in months.items():
        rows[i] = Form1095AMonth(*row)
    return Form1095A(months=tuple(rows), received_unemployment_2021=ui)


class F8962ComputeTests(unittest.TestCase):
    def test_full_year_net_ptc(self):
        # MAGI 25,000 → 250% → figure .04 → 8a=1000, 8b=83.
        # Per month: d = max(0, 300−83) = 217; e = min(premium 250, 217)
        # = 217; aptc (f) = 200.
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})
        r = compute(b, 25_000.0, 2024, _params())
        self.assertEqual(r["f8962_line_5"], 250)
        self.assertEqual(r["f8962_line_8b"], 83)
        self.assertEqual(r["f8962_line_24"], 12 * 217)
        self.assertEqual(r["f8962_line_25"], 12 * 200)
        self.assertEqual(r["f8962_line_26_net_ptc"], 12 * 17)
        self.assertEqual(r["f8962_line_29_repayment"], 0)

    def test_repayment_capped_below_400(self):
        # MAGI 25,000 → 250%: cap band (300, 900). APTC 300/mo vs e=217/mo
        # → line 27 = 996 → capped at 900.
        b = _block({i: (250.0, 300.0, 300.0) for i in range(12)})
        r = compute(b, 25_000.0, 2024, _params())
        self.assertEqual(r["f8962_line_27"], 996)
        self.assertEqual(r["f8962_line_28"], 900)
        self.assertEqual(r["f8962_line_29_repayment"], 900)
        self.assertEqual(r["f8962_line_26_net_ptc"], 0)

    def test_repayment_uncapped_at_400_plus(self):
        # MAGI 45,000 → 450% → ceiling figure .085 → 8b = 319.
        # slcsp 300 < 319 → d=0 → e=0 → full APTC repaid, uncapped.
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})
        r = compute(b, 45_000.0, 2024, _params())
        self.assertEqual(r["f8962_line_24"], 0)
        self.assertEqual(r["f8962_line_29_repayment"], 2400)

    def test_2021_ui_rule_floors_line5(self):
        # Same high MAGI, but UI flag + rule → line 5 = 133 → figure 0
        # → contribution 0 → e = min(premium, slcsp) per month.
        b = _block({i: (250.0, 300.0, 250.0) for i in range(5, 10)}, ui=True)
        r = compute(b, 45_000.0, 2021, _params(unemployment_rule=True))
        self.assertEqual(r["f8962_line_5"], 133)
        self.assertEqual(r["f8962_line_24"], 5 * 250)
        self.assertEqual(r["f8962_line_25"], 5 * 250)
        self.assertEqual(r["f8962_line_26_net_ptc"], 0)
        self.assertEqual(r["f8962_line_29_repayment"], 0)
        self.assertTrue(r["f8962_ui_box_checked"])

    def test_ui_flag_without_params_rule_refuses(self):
        b = _block({8: (250.0, 300.0, 250.0)}, ui=True)
        with self.assertRaises(ValueError):
            compute(b, 45_000.0, 2024, _params(unemployment_rule=False))

    def test_all_zero_block_is_all_zero(self):
        r = compute(_block({}), 45_000.0, 2024, _params())
        self.assertEqual(r["f8962_line_24"], 0)
        self.assertEqual(r["f8962_line_25"], 0)
        self.assertEqual(r["f8962_line_26_net_ptc"], 0)
        self.assertEqual(r["f8962_line_29_repayment"], 0)

    def test_line5_strict_400_pct_boundary(self):
        # Worksheet 2: line 5 = 401 only STRICTLY above 400% FPL (magi >
        # 4 * fpl_single_48 = 40,000). At exactly 400% it's 400 (not 401);
        # just below, it's the ordinary floored percentage (399).
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})

        r_at_400 = compute(b, 40_000.0, 2024, _params())
        self.assertEqual(r_at_400["f8962_line_5"], 400)

        r_over_400 = compute(b, 40_001.0, 2024, _params())
        self.assertEqual(r_over_400["f8962_line_5"], 401)

        r_under_400 = compute(b, 39_999.0, 2024, _params())
        self.assertEqual(r_under_400["f8962_line_5"], 399)

        # The 401 vs 400 change is line-5-only: the applicable figure
        # floor-keys to the same 400-bracket entry either way.
        self.assertEqual(r_over_400["f8962_line_7"], r_at_400["f8962_line_7"])

    def test_line5_inclusive_400_pct_boundary(self):
        # 2021 Worksheet 2 phrasing ("Is the result 400 or more? Yes ->
        # enter 401 here") is INCLUSIVE of exactly 400%, unlike the
        # 2022-2025 STRICT phrasing ("more than 400% ... enter 401")
        # exercised by test_line5_strict_400_pct_boundary above. With
        # line5_400_boundary_inclusive=True, magi == 4 * fpl_single_48
        # (exactly 400% FPL) must itself produce line 5 = 401.
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})
        params = _params(line5_400_boundary_inclusive=True)

        r_at_400 = compute(b, 40_000.0, params.year, params)
        self.assertEqual(r_at_400["f8962_line_5"], 401)

        r_under_400 = compute(b, 39_999.0, params.year, params)
        self.assertEqual(r_under_400["f8962_line_5"], 399)

        # The applicable-figure floor-key lookup lands on the same
        # 400-bracket entry whether line 5 reads 400 or 401.
        self.assertEqual(r_at_400["f8962_line_7"], 0.085)

    def test_line5_exact_integer_pct_no_float_underflow(self):
        # magi=31,257 is EXACTLY 230% of fpl=13,590 (13,590 * 2.30 =
        # 31,257.0). But float division underflows:
        #   31257 / 13590 * 100 == 229.99999999999997 -> floor -> 229.
        # The IRS worksheet step is "divide line 3 by line 4, multiply by
        # 100, drop any numbers after the decimal point" on the EXACT
        # ratio, which for an exact multiple must land on 230, not 229.
        # Integer arithmetic (magi * 100) // fpl avoids the float error.
        params = F8962Params(
            year=2024,
            fpl_single_48=13_590,
            applicable_figures={100: 0.0, 133: 0.0, 150: 0.0, 200: 0.02,
                                250: 0.04, 300: 0.06, 400: 0.085, 500: 0.085},
            applicable_figure_floor_pct=100,
            applicable_figure_ceiling_pct=500,
            repayment_caps_single=((200, 350), (300, 900), (400, 1500)),
            unemployment_rule=False,
            line5_400_boundary_inclusive=False,
        )
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})
        r = compute(b, 31_257.0, 2024, params)
        self.assertEqual(r["f8962_line_5"], 230)

    def test_line5_below_floor_pct_not_clamped_up(self):
        # magi=9,000 with fpl_single_48=10,000 -> exactly 90% FPL, below
        # this params set's applicable_figure_floor_pct=100. Line 5 must
        # report the TRUE percentage (90), not the applicable-figure
        # table's floor (previously the clamp raised it to 100).
        b = _block({i: (250.0, 300.0, 200.0) for i in range(12)})
        r = compute(b, 9_000.0, 2024, _params())
        self.assertEqual(r["f8962_line_5"], 90)
        # The applicable-figure lookup still floor-keys into the table's
        # lowest entry (100 -> 0.0) either way, so PTC dollars for this
        # case are unaffected by the line-5 reporting fix.
        self.assertEqual(r["f8962_line_7"], 0.0)
