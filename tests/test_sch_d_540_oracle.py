"""Unit tests for tests/oracles/sch_d_540_reference.py (CA FTB Schedule D (540)).

unittest.TestCase convention, imports at top, no silent fallthrough.
TDD discipline: each test-function is written and observed to fail before
its implementation lands.
"""

import unittest

from tests.oracles.sch_d_540_reference import (
    SchD540Input,
    Transaction,
    compute_sch_d_540,
)


class EmptyInputTests(unittest.TestCase):
    """Degenerate case: no transactions, no carryover — should produce a
    zero CA-federal delta and a well-formed output dict."""

    def test_empty_input_produces_zero_ca_delta(self):
        inp = SchD540Input(
            filing_status="single",
            transactions=(),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=0.0,
        )
        out = compute_sch_d_540(inp)
        # The key that downstream CA 540 oracle consumes on
        # SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions
        # should be zero when there are no deltas to report.
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 0.0)


class Section1202QSBSTests(unittest.TestCase):
    """IRC §1202 (and §1045 rollover) QSBS exclusion is not conformed to
    by California — R&TC §18152.  Federal excludes some or all of the
    gain; CA recognizes the full gain. Delta lands on line 12b (addition
    to Sch CA col C).

    SOURCE: FTB 2025 Sch D (540) instructions, nonconformity list item
    for IRC §§1045 and 1202."""

    def test_qsbs_full_federal_exclusion_produces_line_12b_addition(self):
        # Sold QSBS with a $100 CA-recognized gain. Federal 1040 line 7a
        # is $0 because the entire gain qualified for §1202 exclusion
        # (100% exclusion applies to QSBS acquired after 2010-09-27).
        t = Transaction(
            description="QSBS in ACME Corp",
            ca_gain_or_loss=100.0,
        )
        inp = SchD540Input(
            filing_status="single",
            transactions=(t,),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=0.0,
        )
        out = compute_sch_d_540(inp)

        # CA recognizes the full $100; federal recognizes $0.
        self.assertEqual(out["schd_540_line_4_total_gains"], 100.0)
        self.assertEqual(out["schd_540_line_8_net_gain_or_loss"], 100.0)
        self.assertEqual(out["schd_540_line_10_federal_1040_line_7a"], 0.0)
        self.assertEqual(out["schd_540_line_11_ca_gain_or_loss"], 100.0)
        # line 10 (0) < line 11 (100) → col C addition.
        self.assertEqual(out["schd_540_line_12a_subtraction_col_b"], 0.0)
        self.assertEqual(out["schd_540_line_12b_addition_col_c"], 100.0)
        # Signed integration delta: CA > fed → positive.
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 100.0)

    def test_qsbs_partial_federal_exclusion_produces_partial_addition(self):
        # QSBS acquired pre-2009-02-18 had only a 50% exclusion under
        # the original §1202. Federal recognizes half the gain; CA
        # recognizes the full gain.
        t = Transaction(
            description="Pre-2009 QSBS",
            ca_gain_or_loss=200.0,
        )
        inp = SchD540Input(
            filing_status="single",
            transactions=(t,),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=100.0,
        )
        out = compute_sch_d_540(inp)

        self.assertEqual(out["schd_540_line_11_ca_gain_or_loss"], 200.0)
        self.assertEqual(out["schd_540_line_10_federal_1040_line_7a"], 100.0)
        self.assertEqual(out["schd_540_line_12b_addition_col_c"], 100.0)
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 100.0)


class Section1400Z2OpportunityZoneTests(unittest.TestCase):
    """IRC §1400Z-2 (and §1400Z-1) Qualified Opportunity Zone gain
    deferral/exclusion is not conformed to by California — R&TC
    §17158.3. Federal defers the gain in the year realized by
    reinvesting in a QOF; CA recognizes the gain in that same year.
    Delta flows to line 12b (addition to Sch CA col C).

    SOURCE: FTB 2025 Sch D (540) instructions, nonconformity list item
    for IRC §§1400Z-1 and 1400Z-2."""

    def test_oz_deferral_produces_line_12b_addition(self):
        # $500 gain realized in TY2025. Taxpayer reinvested into a QOF,
        # deferring federal recognition entirely. CA doesn't conform to
        # the deferral; recognizes the full $500.
        t = Transaction(
            description="Gain deferred into QOF investment",
            ca_gain_or_loss=500.0,
        )
        inp = SchD540Input(
            filing_status="single",
            transactions=(t,),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=0.0,
        )
        out = compute_sch_d_540(inp)

        self.assertEqual(out["schd_540_line_11_ca_gain_or_loss"], 500.0)
        self.assertEqual(out["schd_540_line_10_federal_1040_line_7a"], 0.0)
        self.assertEqual(out["schd_540_line_12b_addition_col_c"], 500.0)
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 500.0)


class IdentityCaseTests(unittest.TestCase):
    """CA recognizes identical gain/loss to federal on every transaction.
    Lines 4, 8, 10, 11 all equal; lines 12a and 12b both zero; aggregate
    delta to Sch CA line 7 is zero. This exercises the full line 1-12
    structure without any nonconformity delta."""

    def test_single_gain_transaction_identity_produces_zero_delta(self):
        # One CA transaction with a $60 gain. Federal 1040 line 7a
        # aggregates to the same $60 (pure-identity case — no federal
        # inclusion adjustments, no other federal capital gain items).
        t = Transaction(
            description="Identity stock sale",
            ca_gain_or_loss=60.0,
        )
        inp = SchD540Input(
            filing_status="single",
            transactions=(t,),
            ca_capital_loss_carryover=0.0,
            federal_1040_line_7a_capital_gain=60.0,
        )
        out = compute_sch_d_540(inp)

        # Line 4: total 2025 gains from all sources (col (e) amounts).
        self.assertEqual(out["schd_540_line_4_total_gains"], 60.0)
        # Line 5: total 2025 losses (col (d) amounts). Identity gain → zero.
        self.assertEqual(out["schd_540_line_5_total_losses"], 0.0)
        # Line 6: CA capital loss carryover from prior year.
        self.assertEqual(out["schd_540_line_6_ca_carryover_from_prior_year"], 0.0)
        # Line 7: total 2025 loss = line 5 + line 6.
        self.assertEqual(out["schd_540_line_7_total_losses_with_carryover"], 0.0)
        # Line 8: net gain or (loss) = line 4 + line 7 (combine with signs).
        self.assertEqual(out["schd_540_line_8_net_gain_or_loss"], 60.0)
        # Line 10: federal 1040 line 7a amount (scalar pass-through).
        self.assertEqual(out["schd_540_line_10_federal_1040_line_7a"], 60.0)
        # Line 11: CA gain from line 8 (or loss from line 9 if net loss).
        self.assertEqual(out["schd_540_line_11_ca_gain_or_loss"], 60.0)
        # Line 12a: subtraction to Sch CA 540 Part I line 7 col B
        # (positive when fed > CA). Identity → zero.
        self.assertEqual(out["schd_540_line_12a_subtraction_col_b"], 0.0)
        # Line 12b: addition to Sch CA 540 Part I line 7 col C
        # (positive when CA > fed). Identity → zero.
        self.assertEqual(out["schd_540_line_12b_addition_col_c"], 0.0)
        # Aggregate signed delta (the integration-stable key).
        self.assertEqual(out["schd_540_ca_fed_delta_to_sch_ca_line_7"], 0.0)


if __name__ == "__main__":
    unittest.main()
