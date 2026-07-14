"""Task 4 — Form 8962 (PTC) wiring into the 1040 spine + orchestrator.

Exercises the four seams the brief specifies at the integration level
(``ReturnOrchestrator.compute_federal``), which is the only place all of
them are visible at once: the orchestrator computes Form 8962 after AGI is
known and threads ``f8962_net_ptc`` into ``total_payments`` and
``f8962_repayment`` into ``overpaid`` — while keeping the line-16-only
``total_tax`` untouched (exactly how f8959 is handled).

All scenarios are synthetic single filers. Net-PTC / repayment scenarios
sit ABOVE the year's EIC income ceiling (single, 0 children = $26,214 for
2025) so they route to the native spine; the EIC-conflict scenario sits
below it so the routing refusal fires.
"""

import tempfile
import unittest
from pathlib import Path

from dataclasses import replace

from tenforty.models import (
    Form1095A,
    Form1095AMonth,
    Form1099INT,
    Scenario,
    TaxReturnConfig,
    W2,
)
from tenforty.orchestrator import ReturnOrchestrator
from tests.helpers import scope_out_attestation_defaults

REPO_ROOT = Path(__file__).parent.parent


def _scenario(wages: float, withheld: float, form_1095a=None) -> Scenario:
    """Single-filer W-2-only scenario. AGI == wages (no adjustments), so the
    8962 MAGI the orchestrator derives is wages + block.tax_exempt_interest."""
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
                ss_wages=wages,
                ss_tax_withheld=round(wages * 0.062),
                medicare_wages=wages,
                medicare_tax_withheld=round(wages * 0.0145),
            ),
        ],
        form_1095a=form_1095a,
    )


def _months(premium: float, slcsp: float, aptc: float) -> tuple[Form1095AMonth, ...]:
    return tuple(
        Form1095AMonth(premium=premium, slcsp=slcsp, aptc=aptc) for _ in range(12)
    )


class F8962SpineWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.orch = ReturnOrchestrator(
            spreadsheets_dir=REPO_ROOT / "spreadsheets",
            work_dir=Path(self._tmp.name) / "work",
        )

    def test_a_net_ptc_adds_to_payments_and_leaves_total_tax_unchanged(self):
        # aptc=0 but real entitlement (premium/slcsp $500/mo) → net PTC > 0.
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=0))
        with_block = self.orch.compute_federal(_scenario(30_000, 2_000, block))
        without = self.orch.compute_federal(_scenario(30_000, 2_000, None))

        # Net PTC computed and nonzero; no repayment on this scenario.
        self.assertGreater(with_block["f8962_net_ptc"], 0)
        self.assertEqual(with_block["f8962_repayment"], 0)

        # Net PTC (Sch 3 line 9 → total other payments) adds into total_payments.
        self.assertEqual(with_block["federal_withheld"], without["federal_withheld"])
        self.assertEqual(
            with_block["total_payments"],
            without["total_payments"] + with_block["f8962_net_ptc"],
        )

        # total_tax is line-16 income tax ONLY — the PTC must NOT change it.
        self.assertEqual(with_block["total_tax"], without["total_tax"])

        # Detail key family passes through only when the block was computed.
        self.assertIn("f8962_line_24", with_block)
        self.assertIn("f8962_line_26_net_ptc", with_block)
        self.assertNotIn("f8962_line_24", without)

    def test_b_repayment_reduces_overpaid_not_total_tax(self):
        # High APTC ($400/mo) with small entitlement → excess-APTC repayment.
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=400))
        with_block = self.orch.compute_federal(_scenario(55_000, 8_000, block))
        without = self.orch.compute_federal(_scenario(55_000, 8_000, None))

        repayment = with_block["f8962_repayment"]
        self.assertGreater(repayment, 0)
        self.assertEqual(with_block["f8962_net_ptc"], 0)

        # Guard: base overpaid must exceed the repayment so the reduction is a
        # real subtraction, not clamped at the max(0, ...) floor.
        self.assertGreater(without["overpaid"], repayment)
        self.assertEqual(with_block["overpaid"], without["overpaid"] - repayment)

        # Excess-APTC repayment (Sch 2 line 2) joins overpaid like f8959, but is
        # kept out of the line-16-only total_tax.
        self.assertEqual(with_block["total_tax"], without["total_tax"])

    def test_c_eic_possible_1095a_scenario_refuses_workbook_fallback(self):
        # Wages below the EIC ceiling → out of native-spine scope. With a
        # 1095-A present, silent workbook fallback would drop the PTC, so the
        # orchestrator must refuse rather than route to the (8962-less) workbook.
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=0))
        scenario = _scenario(10_000, 500, block)
        with self.assertRaisesRegex(
            NotImplementedError, "out of native-1040-spine scope",
        ):
            self.orch.compute_federal(scenario)

    def test_d_no_block_emits_zero_summaries_and_no_detail_keys(self):
        results = self.orch.compute_federal(_scenario(30_000, 2_000, None))
        # Summary keys ALWAYS present, 0 with no block (mirrors f8959_*).
        self.assertEqual(results["f8962_net_ptc"], 0)
        self.assertEqual(results["f8962_repayment"], 0)
        # Detail keys absent from the payload the PDF/mapping layer consumes.
        for key in (
            "f8962_line_2a",
            "f8962_line_24",
            "f8962_line_26_net_ptc",
            "f8962_line_29_repayment",
        ):
            self.assertNotIn(key, results)

    def test_e_1099_int_tax_exempt_interest_with_1095a_refuses(self):
        # A Form 1099-INT reporting tax-exempt interest AND a Form 1095-A
        # (PTC) present at once is the double-count/silent-drop hazard: the
        # spine has exactly one sanctioned MAGI-add knob for tax-exempt
        # interest (form_1095a.tax_exempt_interest), and line 2a is
        # unmodeled, so a nonzero Form1099INT.tax_exempt_interest here must
        # refuse rather than silently omit (or double-count) it in PTC MAGI.
        block = Form1095A(months=_months(premium=500, slcsp=500, aptc=0))
        scenario = replace(
            _scenario(30_000, 2_000, block),
            form1099_int=[
                Form1099INT(
                    payer="Bank",
                    interest=0,
                    tax_exempt_interest=100,
                ),
            ],
        )
        with self.assertRaisesRegex(NotImplementedError, "tax-exempt"):
            self.orch.compute_federal(scenario)


if __name__ == "__main__":
    unittest.main()
