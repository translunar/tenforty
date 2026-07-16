import unittest

from tenforty.amendment import MissingFiledValueError, OutOfScopeAmendmentError
from tenforty.forms import f540
from tenforty.forms.schedule_x import REQUIRED_CA_FILED_KEYS, assemble_ca
from tenforty.models import AmendmentCase, CA540Return, FilingStatus


class ScheduleXAssemblerTests(unittest.TestCase):
    """Synthetic-dict tests for the CA Schedule X assembler.

    Schedule X is NOT a three-column A/B/C grid — it is a balance
    reconciliation (Part I lines 1-11). The invariant we assert is the
    net-liability-change identity: the amount-you-owe (L7) minus the
    refund (L11) equals corrected CA liability minus original CA
    liability. Fixture numbers are arbitrary (100/150/250/1000), NOT
    real tax figures.

    Consistency constraint (mirrors the federal null-case): the amendment
    case's original overpayment (received + applied) must equal the
    filed return's overpayment, or the null self-amendment would compute
    a phantom refund.
    """

    def _case(self, **kw):
        base = dict(
            year=2024,
            explanation="Correcting CA itemized deductions.",
            original_refund_received=0.0,
            original_refund_applied=0.0,
            prior_amendment_note=None,
            ca_original_refund_received=0.0,
            ca_original_refund_applied=0.0,
        )
        base.update(kw)
        return AmendmentCase(**base)

    def _filed(self, **kw):
        # f540_total_liability sign convention: positive = amount owed on
        # the original return (paid with it); negative = overpaid (refunded).
        base = dict(f540_total_liability=-150.0)  # original overpaid 150
        base.update(kw)
        return base

    def _corrected(self, **kw):
        base = dict(f540_total_liability=-150.0)
        base.update(kw)
        return base

    def test_on_form_arithmetic(self):
        filed = self._filed(f540_total_liability=-150.0)
        corrected = self._corrected(f540_total_liability=100.0)  # amended owes 100
        case = self._case(
            ca_original_refund_received=150.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)

        self.assertEqual(
            out["schedule_x_line3"],
            out["schedule_x_line1"] + out["schedule_x_line2"],
        )
        self.assertEqual(
            out["schedule_x_line6"],
            out["schedule_x_line4"] + out["schedule_x_line5"],
        )
        self.assertEqual(
            out["schedule_x_line8c"],
            out["schedule_x_line8a"] + out["schedule_x_line8b"],
        )
        self.assertEqual(
            out["schedule_x_line7"],
            max(0, out["schedule_x_line3"] - out["schedule_x_line6"]),
        )
        self.assertEqual(
            out["schedule_x_line9"],
            max(0, out["schedule_x_line6"] - out["schedule_x_line3"]),
        )
        self.assertEqual(
            out["schedule_x_line11"],
            out["schedule_x_line9"] - out["schedule_x_line10"],
        )

    def test_net_equals_liability_change_owed(self):
        filed = self._filed(f540_total_liability=-150.0)  # overpaid 150
        corrected = self._corrected(f540_total_liability=100.0)  # now owe 100
        case = self._case(ca_original_refund_received=150.0)
        out = assemble_ca(filed, corrected, case)

        net = out["schedule_x_line7"] - out["schedule_x_line11"]
        self.assertEqual(net, 100 - (-150))  # 250 additional owed
        self.assertEqual(out["schedule_x_line7_amount_owed"], 250)
        self.assertEqual(out["schedule_x_line11_refund"], 0)

    def test_net_equals_liability_change_refund(self):
        filed = self._filed(f540_total_liability=100.0)  # original owed/paid 100
        corrected = self._corrected(f540_total_liability=-50.0)  # amended overpaid 50
        case = self._case(
            ca_original_refund_received=0.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)

        net = out["schedule_x_line7"] - out["schedule_x_line11"]
        self.assertEqual(net, -50 - 100)  # -150 -> additional refund 150
        self.assertEqual(out["schedule_x_line7_amount_owed"], 0)
        self.assertEqual(out["schedule_x_line11_refund"], 150)

    def test_self_amendment_is_null(self):
        filed = self._filed(f540_total_liability=-150.0)
        corrected = self._corrected(f540_total_liability=-150.0)
        # Filer received the original 150 overpayment as a refund.
        case = self._case(
            ca_original_refund_received=150.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)

        self.assertEqual(out["schedule_x_line7"], 0)
        self.assertEqual(out["schedule_x_line9"], 0)
        self.assertEqual(out["schedule_x_line11"], 0)
        self.assertEqual(out["schedule_x_line7_amount_owed"], 0)
        self.assertEqual(out["schedule_x_line11_refund"], 0)

    def test_line2_is_received_plus_applied(self):
        filed = self._filed(f540_total_liability=-150.0)
        corrected = self._corrected(f540_total_liability=-150.0)
        # Original overpayment split: 100 refunded + 50 applied forward.
        case = self._case(
            ca_original_refund_received=100.0, ca_original_refund_applied=50.0
        )
        out = assemble_ca(filed, corrected, case)
        self.assertEqual(out["schedule_x_line2"], 150)

    def test_line5_is_original_tax_paid_from_filed(self):
        filed = self._filed(f540_total_liability=250.0)  # original owed 250
        corrected = self._corrected(f540_total_liability=250.0)
        case = self._case(
            ca_original_refund_received=0.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)
        self.assertEqual(out["schedule_x_line5"], 250)
        self.assertEqual(out["schedule_x_line2"], 0)

    def test_explanation_and_year_passthrough(self):
        filed = self._filed()
        corrected = self._corrected()
        case = self._case(
            explanation=" Corrected renter's credit.",
            year=2023,
            ca_original_refund_received=150.0,
        )
        out = assemble_ca(filed, corrected, case)
        self.assertEqual(out["schedule_x_explanation"], " Corrected renter's credit.")
        self.assertEqual(out["schedule_x_taxable_year"], 2023)

    def test_missing_ca_filed_key_refuses(self):
        filed = {}  # no f540_total_liability
        corrected = self._corrected()
        case = self._case(ca_original_refund_received=150.0)
        with self.assertRaises(MissingFiledValueError):
            assemble_ca(filed, corrected, case)

    def test_none_ca_case_field_refuses(self):
        filed = self._filed()
        corrected = self._corrected()
        case = self._case(ca_original_refund_received=None)
        with self.assertRaises(ValueError):
            assemble_ca(filed, corrected, case)

    def test_none_ca_applied_field_refuses(self):
        filed = self._filed()
        corrected = self._corrected()
        case = self._case(ca_original_refund_applied=None)
        with self.assertRaises(ValueError):
            assemble_ca(filed, corrected, case)

    def test_out_of_scope_nonzero_filed_line_raises(self):
        filed = self._filed(f540_other_state_tax_credit=200.0)
        corrected = self._corrected()
        case = self._case(ca_original_refund_received=150.0)
        with self.assertRaises(OutOfScopeAmendmentError):
            assemble_ca(filed, corrected, case)

    def test_required_ca_filed_keys(self):
        self.assertEqual(set(REQUIRED_CA_FILED_KEYS), {"f540_total_liability"})

    def test_ca_stated_overpayment_must_match_filed_refuses(self):
        # Filed original overpaid 200, but the case claims a 5000 overpayment —
        # they describe different as-filed snapshots. Refuse.
        filed = self._filed(f540_total_liability=-200.0)
        corrected = self._corrected(f540_total_liability=-200.0)
        case = self._case(
            ca_original_refund_received=5000.0, ca_original_refund_applied=0.0
        )
        with self.assertRaises(ValueError) as ctx:
            assemble_ca(filed, corrected, case)
        msg = str(ctx.exception)
        self.assertIn("5000", msg)  # stated case overpayment
        self.assertIn("200", msg)  # filed original overpayment

    def test_ca_stated_overpayment_matches_passes(self):
        # Filed original overpaid 200; case states exactly 200 -> consistent.
        filed = self._filed(f540_total_liability=-200.0)
        corrected = self._corrected(f540_total_liability=-200.0)
        case = self._case(
            ca_original_refund_received=200.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)
        self.assertEqual(out["schedule_x_line2"], 200)

    def test_ca_filed_owed_requires_zero_stated_overpayment(self):
        # Filed OWED (positive liability) -> filed original overpayment is 0,
        # so the stated overpayment must be exactly 0.
        filed = self._filed(f540_total_liability=500.0)
        corrected = self._corrected(f540_total_liability=500.0)
        ok_case = self._case(
            ca_original_refund_received=0.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, ok_case)
        self.assertEqual(out["schedule_x_line2"], 0)
        # A nonzero stated overpayment against a filed-owed return is refused.
        bad_case = self._case(
            ca_original_refund_received=300.0, ca_original_refund_applied=0.0
        )
        with self.assertRaises(ValueError):
            assemble_ca(filed, corrected, bad_case)

    # -- CA-withholding channel (WIRE-5): the now-retired f540_withholding
    # out-of-scope guard. -----------------------------------------------

    def _f540(self, ca_withholding):
        """Run the REAL production f540 compute (not a synthetic dict) so
        CA withholding actually flows through f540_line71_ca_withholding into
        f540_total_liability, the only key this assembler reconciles."""
        return f540.compute(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            federal_agi=150_000,
            ca_agi=150_000,
            ca540=CA540Return(),
            num_dependents=0,
            ca_withholding=ca_withholding,
        )

    def test_withholding_difference_flows_through_net(self):
        """Pin 1 (the important one): a filed/corrected pair that differ ONLY
        in CA W-2 withholding, computed via the REAL production f540.compute
        path (not synthetic dicts) so the withholding genuinely flows through
        f540_line71_ca_withholding -> f540_total_liability.

        This is the case the pre-2026-07-16 omission would have gotten wrong:
        with no withholding channel, filed and corrected f540_total_liability
        both landed on the SAME (withholding-blind) number, so the net would
        have wrongly computed to 0 even though the filer's actual withholding
        changed by $5,000. With the channel wired, the Schedule X net (L7 -
        L11) must move by exactly the withholding delta.
        """
        filed_f540 = self._f540(ca_withholding=4_000)
        corrected_f540 = self._f540(ca_withholding=9_000)

        filed = {"f540_total_liability": filed_f540["f540_total_liability"]}
        corrected = {
            "f540_total_liability": corrected_f540["f540_total_liability"]
        }
        # Same income both sides -> filed original overpayment is whatever
        # the filed run's total_liability implies; both runs here are OWED
        # (withholding well under the ~$9,705 base liability), so the case's
        # stated original overpayment is 0.
        self.assertGreaterEqual(filed["f540_total_liability"], 0)
        case = self._case(
            ca_original_refund_received=0.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)

        net = out["schedule_x_line7"] - out["schedule_x_line11"]
        withholding_delta = (
            filed_f540["f540_line71_ca_withholding"]
            - corrected_f540["f540_line71_ca_withholding"]
        )
        self.assertEqual(withholding_delta, 4_000 - 9_000)
        self.assertEqual(
            net,
            corrected["f540_total_liability"] - filed["f540_total_liability"],
        )
        self.assertEqual(net, withholding_delta)

    def test_withholding_cancels_when_equal_on_both_sides(self):
        """Filed and corrected carry the SAME CA withholding (a real amendment
        reason unrelated to withholding, e.g. a CA AGI correction) -> the
        withholding term is identical on both sides of f540_total_liability
        and cancels in the net; the net reflects only the non-withholding
        liability change."""
        same_withholding = 4_000
        filed_f540 = self._f540(ca_withholding=same_withholding)

        # Recompute with a lower CA AGI (the genuine amendment reason) but
        # the SAME withholding, via the real production path.
        corrected_f540 = f540.compute(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            federal_agi=150_000,
            ca_agi=120_000,
            ca540=CA540Return(),
            num_dependents=0,
            ca_withholding=same_withholding,
        )

        # Baseline (zero-withholding) runs isolate the non-withholding
        # liability change that the equal withholding should NOT disturb.
        filed_base = self._f540(ca_withholding=0)
        corrected_base = f540.compute(
            year=2025,
            filing_status=FilingStatus.SINGLE,
            federal_agi=150_000,
            ca_agi=120_000,
            ca540=CA540Return(),
            num_dependents=0,
            ca_withholding=0,
        )
        non_withholding_change = (
            corrected_base["f540_total_liability"]
            - filed_base["f540_total_liability"]
        )

        filed = {"f540_total_liability": filed_f540["f540_total_liability"]}
        corrected = {
            "f540_total_liability": corrected_f540["f540_total_liability"]
        }
        case = self._case(
            ca_original_refund_received=0.0, ca_original_refund_applied=0.0
        )
        out = assemble_ca(filed, corrected, case)

        net = out["schedule_x_line7"] - out["schedule_x_line11"]
        self.assertEqual(net, non_withholding_change)

    def test_f540_withholding_no_longer_out_of_scope(self):
        """NOW-RECONCILES (pin 3): ``f540_withholding`` in
        ``_OUT_OF_SCOPE_CA_FILED_KEYS`` was RETIRED 2026-07-16 (CA withholding
        now reconciles inside the required ``f540_total_liability`` key, via
        f540_line71_ca_withholding). A filed dict carrying a nonzero
        f540_withholding value must NOT raise OutOfScopeAmendmentError
        anymore — the extra key is simply accept-and-ignored (it plays no
        part in the reconciliation; the withholding is already inside
        f540_total_liability). Do not re-add the refusal from memory."""
        filed = self._filed(
            f540_total_liability=-150.0, f540_withholding=5_000.0
        )
        corrected = self._corrected(f540_total_liability=100.0)
        case = self._case(ca_original_refund_received=150.0)

        out = assemble_ca(filed, corrected, case)  # must NOT raise

        net = out["schedule_x_line7"] - out["schedule_x_line11"]
        self.assertEqual(net, 100 - (-150))


if __name__ == "__main__":
    unittest.main()
