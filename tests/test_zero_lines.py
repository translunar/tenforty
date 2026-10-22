"""Unit tests for the always-zero line check (tenforty/verification/
zero_lines.py, [R-ZL-1] option 2). Synthetic records over a real
declaration (Schedule B 2024, whose line 3 is a value-only line); the
battery-wide check itself runs in tests/test_emit_declarations.py."""
import unittest
from pathlib import Path

from tenforty.verification import zero_lines
from tenforty.verification.record import RecordedForm

LINE_3 = ("federal/sch_b", "3")


def _record(**values):
    return ("synthetic/row/2024", RecordedForm(
        form=("federal", "sch_b"), key=2024, copy_id=None,
        values=values, spec=None, pdf_path=Path("unused.pdf")))


class AlwaysZeroLinesTests(unittest.TestCase):

    def test_a_line_zero_in_every_record_is_always_zero(self):
        recs = [_record(excludable_savings_bond=0),
                _record(excludable_savings_bond=0.0)]
        self.assertEqual(zero_lines.always_zero_lines(recs)[LINE_3], 2)

    def test_one_nonzero_record_clears_the_line(self):
        recs = [_record(excludable_savings_bond=0),
                _record(excludable_savings_bond=12)]
        self.assertNotIn(LINE_3, zero_lines.always_zero_lines(recs))

    def test_absent_values_are_not_observations(self):
        recs = [_record(), _record(excludable_savings_bond=None)]
        self.assertNotIn(LINE_3, zero_lines.always_zero_lines(recs))

    def test_a_non_numeric_value_is_not_judged(self):
        recs = [_record(excludable_savings_bond=0),
                _record(excludable_savings_bond="0")]
        self.assertNotIn(LINE_3, zero_lines.always_zero_lines(recs))

    def test_a_bool_is_not_a_number(self):
        recs = [_record(excludable_savings_bond=False)]
        self.assertNotIn(LINE_3, zero_lines.always_zero_lines(recs))

    def test_two_state_lines_are_outside_the_check(self):
        # Line 1's first amount row (interest_amount_1) is two-state.
        recs = [_record(excludable_savings_bond=5, interest_amount_1=0)]
        self.assertEqual(zero_lines.always_zero_lines(recs), {})


class FindingsTests(unittest.TestCase):

    RECS = [_record(excludable_savings_bond=0)]

    def test_unaccounted_line_is_a_finding(self):
        found = zero_lines.findings(self.RECS, attested={}, pending={})
        self.assertEqual(len(found), 1)
        self.assertIn("federal/sch_b line 3", found[0])

    def test_attested_line_is_not_a_finding(self):
        self.assertEqual(zero_lines.findings(
            self.RECS, attested={LINE_3: "reason"}, pending={}), [])

    def test_pending_line_is_not_a_finding(self):
        self.assertEqual(zero_lines.findings(
            self.RECS, attested={}, pending={LINE_3: "PENDING X"}), [])


class AllowlistShapeTests(unittest.TestCase):

    def test_attested_and_pending_are_disjoint(self):
        self.assertEqual(
            set(zero_lines.ATTESTED_ZERO) & set(zero_lines.PENDING), set())

    def test_every_pending_entry_names_its_blocker(self):
        for line, reason in zero_lines.PENDING.items():
            with self.subTest(line=line):
                self.assertTrue(reason.startswith("PENDING "), reason)

    def test_every_reason_cites_its_ruling_or_blocker(self):
        for line, reason in {**zero_lines.ATTESTED_ZERO,
                             **zero_lines.PENDING}.items():
            with self.subTest(line=line):
                self.assertRegex(reason, r"\[R-ZL-\d\]|Q-ZL1")


if __name__ == "__main__":
    unittest.main()
