"""Schedule D line 21 is loss-only (team-lead ruling, sch_d-declaration lane
phase 2): its key is emitted only when line 16 is a loss and is ABSENT on a
gain or zero (the form: "If line 16 is a loss, enter here"; line 21 is not
used otherwise). Its one production consumer, the 1040 income preamble,
reads it strictly in a loss year and takes the gain figure (line 16)
explicitly otherwise; no default papers over a missing key.
"""
import unittest

from tenforty.forms.f1040_spine import compute_income_preamble
from tenforty.params.federal import load as load_federal_params

from tests.helpers import make_simple_scenario


def _preamble(sch_d):
    scenario = make_simple_scenario()
    return compute_income_preamble(
        scenario, load_federal_params(scenario.config.year), {"sch_d": sch_d})


class LineTwentyOneConsumerTests(unittest.TestCase):
    def test_a_gain_year_takes_line_16_with_no_line_21_key(self):
        preamble = _preamble({"sch_d_line_16_total": 2_500})
        self.assertEqual(preamble.schd_line21_allowed, 2_500)

    def test_a_loss_year_reads_line_21(self):
        preamble = _preamble({"sch_d_line_16_total": -8_000,
                              "sch_d_line_21_allowed_loss": -3_000})
        self.assertEqual(preamble.schd_line21_allowed, -3_000)

    def test_a_loss_year_without_line_21_raises(self):
        # Strict: a loss with no allowed-loss figure is a producer defect,
        # never a silent fallback to the uncapped line 16.
        with self.assertRaises(KeyError):
            _preamble({"sch_d_line_16_total": -8_000})


if __name__ == "__main__":
    unittest.main()
