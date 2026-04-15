import unittest

from tenforty.rounding import irs_round, round4, round5


class IrsRoundTests(unittest.TestCase):
    def test_below_half_rounds_down(self):
        self.assertEqual(irs_round(20.49), 20)
        self.assertEqual(irs_round(20.01), 20)

    def test_half_rounds_up(self):
        self.assertEqual(irs_round(20.50), 21)
        self.assertEqual(irs_round(21.50), 22)
        self.assertEqual(irs_round(0.5), 1)
        self.assertEqual(irs_round(1.5), 2)

    def test_above_half_rounds_up(self):
        self.assertEqual(irs_round(20.99), 21)
        self.assertEqual(irs_round(20.51), 21)

    def test_whole_numbers_pass_through(self):
        self.assertEqual(irs_round(20), 20)
        self.assertEqual(irs_round(0), 0)

    def test_negative_half_rounds_away_from_zero(self):
        # IRS rule for negatives is uncommon (1040 amounts are usually non-negative),
        # but keep "half away from zero" symmetry so callers can rely on it.
        self.assertEqual(irs_round(-20.5), -21)
        self.assertEqual(irs_round(-20.49), -20)

    def test_accepts_int_input(self):
        self.assertEqual(irs_round(15000), 15000)


class Round4Tests(unittest.TestCase):
    def test_below_half_rounds_down(self):
        self.assertEqual(round4(0.12344), 0.1234)

    def test_half_rounds_up(self):
        self.assertEqual(round4(0.12345), 0.1235)

    def test_above_half_rounds_up(self):
        self.assertEqual(round4(0.12346), 0.1235)

    def test_negative_half_rounds_away_from_zero(self):
        self.assertEqual(round4(-0.12345), -0.1235)

    def test_whole_number_passes_through(self):
        self.assertEqual(round4(1.0), 1.0)


class Round5Tests(unittest.TestCase):
    def test_below_half_rounds_down(self):
        self.assertEqual(round5(0.123454), 0.12345)

    def test_half_rounds_up(self):
        self.assertEqual(round5(0.123455), 0.12346)

    def test_above_half_rounds_up(self):
        self.assertEqual(round5(0.123456), 0.12346)

    def test_negative_half_rounds_away_from_zero(self):
        self.assertEqual(round5(-0.123455), -0.12346)
