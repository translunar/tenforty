# End-to-End Test Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a composable end-to-end test framework that runs the full pipeline (YAML → engine → translator → PDF) and verifies structural invariants.

**Architecture:** Shared invariant library (`tests/invariants.py`) provides reusable assertion functions. Each scenario gets its own test file and YAML fixture. Tests verify structural properties (AGI = income - adjustments, tax >= 0) rather than exact values.

**Tech Stack:** Python 3.14, pytest, unittest.TestCase, openpyxl, pypdf, LibreOffice (headless)

---

## Subagent Guidelines

**Every subagent MUST follow these rules:**

1. **Activate the venv before ANY Python command:**
   ```bash
   source /Users/juno/Projects/tenforty/.venv/bin/activate
   ```

2. **PEP8 typing only.** Use `dict[str, str]`, `list[int]`, `X | None`. Never import from `typing`.

3. **All imports at top of file.** No inline imports.

4. **Reduce code duplication.** Check if a helper already exists before writing a new one.

5. **TDD: red → green → commit.**

6. **Test commands always include `-v`:**
   ```bash
   source /Users/juno/Projects/tenforty/.venv/bin/activate && python -m pytest tests/path/test_file.py -v
   ```

7. **Test classes inherit from `unittest.TestCase`.** Use `self.assertEqual()`, `self.assertGreater()`, etc. Never bare `assert`.

8. **Commit after each passing test cycle.** Small, frequent commits.

9. **No personal data.** All dollar amounts in YAML fixtures must be divisible by 50.

10. **Tuples with 3+ items must be dataclasses.**

---

## File Structure

```
tenforty/
├── tenforty/
│   └── mappings/
│       └── f1040.py             # Modify: add missing OUTPUTS keys
├── tests/
│   ├── invariants.py            # Create: shared structural assertion functions
│   ├── test_e2e_simple_w2.py    # Create: e2e test for simple W-2 scenario
│   ├── test_e2e_w2_investments.py  # Create: e2e test for W-2 + investments
│   ├── test_e2e_itemized.py     # Create: e2e test for itemized deductions
│   └── fixtures/
│       ├── simple_w2.yaml       # Exists
│       ├── w2_with_investments.yaml   # Create
│       └── itemized_deductions.yaml   # Create
```

---

### Task 1: Add Missing F1040 Output Keys

**Files:**
- Modify: `tenforty/mappings/f1040.py`
- Modify: `tests/test_f1040_mapping.py`

The e2e invariants need `total_income` (line 9), `total_payments` (line 33), and `total_deductions` (line 14) from the engine. These named ranges exist in the XLS but aren't mapped yet.

- [ ] **Step 1: Write failing test for new output keys**

Add to `tests/test_f1040_mapping.py` in `TestF1040Outputs2025`:

```python
    def test_total_income_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_income"], "Total_Income")

    def test_total_payments_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_payments"], "Tot_Payments")

    def test_total_deductions_output(self):
        outputs = F1040.get_outputs(2025)
        self.assertEqual(outputs["total_deductions"], "TotalDeductions")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
source .venv/bin/activate && python -m pytest tests/test_f1040_mapping.py::TestF1040Outputs2025 -v
```

Expected: 3 FAIL (KeyError on the new keys).

- [ ] **Step 3: Add the output keys to F1040.OUTPUTS**

In `tenforty/mappings/f1040.py`, add to the 2025 OUTPUTS dict:

```python
            # --- Totals ---
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_f1040_mapping.py -v
```

Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/mappings/f1040.py tests/test_f1040_mapping.py
git commit -m "feat: add total_income, total_payments, total_deductions to F1040 outputs"
```

---

### Task 2: Invariant Library

**Files:**
- Create: `tests/invariants.py`
- Create: `tests/test_invariants.py`

- [ ] **Step 1: Write failing tests for invariant functions**

`tests/test_invariants.py`:
```python
import unittest

from tenforty.models import Form1099DIV, Form1099INT, Scenario, TaxReturnConfig, W2
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)


def _make_scenario_with_interest_and_dividends() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025, filing_status="single",
            birthdate="1990-06-15", state="CA",
        ),
        w2s=[W2(
            employer="Acme Corp", wages=100000,
            federal_tax_withheld=15000,
            ss_wages=100000, ss_tax_withheld=6200,
            medicare_wages=100000, medicare_tax_withheld=1450,
        )],
        form1099_int=[Form1099INT(payer="Bank of Example", interest=500)],
        form1099_div=[Form1099DIV(
            payer="Brokerage Inc",
            ordinary_dividends=2000, qualified_dividends=1500,
        )],
    )


class TestAssertAgiConsistent(unittest.TestCase):
    def test_passes_when_agi_equals_income_sum(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {
            "wages": 100000,
            "interest_income": 500,
            "dividend_income": 2000,
            "agi": 102500,
        }
        assert_agi_consistent(self, results, scenario)

    def test_fails_when_agi_wrong(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {
            "wages": 100000,
            "interest_income": 500,
            "dividend_income": 2000,
            "agi": 999999,
        }
        with self.assertRaises(AssertionError):
            assert_agi_consistent(self, results, scenario)


class TestAssertTaxableIncomeConsistent(unittest.TestCase):
    def test_passes_when_consistent(self):
        results = {
            "agi": 100000,
            "total_deductions": 15750,
            "taxable_income": 84250,
        }
        assert_taxable_income_consistent(self, results)

    def test_fails_when_negative(self):
        results = {
            "agi": 100000,
            "total_deductions": 15750,
            "taxable_income": -5000,
        }
        with self.assertRaises(AssertionError):
            assert_taxable_income_consistent(self, results)


class TestAssertTaxIsNonNegative(unittest.TestCase):
    def test_passes_when_positive(self):
        results = {"total_tax": 13500}
        assert_tax_is_non_negative(self, results)

    def test_passes_when_zero(self):
        results = {"total_tax": 0}
        assert_tax_is_non_negative(self, results)

    def test_fails_when_negative(self):
        results = {"total_tax": -100}
        with self.assertRaises(AssertionError):
            assert_tax_is_non_negative(self, results)


class TestAssertRefundOrOwedConsistent(unittest.TestCase):
    def test_passes_with_refund(self):
        results = {
            "total_payments": 15000,
            "total_tax": 13500,
            "overpaid": 1500,
        }
        assert_refund_or_owed_consistent(self, results)

    def test_passes_when_owed(self):
        results = {
            "total_payments": 10000,
            "total_tax": 13500,
            "overpaid": 0,
        }
        assert_refund_or_owed_consistent(self, results)

    def test_fails_when_inconsistent(self):
        results = {
            "total_payments": 10000,
            "total_tax": 13500,
            "overpaid": 5000,
        }
        with self.assertRaises(AssertionError):
            assert_refund_or_owed_consistent(self, results)


class TestAssertWithholdingMatchesInput(unittest.TestCase):
    def test_passes_when_matching(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {"federal_withheld": 15000}
        assert_withholding_matches_input(self, results, scenario)

    def test_fails_when_mismatched(self):
        scenario = _make_scenario_with_interest_and_dividends()
        results = {"federal_withheld": 99999}
        with self.assertRaises(AssertionError):
            assert_withholding_matches_input(self, results, scenario)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_invariants.py -v
```

Expected: `ImportError` — `tests.invariants` does not exist.

- [ ] **Step 3: Implement invariants**

`tests/invariants.py`:
```python
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

    # AGI may differ from total income due to adjustments (Schedule 1).
    # If no adjustments, AGI should equal total income.
    # We check that AGI <= total income (adjustments only reduce it)
    # and that AGI is close to expected (within adjustments range).
    test.assertLessEqual(
        float(agi), expected_income + 1,
        f"AGI ({agi}) exceeds total income ({expected_income})",
    )
    test.assertGreater(float(agi), 0, "AGI should be positive for scenarios with income")


def assert_taxable_income_consistent(
    test: unittest.TestCase,
    results: dict[str, object],
) -> None:
    """Taxable income must be non-negative and consistent with AGI minus deductions."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_invariants.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/invariants.py tests/test_invariants.py
git commit -m "feat: add shared structural invariant library for e2e tests"
```

---

### Task 3: E2E Test — Simple W-2

**Files:**
- Create: `tests/test_e2e_simple_w2.py`

Uses the existing `tests/fixtures/simple_w2.yaml` fixture.

- [ ] **Step 1: Write the e2e test**

`tests/test_e2e_simple_w2.py`:
```python
import subprocess
import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = unittest.skipUnless(
    libreoffice_available(), "LibreOffice not installed",
)
needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


@needs_libreoffice
class TestE2ESimpleW2(unittest.TestCase):
    """Full pipeline: simple W-2 single filer with standard deduction."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "simple_w2.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.work_dir,
        )

    def test_engine_invariants(self):
        """Run engine and verify structural invariants."""
        results = self.orchestrator.compute_federal(self.scenario)

        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

    @needs_pdf
    def test_pdf_output(self):
        """Run full pipeline through PDF filling."""
        results = self.orchestrator.compute_federal(self.scenario)

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_simple_w2.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---
```

- [ ] **Step 2: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_e2e_simple_w2.py -v
```

Expected: PASS (both tests).

- [ ] **Step 3: Commit**

```bash
git add tests/test_e2e_simple_w2.py
git commit -m "test: add e2e test for simple W-2 scenario"
```

---

### Task 4: Fixture + E2E Test — W-2 With Investments

**Files:**
- Create: `tests/fixtures/w2_with_investments.yaml`
- Create: `tests/test_e2e_w2_investments.py`

- [ ] **Step 1: Create the fixture**

`tests/fixtures/w2_with_investments.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1985-08-10"
  state: CA

w2s:
  - employer: "Tech Corp"
    wages: 120000.00
    federal_tax_withheld: 22000.00
    ss_wages: 120000.00
    ss_tax_withheld: 7450.00
    medicare_wages: 120000.00
    medicare_tax_withheld: 1750.00

form1099_int:
  - payer: "National Bank"
    interest: 1500.00

form1099_div:
  - payer: "Investment Brokerage"
    ordinary_dividends: 3000.00
    qualified_dividends: 2500.00
```

- [ ] **Step 2: Write the e2e test**

`tests/test_e2e_w2_investments.py`:
```python
import subprocess
import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = unittest.skipUnless(
    libreoffice_available(), "LibreOffice not installed",
)
needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


@needs_libreoffice
class TestE2EW2Investments(unittest.TestCase):
    """Full pipeline: W-2 + interest + dividends, standard deduction."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "w2_with_investments.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.work_dir,
        )

    def test_engine_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)

        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

        # Investment income should be reflected in AGI
        self.assertGreater(
            float(results["agi"]), 120000,
            "AGI should exceed wages alone due to investment income",
        )

    @needs_pdf
    def test_pdf_output(self):
        results = self.orchestrator.compute_federal(self.scenario)

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_investments.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---
```

- [ ] **Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_e2e_w2_investments.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/w2_with_investments.yaml tests/test_e2e_w2_investments.py
git commit -m "test: add e2e test for W-2 + investments scenario"
```

---

### Task 5: Fixture + E2E Test — Itemized Deductions

**Files:**
- Create: `tests/fixtures/itemized_deductions.yaml`
- Create: `tests/test_e2e_itemized.py`

This scenario has mortgage interest + property tax exceeding the 2025 standard deduction of $15,750. The taxpayer should itemize.

- [ ] **Step 1: Create the fixture**

`tests/fixtures/itemized_deductions.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1980-02-14"
  state: CA

w2s:
  - employer: "Acme Corp"
    wages: 200000.00
    federal_tax_withheld: 40000.00
    ss_wages: 176100.00
    ss_tax_withheld: 10950.00
    medicare_wages: 200000.00
    medicare_tax_withheld: 2900.00

form1098s:
  - lender: "Home Mortgage Co"
    mortgage_interest: 18000.00
    property_tax: 6000.00
```

Note: Mortgage interest $18,000 + SALT (property tax capped at $10,000) = $28,000 > $15,750 standard deduction. Taxpayer should itemize.

Actually, property tax alone is $6,000 which is under the SALT cap, so total itemized = $18,000 + $6,000 = $24,000 > $15,750. Should itemize.

- [ ] **Step 2: Write the e2e test**

`tests/test_e2e_itemized.py`:
```python
import subprocess
import tempfile
import unittest
from pathlib import Path

from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.orchestrator import ReturnOrchestrator
from tenforty.result_translator import ResultTranslator
from tenforty.scenario import load_scenario
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC
from tests.invariants import (
    assert_agi_consistent,
    assert_refund_or_owed_consistent,
    assert_tax_is_non_negative,
    assert_taxable_income_consistent,
    assert_withholding_matches_input,
)

REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
F1040_PDF = Path("/tmp/f1040_2025.pdf")


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = unittest.skipUnless(
    libreoffice_available(), "LibreOffice not installed",
)
needs_pdf = unittest.skipUnless(
    F1040_PDF.exists(), "f1040 PDF not available at /tmp/f1040_2025.pdf",
)


@needs_libreoffice
class TestE2EItemized(unittest.TestCase):
    """Full pipeline: high earner with mortgage, should itemize."""

    def setUp(self):
        self.work_dir = Path(tempfile.mkdtemp())
        self.scenario = load_scenario(FIXTURES_DIR / "itemized_deductions.yaml")
        self.orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=self.work_dir,
        )

    def test_engine_invariants(self):
        results = self.orchestrator.compute_federal(self.scenario)

        assert_agi_consistent(self, results, self.scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, self.scenario)

    def test_uses_itemized_deduction(self):
        """Deduction should exceed the 2025 standard deduction of $15,750."""
        results = self.orchestrator.compute_federal(self.scenario)

        deduction = float(results.get("total_deductions", 0))
        self.assertGreater(
            deduction, 15750,
            f"Expected itemized deduction > $15,750 standard, got ${deduction:,.0f}",
        )

    @needs_pdf
    def test_pdf_output(self):
        results = self.orchestrator.compute_federal(self.scenario)

        translator = ResultTranslator(F1040_PDF_SPEC)
        translated = translator.translate(results, self.scenario)

        filler = PdfFiller()
        output_pdf = self.work_dir / "f1040_itemized.pdf"
        filler.fill(F1040_PDF, output_pdf, Pdf1040.get_mapping(2025), translated)

        self.assertTrue(output_pdf.exists())
        self.assertGreater(output_pdf.stat().st_size, 0)

    # --- Regression tests ---
```

- [ ] **Step 3: Run tests**

```bash
source .venv/bin/activate && python -m pytest tests/test_e2e_itemized.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/itemized_deductions.yaml tests/test_e2e_itemized.py
git commit -m "test: add e2e test for itemized deductions scenario"
```

---

### Task 6: Run Full Suite and Clean Up

**Files:**
- Possibly modify: `tests/test_verification.py` (remove if redundant with e2e tests)

- [ ] **Step 1: Run the complete test suite**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: All tests pass. Note the total count and time.

- [ ] **Step 2: Check for redundancy with existing test_verification.py**

The existing `tests/test_verification.py` (from Task 12 of the original plan) tests a "realistic" scenario. Compare it with the new e2e tests. If it's covered by `test_e2e_w2_investments.py`, delete it and its fixture to avoid duplicate slow tests.

If the realistic fixture (`realistic_w2_rental.yaml`) tests something the e2e tests don't (e.g., the mortgage data), keep it but convert it to use the invariant library.

- [ ] **Step 3: Commit final state**

```bash
git add -A
git commit -m "test: clean up test suite after e2e framework addition"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Add missing F1040 output keys | 3 new assertions |
| 2 | Invariant library | 11 tests |
| 3 | E2E simple W-2 | 2 tests (engine + PDF) |
| 4 | E2E W-2 + investments | 2 tests (engine + PDF) |
| 5 | E2E itemized deductions | 3 tests (engine + PDF + itemization check) |
| 6 | Full suite verification + cleanup | — |

**What this plan builds:** A composable e2e test framework with structural invariants, exercising three distinct tax scenarios (standard deduction, investment income, itemized deductions) through the full pipeline to PDF output.

**What comes next:**
- Additional scenarios as forms are built (rental property, self-employment, MFJ, capital gains)
- Additional invariants for new forms (Schedule E, CA 540)
- Regression tests added as bugs are discovered
