"""Shared structural invariants for end-to-end tax return tests.

Each function asserts a property that must hold for any valid tax return,
regardless of the specific dollar amounts. Functions take a unittest.TestCase
as the first argument so they can use self.assertEqual, self.assertGreater, etc.
"""

import unittest
from pathlib import Path

from pypdf import PdfReader

from tenforty.filing.pdf import PdfFiller
from tenforty.models import Scenario
from tenforty.result_translator import ResultTranslator, TranslationSpec


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


def assert_withholding_matches_input(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
) -> None:
    """Federal withholding in results should match sum of W-2 withholding."""
    expected = sum(w2.federal_tax_withheld for w2 in scenario.w2s)
    actual = results.get("federal_withheld")
    test.assertIsNotNone(actual, "Federal withholding is missing from results")
    test.assertEqual(
        float(actual), expected,
        f"Withholding mismatch: engine={actual}, scenario sum={expected}",
    )


def verify_pdf_round_trip(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
    translation_spec: TranslationSpec,
    pdf_mapping_cls: type,
    pdf_template: Path,
    year: int,
    work_dir: Path,
) -> None:
    """Verify that engine results survive the full pipeline to the PDF.

    Runs: translate -> fill PDF -> read back -> compare every field.
    Reports mismatches and coverage gaps.
    """
    translator = ResultTranslator(translation_spec)
    translated = translator.translate(results, scenario)

    filler = PdfFiller()
    output_pdf = work_dir / "round_trip_verify.pdf"
    mapping = pdf_mapping_cls.get_mapping(year)
    filler.fill(pdf_template, output_pdf, mapping, translated)

    reader = PdfReader(output_pdf)
    pdf_fields = reader.get_fields()

    mismatches: list[str] = []
    gaps: list[str] = []
    verified_count = 0

    # Check: do filled fields match?
    for our_key, pdf_field_name in mapping.items():
        translated_value = translated.get(our_key)
        if translated_value is None:
            continue

        expected_str = str(translated_value)
        actual_str = pdf_fields.get(pdf_field_name, {}).get("/V", "")

        if actual_str != expected_str:
            mismatches.append(
                f"  {our_key}: expected '{expected_str}', "
                f"got '{actual_str}' (PDF field: {pdf_field_name})"
            )
        else:
            verified_count += 1

    # Check: are there translated keys with no PDF mapping? (coverage gaps)
    mapped_keys = set(mapping.keys())
    for key, value in translated.items():
        if value is not None and key not in mapped_keys:
            gaps.append(f"  {key}={value} (no PDF mapping)")

    errors: list[str] = []
    if mismatches:
        errors.append(
            f"{len(mismatches)} field(s) did not round-trip correctly:\n"
            + "\n".join(mismatches)
        )
    if gaps:
        errors.append(
            f"{len(gaps)} translated key(s) have no PDF mapping (coverage gaps):\n"
            + "\n".join(gaps)
        )
    if errors:
        test.fail("\n\n".join(errors))
