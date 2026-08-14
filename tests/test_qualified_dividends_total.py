"""Total qualified dividends = 1099-DIV + K-1 (IRC 1366(b) conduit treatment).

All figures are GENERIC/synthetic.
"""

import unittest

from tenforty.forms import f1040_spine
from tenforty.models import K1FanoutData
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_simple_scenario


class QualifiedDividendsTotalPreambleTests(unittest.TestCase):
    def _fanout(self, k1_qual):
        return K1FanoutData(
            sch_b_interest_additions=(),
            sch_b_dividend_additions=(),
            sch_d_short_term_additions=(),
            sch_d_long_term_additions=(),
            qbi_aggregate=0.0,
            qualified_dividends_aggregate=k1_qual,
            passive_activities=(),
        )

    def test_total_is_1099div_plus_k1(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        # Give the scenario a 1099-DIV carrying qualified dividends.
        from tenforty.models import Form1099DIV
        s.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=8_000.0,
        )]
        pre = f1040_spine.compute_income_preamble(
            s, params, {}, k1_fanout=self._fanout(3_000.0),
        )
        self.assertEqual(pre.qualified_divs, 8_000)        # 1099-DIV component
        self.assertEqual(pre.qualified_divs_k1, 3_000)     # K-1 component
        self.assertEqual(pre.qualified_divs_total, 11_000) # the authoritative total

    def test_total_equals_1099div_when_no_k1(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        from tenforty.models import Form1099DIV
        s.form1099_div = [Form1099DIV(
            payer="Generic Brokerage",
            ordinary_dividends=9_000.0,
            qualified_dividends=8_000.0,
        )]
        pre = f1040_spine.compute_income_preamble(s, params, {})
        self.assertEqual(pre.qualified_divs_k1, 0)
        self.assertEqual(pre.qualified_divs_total, 8_000)

    def test_total_equals_k1_when_no_1099div(self):
        s = make_simple_scenario()
        params = load_federal_params(2025)
        s.form1099_div = []
        pre = f1040_spine.compute_income_preamble(
            s, params, {}, k1_fanout=self._fanout(3_000.0),
        )
        self.assertEqual(pre.qualified_divs, 0)
        self.assertEqual(pre.qualified_divs_total, 3_000)
