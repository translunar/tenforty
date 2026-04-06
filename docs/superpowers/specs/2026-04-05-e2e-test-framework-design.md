# End-to-End Test Framework

**Date:** 2026-04-05
**Status:** Draft
**Goal:** A composable test framework that runs the full pipeline (YAML → engine → translator → PDF) and verifies structural invariants, extensible as new forms are added.

## Problem

We have unit and integration tests for individual components, but no test that proves the full pipeline produces a valid filled PDF from a scenario file. We also need to support multiple scenario types (standard vs. itemized, different filing statuses, different income combinations) without the tests becoming brittle or coupled.

## Design

### Structure

Each scenario gets:
- A YAML fixture in `tests/fixtures/`
- A test class in `tests/test_e2e_<scenario_name>.py`

Test classes are independent. Adding a new scenario means adding a new file — no existing tests are modified.

### Shared Invariant Library

`tests/invariants.py` — a module of assertion functions that encode structural truths about tax returns. Each function takes the computed results dict and asserts a property that must hold regardless of the specific numbers.

Invariants for the current codebase:

- **`assert_agi_consistent`** — AGI equals wages + interest + dividends + other income - adjustments (for the income sources present in the scenario)
- **`assert_taxable_income_consistent`** — taxable income equals AGI minus deduction used, and is non-negative
- **`assert_tax_is_non_negative`** — total tax >= 0
- **`assert_refund_or_owed_consistent`** — if overpaid > 0, then total payments > total tax; if overpaid is 0 or absent, total payments <= total tax
- **`assert_withholding_matches_input`** — federal withholding in results matches what was in the scenario

As we add forms, we add invariants:
- Schedule E: rental income minus expenses equals net rental income
- CA 540: California AGI derives from federal AGI
- 1120-S: K-1 output flows into Schedule E

### Test Flow

Each test class:

```python
class TestE2ESimpleW2(unittest.TestCase):
    def test_full_pipeline(self):
        # 1. Load scenario
        scenario = load_scenario(FIXTURES / "simple_w2.yaml")
        
        # 2. Engine computation
        results = orchestrator.compute_federal(scenario)
        
        # 3. Translation
        translated = translator.translate(results, scenario)
        
        # 4. PDF filling
        pdf_path = filler.fill(template, output, mapping, translated)
        
        # 5. Structural invariants on computed results
        assert_agi_consistent(self, results, scenario)
        assert_taxable_income_consistent(self, results)
        assert_tax_is_non_negative(self, results)
        assert_refund_or_owed_consistent(self, results)
        assert_withholding_matches_input(self, results, scenario)
        
        # 6. PDF exists and has content
        self.assertTrue(pdf_path.exists())
        
    # --- Regression tests ---
    # (added as bugs are discovered, with comments referencing the bug)
```

### Initial Scenarios

| Scenario | Exercises | Key Invariants |
|----------|-----------|----------------|
| `simple_w2.yaml` | W-2 + small interest, standard deduction | AGI = wages + interest, standard deduction used |
| `w2_with_investments.yaml` | W-2 + 1099-INT + 1099-DIV, standard deduction (no mortgage) | AGI includes interest and dividends, standard deduction |
| `itemized_deductions.yaml` | W-2 + mortgage interest + property tax exceeding standard deduction threshold | Itemized deduction used, deduction > standard deduction amount |

Future scenarios added as forms are built:
- `rental_property.yaml` — Schedule E
- `self_employed.yaml` — Schedule C + SE
- `married_joint.yaml` — MFJ filing status
- `capital_gains.yaml` — Schedule D + 8949

### Regression Tests

Each test class has space for regression tests at the bottom. These are specific value assertions added when bugs are found:

```python
    # --- Regression tests ---
    def test_regression_interest_not_double_counted(self):
        """Bug: interest was added to AGI twice. Fixed in commit abc123."""
        results = ...
        self.assertEqual(results["agi"], 100250)  # not 100500
```

### File Layout

```
tests/
├── invariants.py                    # Shared structural assertion functions
├── test_e2e_simple_w2.py
├── test_e2e_w2_investments.py
├── test_e2e_itemized.py
└── fixtures/
    ├── simple_w2.yaml               # (already exists)
    ├── w2_with_investments.yaml      # (new — based on realistic_w2_rental.yaml)
    └── itemized_deductions.yaml      # (new)
```

### Invariant Function Signatures

All invariant functions take `self` (the TestCase) as first argument so they can use `self.assertEqual`, `self.assertGreater`, etc.:

```python
def assert_agi_consistent(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
) -> None:
    ...
```

This pattern lets invariants produce clear assertion messages tied to the calling test.
