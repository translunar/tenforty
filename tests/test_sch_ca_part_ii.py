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
    """A Schedule A result stub (as returned by forms.sch_a.compute).

    Callers state the lines their case is about; the dependent federal lines
    (5d, 7, 10, 11, 14, 17) are filled in the way Schedule A itself adds them,
    unless stated, so the stub is always an internally consistent Schedule A."""
    base = {
        "sch_a_line_1_medical_gross": 0,
        "sch_a_line_2_agi": 0,
        "sch_a_line_3_medical_floor": 0,
        "sch_a_line_4_medical_deductible": 0,
        "sch_a_line_5a_state_income_tax": 0,
        "sch_a_line_5b_property_tax": 0,
        "sch_a_line_5c_personal_property_tax": 0,
        "sch_a_line_5e_salt_capped": 0,
        "sch_a_line_6_other_taxes": 0,
        "sch_a_line_8a_mortgage_interest": 0,
        "sch_a_line_12_charity_noncash": 0,
        "sch_a_line_15_casualty": 0,
        "sch_a_line_16_other": 0,
    }
    base.update(overrides)
    base.setdefault("sch_a_line_5d_salt_sum", (
        base["sch_a_line_5a_state_income_tax"]
        + base["sch_a_line_5b_property_tax"]
        + base["sch_a_line_5c_personal_property_tax"]))
    base.setdefault("sch_a_line_7_taxes_total", (
        base["sch_a_line_5e_salt_capped"] + base["sch_a_line_6_other_taxes"]))
    base.setdefault("sch_a_line_10_interest_total",
                    base["sch_a_line_8a_mortgage_interest"])
    if "sch_a_line_14_charity_total" in base:
        base.setdefault("sch_a_line_11_charity_cash", (
            base["sch_a_line_14_charity_total"]
            - base["sch_a_line_12_charity_noncash"]))
    else:
        base.setdefault("sch_a_line_11_charity_cash", 0)
        base["sch_a_line_14_charity_total"] = (
            base["sch_a_line_11_charity_cash"]
            + base["sch_a_line_12_charity_noncash"])
    base.setdefault("sch_a_line_17_total", (
        base["sch_a_line_4_medical_deductible"]
        + base["sch_a_line_7_taxes_total"]
        + base["sch_a_line_10_interest_total"]
        + base["sch_a_line_14_charity_total"]
        + base["sch_a_line_15_casualty"]
        + base["sch_a_line_16_other"]))
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


def _cell(out: dict, line: str, column: str | None = None):
    key = f"sch_ca_line_part_ii_{line}"
    return out.get(key if column is None else f"{key}_{column}")


class PartIIPrintedLinesTests(unittest.TestCase):
    """The per-line, per-column figures Part II prints (Col A federal, Col B
    subtractions, Col C additions), which must foot to the section sums and
    to the total Form 540 line 18 takes."""

    def _itemizer(self, **overrides):
        base = dict(
            sch_a_line_1_medical_gross=20_000,
            sch_a_line_2_agi=100_000,
            sch_a_line_3_medical_floor=7_500,
            sch_a_line_4_medical_deductible=12_500,
            sch_a_line_5a_state_income_tax=9_000,
            sch_a_line_5b_property_tax=6_000,
            sch_a_line_5e_salt_capped=10_000,
            sch_a_line_8a_mortgage_interest=4_000,
            sch_a_line_11_charity_cash=2_500,
        )
        base.update(overrides)
        return form_sch_ca.compute_part_ii_itemized(_fed(**base))

    def test_medical_lines_replicate_federal(self):
        out = self._itemizer()
        self.assertEqual(_cell(out, "1"), 20_000)
        self.assertEqual(_cell(out, "2"), 100_000)
        self.assertEqual(_cell(out, "3"), 7_500)
        self.assertEqual(_cell(out, "4", "col_a"), 12_500)

    def test_taxes_follow_the_printed_line_5e_rule(self):
        out = self._itemizer()
        self.assertEqual(_cell(out, "5a", "col_a"), 9_000)
        self.assertEqual(_cell(out, "5a", "subtractions"), 9_000)
        self.assertEqual(_cell(out, "5b", "col_a"), 6_000)
        self.assertEqual(_cell(out, "5d", "col_a"), 15_000)
        self.assertEqual(_cell(out, "5e", "col_a"), 10_000)
        self.assertEqual(_cell(out, "5e", "subtractions"), 9_000)
        self.assertEqual(_cell(out, "5e", "additions"), 5_000)
        self.assertEqual(_cell(out, "7", "col_a"), 10_000)
        self.assertEqual(_cell(out, "7", "subtractions"), 9_000)
        self.assertEqual(_cell(out, "7", "additions"), 5_000)

    def test_interest_and_charity_pass_through_col_a(self):
        out = self._itemizer()
        self.assertEqual(_cell(out, "8a", "col_a"), 4_000)
        self.assertEqual(_cell(out, "8e", "col_a"), 4_000)
        self.assertEqual(_cell(out, "10", "col_a"), 4_000)
        self.assertEqual(_cell(out, "11", "col_a"), 2_500)
        self.assertEqual(_cell(out, "14", "col_a"), 2_500)

    def test_line_17_columns_and_the_totals_below_it(self):
        out = self._itemizer()
        self.assertEqual(_cell(out, "17", "col_a"), 29_000)
        self.assertEqual(_cell(out, "17", "subtractions"), 9_000)
        self.assertEqual(_cell(out, "17", "additions"), 5_000)
        for line in ("18", "26", "28", "29"):
            with self.subTest(line=line):
                self.assertEqual(_cell(out, line), 25_000)

    def test_printed_lines_foot_to_the_section_sums_and_the_total(self):
        out = self._itemizer()
        net = lambda line: (_cell(out, line, "col_a")
                            - (_cell(out, line, "subtractions") or 0)
                            + (_cell(out, line, "additions") or 0))
        self.assertEqual(net("4"), out["sch_ca_part_ii_medical"])
        self.assertEqual(net("7"), out["sch_ca_part_ii_taxes"])
        self.assertEqual(net("10"), out["sch_ca_part_ii_mortgage"])
        self.assertEqual(net("14"), out["sch_ca_part_ii_charity"])
        self.assertEqual(_cell(out, "18"), out["ca_itemized_total"])
        self.assertEqual(out["ca_itemized_total"], 25_000)

    def test_state_income_tax_above_the_cap_still_nets_to_property_tax(self):
        # 5a alone exceeds the cap: Col B subtracts all of 5a, Col C adds back
        # the capped-off excess, leaving exactly the property tax.
        out = self._itemizer(sch_a_line_5a_state_income_tax=30_000,
                             sch_a_line_5b_property_tax=5_000,
                             sch_a_line_5e_salt_capped=10_000)
        self.assertEqual(_cell(out, "5e", "subtractions"), 30_000)
        self.assertEqual(_cell(out, "5e", "additions"), 25_000)
        self.assertEqual(out["sch_ca_part_ii_taxes"], 5_000)

    def test_zero_detail_lines_are_not_emitted(self):
        out = form_sch_ca.compute_part_ii_itemized(
            _fed(sch_a_line_8a_mortgage_interest=5_000))
        for line, column in (("1", None), ("2", None), ("3", None),
                             ("5a", "col_a"), ("5a", "subtractions"),
                             ("5b", "col_a"), ("5c", "col_a"),
                             ("11", "col_a"), ("12", "col_a")):
            with self.subTest(line=line, column=column):
                self.assertIsNone(_cell(out, line, column))
        # Computed lines print even at zero.
        self.assertEqual(_cell(out, "4", "col_a"), 0)
        self.assertEqual(_cell(out, "7", "col_a"), 0)
        self.assertEqual(_cell(out, "18"), 5_000)

    def test_unmodeled_federal_line_refuses_and_names_the_line(self):
        for key, line in (("sch_a_line_6_other_taxes", "line 6"),
                          ("sch_a_line_15_casualty", "line 15"),
                          ("sch_a_line_16_other", "line 16")):
            with self.subTest(key=key):
                with self.assertRaisesRegex(NotImplementedError, line + r"\b"):
                    form_sch_ca.compute_part_ii_itemized(_fed(**{key: 100}))

    def test_col_a_that_does_not_foot_to_federal_names_the_line(self):
        cases = (
            ("sch_a_line_5d_salt_sum", 99_999, "line 5d"),
            ("sch_a_line_7_taxes_total", 99_999, "line 7"),
            ("sch_a_line_10_interest_total", 99_999, "line 10"),
            ("sch_a_line_14_charity_total", 99_999, "line 14"),
            ("sch_a_line_17_total", 99_999, "line 17"),
        )
        for key, value, line in cases:
            with self.subTest(key=key):
                with self.assertRaisesRegex(ValueError, line + r"\b"):
                    self._itemizer(**{key: value})


if __name__ == "__main__":
    unittest.main()
