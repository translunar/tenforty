import unittest
from scripts.reconcile_ca540 import reconcile


class ReconcileCA540Tests(unittest.TestCase):
    def test_flags_match_and_difference(self):
        recomputed = {"f540_taxable_income": 100, "f540_total_liability": 18}
        filed = {"f540_taxable_income": 100, "f540_total_liability": 22}
        report = reconcile(recomputed, filed,
                           keys=("f540_taxable_income", "f540_total_liability"))
        by_key = {r["key"]: r for r in report}
        self.assertEqual(by_key["f540_taxable_income"]["flag"], "match")
        self.assertEqual(by_key["f540_total_liability"]["flag"], "recompute-differs")
        self.assertEqual(by_key["f540_total_liability"]["delta"], -4)

    def test_missing_key_treated_as_zero(self):
        """Missing keys on either side are treated as 0."""
        recomputed = {"f540_taxable_income": 50}
        filed = {"f540_total_liability": 10}
        report = reconcile(recomputed, filed,
                           keys=("f540_taxable_income", "f540_total_liability"))
        by_key = {r["key"]: r for r in report}
        # recomputed has it, filed doesn't -> delta = 50 - 0 = 50
        self.assertEqual(by_key["f540_taxable_income"]["recomputed"], 50)
        self.assertEqual(by_key["f540_taxable_income"]["filed"], None)
        self.assertEqual(by_key["f540_taxable_income"]["delta"], 50)
        # filed has it, recomputed doesn't -> delta = 0 - 10 = -10
        self.assertEqual(by_key["f540_total_liability"]["recomputed"], None)
        self.assertEqual(by_key["f540_total_liability"]["filed"], 10)
        self.assertEqual(by_key["f540_total_liability"]["delta"], -10)

    def test_row_structure(self):
        """Each row contains key, recomputed, filed, delta, flag."""
        recomputed = {"f540_tax_before_credit": 25}
        filed = {"f540_tax_before_credit": 25}
        report = reconcile(recomputed, filed,
                           keys=("f540_tax_before_credit",))
        self.assertEqual(len(report), 1)
        row = report[0]
        self.assertIn("key", row)
        self.assertIn("recomputed", row)
        self.assertIn("filed", row)
        self.assertIn("delta", row)
        self.assertIn("flag", row)
        self.assertEqual(row["key"], "f540_tax_before_credit")
