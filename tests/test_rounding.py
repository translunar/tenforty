import unittest

from tenforty.rounding import irs_round


class TestIrsRound(unittest.TestCase):
    def test_below_half_rounds_down(self):
        self.assertEqual(irs_round(20.49), 20)
        self.assertEqual(irs_round(20.01), 20)

    def test_half_rounds_up(self):
        self.assertEqual(irs_round(20.50), 21)
        self.assertEqual(irs_round(21.50), 22)  # banker's would give 22 too
        self.assertEqual(irs_round(20.5), 21)   # banker's would give 20

    def test_above_half_rounds_up(self):
        self.assertEqual(irs_round(20.99), 21)
        self.assertEqual(irs_round(20.51), 21)

    def test_whole_numbers_pass_through(self):
        self.assertEqual(irs_round(20), 20)
        self.assertEqual(irs_round(0), 0)

    def test_negative_half_rounds_away_from_zero(self):
        # IRS rule for negatives is less common (usually only non-negatives
        # appear on the 1040), but keep the "half away from zero" symmetry.
        self.assertEqual(irs_round(-20.5), -21)
        self.assertEqual(irs_round(-20.49), -20)

    def test_accepts_int_input(self):
        self.assertEqual(irs_round(15000), 15000)
