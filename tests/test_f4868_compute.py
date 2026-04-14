import unittest
from types import SimpleNamespace

from tenforty.forms.f4868 import compute, compute_balance_due


def _scenario(**overrides):
    config = SimpleNamespace(
        first_name="Ada",
        last_name="Lovelace",
        ssn="000-45-6789",
        spouse_ssn="",
        address="1 Analytical Engine Way",
        address_city="London",
        address_state="",
        address_zip="",
        **overrides,
    )
    return SimpleNamespace(config=config)


class ComputeBalanceDueTests(unittest.TestCase):
    def test_positive_balance_due(self):
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=3000), 2000)

    def test_zero_when_overpaid(self):
        # Refund case: 4868 always reports 0, never a negative balance due.
        self.assertEqual(compute_balance_due(total_tax=3000, total_payments=5000), 0)

    def test_zero_when_exactly_matched(self):
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=5000), 0)

    def test_handles_none_total_payments(self):
        # Engine may return None for 1099/other withholding fields.
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=None), 5000)


class F4868ComputeTests(unittest.TestCase):
    def test_produces_pdf_ready_keys(self):
        scenario = _scenario()
        upstream = {"f1040": {"total_tax": 5000, "total_payments": 3000}}
        result = compute(scenario, upstream)
        self.assertEqual(result["full_name"], "Ada Lovelace")
        self.assertEqual(result["ssn"], "000-45-6789")
        self.assertEqual(result["spouse_ssn"], "")
        self.assertEqual(result["address"], "1 Analytical Engine Way")
        self.assertEqual(result["address_city"], "London")
        self.assertEqual(result["address_state"], "")
        self.assertEqual(result["address_zip"], "")
        self.assertEqual(result["estimated_total_tax"], 5000)
        self.assertEqual(result["total_payments"], 3000)
        self.assertEqual(result["balance_due"], 2000)
        self.assertEqual(result["amount_paying_with_extension"], 0)
        self.assertEqual(result["voucher_amount"], 2000)

    def test_refund_case_zeroes_balance(self):
        scenario = _scenario()
        upstream = {"f1040": {"total_tax": 3000, "total_payments": 5000}}
        result = compute(scenario, upstream)
        self.assertEqual(result["balance_due"], 0)
        self.assertEqual(result["voucher_amount"], 0)
