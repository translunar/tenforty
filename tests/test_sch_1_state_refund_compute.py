"""State tax refund tax-benefit-rule (recovery limitation)."""

import unittest

from tenforty.forms import sch_1 as form_sch_1
from tenforty.models import Form1099G

from tests.helpers import make_simple_scenario


class TaxBenefitRuleTests(unittest.TestCase):
    def test_prior_year_standard_deduction_refund_not_taxable(self):
        s = make_simple_scenario()
        s.config.prior_year_itemized = False
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 0)

    def test_itemized_recovery_cap_binds(self):
        """Recovery cap = itemized − standard = 5000 − 14600 = <0 → 0 taxable,
        because the filer did NOT benefit from itemizing above standard.
        (Hypothetical — in practice a filer wouldn't itemize below standard,
        but the clamp matters for edge cases.)"""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 5_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 0)

    def test_refund_below_recovery_cap_fully_taxable(self):
        """itemized 30k, standard 14.6k → recovery cap 15.4k. Refund 1.5k <
        cap → full refund taxable."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 1_500)

    def test_refund_above_recovery_cap_capped(self):
        """itemized 15k, standard 14.6k → recovery cap 400. Refund 1500 >
        cap → taxable amount capped at 400."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 15_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 400)

    def test_salt_cap_headroom_limits_taxable(self):
        """Prior-year single filer, SALT-cap was $10k binding. If prior-year
        state-tax paid was exactly at the cap, only refunds attributable to
        tax below the cap produced a benefit.

        Simpler, Plan D formulation: taxable amount is LEAST of
           (a) refund, (b) recovery cap, (c) SALT cap.
        A filer with 30k prior-year itemized of which 12k was state tax and
        the SALT cap capped it at 10k: the extra 2k over the cap never
        produced a benefit. Refund of 1500 → limited to min(refund 1500,
        recovery cap 15400, SALT cap 10000) = 1500. But if refund is 12000,
        it's limited to 10000 (the SALT cap that applied)."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        # filing_status=single → SALT cap 10_000
        # taxable = min(12_000, 15_400, 10_000) = 10_000
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)


class TaxBenefitRuleYearAwarenessTests(unittest.TestCase):
    """Verify sch_1.compute uses year-correct prior_year_salt_cap from FederalParams."""

    def test_2024_prior_year_salt_cap_10k_single(self):
        """A 2024 return uses FederalParams.prior_year_salt_cap (looks back to 2023).
        For single: $10k. Refund of $12k capped at $10k SALT cap."""
        s = make_simple_scenario()
        s.config.year = 2024
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 13_850.0  # 2023 single std deduction
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2023)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        # recovery_cap = 30_000 - 13_850 = 16_150
        # prior_year_salt_cap = 10_000
        # taxable = min(12_000, 16_150, 10_000) = 10_000
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)

    def test_2025_prior_year_salt_cap_10k_single(self):
        """A 2025 return uses FederalParams.prior_year_salt_cap (looks back to 2024).
        For single: $10k. Same $10k cap applies."""
        s = make_simple_scenario()
        s.config.year = 2025
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0  # 2024 single std deduction
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        # recovery_cap = 30_000 - 14_600 = 15_400
        # prior_year_salt_cap = 10_000
        # taxable = min(12_000, 15_400, 10_000) = 10_000
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)


if __name__ == "__main__":
    unittest.main()
