import unittest

from tenforty.amendment import MissingFiledValueError, OutOfScopeAmendmentError
from tenforty.forms.f1040x import REQUIRED_FILED_KEYS, assemble
from tenforty.models import AmendmentCase


class F1040XAssemblerTests(unittest.TestCase):
    """Synthetic-dict tests for the Form 1040-X three-column assembler.

    Fixture numbers are arbitrary (agi 1000, deductions 250, tax 100, …),
    NOT real tax figures. The only internal-consistency constraint is that
    a filed return's original overpayment equals filed total_payments minus
    filed total_tax — the amendment case must reflect the refund the filer
    already received, or the null self-amendment would compute a phantom
    refund.
    """

    def _case(self, **kw):
        base = dict(
            year=2024,
            explanation="test",
            original_refund_received=0.0,
            original_refund_applied=0.0,
            prior_amendment_note=None,
        )
        base.update(kw)
        return AmendmentCase(**base)

    def _filed(self, **kw):
        # taxable_income = agi - total_deductions - qbi = 1000 - 250 - 0 = 750
        # overpaid = total_payments - total_tax = 250 - 100 = 150
        base = dict(
            agi=1000.0,
            total_deductions=250.0,
            _qbi_deduction_1040=0.0,
            taxable_income=750.0,
            total_tax=100.0,
            federal_withheld=250.0,
            total_payments=250.0,
        )
        base.update(kw)
        return base

    def _triples(self, out):
        """Yield (line, a, b, c) for every emitted three-column line."""
        for key in out:
            if key.endswith("_a"):
                stem = key[:-2]  # strip "_a"
                yield (
                    stem,
                    out[f"{stem}_a"],
                    out[f"{stem}_b"],
                    out[f"{stem}_c"],
                )

    def test_column_arithmetic_a_plus_b_equals_c(self):
        filed = self._filed()
        corrected = self._filed(agi=1200.0, total_tax=150.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        triples = list(self._triples(out))
        self.assertTrue(triples)  # something was emitted
        for stem, a, b, c in triples:
            self.assertEqual(a + b, c, msg=f"{stem}: {a} + {b} != {c}")

    def test_self_amendment_is_null(self):
        filed = self._filed()
        corrected = dict(filed)
        # Filer already received the original 150 overpayment as a refund.
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        for key, value in out.items():
            if key.endswith("_b"):
                self.assertEqual(value, 0, msg=f"{key} should be 0 in null case")

        self.assertEqual(out["f1040x_line20_amount_owed"], 0)
        self.assertEqual(out["f1040x_line22_refund"], 0)

    def test_owed_when_corrected_tax_exceeds_filed(self):
        filed = self._filed()  # total_tax 100, overpaid 150
        corrected = self._filed(total_tax=200.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        # L17=250, L18=150, L19=100, L11c=200 > 100 -> owe 100
        self.assertEqual(out["f1040x_line20_amount_owed"], 100)
        self.assertEqual(out["f1040x_line22_refund"], 0)

    def test_refund_when_corrected_tax_below_filed(self):
        filed = self._filed()  # total_tax 100, overpaid 150
        corrected = self._filed(total_tax=50.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        # L17=250, L18=150, L19=100, L11c=50 < 100 -> refund 50
        self.assertEqual(out["f1040x_line20_amount_owed"], 0)
        self.assertEqual(out["f1040x_line22_refund"], 50)

    def test_original_refund_reduces_line_18_correctly(self):
        filed = self._filed()
        corrected = dict(filed)
        # Original overpayment split: 100 refunded + 50 applied to estimates.
        case = self._case(
            original_refund_received=100.0, original_refund_applied=50.0
        )
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line18_overpayment_on_original"], 150)
        # L19 = L17 (250) - L18 (150) = 100
        self.assertEqual(out["f1040x_line19"], 100)

    def test_4a_qbi_delta(self):
        filed = self._filed()  # qbi 0
        corrected = self._filed(_qbi_deduction_1040=300.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line4a_a"], 0.0)
        self.assertEqual(out["f1040x_line4a_b"], 300.0)
        self.assertEqual(out["f1040x_line4a_c"], 300.0)

    def test_missing_filed_key_refuses(self):
        filed = self._filed()
        del filed["total_tax"]
        corrected = self._filed()
        case = self._case(original_refund_received=150.0)
        with self.assertRaises(MissingFiledValueError):
            assemble(filed, corrected, case)

    def test_nonzero_filed_eic_raises_out_of_scope(self):
        filed = self._filed(earned_income_credit=200.0)
        corrected = self._filed(earned_income_credit=200.0)
        case = self._case(original_refund_received=150.0)
        with self.assertRaises(OutOfScopeAmendmentError):
            assemble(filed, corrected, case)

    def test_nonzero_filed_schedule_1a_raises_out_of_scope(self):
        filed = self._filed(schedule_1a_deduction=500.0)
        corrected = self._filed(schedule_1a_deduction=500.0)
        case = self._case(original_refund_received=150.0)
        with self.assertRaises(OutOfScopeAmendmentError):
            assemble(filed, corrected, case)

    def test_required_filed_keys_are_the_column_a_sources(self):
        self.assertEqual(
            set(REQUIRED_FILED_KEYS),
            {
                "agi",
                "total_deductions",
                "_qbi_deduction_1040",
                "taxable_income",
                "total_tax",
                "federal_withheld",
                "total_payments",
            },
        )


if __name__ == "__main__":
    unittest.main()
