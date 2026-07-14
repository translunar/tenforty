import unittest

from tenforty.forms.f8962 import compute
from tenforty.models import Form1095A, Form1095AMonth
from tenforty.params.f8962 import F8962Params


def _params(unemployment_rule=False):
    return F8962Params(
        year=2021 if unemployment_rule else 2024,
        fpl_single_48=10_000,
        applicable_figures={100: 0.0, 133: 0.0, 150: 0.0, 200: 0.02,
                            250: 0.04, 300: 0.06, 400: 0.085, 500: 0.085},
        applicable_figure_floor_pct=100,
        applicable_figure_ceiling_pct=500,
        repayment_caps_single=((200, 350), (300, 900), (400, 1500)),
        unemployment_rule=unemployment_rule,
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
