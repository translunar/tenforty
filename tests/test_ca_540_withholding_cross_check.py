"""Production f540 vs. CA-540 reference oracle — the withholding parity guard.

## Why this file exists (the causal story)

Production ``tenforty.forms.f540.compute`` OMITTED California withholding
ENTIRELY until 2026-07-16: the Form 540 balance had no line-71 term at all,
so ``f540_total_liability`` was wrong by the full withholding for every CA
W-2 return. The independent CA-540 reference oracle
(``tests.oracles.ca_540_reference``) ALWAYS modeled it correctly (line 71 →
line 78 total payments → refund/owe balance). The bug survived undetected for
one simple reason: **no test had ever compared production f540 to the oracle
on a withholding-bearing scenario.** The two implementations existed side by
side and were never diffed where it mattered.

This file is that missing comparison, made permanent. It reconciles the
production balance against the oracle's line 114 (amount due) minus line 115
(refund) on a matched wages-only single scenario — with withholding and,
critically, WITHOUT — so a future regression that drops (or double-counts)
line 71 breaks here immediately.

## Scope (deliberately narrow)

One matched scenario: single, 2025, wages-only (federal AGI == CA AGI, so no
Schedule CA divergence), standard deduction, NO dependents, no renter's /
dep-care credits, income far under the $1M BHST threshold, and every other
oracle line the production v1 does not model held at ZERO. Under those
constraints the two implementations converge on exactly three moving parts:
CA tax, the exemption credit, and the withholding. This is a targeted parity
guard, NOT a general CA cross-check framework.

## Coverage division

This test drives ``f540.compute`` DIRECTLY and therefore BYPASSES the
orchestrator's ``scenario.w2s``-where-``state == "CA"`` summation/filter that
WIRE-2 added. It guards the BALANCE-CHAIN half (line 71 → line 78 total
payments → refund/owe) against the independent oracle; it cannot catch a
regression in the W-2 summation/filter. That half is guarded by the structural
pin in ``test_ca_withholding_channel`` (which drives the orchestrator CA path).
Two named halves of one chain, no gap — the same explicitness whose absence let
the original omission survive.

## Rounding

The oracle intentionally does not round (its docstring: "rounding is
production's job ... the comparison harness rounds ... before comparing").
Production applies FTB whole-dollar rounding to the tax (line 31), so the
oracle's unrounded signed net differs from production by at most the sub-dollar
tax remainder. We therefore apply ``irs_round`` to the oracle's signed net
before comparing. Three facts together justify that this bridges a
REPRESENTATION gap rather than masking a discrepancy:
  1. It honors the oracle's OWN documented contract ("rounding is production's
     job ... the harness rounds before comparing") — not an ad-hoc fudge.
  2. The X=0 control reconciles at the dollar ($9,705 both sides), so the two
     implementations already AGREE with no withholding — the round is aligning
     representations of the same number, not papering over a real gap.
  3. A mutation that drops production's line-71 term ($4,000) still FAILS this
     test THROUGH the round — so the round cannot hide a genuine breakage; it
     only absorbs the ≤$0.50 tax-rounding remainder.
"""

import dataclasses
import unittest

from tenforty.forms import f540
from tenforty.models import CA540Return, FilingStatus
from tenforty.rounding import irs_round
from tests.oracles import ca_540_reference as ora


# Matched inputs. Federal AGI == CA AGI (wages-only, no Sch CA divergence).
# $150k is > the $100k tax-table/rate-schedule boundary (so production's
# compute_ca_tax and the oracle both walk the rate schedule directly, avoiding
# the documented ~$3 tax-table-midpoint divergence) and < the $252,203 CA
# exemption-credit phaseout threshold (so f540.compute does not raise and no
# phaseout applies to either side).
_FEDERAL_AGI = 150_000.0
_CA_AGI = 150_000.0
_WITHHOLDING = 4_000


def _production(federal_agi, ca_agi, withholding):
    return f540.compute(
        year=2025,
        filing_status=FilingStatus.SINGLE,
        federal_agi=federal_agi,
        ca_agi=ca_agi,
        ca540=CA540Return(),
        num_dependents=0,
        ca_withholding=withholding,
    )


def _zero_part_i():
    fields = dataclasses.fields(ora.SchCAPartIAdjustments)
    return ora.SchCAPartIAdjustments(**{f.name: 0.0 for f in fields})


def _zero_part_ii():
    values = {f.name: 0.0 for f in dataclasses.fields(ora.SchCAPartIIAdjustments)}
    values["itemize"] = False  # standard deduction
    return ora.SchCAPartIIAdjustments(**values)


def _oracle(federal_agi, ca_agi, withholding):
    """Build the matched minimal CA540Input and compute the oracle output.

    Everything the production v1 doesn't model is zeroed so the two converge
    on CA tax + exemption credit + withholding.
    """
    inp = ora.CA540Input(
        demographics=ora.Demographics(
            filing_status="single",
            can_be_claimed_as_dependent=False,
            spouse_can_be_claimed_as_dependent=False,
            taxpayer_age_65_or_older=False,
            spouse_age_65_or_older=False,
            taxpayer_blind=False,
            spouse_blind=False,
            dependent_count=0,
            dependent_earned_income=0.0,
        ),
        # state_wages_from_w2_box16 only feeds Form 540 line 12 (informational
        # in the oracle); CA AGI is driven by federal_agi with zero Sch CA
        # adjustments. Set it to ca_agi for a coherent wages-only return.
        federal=ora.FederalCarryIn(
            federal_agi=federal_agi,
            state_wages_from_w2_box16=ca_agi,
        ),
        sch_ca_part_i=_zero_part_i(),
        sch_ca_part_ii=_zero_part_ii(),
        payments=ora.Form540Payments(
            line_71_ca_withholding=float(withholding),
            line_72_estimated_payments_and_carryover=0.0,
            line_73_592b_593_withholding=0.0,
            line_74_motion_picture_credit=0.0,
            line_75_eitc=0.0,
            line_76_yctc=0.0,
            line_77_fytc=0.0,
        ),
        credits=ora.Form540Credits(
            dep_care_federal_agi_for_eligibility=federal_agi,
            dep_care_credit_amount=0.0,
            eligible_for_renters_credit=False,
            other_nonrefundable_credits=0.0,
        ),
        other_taxes=ora.Form540OtherTaxes(line_63_other_taxes=0.0),
        misc=ora.Form540Misc(
            line_91_use_tax=0.0,
            line_98_overpayment_applied_to_2026=0.0,
            line_110_voluntary_contributions=0.0,
        ),
        scope_out=ora.ScopeOut(
            amt_preferences_present=False,
            lump_sum_distribution_tax=0.0,
            accumulation_distribution_tax=0.0,
            kiddie_tax_child_filer=False,
            nol_deduction=0.0,
            excess_business_loss_adjustment=0.0,
            isr_penalty=0.0,
            underpayment_penalty=0.0,
        ),
    )
    return ora.compute_ca_540(inp)


class CA540WithholdingCrossCheckTest(unittest.TestCase):
    def _check(self, withholding):
        prod = _production(_FEDERAL_AGI, _CA_AGI, withholding)
        oracle = _oracle(_FEDERAL_AGI, _CA_AGI, withholding)

        # Production total_liability is a SIGNED net (owe > 0 / refund < 0).
        # The oracle splits the balance into non-negative line 114 (amount due)
        # and line 115 (refund); exactly one is nonzero, so their difference is
        # the same signed net. This is the line 71 → total payments →
        # refund/owe reconciliation.
        oracle_signed_net = (
            oracle["f540_line_114_total_amount_due"]
            - oracle["f540_line_115_refund"]
        )

        # Diagnostic arithmetic (printed for review; not asserted on).
        print(
            f"[cross-check X={withholding}] "
            f"prod total_liability={prod['f540_total_liability']} "
            f"prod line71={prod['f540_line71_ca_withholding']} | "
            f"oracle line_71={oracle['f540_line_71_withholding']} "
            f"line_114={oracle['f540_line_114_total_amount_due']:.2f} "
            f"line_115={oracle['f540_line_115_refund']:.2f} "
            f"signed_net={oracle_signed_net:.2f} "
            f"irs_round(signed_net)={irs_round(oracle_signed_net)}"
        )

        # (1) The withholding is line 71 on both sides (keys differ by design).
        self.assertEqual(
            prod["f540_line71_ca_withholding"],
            oracle["f540_line_71_withholding"],
        )
        self.assertEqual(prod["f540_line71_ca_withholding"], withholding)

        # (2) Full-balance reconciliation. irs_round bridges the oracle's
        # deliberately-unrounded output to production's FTB whole-dollar
        # convention (see module docstring "Rounding"). Because every term
        # other than the tax is integral, this is exact, not tolerant.
        self.assertEqual(
            prod["f540_total_liability"],
            irs_round(oracle_signed_net),
        )

    def test_with_ca_withholding(self):
        """Withholding present: line 71 nonzero, balance reconciles."""
        self._check(_WITHHOLDING)

    def test_zero_withholding_control(self):
        """Zero-withholding control. Proves the comparison validates the WHOLE
        balance chain (tax → exemption → payments → owe), not merely the
        withholding delta. If this control fails, the discrepancy is a
        pre-existing production-vs-oracle CA-balance divergence unrelated to
        withholding (it did not fail at authoring time: both sides = $9,705)."""
        self._check(0)


if __name__ == "__main__":
    unittest.main()
