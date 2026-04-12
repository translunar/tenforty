"""Unit tests for the CLI deduction-analysis output block."""

import io
import unittest

from tenforty.__main__ import _which_applied, print_results


class TestWhichApplied(unittest.TestCase):
    def test_standard_applied_when_standard_wins(self):
        self.assertEqual(_which_applied(31500, 24000, 31500), "standard applied")

    def test_itemized_applied_when_itemized_wins(self):
        self.assertEqual(_which_applied(15750, 24000, 24000), "itemized applied")

    def test_standard_applied_when_no_schedule_a(self):
        self.assertEqual(_which_applied(15750, 0, 15750), "standard applied")

    def test_indeterminate_when_applied_matches_neither(self):
        self.assertEqual(_which_applied(15750, 24000, 9999), "indeterminate")

    def test_tie_reports_standard(self):
        # If standard == schedule_a, report standard (it's the default path).
        self.assertEqual(_which_applied(20000, 20000, 20000), "standard applied")


class TestPrintResultsDeductionBlock(unittest.TestCase):
    def _format(self, results: dict) -> str:
        buf = io.StringIO()
        print_results(results, stream=buf)
        return buf.getvalue()

    def test_deduction_analysis_always_present(self):
        output = self._format({
            "standard_deduction": 15750,
            "schedule_a_total": 0,
            "total_deductions": 15750,
        })
        self.assertIn("=== Deduction Analysis ===", output)
        self.assertIn("standard_deduction", output)
        self.assertIn("schedule_a_total", output)
        self.assertIn("total_deductions", output)

    def test_zero_schedule_a_still_printed(self):
        """The always-print rule: zero schedule_a must still appear so the
        user sees both amounts were considered."""
        output = self._format({
            "standard_deduction": 15750,
            "schedule_a_total": 0,
            "total_deductions": 15750,
        })
        # The schedule_a_total line must exist with a formatted 0 value.
        self.assertRegex(output, r"schedule_a_total\s+\$\s+0")

    def test_standard_applied_label_rendered(self):
        output = self._format({
            "standard_deduction": 31500,
            "schedule_a_total": 24000,
            "total_deductions": 31500,
        })
        self.assertIn("(standard applied)", output)

    def test_itemized_applied_label_rendered(self):
        output = self._format({
            "standard_deduction": 15750,
            "schedule_a_total": 24000,
            "total_deductions": 24000,
        })
        self.assertIn("(itemized applied)", output)

    def test_missing_keys_treated_as_zero(self):
        """Defensive: a results dict missing a deduction key should render
        as 0, not crash."""
        output = self._format({})
        self.assertIn("=== Deduction Analysis ===", output)
        self.assertRegex(output, r"standard_deduction\s+\$\s+0")
        self.assertRegex(output, r"schedule_a_total\s+\$\s+0")
        self.assertRegex(output, r"total_deductions\s+\$\s+0")


if __name__ == "__main__":
    unittest.main()
