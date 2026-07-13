import unittest

from tenforty.orchestrator import _split_ownership_percent


class TestSplitOwnershipPercent(unittest.TestCase):
    """Schedule K-1 (100S) Item A allocation-% is printed as two AcroForm
    boxes: "<whole>.<frac>%" where frac is always a two-digit 00-99 value.
    Float truncation in the old implementation could push frac to "100"
    (e.g. 29% -> ("28", "100") -> "28.100%"), which is not a valid rendering
    of the field. These cases pin the correct two-decimal-precision split.
    """

    def test_known_fractions(self):
        cases = [
            (0.29, ("29", "00")),
            (0.58, ("58", "00")),
            (0.3333, ("33", "33")),
            (0.99999, ("100", "00")),
            (0.125, ("12", "50")),
            (1.0, ("100", "00")),
            (0.6, ("60", "00")),
        ]
        for fraction, expected in cases:
            with self.subTest(fraction=fraction):
                self.assertEqual(_split_ownership_percent(fraction), expected)

    def test_frac_box_never_reaches_100(self):
        """Invariant: for every fraction from 0.00 to 1.00 in steps of 0.01,
        the fractional box must be strictly less than 100 (i.e. a valid
        two-digit 00-99 value), never "100" or higher."""
        for i in range(101):
            fraction = i / 100
            with self.subTest(fraction=fraction):
                _whole, frac = _split_ownership_percent(fraction)
                frac_int = int(frac)
                self.assertGreaterEqual(frac_int, 0)
                self.assertLessEqual(frac_int, 99)


if __name__ == "__main__":
    unittest.main()
