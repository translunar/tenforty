"""State tax refund tax-benefit-rule (recovery limitation).

Pub. 525 worksheet (SALT-cap portion) formula used throughout this file:
    benefit = max(0, min(salt_paid, cap) - min(max(salt_paid - refund, 0), cap))
    taxable = min(refund, recovery_cap, benefit)
where recovery_cap = max(0, prior_year_itemized - prior_year_standard) and
cap = params.prior_year_salt_cap[filing_status] (unchanged from before).
"""

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
        but the clamp matters for edge cases.)

        recovery_cap is 0, so it dominates the min() regardless of the
        benefit computation — result is unchanged at 0 whether salt_paid is
        3000 or any other value. Old flat-ceiling result was also 0
        (min(1500, 0, 10000) = 0), so this assertion does not change."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 5_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 3_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 0)

    def test_refund_below_recovery_cap_fully_taxable(self):
        """itemized 30k, standard 14.6k → recovery cap 15.4k. Refund 1.5k <
        cap → full refund taxable.

        salt_paid=2000, cap=10000 (single 2025):
          benefit = min(2000,10000) - min(max(2000-1500,0),10000)
                  = 2000 - min(500,10000) = 2000 - 500 = 1500
          taxable = min(1500, 15400, 1500) = 1500
        UNCHANGED from the old flat-ceiling result of 1500 (salt_paid comfortably
        exceeds the refund and the cap doesn't bind, so benefit == refund)."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 2_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 1_500)

    def test_refund_above_recovery_cap_capped(self):
        """itemized 15k, standard 14.6k → recovery cap 400. Refund 1500 >
        cap → taxable amount capped at 400.

        salt_paid=2000, cap=10000 (single 2025):
          benefit = min(2000,10000) - min(max(2000-1500,0),10000)
                  = 2000 - 500 = 1500
          taxable = min(1500, 400, 1500) = 400
        UNCHANGED from the old flat-ceiling result of 400 — the recovery cap
        (400) is the binding constraint, well below the benefit (1500)."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 15_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 2_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 400)

    def test_salt_paid_at_cap_boundary_matches_old_flat_ceiling(self):
        """Prior-year single filer, SALT-cap was $10k binding: prior-year SALT
        actually paid was exactly at the cap ($10,000), and the refund ($12,000)
        exceeds what was paid.

        itemized 30k, standard 14.6k → recovery_cap = 15400.
        salt_paid=10000, cap=10000, refund=12000:
          benefit = min(10000,10000) - min(max(10000-12000,0),10000)
                  = 10000 - min(0,10000) = 10000 - 0 = 10000
          taxable = min(12000, 15400, 10000) = 10000
        UNCHANGED from the old flat-ceiling result of 10000 — this is the
        boundary case where salt_paid == cap exactly, so the benefit formula
        degenerates to the same number the flat ceiling always gave. That
        coincidence does NOT generalize (see the OVER-INCLUSION and
        INNER-CLAMP tests below, where salt_paid != cap and the results
        diverge from the flat-ceiling approximation)."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 10_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        # filing_status=single → SALT cap 10_000
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)

    def test_over_inclusion_flat_ceiling_would_overtax(self):
        """MANDATORY pin: salt_paid=12000 (over the $10k cap), cap=10000,
        refund=1500, recovery_cap large (15400, non-binding).

        benefit = min(12000,10000) - min(max(12000-1500,0),10000)
                = 10000 - min(10500,10000) = 10000 - 10000 = 0
        taxable = min(1500, 15400, 0) = 0

        OLD flat-ceiling result: min(refund 1500, recovery_cap 15400,
        salt_cap 10000) = 1500 — WRONG. The filer paid $12,000 in SALT but
        could only ever deduct $10,000 of it (the cap already fully absorbed
        by the non-refunded portion: 12000 - 1500 = 10500 > 10000), so NONE
        of the $1,500 refund produced any additional tax benefit.
        OLD=1500, NEW=0."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 12_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_500.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 0)

    def test_inner_clamp_refund_exceeds_salt_paid(self):
        """MANDATORY pin: salt_paid=800, cap=10000, refund=1200 (refund >
        salt_paid), recovery_cap large (15400, non-binding).

        benefit = min(800,10000) - min(max(800-1200,0),10000)
                = 800 - min(max(-400,0),10000) = 800 - min(0,10000) = 800 - 0 = 800
        taxable = min(1200, 15400, 800) = 800

        The INNER clamp max(salt_paid - refund, 0) is LOAD-BEARING here:
        without it, benefit = 800 - min(-400,10000) = 800 - (-400) = 1200,
        which is WRONG — the filer only ever deducted $800 of SALT, so the
        refund cannot produce a tax benefit greater than $800 no matter how
        large the refund is.
        OLD flat-ceiling result: min(refund 1200, recovery_cap 15400,
        salt_cap 10000) = 1200 (fully taxable) — WRONG for the same reason.
        OLD=1200, NEW=800."""
        s = make_simple_scenario()
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0
        s.config.prior_year_salt_paid = 800.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=1_200.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 800)


class TaxBenefitRuleYearAwarenessTests(unittest.TestCase):
    """Verify sch_1.compute uses year-correct prior_year_salt_cap from FederalParams."""

    def test_2024_prior_year_salt_cap_10k_single(self):
        """A 2024 return uses FederalParams.prior_year_salt_cap (looks back to 2023).
        For single: $10k. salt_paid=10000 (at the cap), refund of $12k.

        recovery_cap = 30_000 - 13_850 = 16_150
        benefit = min(10000,10000) - min(max(10000-12000,0),10000)
                = 10000 - 0 = 10000
        taxable = min(12_000, 16_150, 10_000) = 10_000
        UNCHANGED from the old flat-ceiling result of 10_000 (boundary case,
        salt_paid == cap; see test_salt_paid_at_cap_boundary_matches_old_flat_ceiling)."""
        s = make_simple_scenario()
        s.config.year = 2024
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 13_850.0  # 2023 single std deduction
        s.config.prior_year_salt_paid = 10_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2023)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)

    def test_2025_prior_year_salt_cap_10k_single(self):
        """A 2025 return uses FederalParams.prior_year_salt_cap (looks back to 2024).
        For single: $10k. salt_paid=10000 (at the cap), refund of $12k.

        recovery_cap = 30_000 - 14_600 = 15_400
        benefit = min(10000,10000) - min(max(10000-12000,0),10000)
                = 10000 - 0 = 10000
        taxable = min(12_000, 15_400, 10_000) = 10_000
        UNCHANGED from the old flat-ceiling result of 10_000 (boundary case,
        salt_paid == cap; see test_salt_paid_at_cap_boundary_matches_old_flat_ceiling)."""
        s = make_simple_scenario()
        s.config.year = 2025
        s.config.prior_year_itemized = True
        s.config.prior_year_itemized_deduction_amount = 30_000.0
        s.config.prior_year_standard_deduction_amount = 14_600.0  # 2024 single std deduction
        s.config.prior_year_salt_paid = 10_000.0
        s.form1099_g = [Form1099G(payer="State", state_tax_refund=12_000.0,
                                   state_tax_refund_tax_year=2024)]
        out = form_sch_1.compute(s, upstream={"sch_e": {}})
        self.assertEqual(out["sch_1_line_1_taxable_refunds"], 10_000)


if __name__ == "__main__":
    unittest.main()
