import dataclasses
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tenforty import models
from tenforty.forms.f4868 import (
    compose_line_24,
    compute,
    compute_balance_due,
    total_tax_liability_line_24,
)
from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import REPO_ROOT, scope_out_attestation_defaults
from tests.invariants import expected_4868_pdf_values


def _scenario(**overrides):
    config = SimpleNamespace(
        full_name="Ada Lovelace",
        ssn="000-45-6789",
        spouse_ssn="",
        address="1 Analytical Engine Way",
        address_city="London",
        address_state="",
        address_zip="",
        **overrides,
    )
    return SimpleNamespace(config=config)


class ComputeBalanceDueTests(unittest.TestCase):
    def test_positive_balance_due(self):
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=3000), 2000)

    def test_zero_when_overpaid(self):
        # Refund case: 4868 always reports 0, never a negative balance due.
        self.assertEqual(compute_balance_due(total_tax=3000, total_payments=5000), 0)

    def test_zero_when_exactly_matched(self):
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=5000), 0)

    def test_handles_none_total_payments(self):
        # Engine may return None for 1099/other withholding fields. A missing
        # payment OVERSTATES the balance due, which is the safe direction on a
        # payment form; a missing TAX understates it, which is why that side
        # raises instead (see below).
        self.assertEqual(compute_balance_due(total_tax=5000, total_payments=None), 5000)

    def test_none_total_tax_raises_rather_than_reporting_zero_owed(self):
        """A `None` tax must RAISE, not fall open to a $0 balance due.

        The former `total_tax or 0` answered "you owe nothing" on a return
        whose tax we failed to compute — on the form whose line 6 the filer
        pays from. The message must name WHICH input was missing, so the
        failure is actionable rather than a bare arithmetic TypeError.
        """
        with self.assertRaises(ValueError) as ctx:
            compute_balance_due(total_tax=None, total_payments=3000)
        self.assertIn("total_tax", str(ctx.exception))

    def test_none_total_tax_raises_even_when_payments_would_cover_it(self):
        # The fail-open was invisible precisely in the refund-shaped case: with
        # payments present, `None or 0` produced a legitimate-looking 0.
        with self.assertRaises(ValueError):
            compute_balance_due(total_tax=None, total_payments=99_000)


class ComposeLine24Tests(unittest.TestCase):
    """IRS Form 1040 line 24 is composed, not one number.

    Verified against every shipped vendor workbook (2021-2025); the 2025
    cells are quoted here, the other four years are the same formulas at
    different addresses (pinned per-year in tests/test_f1040_mapping.py):

        AL102 (line 22) = IF(<override>, ..., MAX(0, SUM(Tax, -AL101)))
        AL103 (line 23) = TotalOtherTaxes
        AL104 (line 24) = SUM(AL102, AL103)

    where `Tax` is line 18 and AL101 is line 21 (total nonrefundable
    credits). The ZERO FLOOR sits on (line 18 - credits) and NOTHING ELSE.
    """

    def test_ordinary_case_sums_all_three_parts(self):
        self.assertEqual(
            compose_line_24(
                line_16=69_035,
                schedule_2_part_i=4_800,
                nonrefundable_credits=0,
                schedule_2_part_ii=900,
            ),
            74_735,
        )

    def test_credits_reduce_line_22_but_never_below_zero(self):
        # Credits (12,000) exceed line 18 (10,000 + 500): line 22 floors at 0.
        self.assertEqual(
            compose_line_24(
                line_16=10_000,
                schedule_2_part_i=500,
                nonrefundable_credits=12_000,
                schedule_2_part_ii=0,
            ),
            0,
        )

    def test_floor_applies_before_part_ii_is_added(self):
        """THE FLOOR TRAP, pinned.

        Credits (12,000) exceed line 18 (10,500), so line 22 = 0 and line 24
        is the Schedule 2 Part II tax alone: 900.

        Flooring the WHOLE thing after adding Part II instead would give
        max(0, 10,500 - 12,000 + 900) = 0 — it would swallow a Part II tax
        the filer genuinely owes and print a smaller payment voucher.

        This assertion is the difference between the two orders. The inputs
        are chosen so the UNFLOORED line 22 (10,000 + 500 - 12,000 = -1,500)
        is negative, which is the only region where the two orders disagree
        at all. Confirmed live by mutation: applying the floor after Part II
        makes this call return 0.
        """
        self.assertEqual(
            compose_line_24(
                line_16=10_000,
                schedule_2_part_i=500,
                nonrefundable_credits=12_000,
                schedule_2_part_ii=900,
            ),
            900,
        )

    def test_credits_do_not_reach_part_ii_when_line_22_stays_positive(self):
        # Complementary direction: with the floor slack, credits subtract
        # normally and Part II still rides on top.
        self.assertEqual(
            compose_line_24(
                line_16=10_000,
                schedule_2_part_i=500,
                nonrefundable_credits=2_000,
                schedule_2_part_ii=900,
            ),
            9_400,
        )


class TotalTaxLiabilityLine24SourceTests(unittest.TestCase):
    """Which of the two paths supplies line 24, and how each is detected."""

    def test_harvested_key_wins_over_composition(self):
        # Workbook path: `Tot_Tax` is harvested whole. It legitimately
        # DIFFERS from the composition (it includes NIIT and AMT, which the
        # native spine cannot compute), so it must not be recomputed from the
        # parts that happen to sit beside it in the same dict.
        harvested = total_tax_liability_line_24({
            "tax_liability_line24": 88_000,
            "total_tax": 69_035,
            "f8962_repayment": 4_800,
            "f8959_tax_total": 900,
        })
        self.assertEqual(harvested, 88_000)

    def test_composes_when_no_harvested_key_is_present(self):
        composed = total_tax_liability_line_24({
            "total_tax": 69_035,
            "f8962_repayment": 4_800,
            "f8959_tax_total": 900,
        })
        self.assertEqual(composed, 74_735)

    def test_composition_reads_nonrefundable_credits_when_present(self):
        composed = total_tax_liability_line_24({
            "total_tax": 10_000,
            "f8962_repayment": 500,
            "nonrefundable_credits": 12_000,
            "f8959_tax_total": 900,
        })
        self.assertEqual(composed, 900)

    def test_missing_line_16_yields_none_so_the_balance_due_raise_names_it(self):
        self.assertIsNone(total_tax_liability_line_24({}))


class F4868ComputeTests(unittest.TestCase):
    def test_produces_pdf_ready_keys(self):
        scenario = _scenario()
        upstream = {"f1040": {"total_tax": 5000, "total_payments": 3000}}
        result = compute(scenario, upstream)
        self.assertEqual(result["full_name"], "Ada Lovelace")
        self.assertEqual(result["ssn"], "000-45-6789")
        self.assertEqual(result["spouse_ssn"], "")
        self.assertEqual(result["address"], "1 Analytical Engine Way")
        self.assertEqual(result["address_city"], "London")
        self.assertEqual(result["address_state"], "")
        self.assertEqual(result["address_zip"], "")
        self.assertEqual(result["estimated_total_tax"], 5000)
        self.assertEqual(result["total_payments"], 3000)
        self.assertEqual(result["balance_due"], 2000)
        self.assertEqual(result["amount_paying_with_extension"], 0)
        self.assertEqual(result["voucher_amount"], 2000)

    def test_refund_case_zeroes_balance(self):
        scenario = _scenario()
        upstream = {"f1040": {"total_tax": 3000, "total_payments": 5000}}
        result = compute(scenario, upstream)
        self.assertEqual(result["balance_due"], 0)
        self.assertEqual(result["voucher_amount"], 0)

    def test_line_4_uses_the_harvested_workbook_line_24(self):
        """Workbook path: line 4 is `Tot_Tax`, not `Tax_SubTotal`.

        IRS Form 4868, "Line 4—Estimate of Total Tax Liability for 2025"
        (pdfs/federal/2025/f4868.pdf), verbatim:

            "Enter on line 4 the total tax liability you expect to report on
            your 2025:
            • Form 1040, 1040-SR, or 1040-NR, line 24; or
            • Form 1040-SS, Part I, line 7.
            If you expect this amount to be zero, enter -0-."

        `total_tax` is 1040 line 16, so reading it raw for line 4 leaves out
        every Schedule 2 tax the filer owes.
        """
        upstream = {"f1040": {
            "tax_liability_line24": 74_735,
            "total_tax": 69_035,
            "total_payments": 60_000,
        }}
        result = compute(_scenario(), upstream)
        self.assertEqual(result["estimated_total_tax"], 74_735)
        self.assertEqual(result["balance_due"], 14_735)
        self.assertEqual(result["voucher_amount"], 14_735)

    def test_missing_total_tax_raises_before_any_field_is_emitted(self):
        with self.assertRaises(ValueError) as ctx:
            compute(_scenario(), {"f1040": {"total_payments": 3000}})
        self.assertIn("total_tax", str(ctx.exception))


def _native_scenario(wages: float, withheld: float, form_1095a) -> Scenario:
    """Single filer well above the EIC ceiling, so it routes to the native
    1040 spine (orchestrator._scenario_in_spine_scope)."""
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="TX",
            **scope_out_attestation_defaults(),
        ),
        w2s=[
            W2(
                employer="Acme Corp",
                wages=wages,
                federal_tax_withheld=withheld,
                ss_wages=176_100,
                ss_tax_withheld=round(176_100 * 0.062),
                medicare_wages=wages,
                medicare_tax_withheld=round(wages * 0.0145),
            ),
        ],
        form_1095a=form_1095a,
    )


class F4868NativePathLine24Tests(unittest.TestCase):
    """End-to-end on the native spine, with BOTH Schedule 2 parts nonzero.

    IRS Form 4868, "Line 4—Estimate of Total Tax Liability for 2025"
    (pdfs/federal/2025/f4868.pdf), verbatim:

        "Enter on line 4 the total tax liability you expect to report on your
        2025:
        • Form 1040, 1040-SR, or 1040-NR, line 24; or
        • Form 1040-SS, Part I, line 7.
        If you expect this amount to be zero, enter -0-."

    $300k of wages triggers Form 8959 Additional Medicare Tax (Schedule 2
    PART II) and a 12-month Form 1095-A with APTC far above entitlement
    triggers the excess-APTC repayment (Schedule 2 PART I). Line 4 must carry
    both; reading `total_tax` raw carries neither.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )
        block = Form1095A(months=tuple(
            Form1095AMonth(premium=500, slcsp=500, aptc=400) for _ in range(12)
        ))
        self.scenario = _native_scenario(300_000, 60_000, block)
        self.results = orch.compute_federal(self.scenario)
        self.f4868 = compute(self.scenario, {"f1040": self.results})

    def test_both_schedule_2_parts_are_actually_nonzero(self):
        # Guard: without this the line-4 assertion below would pass even if
        # line 4 were still plain line 16.
        self.assertGreater(self.results["f8962_repayment"], 0)
        self.assertGreater(self.results["f8959_tax_total"], 0)

    def test_line_4_is_line_16_plus_both_schedule_2_parts(self):
        self.assertEqual(
            self.f4868["estimated_total_tax"],
            self.results["total_tax"]
            + self.results["f8962_repayment"]
            + self.results["f8959_tax_total"],
        )

    def test_line_4_strictly_exceeds_line_16(self):
        # The defect being removed, stated as a bare inequality.
        self.assertGreater(
            self.f4868["estimated_total_tax"], self.results["total_tax"])

    def test_line_6_balance_due_follows_from_line_4_not_line_16(self):
        expected = (
            self.f4868["estimated_total_tax"] - self.results["total_payments"])
        self.assertGreater(expected, 0)  # a real balance due, not the floor
        self.assertEqual(self.f4868["balance_due"], expected)

    def test_voucher_amount_is_the_line_24_balance_not_the_line_16_one(self):
        """The figure the filer actually pays; understating it is the
        penalty-and-interest direction.

        Asserted against the 1040's own parts, NOT against
        `self.f4868["balance_due"]`: `compute` assigns both keys from the same
        local, so comparing them to each other could not fail however badly
        line 4 regressed.
        """
        line_24 = (
            self.results["total_tax"]
            + self.results["f8962_repayment"]
            + self.results["f8959_tax_total"]
        )
        self.assertEqual(
            self.f4868["voucher_amount"],
            line_24 - self.results["total_payments"],
        )
        # And that is strictly more than the line-16-based voucher this task
        # removed — the $5,700 of Schedule 2 the filer used to be told to skip.
        self.assertGreater(
            self.f4868["voucher_amount"],
            self.results["total_tax"] - self.results["total_payments"],
        )

    def test_line_5_is_the_1040_total_payments(self):
        self.assertEqual(
            self.f4868["total_payments"], self.results["total_payments"])


class Expected4868PdfValuesTests(unittest.TestCase):
    """`tests/invariants.py::expected_4868_pdf_values`, on the standard gate.

    That function is the oracle behind `assert_4868_fills_correctly`, and it
    BRANCHES BY PATH: on the workbook path it compares against the harvested
    `Tot_Tax`, on the native path against production's composition. Its three
    live callers are all `@needs_libreoffice`, and — verified against the
    fixtures and `orchestrator._scenario_in_spine_scope` — NONE of them
    currently reaches the workbook branch:

      - `test_e2e_simple_w2.py` (simple_w2.yaml) and `test_e2e_itemized.py`
        (itemized_deductions.yaml) are SINGLE filers with
        `_scenario_in_spine_scope` True, so they route NATIVE.
      - `test_deduction_outputs.py::TestStandardDeductionMFJ` (mfj_simple.yaml)
        is the only workbook-path caller, and it is `xfail(strict=True)`,
        dying in `setUpClass` on the `Deduction`-diagnostic refusal before any
        assertion runs.

    So the branch that carries the honest, independent oracle is the one no
    executing test touches. This class closes that: `expected_4868_pdf_values`
    is a pure dict->dict function, so injected dicts exercise both arms here,
    on the always-running `-m "not oracle"` gate, with no LibreOffice. Guard
    and oracle LOGIC belongs on that gate; only soffice plumbing may sit
    behind the oracle marker.
    """

    # A harvest that DISAGREES with the composition of its sibling keys, in
    # exactly the shape the real disagreement takes: the workbook's line 23
    # (`TotalOtherTaxes`) carries self-employment tax and NIIT, for which the
    # native composition has no term at all, in all five workbook years.
    _NIIT_AND_SE_TAX = 6_500

    def _workbook_results(self) -> dict:
        parts = {"total_tax": 69_035, "f8962_repayment": 4_800,
                 "f8959_tax_total": 900, "total_payments": 60_000}
        return {
            "tax_liability_line24": (
                69_035 + 4_800 + 900 + self._NIIT_AND_SE_TAX),
            **parts,
        }

    def _native_results(self) -> dict:
        return {k: v for k, v in self._workbook_results().items()
                if k != "tax_liability_line24"}

    def test_workbook_branch_uses_the_harvested_tot_tax(self):
        got = expected_4868_pdf_values(self._workbook_results())
        self.assertEqual(got["estimated_total_tax"], "81235")
        self.assertEqual(got["balance_due"], "21235")

    def test_native_branch_uses_the_composition(self):
        got = expected_4868_pdf_values(self._native_results())
        self.assertEqual(got["estimated_total_tax"], "74735")
        self.assertEqual(got["balance_due"], "14735")

    def test_workbook_branch_differs_from_the_native_composition(self):
        """THE assertion the branch exists for.

        The two dicts differ ONLY by the presence of `tax_liability_line24`.
        If this helper ever stopped honouring the harvest — the same silent
        fallback that `TestF1040TotalTaxLiabilityLine24::
        test_named_range_exists_in_every_workbook` guards on the mapping side
        — the two would collapse to the same number and the oracle would go
        on passing while silently checking the wrong quantity.

        Both sides are pinned to their actual values as well as being asserted
        unequal, so a change that accidentally equalises them fails with the
        numbers rather than a bare NotEqual.
        """
        workbook = expected_4868_pdf_values(self._workbook_results())
        native = expected_4868_pdf_values(self._native_results())
        self.assertNotEqual(
            workbook["estimated_total_tax"], native["estimated_total_tax"])
        self.assertEqual(workbook["estimated_total_tax"], "81235")
        self.assertEqual(native["estimated_total_tax"], "74735")
        self.assertEqual(
            int(workbook["estimated_total_tax"])
            - int(native["estimated_total_tax"]),
            self._NIIT_AND_SE_TAX,
        )

    def test_rounds_the_whole_value_once_not_each_part(self):
        """Matches the RENDERER, which rounds once.

        `filing/pdf.py::PdfFiller._render_scalar` is `str(irs_round(value))`,
        so the printed figure is one half-up rounding of the whole amount.
        69,035.4 + 4,800.4 + 900.4 = 74,736.2 -> 74,736. The old helper
        rounded each part first and would print 74,735 — a dollar low.

        (This is NOT because the workbook rounds the total. It does not:
        `Tot_Tax` is a bare `SUM(<line 22>, <line 23>)` with no `ROUND` in any
        of the five years.)
        """
        got = expected_4868_pdf_values({
            "total_tax": 69_035.4,
            "f8962_repayment": 4_800.4,
            "f8959_tax_total": 900.4,
            "total_payments": 60_000,
        })
        self.assertEqual(got["estimated_total_tax"], "74736")

    def test_rendering_is_irs_half_up_not_bankers(self):
        # Python's built-in round() is half-to-even and gives 74,734 here;
        # irs_round gives 74,735. The old helper used int(round(...)).
        got = expected_4868_pdf_values(
            {"tax_liability_line24": 74_734.5, "total_payments": 0})
        self.assertEqual(got["estimated_total_tax"], "74735")

    def test_refund_case_floors_the_balance_at_zero(self):
        got = expected_4868_pdf_values(
            {"total_tax": 3_000, "total_payments": 5_000})
        self.assertEqual(got["balance_due"], "0")
        self.assertEqual(got["amount_paying_with_extension"], "0")

    def test_missing_line_24_raises_rather_than_asserting_zero_owed(self):
        # Inherited from compute_balance_due: a results dict with no tax at
        # all must not quietly produce a "$0 balance due" expectation that a
        # broken emit would then match.
        with self.assertRaises(ValueError) as ctx:
            expected_4868_pdf_values({"total_payments": 5_000})
        self.assertIn("total_tax", str(ctx.exception))


class ExtensionPaymentFieldAbsenceTests(unittest.TestCase):
    """4868 line 5 must EXCLUDE Schedule 3 line 10, and does so VACUOUSLY.

    IRS Form 4868, "Line 5—Estimate of Total Payments for 2025"
    (pdfs/federal/2025/f4868.pdf), verbatim:

        "Enter on line 5 the total payments you expect to report on your
        2025:
        • Form 1040, 1040-SR, or 1040-NR, line 33 (excluding Schedule 3,
        line 10); or
        • Form 1040-SS, Part I, line 12 (excluding Part I, line 9)."

    Schedule 3 line 10 is "Amount paid with request for extension to file".
    tenforty's line 5 is 1040 line 33 with NO such exclusion applied — it is
    compliant only because no extension payment can enter the model at all:
    the spine's `total_payments` is federal_withheld + estimated_payments +
    f8962_net_ptc, and no extension-payment field exists on ANY scenario
    model. That is a LATENT condition, not a design: the day such a field is
    added, 1040 line 33 picks it up and 4868 line 5 silently violates the
    instruction. This test is the tripwire on that day.
    """

    # Substrings that any extension-payment field name would have to carry.
    _EXTENSION_PAYMENT_TOKENS = ("extension", "4868", "paid_with_request")

    @classmethod
    def _matched_tokens(cls, field_name: str) -> list[str]:
        lowered = field_name.lower()
        return [t for t in cls._EXTENSION_PAYMENT_TOKENS if t in lowered]

    def _model_fields(self) -> dict[str, set[str]]:
        """Every dataclass field name declared in tenforty.models, with the
        model(s) declaring it."""
        found: dict[str, set[str]] = {}
        for attr_name in dir(models):
            obj = getattr(models, attr_name)
            if not (isinstance(obj, type) and dataclasses.is_dataclass(obj)):
                continue
            for field in dataclasses.fields(obj):
                found.setdefault(field.name, set()).add(attr_name)
        return found

    def test_the_detector_is_not_vacuous(self):
        """Reachability control: prove the matcher CAN fire.

        Without this, emptying `_EXTENSION_PAYMENT_TOKENS` (or misspelling
        every entry) would leave the absence test below passing forever while
        detecting nothing.
        """
        for plausible_name in (
            "extension_payment",
            "amount_paid_with_extension",
            "paid_with_4868",
            "paid_with_request_for_extension",
        ):
            with self.subTest(field=plausible_name):
                self.assertTrue(
                    self._matched_tokens(plausible_name),
                    f"detector missed {plausible_name!r}",
                )

    def test_the_detector_does_not_fire_on_unrelated_payment_fields(self):
        # The models DO carry payment fields; the matcher must distinguish
        # them from extension payments or the test below would already fail.
        for benign in (
            "estimated_tax_payments",
            "federal_tax_withheld",
            "prior_year_overpayment_applied",
        ):
            with self.subTest(field=benign):
                self.assertEqual([], self._matched_tokens(benign))

    def test_the_models_scan_actually_sees_real_fields(self):
        # Guard against a scan that silently finds nothing (e.g. if models
        # stopped being dataclasses), which would make the absence assertion
        # below trivially true.
        fields = self._model_fields()
        self.assertIn("estimated_tax_payments", fields)
        self.assertIn("TaxReturnConfig", fields["estimated_tax_payments"])

    def test_no_extension_payment_field_exists_on_any_scenario_model(self):
        offenders = {
            name: sorted(owners)
            for name, owners in self._model_fields().items()
            if self._matched_tokens(name)
        }
        self.assertEqual(
            {}, offenders,
            "An extension-payment field appeared on a scenario model: "
            f"{offenders}. Form 4868 line 5 is 1040 line 33 EXCLUDING "
            "Schedule 3 line 10, and tenforty applies no such exclusion — it "
            "has been compliant only because this field could not exist. "
            "Subtract the extension payment from f4868's line 5 (and add the "
            "exclusion to forms/f4868.py's line-5 comment) before landing "
            "this field.",
        )


if __name__ == "__main__":
    unittest.main()
