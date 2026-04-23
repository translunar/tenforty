"""Shared structural invariants for end-to-end tax return tests.

Each function asserts a property that must hold for any valid tax return,
regardless of the specific dollar amounts. Functions take a unittest.TestCase
as the first argument so they can use self.assertEqual, self.assertGreater, etc.
"""

import sys
import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.models import Scenario


def assert_agi_consistent(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
) -> None:
    """AGI should equal the sum of all income sources present in the scenario."""
    expected_income = 0.0

    for w2 in scenario.w2s:
        expected_income += w2.wages

    for f in scenario.form1099_int:
        expected_income += f.interest

    for f in scenario.form1099_div:
        expected_income += f.ordinary_dividends
        expected_income += f.capital_gain_distributions

    agi = results.get("agi")
    test.assertIsNotNone(agi, "AGI is missing from results")
    test.assertLessEqual(
        float(agi), expected_income + 1,
        f"AGI ({agi}) exceeds total income ({expected_income})",
    )
    test.assertGreater(float(agi), 0, "AGI should be positive for scenarios with income")


def assert_taxable_income_consistent(
    test: unittest.TestCase,
    results: dict[str, object],
) -> None:
    """Taxable income must be non-negative and cannot exceed AGI."""
    taxable = results.get("taxable_income")
    test.assertIsNotNone(taxable, "Taxable income is missing from results")
    test.assertGreaterEqual(float(taxable), 0, "Taxable income cannot be negative")

    agi = results.get("agi")
    if agi is not None:
        test.assertLessEqual(
            float(taxable), float(agi),
            "Taxable income cannot exceed AGI",
        )


def assert_tax_is_non_negative(
    test: unittest.TestCase,
    results: dict[str, object],
) -> None:
    """Total tax must be zero or positive."""
    tax = results.get("total_tax")
    test.assertIsNotNone(tax, "Total tax is missing from results")
    test.assertGreaterEqual(float(tax), 0, "Tax cannot be negative")


def assert_refund_or_owed_consistent(
    test: unittest.TestCase,
    results: dict[str, object],
) -> None:
    """If overpaid > 0, then total_payments must exceed total_tax."""
    payments = results.get("total_payments")
    tax = results.get("total_tax")
    overpaid = results.get("overpaid", 0)

    test.assertIsNotNone(payments, "Total payments is missing from results")
    test.assertIsNotNone(tax, "Total tax is missing from results")

    if float(overpaid) > 0:
        test.assertGreater(
            float(payments), float(tax),
            f"Overpaid is {overpaid} but payments ({payments}) <= tax ({tax})",
        )
    else:
        test.assertLessEqual(
            float(payments), float(tax),
            f"Overpaid is 0 but payments ({payments}) > tax ({tax})",
        )


def assert_all_income_accounted_for(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
) -> None:
    """AGI should account for all income sources in the scenario.

    Computes a minimum expected income from all scenario data (wages,
    interest, dividends, capital gains, K-1 income). AGI can be lower
    than this due to adjustments, but if it's dramatically lower,
    income was probably silently dropped.

    Uses a threshold of 50% of expected non-wage income to allow for
    adjustments and losses while still catching completely missing forms.
    """
    agi = results.get("agi")
    test.assertIsNotNone(agi, "AGI is missing from results")
    agi_float = float(agi)

    # Sum all income sources the scenario claims to have
    wage_income = sum(w2.wages for w2 in scenario.w2s)
    interest_income = sum(f.interest for f in scenario.form1099_int)
    dividend_income = sum(f.ordinary_dividends for f in scenario.form1099_div)
    capital_gains = sum(f.gain_loss for f in scenario.form1099_b)
    k1_income = sum(
        k.ordinary_income + k.rental_income + k.interest_income + k.dividend_income
        for k in scenario.schedule_k1s
    )

    non_wage_income = interest_income + dividend_income + capital_gains + k1_income

    # AGI must be at least wages + 50% of non-wage income.
    # The 50% threshold accounts for adjustments, but catches
    # completely missing forms (which would be 0% of expected).
    minimum_agi = wage_income + (non_wage_income * 0.5)

    test.assertGreaterEqual(
        agi_float, minimum_agi,
        f"AGI ({agi_float:,.0f}) is suspiciously low. "
        f"Expected at least {minimum_agi:,.0f} "
        f"(wages={wage_income:,.0f} + 50% of non-wage={non_wage_income:,.0f}). "
        f"Was income from a form silently dropped?",
    )


def assert_w2_withholding_matches_input(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
) -> None:
    """W-2 (line 25a) withholding in results should match sum of W-2 withholding.

    Post-Task-6, `federal_withheld` is the 25d total (25a + 25b + 25c).
    This invariant specifically checks 25a — the W-2 portion — which is
    stored under `federal_withheld_w2` after forms.f1040.compute.
    """
    expected = sum(w2.federal_tax_withheld for w2 in scenario.w2s)
    actual = results.get("federal_withheld_w2")
    test.assertIsNotNone(actual, "W-2 federal withholding is missing from results")
    test.assertEqual(
        float(actual), expected,
        f"W-2 withholding mismatch: engine={actual}, scenario sum={expected}",
    )


def verify_pdf_round_trip(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
    pdf_mapping_cls: type,
    pdf_template: Path,
    year: int,
    work_dir: Path,
) -> None:
    """Verify that engine results survive the full pipeline to the PDF.

    Runs: fill PDF -> read back -> compare every field.
    Reports mismatches and coverage gaps.
    """
    pdf_values = results

    filler = PdfFiller()
    output_pdf = work_dir / "round_trip_verify.pdf"
    mapping = pdf_mapping_cls.get_mapping(year)
    filler.fill(pdf_template, output_pdf, mapping, pdf_values)

    reader = PdfReader(output_pdf)
    pdf_fields = reader.get_fields()

    mismatches: list[str] = []
    gaps: list[str] = []
    verified_count = 0

    # Check: do filled fields match?
    for our_key, pdf_field_name in mapping.items():
        value = pdf_values.get(our_key)
        if value is None:
            continue

        expected_str = str(value)
        field_obj = pdf_fields.get(pdf_field_name)
        if field_obj is not None:
            raw = field_obj.get("/V", "")
            actual_str = str(raw) if raw is not None else ""
        else:
            actual_str = ""

        if actual_str != expected_str:
            mismatches.append(
                f"  {our_key}: expected '{expected_str}', "
                f"got '{actual_str}' (PDF field: {pdf_field_name})"
            )
        else:
            verified_count += 1

    # Check: are there result keys with no PDF mapping? (coverage gaps)
    mapped_keys = set(mapping.keys())
    for key, value in pdf_values.items():
        if value is not None and key not in mapped_keys:
            gaps.append(f"  {key}={value} (no PDF mapping)")

    # Mismatches are errors — wrong values in the PDF
    if mismatches:
        test.fail(
            f"{len(mismatches)} field(s) did not round-trip correctly:\n"
            + "\n".join(mismatches)
        )

    # Gaps are informational — engine outputs for other forms (e.g., Schedule E
    # values that belong on a different PDF) are expected. Print but don't fail.
    if gaps:
        print(
            f"\n  [{len(gaps)} coverage gap(s) — result keys with no PDF mapping "
            f"(expected for cross-form values)]:",
            file=sys.stderr,
        )
        for gap in gaps:
            print(f"    {gap}", file=sys.stderr)


def assert_4868_fills_correctly(
    testcase,
    results: dict,
    config_with_personal,
    output_dir,
) -> None:
    """Emit a 4868 from results + config, re-read it, assert lines 4/5/6/7.

    Line 4 = results['total_tax']
    Line 5 = results['total_payments']
    Line 6 = max(0, line_4 − line_5)
    Line 7 = 0 (default — no amount paid with extension in the fixture path)

    ASSUMES personal-info fields populated on config. This helper patches a copy
    of the scenario's config in memory; it does not mutate the caller's scenario.
    """
    import tempfile

    from tenforty.forms.f4868 import compute_balance_due
    from tenforty.mappings.pdf_4868 import Pdf4868
    from tenforty.models import Scenario
    from tenforty.orchestrator import ReturnOrchestrator

    REPO_ROOT = Path(__file__).parent.parent
    spreadsheets_dir = REPO_ROOT / "spreadsheets"

    orchestrator = ReturnOrchestrator(
        spreadsheets_dir=spreadsheets_dir,
        work_dir=Path(tempfile.mkdtemp()),
    )

    scenario = Scenario(config=config_with_personal, w2s=[])
    year = config_with_personal.year

    orchestrator.emit_pdfs(scenario, results, output_dir)

    out_4868 = output_dir / f"f4868_{year}.pdf"
    reader = PdfReader(out_4868)
    fields = reader.get_fields()

    mapping = Pdf4868.get_mapping(year)

    total_tax = int(round(float(results.get("total_tax", 0))))
    total_payments = int(round(float(results.get("total_payments", 0))))
    balance_due = compute_balance_due(total_tax, total_payments)

    expected = {
        "estimated_total_tax": str(total_tax),
        "total_payments": str(total_payments),
        "balance_due": str(balance_due),
        "amount_paying_with_extension": "0",
        "voucher_amount": str(balance_due),
    }

    for key, expected_val in expected.items():
        pdf_field = mapping[key]
        field_obj = fields.get(pdf_field)
        actual = str(field_obj.get("/V", "")) if field_obj is not None else ""
        testcase.assertEqual(
            actual,
            expected_val,
            f"4868 field '{key}' (PDF: {pdf_field}): expected '{expected_val}', got '{actual}'",
        )


def assert_sch_d_no_double_count(
    test: unittest.TestCase,
    results: dict,
    *,
    total_scenario_proceeds: float,
) -> None:
    """Sch D line 1a/1b/2/3/8a/8b/9/10 proceeds must sum to exactly the total
    1099-B proceeds for the scenario. Catches lot-partitioning bugs where a
    lot ends up on two lines (over-counted) or zero lines (dropped)."""
    short_lines = ("1a", "1b", "2", "3")
    long_lines = ("8a", "8b", "9", "10")
    total = sum(
        int(results.get(f"sch_d_line_{ln}_proceeds", 0))
        for ln in (*short_lines, *long_lines)
    )
    test.assertEqual(
        total, int(total_scenario_proceeds),
        f"Sch D double-count: lines sum to {total} but scenario had "
        f"{total_scenario_proceeds} total 1099-B proceeds",
    )


def assert_deduction_choice_consistent(testcase, results: dict) -> None:
    """Assert total_deductions equals max(standard_deduction, schedule_a_total).

    ASSUMES filing status not in {MFS-forced-itemize, dependent, dual-status/NRA}.
    MFS where the other spouse itemizes forces itemization regardless of which
    amount is larger; dependents get a reduced standard deduction (earned income
    + $450, capped at the regular standard); dual-status/NRA filers cannot claim
    the standard deduction. tenforty does not model these cases today.
    """
    std = int(results.get("standard_deduction") or 0)
    sch_a = int(results.get("schedule_a_total") or 0)
    applied = int(results.get("total_deductions") or 0)
    testcase.assertEqual(
        applied, max(std, sch_a),
        f"Expected total_deductions=max(standard={std}, schedule_a={sch_a}) "
        f"but got {applied}. If this filer is MFS-forced-itemize, a dependent, "
        f"or dual-status/NRA, this invariant does not apply and the test should "
        f"be suppressed rather than weakened.",
    )
