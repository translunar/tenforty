"""Form 8995 simple-QBI compute tests."""

import unittest

from tenforty.forms import f8995
from tenforty.models import ScheduleK1

from tests.helpers import make_k1_scenario


def _scenario_with_qbi(qbi: float = 20_000.0, taxable_income: float = 100_000.0,
                       net_cap_gain: float = 0.0):
    s = make_k1_scenario()
    s.schedule_k1s = [ScheduleK1(
        entity_name="Fake S-Corp Inc",
        entity_ein="00-0000000",
        entity_type="s_corp",
        material_participation=True,
        qbi_amount=qbi,
    )]
    upstream = {
        "f1040": {
            "taxable_income_before_qbi_deduction": taxable_income,
            "net_capital_gain": net_cap_gain,
        },
        "_k1_fanout": {
            "qbi_total": qbi,
            "qualified_dividends_total": 0.0,
        },
    }
    return s, upstream


class F8995SimpleTests(unittest.TestCase):
    def test_below_threshold_basic(self):
        s, upstream = _scenario_with_qbi()
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_1_qbi"], 20_000)
        self.assertEqual(out["f8995_line_3_component"], 4_000)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 4_000)

    def test_income_limit_binds(self):
        s, upstream = _scenario_with_qbi(
            qbi=100_000.0, taxable_income=50_000.0, net_cap_gain=10_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        # line_13 = 50_000 - 10_000 = 40_000
        # line_14 = 0.20 * 40_000 = 8_000
        # line_6  = 0.20 * 100_000 = 20_000
        # line_15 = min(20_000, 8_000) = 8_000
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 8_000)


class F8995ThresholdGateTests(unittest.TestCase):
    def test_above_threshold_with_qbi_raises(self):
        s, upstream = _scenario_with_qbi(
            qbi=20_000.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        with self.assertRaisesRegex(
            NotImplementedError, "acknowledges_qbi_below_threshold"
        ):
            f8995.compute(s, upstream=upstream)

    def test_above_threshold_with_qbi_ok_when_attestation_true(self):
        s, upstream = _scenario_with_qbi(
            qbi=20_000.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = True
        out = f8995.compute(s, upstream=upstream)
        self.assertIn("f8995_line_15_qbi_deduction", out)

    def test_above_threshold_but_no_qbi_never_raises(self):
        """High-earner return with no QBI — the 8995-A scope gate must
        not fire, because there is no QBI to deduct at all."""
        s, upstream = _scenario_with_qbi(
            qbi=0.0, taxable_income=250_000.0,
        )
        s.config.acknowledges_qbi_below_threshold = False
        out = f8995.compute(s, upstream=upstream)
        self.assertEqual(out["f8995_line_15_qbi_deduction"], 0)


if __name__ == "__main__":
    unittest.main()
