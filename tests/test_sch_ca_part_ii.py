"""Schedule CA (540) Part II — CA itemized deductions.

Verifies the Part II compute kernel and the Form 540 deduction selection.
Mechanics confirmed against the 2024 Schedule CA (540) form by team-lead:
  - Part II lines 1–4 (medical) replicate federal Schedule A exactly, because
    the form's line-2 instruction reads "Enter amount from federal Form 1040
    ... line 11" (FEDERAL AGI). So CA medical = the federal medical deductible,
    passed through — NOT recomputed against CA AGI.
  - Taxes: CA disallows state/local income tax and applies NO SALT cap;
    deductible taxes = property + personal-property (uncapped).
  - Mortgage/charity: conform (pass-through) for the amounts in scope.
"""
import unittest

from tenforty.forms import sch_ca as form_sch_ca, f540 as form_f540
from tenforty.models import CA540Return, FilingStatus


def _fed(**overrides) -> dict:
    """A Schedule A result stub (as returned by forms.sch_a.compute) carrying
    the line keys compute_part_ii_itemized reads."""
    base = {
        "sch_a_line_1_medical_gross": 0,
        "sch_a_line_4_medical_deductible": 0,
        "sch_a_line_5a_state_income_tax": 0,
        "sch_a_line_5b_property_tax": 0,
        "sch_a_line_5c_personal_property_tax": 0,
        "sch_a_line_5e_salt_capped": 0,
        "sch_a_line_8a_mortgage_interest": 0,
        "sch_a_line_14_charity_total": 0,
        "sch_a_line_17_total": 0,
    }
    base.update(overrides)
    return base


class FederalItemizationAppliedGateTests(unittest.TestCase):
    """The gate that decides whether CA Part II runs at all.

    schedule_a_total is the RAW Schedule A total, emitted even when the
    standard deduction won — so the gate must compare it to applied_deduction,
    not just check schedule_a_total > 0.
    """

    def test_itemized_applied_is_true(self):
        self.assertTrue(form_sch_ca.federal_itemization_applied(
            {"schedule_a_total": 22014, "applied_deduction": 22014}))

    def test_itemized_below_standard_is_false(self):
        # Sch A total 3000 but standard 14600 won → NOT federal-itemized.
        self.assertFalse(form_sch_ca.federal_itemization_applied(
            {"schedule_a_total": 3000, "applied_deduction": 14600}))

    def test_no_itemized_is_false(self):
        self.assertFalse(form_sch_ca.federal_itemization_applied(
            {"schedule_a_total": 0, "applied_deduction": 14600}))


class ComputePartIIItemizedTests(unittest.TestCase):
    def test_medical_passes_through_federal_deductible(self):
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_4_medical_deductible=13005))
        self.assertEqual(out["sch_ca_part_ii_medical"], 13005)
        self.assertEqual(out["ca_itemized_total"], 13005)

    def test_state_income_tax_disallowed(self):
        # Federal line 5a (state income tax) 9009, no property → CA taxes 0.
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_5a_state_income_tax=9009,
                 sch_a_line_5e_salt_capped=9009))
        self.assertEqual(out["sch_ca_part_ii_taxes"], 0)
        self.assertEqual(out["ca_itemized_total"], 0)

    def test_property_tax_allowed_uncapped(self):
        # Property tax 15000 exceeds the federal $10k SALT cap; CA has no cap,
        # so all 15000 is deductible (state income tax still excluded).
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_5a_state_income_tax=9000,
                 sch_a_line_5b_property_tax=15000,
                 sch_a_line_5e_salt_capped=10000))
        self.assertEqual(out["sch_ca_part_ii_taxes"], 15000)
        self.assertEqual(out["ca_itemized_total"], 15000)

    def test_mortgage_and_charity_pass_through(self):
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_8a_mortgage_interest=5000,
                 sch_a_line_14_charity_total=1000))
        self.assertEqual(out["sch_ca_part_ii_mortgage"], 5000)
        self.assertEqual(out["sch_ca_part_ii_charity"], 1000)
        self.assertEqual(out["ca_itemized_total"], 6000)

    def test_worked_example_medical_plus_disallowed_state_tax(self):
        # This return's shape: medical deductible 13005 + state income tax 9009
        # (disallowed) + no property/mortgage/charity → CA itemized = 13005.
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_1_medical_gross=22457,
                 sch_a_line_4_medical_deductible=13005,
                 sch_a_line_5a_state_income_tax=9009,
                 sch_a_line_5e_salt_capped=9009,
                 sch_a_line_17_total=22014))
        self.assertEqual(out["ca_itemized_total"], 13005)


class Form540DeductionSelectionTests(unittest.TestCase):
    def _deduction(self, ca_itemized):
        out = form_f540.compute(
            year=2024,
            filing_status=FilingStatus.SINGLE,
            federal_agi=126024,
            ca_agi=125639,
            ca540=CA540Return(),
            ca_itemized=ca_itemized,
        )
        return out["f540_deduction"]

    def test_itemized_wins_when_above_standard(self):
        # CA single standard 2024 = 5540; itemized 13005 wins.
        self.assertEqual(self._deduction(13005), 13005)

    def test_standard_wins_when_no_itemized(self):
        self.assertEqual(self._deduction(None), 5540)

    def test_standard_wins_when_itemized_below_standard(self):
        self.assertEqual(self._deduction(3000), 5540)


if __name__ == "__main__":
    unittest.main()
