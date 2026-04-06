"""Shared structural invariants for end-to-end tax return tests.

Each function asserts a property that must hold for any valid tax return,
regardless of the specific dollar amounts. Functions take a unittest.TestCase
as the first argument so they can use self.assertEqual, self.assertGreater, etc.
"""

import unittest

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
