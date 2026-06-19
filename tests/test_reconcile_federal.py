import unittest
from scripts.reconcile_federal import reconcile


class ReconcileTests(unittest.TestCase):
    def test_flags_differences_and_matches(self):
        recomputed = {"taxable_income": 100, "total_tax": 18}
        prior = {"taxable_income": 100, "total_tax": 20}
        report = reconcile(recomputed, prior, keys=("taxable_income", "total_tax"))
        by_key = {r["key"]: r for r in report}
        self.assertEqual(by_key["taxable_income"]["flag"], "match")
        self.assertEqual(by_key["total_tax"]["flag"], "recompute-differs")
        self.assertEqual(by_key["total_tax"]["delta"], -2)
