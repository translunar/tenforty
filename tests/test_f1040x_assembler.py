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
        # Nonzero estimated_tax_payments, SAME on both filed and corrected —
        # the null-self-amendment property (byte-identical filed/corrected ->
        # every _b == 0) must survive the line-13 sourcing.
        filed = self._filed(estimated_tax_payments=800.0)
        corrected = dict(filed)
        # Filer already received the original 150 overpayment as a refund.
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        for key, value in out.items():
            if key.endswith("_b"):
                self.assertEqual(value, 0, msg=f"{key} should be 0 in null case")

        self.assertEqual(out["f1040x_line13_b"], 0)
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

    def test_federal_overpaid_key_mismatch_refuses(self):
        # Filed carries an original overpayment of 500, but the case claims the
        # filer received/applied 1000 — contradictory snapshots. Refuse.
        filed = self._filed(overpaid=500.0)
        corrected = self._filed(overpaid=500.0)
        case = self._case(
            original_refund_received=1000.0, original_refund_applied=0.0
        )
        with self.assertRaises(ValueError) as ctx:
            assemble(filed, corrected, case)
        msg = str(ctx.exception)
        self.assertIn("1000", msg)  # stated case overpayment
        self.assertIn("500", msg)  # filed original overpayment

    def test_federal_overpaid_key_match_passes(self):
        # Filed original overpayment 500; case received+applied == 500.
        filed = self._filed(overpaid=500.0)
        corrected = self._filed(overpaid=500.0)
        case = self._case(
            original_refund_received=500.0, original_refund_applied=0.0
        )
        out = assemble(filed, corrected, case)
        self.assertEqual(out["f1040x_line18_overpayment_on_original"], 500)

    def test_federal_overpaid_key_absent_no_check(self):
        # No "overpaid" key -> the if-present guard does not fire; existing
        # behavior (no consistency check) is preserved.
        filed = self._filed()
        corrected = self._filed()
        self.assertNotIn("overpaid", filed)
        case = self._case(
            original_refund_received=999.0, original_refund_applied=0.0
        )
        out = assemble(filed, corrected, case)
        self.assertEqual(out["f1040x_line18_overpayment_on_original"], 999)

    def test_no_sch2_regression_pin_line11_equals_total_tax(self):
        """BINDING regression pin: with neither f8962_repayment nor
        f8959_tax_total (nor nonrefundable_credits) present in either column,
        L11 must be BYTE-IDENTICAL to the old direct-total_tax sourcing."""
        filed = self._filed()
        corrected = self._filed(agi=1200.0, total_tax=150.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line11_a"], filed["total_tax"])
        self.assertEqual(out["f1040x_line11_c"], corrected["total_tax"])
        self.assertEqual(
            out["f1040x_line11_b"], corrected["total_tax"] - filed["total_tax"]
        )

    def test_sch2_components_source_lines_6_8_10_11(self):
        filed = self._filed(f8962_repayment=40.0, f8959_tax_total=10.0)
        corrected = self._filed(
            total_tax=150.0, f8962_repayment=60.0, f8959_tax_total=20.0
        )
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        for line in ("6", "7", "8", "10", "11"):
            a = out[f"f1040x_line{line}_a"]
            b = out[f"f1040x_line{line}_b"]
            c = out[f"f1040x_line{line}_c"]
            self.assertEqual(a + b, c, msg=f"line {line}: {a} + {b} != {c}")

        self.assertEqual(out["f1040x_line6_a"], filed["total_tax"] + 40.0)
        self.assertEqual(out["f1040x_line6_c"], corrected["total_tax"] + 60.0)
        self.assertEqual(out["f1040x_line10_a"], 10.0)
        self.assertEqual(out["f1040x_line10_c"], 20.0)
        self.assertEqual(
            out["f1040x_line8_a"], out["f1040x_line6_a"] - out["f1040x_line7_a"]
        )
        self.assertEqual(
            out["f1040x_line8_c"], out["f1040x_line6_c"] - out["f1040x_line7_c"]
        )
        self.assertEqual(
            out["f1040x_line11_a"], out["f1040x_line8_a"] + out["f1040x_line10_a"]
        )
        self.assertEqual(
            out["f1040x_line11_c"], out["f1040x_line8_c"] + out["f1040x_line10_c"]
        )

    def test_tail_uses_computed_line11c_not_bare_total_tax(self):
        """The refund/owed tail must key off the COMPUTED L11c (L8+L10), not a
        bare corrected["total_tax"] — otherwise a corrected f8962_repayment
        would silently vanish from the amount-owed/refund figures."""
        filed = self._filed()  # total_tax 100, total_payments 250
        corrected = self._filed(f8962_repayment=60.0)  # total_tax still 100
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        # L11c = total_tax(100) + f8962_repayment(60) - 0(L7) + 0(L10) = 160
        self.assertEqual(out["f1040x_line11_c"], 160)
        # L17=250, L18=150, L19=100, L11c=160 > 100 -> owe 60
        self.assertEqual(out["f1040x_line20_amount_owed"], 60)
        self.assertEqual(out["f1040x_line22_refund"], 0)

    def test_line13_estimated_tax_payments_sourced(self):
        """Line 13 is now SOURCED as an A/B/C triple keyed off
        ``estimated_tax_payments`` on BOTH filed and corrected (same key,
        both columns) — independently-derived numbers, no tautologies."""
        filed = self._filed(estimated_tax_payments=2000.0)
        corrected = self._filed(estimated_tax_payments=5000.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line13_a"], 2000.0)
        self.assertEqual(out["f1040x_line13_c"], 5000.0)
        self.assertEqual(out["f1040x_line13_b"], 3000.0)

    def test_line13_absent_defaults_to_zero(self):
        """OPTIONAL key: absent from both filed and corrected -> 0.0/0.0/0.0
        (the ``.get(..., 0.0)`` default), not a MissingFiledValueError."""
        filed = self._filed()
        corrected = self._filed(agi=1200.0, total_tax=150.0)
        self.assertNotIn("estimated_tax_payments", filed)
        self.assertNotIn("estimated_tax_payments", corrected)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line13_a"], 0.0)
        self.assertEqual(out["f1040x_line13_b"], 0.0)
        self.assertEqual(out["f1040x_line13_c"], 0.0)

    def test_line13_column_a_defaults_to_corrected_when_filed_silent(self):
        """When the amendment does not change estimated payments, a (legacy)
        filed dict may omit the key while the corrected run carries it. Column
        A must then equal Column C (B == 0) — estimated payments are a fixed
        as-filed input, not a computed line. Regression guard for the defect
        where A defaulted to 0.0 and the whole amount spilled into Column B."""
        filed = self._filed()  # no estimated_tax_payments key
        corrected = self._filed(estimated_tax_payments=4000.0)
        self.assertNotIn("estimated_tax_payments", filed)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line13_a"], 4000.0)
        self.assertEqual(out["f1040x_line13_c"], 4000.0)
        self.assertEqual(out["f1040x_line13_b"], 0.0)

    def test_line15_sources_refundable_credits_not_total_payments(self):
        """Line 15 is 'Total refundable credits' — tenforty's one modeled
        component is net premium tax credit (f8962_net_ptc). It must NOT be
        sourced from total_payments (the line-17 quantity); that duplicate
        mislabel broke line 17's printed 'add lines 12-15, col C' footing."""
        filed = self._filed(f8962_net_ptc=0.0)
        corrected = self._filed(f8962_net_ptc=700.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line15_a"], 0.0)
        self.assertEqual(out["f1040x_line15_c"], 700.0)
        # Not the total_payments (250) that the buggy code emitted here.
        self.assertNotEqual(out["f1040x_line15_c"], filed["total_payments"])

    def test_line15_zero_when_no_net_ptc(self):
        """No 1095-A -> net PTC 0 -> line 15 is 0/0/0 (the observed all-years
        emit), never the total_payments duplicate."""
        filed = self._filed()
        corrected = self._filed(agi=1200.0, total_tax=150.0)
        case = self._case(original_refund_received=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line15_a"], 0.0)
        self.assertEqual(out["f1040x_line15_b"], 0.0)
        self.assertEqual(out["f1040x_line15_c"], 0.0)

    def test_line17_foots_over_payments_grid_column_c(self):
        """Line 17 (total payments) must equal 12c + 13c + 14c + 15c (+ line
        16, 0 here: refund-year original) — the form's printed arithmetic. With line 15 sourced
        from net PTC (not a duplicate of total_payments), the chain foots."""
        corrected = self._filed(
            federal_withheld=3000.0,
            estimated_tax_payments=1000.0,
            f8962_net_ptc=200.0,
            total_payments=4200.0,  # 3000 + 1000 + 200
            total_tax=100.0,
        )
        filed = self._filed(total_payments=4200.0)
        case = self._case(original_refund_received=4100.0)
        out = assemble(filed, corrected, case)

        grid_c = (
            out["f1040x_line12_c"]
            + out["f1040x_line13_c"]
            + out.get("f1040x_line14_c", 0)
            + out["f1040x_line15_c"]
        )
        self.assertEqual(grid_c, out["f1040x_line17"])

    # ----- Line 16: tax paid with extension / original return / after filing

    def test_line16_refund_year_unstated_stays_zero(self):
        """Filed return was OVERPAID and the case does not state
        original_tax_paid: line 16 is silently 0 and the tail is unchanged."""
        filed = self._filed()  # total_tax 100, payments 250 -> overpaid 150
        corrected = self._filed(total_tax=200.0)
        case = self._case(original_refund_received=150.0)
        self.assertIsNone(case.original_tax_paid)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line16"], 0)
        self.assertEqual(out["f1040x_line17"], 250)
        self.assertEqual(out["f1040x_line19"], 100)
        self.assertEqual(out["f1040x_line20_amount_owed"], 100)
        self.assertEqual(out["f1040x_line22_refund"], 0)

    def test_line16_filed_exactly_even_unstated_stays_zero(self):
        """Filed liability == filed payments: no balance due, no refusal."""
        filed = self._filed(total_tax=250.0)  # payments 250 -> even
        corrected = self._filed(total_tax=300.0)
        out = assemble(filed, corrected, self._case())

        self.assertEqual(out["f1040x_line16"], 0)
        self.assertEqual(out["f1040x_line20_amount_owed"], 50)

    def test_line16_balance_due_filed_unstated_refuses(self):
        """Filed return had a balance due and the case does not say what was
        paid: refuse, naming the field and the filed balance due."""
        filed = self._filed(total_tax=400.0)  # payments 250 -> balance due 150
        corrected = self._filed(total_tax=500.0)
        with self.assertRaises(ValueError) as ctx:
            assemble(filed, corrected, self._case())
        msg = str(ctx.exception)
        self.assertIn("original_tax_paid", msg)
        self.assertIn("150", msg)
        self.assertIn("line 16", msg)

    def test_line16_balance_due_detected_on_line11_not_bare_total_tax(self):
        """The filed balance due is measured on the Column-A line 11 total
        (tax + other taxes), not bare total_tax: total_tax 200 alone is under
        payments 250, but SE tax 100 makes the filed liability 300."""
        filed = self._filed(total_tax=200.0, sch_se_line_12_se_tax=100.0)
        corrected = self._filed(total_tax=260.0, sch_se_line_12_se_tax=100.0)
        with self.assertRaises(ValueError) as ctx:
            assemble(filed, corrected, self._case())
        msg = str(ctx.exception)
        self.assertIn("original_tax_paid", msg)
        self.assertIn("balance due of 50", msg)

    def test_line16_balance_due_stated_flows_through_tail(self):
        """Balance-due original, payment stated: L16 -> L17 -> L19 -> L20."""
        filed = self._filed(total_tax=400.0)  # balance due 150, paid in full
        corrected = self._filed(total_tax=500.0)
        case = self._case(original_tax_paid=150.0)
        out = assemble(filed, corrected, case)

        self.assertEqual(out["f1040x_line16"], 150)
        self.assertEqual(out["f1040x_line17"], 400)   # 250 + 150
        self.assertEqual(out["f1040x_line18"], 0)
        self.assertEqual(out["f1040x_line19"], 400)   # 400 - 0
        self.assertEqual(out["f1040x_line20_amount_owed"], 100)  # 500 - 400
        self.assertEqual(out["f1040x_line21"], 0)
        self.assertEqual(out["f1040x_line22_refund"], 0)
        # Net invariant: L20 - L22 == (corrected L11 - corrected payments)
        #                            - (filed L11 - filed payments)
        self.assertEqual(
            out["f1040x_line20"] - out["f1040x_line22"],
            (500 - 250) - (400 - 250),
        )

    def test_line16_stated_payment_can_produce_refund(self):
        """Paid 150 with the original; the amendment lowers tax below what
        was paid in total -> the excess comes back on line 22."""
        filed = self._filed(total_tax=400.0)
        corrected = self._filed(total_tax=300.0)
        out = assemble(filed, corrected, self._case(original_tax_paid=150.0))

        self.assertEqual(out["f1040x_line17"], 400)
        self.assertEqual(out["f1040x_line20_amount_owed"], 0)
        self.assertEqual(out["f1040x_line22_refund"], 100)

    def test_line16_stated_zero_accepted_never_paid(self):
        """Balance-due original the filer never paid: stating 0 is an
        accepted assertion, and line 20 is what it was before line 16 was
        sourced (corrected L11 500 - payments 250)."""
        filed = self._filed(total_tax=400.0)
        corrected = self._filed(total_tax=500.0)
        out = assemble(filed, corrected, self._case(original_tax_paid=0.0))

        self.assertEqual(out["f1040x_line16"], 0)
        self.assertEqual(out["f1040x_line17"], 250)
        self.assertEqual(out["f1040x_line19"], 250)
        self.assertEqual(out["f1040x_line20_amount_owed"], 250)
        self.assertEqual(out["f1040x_line22_refund"], 0)

    def test_line16_negative_stated_refuses(self):
        filed = self._filed(total_tax=400.0)
        corrected = self._filed(total_tax=500.0)
        with self.assertRaises(ValueError) as ctx:
            assemble(filed, corrected, self._case(original_tax_paid=-1.0))
        self.assertIn("original_tax_paid", str(ctx.exception))

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
