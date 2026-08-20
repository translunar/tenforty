"""SE-health deduction end-to-end through a 1040-X amendment (Task 4).

The motivating case for the self-employed-health-insurance input channel: a
1040-X has Column A (as-filed, from a filed-values dict), Column C (corrected,
re-computed by running the whole pipeline on the amended ``Scenario``), and
Column B = C - A. Before the input channel, tenforty could not put the
SE-health deduction into Column C's recompute, so a filed return that DID claim
the deduction got a Column C with an overstated AGI — a spurious deduction-sized
gap on line 1 Column B, which is what quarantined the real 2023 amendment.

These two tests prove, with SYNTHETIC values, that:
  * Column C's recompute genuinely honors ``self_employed_health_insurance_
    deduction`` (Test 1), and
  * when the filed return already claimed it, the deduction cancels out of
    Column B rather than leaking in as a spurious change (Test 2).

Mirrors ``tests/test_amendment_packet_emit.py``: the filed-values dict is the
original run's ``form_f1040x.REQUIRED_FILED_KEYS`` (Column A); Column C is a
straight ``compute_federal`` of the amended scenario; the 1040-X grid is
``form_f1040x.assemble`` over the two dicts (the soffice-free assembly path —
no PDF fill, no LibreOffice).

Single filer throughout (native spine — matches Juno's 2023 case, avoids the
workbook path's deferred wiring / Task-3 guard). NO Form 1095-A (Juno's 2023
case has none; a 1095-A would trip the Task-2 SE-health x PTC guard). All
figures are clearly synthetic.
"""
import dataclasses
import tempfile
import unittest
from pathlib import Path

from tenforty.forms import f1040x as form_f1040x
from tenforty.models import AmendmentCase, Form1099INT
from tenforty.orchestrator import ReturnOrchestrator
from tests.fixtures.spine_battery import build_canonical_wage_investment_rental

REPO_ROOT = Path(__file__).parent.parent

# Clearly-synthetic figures. Deliberately unlike any real premium total.
_SE_HEALTH_V = 4_800.0   # Test 1 deduction amount
_FILED_V = 3_600.0       # Test 2 deduction amount (already on the filed return)
_INCOME_BUMP = 1_200.0   # Test 2 "other change" (additional taxable interest)
_ORIG_INTEREST = 2_000.0  # canonical fixture's as-filed interest


def _with_se_health(scenario, amount):
    """Twin carrying ``self_employed_health_insurance_deduction = amount``."""
    cfg = dataclasses.replace(
        scenario.config, self_employed_health_insurance_deduction=amount)
    return dataclasses.replace(scenario, config=cfg)


def _set_interest(scenario, amount):
    """Twin whose ONLY interest is a single synthetic 1099-INT of ``amount``."""
    return dataclasses.replace(
        scenario, form1099_int=[Form1099INT(payer="Synthetic Bank", interest=amount)])


class SEHealthAmendmentColumnCTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=self.tmp / "work",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _filed_from(self, scenario):
        """The one sanctioned recompute-as-filed spot: build the Column-A dict
        from ``scenario``'s own computed REQUIRED_FILED_KEYS (as
        ``test_amendment_packet_emit._write_federal_filed`` does)."""
        results = self.orch.compute_federal(scenario)
        return {k: results[k] for k in form_f1040x.REQUIRED_FILED_KEYS}

    # -------------------------------------------------------------- Test 1
    def test_column_c_recompute_honors_se_health_deduction(self):
        """Column C's recompute genuinely honors the SE-health field.

        Assemble the SAME amendment two ways — amended scenario WITH
        ``self_employed_health_insurance_deduction = V`` vs WITHOUT (0) — and
        assert Column C AGI (``f1040x_line1_c``) and Column C taxable income
        (``f1040x_line5_c``) are EXACTLY V lower with the deduction. Taxable
        income stays well above 0 (canonical ~$195k income, standard deduction,
        no QBI), so nothing floors and the delta lands whole on line 5 too.

        Falsifiable: if Column C ignored the field, both recomputes would
        produce the same AGI/taxable income and the delta would be 0, not V.
        """
        base = build_canonical_wage_investment_rental(2024)  # single filer
        filed = self._filed_from(base)  # Column A (identical for both assemblies)

        amended_without = base                                   # field = 0
        amended_with = _with_se_health(base, _SE_HEALTH_V)       # field = V

        # Column C recomputes must genuinely differ — the amendment path really
        # ran the pipeline on the amended scenario (not a cached figure).
        corrected_without = self.orch.compute_federal(amended_without)
        corrected_with = self.orch.compute_federal(amended_with)

        case = AmendmentCase(
            year=2024,
            explanation="Added self-employed health-insurance deduction.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out_without = form_f1040x.assemble(filed, corrected_without, case)
        out_with = form_f1040x.assemble(filed, corrected_with, case)

        # Taxable income really is well above 0 on both sides (no flooring).
        self.assertGreater(out_with["f1040x_line5_c"], 100_000)
        self.assertGreater(out_without["f1040x_line5_c"], 100_000)

        with self.subTest(line="1_c (AGI)"):
            self.assertEqual(
                out_without["f1040x_line1_c"] - out_with["f1040x_line1_c"],
                _SE_HEALTH_V)
        with self.subTest(line="5_c (taxable income)"):
            self.assertEqual(
                out_without["f1040x_line5_c"] - out_with["f1040x_line5_c"],
                _SE_HEALTH_V)

    # -------------------------------------------------------------- Test 2
    def test_filed_deduction_cancels_out_of_column_b(self):
        """The gap cancels — the literal motivating property.

        The filed (Column A) return ALREADY claims the deduction (= V). The
        amended scenario ALSO carries = V, plus one OTHER change: +Δ taxable
        interest. Because the deduction is in BOTH Column A and Column C, it
        must NOT appear as a Column-B delta: line 1 Column B (the AGI change)
        must reflect ONLY Δ, not Δ + V.

        Contrast (the OLD broken behavior): if the amended scenario DROPPED the
        deduction (field = 0) while the filed return still carried it, Column C
        AGI would be V too high and line 1 Column B would be inflated to Δ + V.
        Asserting both proves the fix rather than merely describing it.
        """
        # Original (== as-filed) already claims the deduction.
        original = _with_se_health(
            build_canonical_wage_investment_rental(2024), _FILED_V)
        filed = self._filed_from(original)  # Column A reflects the deduction

        bumped_interest = _ORIG_INTEREST + _INCOME_BUMP
        # FIXED amended: same deduction (V) + the one other change (+Δ interest).
        amended_fixed = _set_interest(
            _with_se_health(original, _FILED_V), bumped_interest)
        # BROKEN amended: the OLD behavior — same +Δ interest, but the deduction
        # is dropped from Column C's recompute.
        amended_broken = _set_interest(
            _with_se_health(original, 0.0), bumped_interest)

        corrected_fixed = self.orch.compute_federal(amended_fixed)
        corrected_broken = self.orch.compute_federal(amended_broken)

        case = AmendmentCase(
            year=2024, explanation="Corrected taxable interest income.",
            original_refund_received=0.0, original_refund_applied=0.0)
        out_fixed = form_f1040x.assemble(filed, corrected_fixed, case)
        out_broken = form_f1040x.assemble(filed, corrected_broken, case)

        # FIXED: line 1 Column B reflects ONLY the +Δ interest change. The
        # deduction, present in both A and C, cancels out of B entirely.
        self.assertEqual(out_fixed["f1040x_line1_b"], _INCOME_BUMP)

        # BROKEN: dropping the deduction from Column C inflates line 1 Column B
        # by V — the spurious deduction-sized gap this unit removes.
        self.assertEqual(out_broken["f1040x_line1_b"], _INCOME_BUMP + _FILED_V)

        # The two Column-B figures differ by exactly V — the deduction is the
        # whole gap, nothing else moved between the fixed and broken recomputes.
        self.assertEqual(
            out_broken["f1040x_line1_b"] - out_fixed["f1040x_line1_b"], _FILED_V)

        # Sanity: A + B == C on line 1 for both (the grid guarantees it).
        for label, out in (("fixed", out_fixed), ("broken", out_broken)):
            with self.subTest(assembly=label):
                self.assertEqual(
                    out["f1040x_line1_a"] + out["f1040x_line1_b"],
                    out["f1040x_line1_c"])


if __name__ == "__main__":
    unittest.main()
