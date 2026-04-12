"""Tests for the 4868 line-6 balance-due helper."""

import unittest

from tenforty.filing.balance_due import compute_balance_due


class TestComputeBalanceDue(unittest.TestCase):
    def test_positive_balance(self):
        self.assertEqual(compute_balance_due(10000, 7000), 3000)

    def test_exact_zero(self):
        self.assertEqual(compute_balance_due(10000, 10000), 0)

    def test_refund_floored_to_zero(self):
        # Overpayment — balance due cannot be negative
        self.assertEqual(compute_balance_due(7000, 10000), 0)

    def test_fractional_rounds_to_int(self):
        # 100.6 - 0 = 100.6, rounds to 101
        self.assertEqual(compute_balance_due(100.6, 0), 101)

    def test_fractional_rounds_down(self):
        # 100.4 - 0 = 100.4, rounds to 100
        self.assertEqual(compute_balance_due(100.4, 0), 100)

    def test_result_is_int(self):
        result = compute_balance_due(5000.0, 2000.0)
        self.assertIsInstance(result, int)


if __name__ == "__main__":
    unittest.main()
