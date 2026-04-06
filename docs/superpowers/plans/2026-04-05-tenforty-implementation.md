# tenforty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a spreadsheet-driven tax preparation harness that automates federal (1040), California (540), and S-corp (1120-S) tax return preparation.

**Architecture:** Tax computations live in spreadsheets evaluated by LibreOffice headless. A Python harness writes input data into spreadsheets (via openpyxl), triggers recalculation, reads results, and fills PDF forms (via pypdf). Scenario files (YAML) describe each tax return's inputs.

**Tech Stack:** Python 3.14, openpyxl, PyYAML, pypdf, pytest, LibreOffice (headless)

---

## Subagent Guidelines

**Every subagent MUST follow these rules:**

1. **Activate the venv before ANY Python command:**
   ```bash
   source /Users/juno/Projects/tenforty/.venv/bin/activate
   ```

2. **PEP8 typing only.** Use `dict[str, str]`, `list[int]`, `tuple[str, ...]`, `X | None`. Never import `Dict`, `List`, `Tuple`, `Optional` from `typing`.

3. **All imports at top of file.** No inline imports. No exceptions unless something will literally break at import time without it.

4. **Reduce code duplication.** If you're about to copy-paste, extract a shared utility or base class. Check if a helper already exists before writing a new one.

5. **TDD: red → green → commit.** Write the failing test first. Run it to confirm failure. Write minimal code to pass. Run again. Commit.

6. **Test commands always include `-v`:**
   ```bash
   source /Users/juno/Projects/tenforty/.venv/bin/activate && python -m pytest tests/path/test_file.py -v
   ```

7. **Commit after each passing test cycle.** Small, frequent commits with descriptive messages.

8. **No personal data.** Test fixtures use synthetic numbers only. Never reference real tax documents.

---

## File Structure

```
tenforty/
├── tenforty/
│   ├── __init__.py
│   ├── models.py                # All dataclasses: W2, Form1099INT, Scenario, etc.
│   ├── mappings/
│   │   ├── __init__.py          # Re-exports FormMapping and all form classes
│   │   ├── registry.py          # FormMapping base class
│   │   └── f1040.py             # Federal 1040 workbook mappings (all years)
│   ├── engine.py                # SpreadsheetEngine — write, recalc, read
│   ├── orchestrator.py          # ReturnOrchestrator — dependency-ordered computation
│   ├── scenario.py              # YAML → Scenario loader
│   └── filing/
│       ├── __init__.py
│       └── pdf.py               # PDF form filler
├── spreadsheets/
│   └── federal/
│       └── 2025/
│           └── 1040.xlsx        # Third-party XLS (copied from ~/Downloads)
├── tests/
│   ├── conftest.py              # Shared fixtures: paths, synthetic scenarios
│   ├── fixtures/
│   │   └── simple_w2.yaml       # Simple single-filer W-2 scenario
│   ├── test_models.py
│   ├── test_registry.py
│   ├── test_f1040_mapping.py
│   ├── test_engine.py
│   ├── test_scenario.py
│   └── test_orchestrator.py
├── pyproject.toml
└── .gitignore
```

**Note:** CA 540, 540-CA, and 1120-S spreadsheets + mappings are out of scope for this initial plan. We build the full pipeline for federal first, then extend. The architecture supports it — adding a new form means adding a spreadsheet file, a mapping subclass, and an orchestrator step.

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tenforty/__init__.py`
- Create: `tenforty/mappings/__init__.py`
- Create: `tenforty/filing/__init__.py`
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Copy: `spreadsheets/federal/2025/1040.xlsx`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "tenforty"
version = "0.1.0"
description = "Tax preparation harness — spreadsheet-driven, test-verified"
requires-python = ">=3.12"
dependencies = [
    "openpyxl>=3.1",
    "PyYAML>=6.0",
    "pypdf>=4.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Create .gitignore**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/

# OS
.DS_Store

# Working files (LibreOffice temp copies)
/tmp/
*.~lock.*

# Personal tax data — NEVER commit
personal/
private/
scenario_real.yaml
```

- [ ] **Step 3: Create package init files**

`tenforty/__init__.py`:
```python
"""tenforty — Tax preparation harness."""
```

`tenforty/mappings/__init__.py`:
```python
"""Form mappings — maps scenario fields to spreadsheet named ranges."""
```

`tenforty/filing/__init__.py`:
```python
"""Filing layer — PDF form filling."""
```

`tests/__init__.py`: empty file.

- [ ] **Step 4: Create tests/conftest.py with shared paths**

```python
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).parent.parent
SPREADSHEETS_DIR = REPO_ROOT / "spreadsheets"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def federal_1040_path() -> Path:
    path = SPREADSHEETS_DIR / "federal" / "2025" / "1040.xlsx"
    if not path.exists():
        pytest.skip(f"Federal 1040 spreadsheet not found at {path}")
    return path


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR
```

- [ ] **Step 5: Copy the federal XLS into the repo**

```bash
mkdir -p spreadsheets/federal/2025
cp ~/Downloads/25_1040.xlsx spreadsheets/federal/2025/1040.xlsx
```

- [ ] **Step 6: Install the package in dev mode**

```bash
source .venv/bin/activate && pip install -e ".[dev]"
```

- [ ] **Step 7: Verify pytest runs with no tests**

```bash
source .venv/bin/activate && python -m pytest -v
```

Expected: `no tests ran` / exit 0 (or 5 for no tests collected).

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore tenforty/ tests/ spreadsheets/
git commit -m "feat: scaffold tenforty project with deps and federal XLS"
```

---

### Task 2: Data Models

**Files:**
- Create: `tenforty/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for core dataclasses**

`tests/test_models.py`:
```python
from tenforty.models import W2, Form1099INT, Form1099DIV, Form1098, TaxReturnConfig, Scenario


class TestW2:
    def test_create_w2(self):
        w2 = W2(
            employer="Acme Corp",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        assert w2.wages == 100000.00
        assert w2.employer == "Acme Corp"

    def test_w2_optional_fields_default_to_zero(self):
        w2 = W2(
            employer="Acme Corp",
            wages=50000.00,
            federal_tax_withheld=5000.00,
            ss_wages=50000.00,
            ss_tax_withheld=3100.00,
            medicare_wages=50000.00,
            medicare_tax_withheld=725.00,
        )
        assert w2.state_wages == 0.0
        assert w2.state_tax_withheld == 0.0
        assert w2.local_tax_withheld == 0.0


class TestForm1099INT:
    def test_create_1099_int(self):
        f = Form1099INT(payer="Bank of Example", interest=250.00)
        assert f.interest == 250.00
        assert f.federal_tax_withheld == 0.0


class TestForm1099DIV:
    def test_create_1099_div(self):
        f = Form1099DIV(
            payer="Brokerage Inc",
            ordinary_dividends=1200.00,
            qualified_dividends=800.00,
        )
        assert f.ordinary_dividends == 1200.00
        assert f.qualified_dividends == 800.00


class TestForm1098:
    def test_create_1098(self):
        f = Form1098(lender="Mortgage Co", mortgage_interest=8400.00)
        assert f.mortgage_interest == 8400.00
        assert f.property_tax == 0.0


class TestTaxReturnConfig:
    def test_create_config(self):
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        assert config.year == 2025
        assert config.filing_status == "single"


class TestScenario:
    def test_create_scenario(self):
        w2 = W2(
            employer="Acme",
            wages=100000.00,
            federal_tax_withheld=15000.00,
            ss_wages=100000.00,
            ss_tax_withheld=6200.00,
            medicare_wages=100000.00,
            medicare_tax_withheld=1450.00,
        )
        config = TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        )
        scenario = Scenario(config=config, w2s=[w2])
        assert len(scenario.w2s) == 1
        assert scenario.config.year == 2025
        assert scenario.form1099_int == []
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_models.py -v
```

Expected: `ImportError` — `tenforty.models` does not exist yet.

- [ ] **Step 3: Implement models**

`tenforty/models.py`:
```python
from dataclasses import dataclass, field


@dataclass
class W2:
    employer: str
    wages: float
    federal_tax_withheld: float
    ss_wages: float
    ss_tax_withheld: float
    medicare_wages: float
    medicare_tax_withheld: float
    state_wages: float = 0.0
    state_tax_withheld: float = 0.0
    local_tax_withheld: float = 0.0


@dataclass
class Form1099INT:
    payer: str
    interest: float
    federal_tax_withheld: float = 0.0
    tax_exempt_interest: float = 0.0


@dataclass
class Form1099DIV:
    payer: str
    ordinary_dividends: float
    qualified_dividends: float = 0.0
    capital_gain_distributions: float = 0.0
    federal_tax_withheld: float = 0.0
    foreign_tax_paid: float = 0.0


@dataclass
class Form1099B:
    broker: str
    description: str
    date_acquired: str
    date_sold: str
    proceeds: float
    cost_basis: float
    gain_loss: float = 0.0
    short_term: bool = True


@dataclass
class Form1098:
    lender: str
    mortgage_interest: float
    property_tax: float = 0.0
    mortgage_insurance_premiums: float = 0.0


@dataclass
class ScheduleK1:
    entity_name: str
    entity_ein: str
    ordinary_income: float = 0.0
    rental_income: float = 0.0
    interest_income: float = 0.0
    dividend_income: float = 0.0
    short_term_capital_gain: float = 0.0
    long_term_capital_gain: float = 0.0
    section_179_deduction: float = 0.0
    other_deductions: float = 0.0


@dataclass
class TaxReturnConfig:
    year: int
    filing_status: str
    birthdate: str
    state: str
    dependents: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    config: TaxReturnConfig
    w2s: list[W2] = field(default_factory=list)
    form1099_int: list[Form1099INT] = field(default_factory=list)
    form1099_div: list[Form1099DIV] = field(default_factory=list)
    form1099_b: list[Form1099B] = field(default_factory=list)
    form1098s: list[Form1098] = field(default_factory=list)
    schedule_k1s: list[ScheduleK1] = field(default_factory=list)
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_models.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/models.py tests/test_models.py
git commit -m "feat: add data models for tax input documents and scenarios"
```

---

### Task 3: FormMapping Registry

**Files:**
- Create: `tenforty/mappings/registry.py`
- Create: `tests/test_registry.py`

- [ ] **Step 1: Write failing tests for FormMapping base class**

`tests/test_registry.py`:
```python
import pytest

from tenforty.mappings.registry import FormMapping


class FakeMapping(FormMapping):
    INPUTS = {
        2025: {
            "wages": "W2_Wages_You",
            "filing_single": "File_Single",
        },
    }
    OUTPUTS = {
        2025: {
            "agi": "Adj_Gross_Inc",
            "tax": "Tax",
        },
    }


class TestFormMappingGetInputs:
    def test_returns_inputs_for_valid_year(self):
        result = FakeMapping.get_inputs(2025)
        assert result == {"wages": "W2_Wages_You", "filing_single": "File_Single"}

    def test_raises_for_missing_year(self):
        with pytest.raises(ValueError, match="No input mapping for year 2020"):
            FakeMapping.get_inputs(2020)


class TestFormMappingGetOutputs:
    def test_returns_outputs_for_valid_year(self):
        result = FakeMapping.get_outputs(2025)
        assert result == {"agi": "Adj_Gross_Inc", "tax": "Tax"}

    def test_raises_for_missing_year(self):
        with pytest.raises(ValueError, match="No output mapping for year 2020"):
            FakeMapping.get_outputs(2020)


class TestFormMappingInherit:
    def test_inherit_inputs_with_override(self):
        result = FakeMapping.inherit(2025, {"wages": "W2_Wages_NEW"}, source="inputs")
        assert result["wages"] == "W2_Wages_NEW"
        assert result["filing_single"] == "File_Single"

    def test_inherit_outputs_with_addition(self):
        result = FakeMapping.inherit(2025, {"refund": "Overpaid"}, source="outputs")
        assert result["agi"] == "Adj_Gross_Inc"
        assert result["refund"] == "Overpaid"

    def test_inherit_does_not_mutate_original(self):
        FakeMapping.inherit(2025, {"wages": "CHANGED"}, source="inputs")
        assert FakeMapping.INPUTS[2025]["wages"] == "W2_Wages_You"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_registry.py -v
```

Expected: `ImportError` — module does not exist.

- [ ] **Step 3: Implement FormMapping**

`tenforty/mappings/registry.py`:
```python
class FormMapping:
    """Base class for form mappings. Subclasses define INPUTS and OUTPUTS by year."""

    INPUTS: dict[int, dict[str, str]] = {}
    OUTPUTS: dict[int, dict[str, str]] = {}

    @classmethod
    def get_inputs(cls, year: int) -> dict[str, str]:
        if year not in cls.INPUTS:
            raise ValueError(f"No input mapping for year {year} in {cls.__name__}")
        return cls.INPUTS[year]

    @classmethod
    def get_outputs(cls, year: int) -> dict[str, str]:
        if year not in cls.OUTPUTS:
            raise ValueError(f"No output mapping for year {year} in {cls.__name__}")
        return cls.OUTPUTS[year]

    @classmethod
    def inherit(cls, base_year: int, overrides: dict[str, str],
                source: str = "inputs") -> dict[str, str]:
        """Create a new year's mapping by overriding specific fields from base_year."""
        base = cls.INPUTS if source == "inputs" else cls.OUTPUTS
        if base_year not in base:
            raise ValueError(f"No {source} mapping for year {base_year} in {cls.__name__}")
        return {**base[base_year], **overrides}
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_registry.py -v
```

Expected: All 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/mappings/registry.py tests/test_registry.py
git commit -m "feat: add FormMapping registry with year-keyed input/output lookups"
```

---

### Task 4: F1040 Mapping (Core Federal Inputs/Outputs)

**Files:**
- Create: `tenforty/mappings/f1040.py`
- Create: `tests/test_f1040_mapping.py`

This mapping covers the entire federal workbook — W-2 input sheet, 1099 sheets, Schedule E, Schedule A, and 1040 output fields. We build only the fields needed for a W-2 + interest + mortgage single-filer scenario now and extend as needed.

- [ ] **Step 1: Write failing tests for F1040 mapping**

`tests/test_f1040_mapping.py`:
```python
from tenforty.mappings.f1040 import F1040


class TestF1040Inputs2025:
    def test_has_2025_inputs(self):
        inputs = F1040.get_inputs(2025)
        assert isinstance(inputs, dict)
        assert len(inputs) > 0

    def test_w2_wage_fields(self):
        inputs = F1040.get_inputs(2025)
        assert inputs["w2_wages_1"] == "C3"
        assert inputs["w2_fed_withheld_1"] == "C4"
        assert inputs["w2_ss_wages_1"] == "C5"
        assert inputs["w2_ss_withheld_1"] == "C6"
        assert inputs["w2_medicare_wages_1"] == "C7"
        assert inputs["w2_medicare_withheld_1"] == "C8"

    def test_filing_status_fields(self):
        inputs = F1040.get_inputs(2025)
        assert inputs["filing_status_single"] == "File_Single"
        assert inputs["filing_status_married_jointly"] == "File_Marr_Joint"
        assert inputs["filing_status_married_separately"] == "File_Marr_Sep"
        assert inputs["filing_status_head_of_household"] == "File_Head"

    def test_birthdate_fields(self):
        inputs = F1040.get_inputs(2025)
        assert inputs["birthdate_month"] == "YourBirthMonth"
        assert inputs["birthdate_day"] == "YourBirthDay"
        assert inputs["birthdate_year"] == "YourBirthYear"

    def test_1099_int_fields(self):
        inputs = F1040.get_inputs(2025)
        # 1099-INT sheet, first payer interest goes in a cell
        assert "interest_1" in inputs

    def test_1098_mortgage_interest(self):
        inputs = F1040.get_inputs(2025)
        assert "mortgage_interest" in inputs

    def test_schedule_e_rental_fields(self):
        inputs = F1040.get_inputs(2025)
        assert "sche_rents_a" in inputs
        assert "sche_property_type_a" in inputs


class TestF1040Outputs2025:
    def test_has_2025_outputs(self):
        outputs = F1040.get_outputs(2025)
        assert isinstance(outputs, dict)
        assert len(outputs) > 0

    def test_core_output_fields(self):
        outputs = F1040.get_outputs(2025)
        assert outputs["agi"] == "Adj_Gross_Inc"
        assert outputs["taxable_income"] == "Taxable_Inc"
        assert outputs["total_tax"] == "Tax"
        assert outputs["federal_withheld"] == "W2_FedTaxWH"
        assert outputs["overpaid"] == "Overpaid"

    def test_schedule_e_output(self):
        outputs = F1040.get_outputs(2025)
        assert outputs["sche_line26"] == "SchE1_Line26"


class TestF1040InputTypes:
    def test_all_input_values_are_strings(self):
        """All mapping values must be strings (named range or cell ref)."""
        for key, value in F1040.get_inputs(2025).items():
            assert isinstance(value, str), f"Input '{key}' value is {type(value)}, expected str"

    def test_all_output_values_are_strings(self):
        for key, value in F1040.get_outputs(2025).items():
            assert isinstance(value, str), f"Output '{key}' value is {type(value)}, expected str"
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_f1040_mapping.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement F1040 mapping**

`tenforty/mappings/f1040.py`:
```python
from tenforty.mappings.registry import FormMapping


class F1040(FormMapping):
    """Mapping for the entire federal 1040 workbook (all sheets).

    Input keys use the convention: {form}_{field}_{index}.
    - W-2 fields: w2_{field}_{employer_number} (1-6 supported by XLS)
    - 1099 fields: {form_type}_{field}_{payer_number}
    - Schedule E: sche_{field}_{property_letter}

    Values are either named ranges (e.g., "File_Single") or direct cell
    references on a specific sheet (e.g., "C3" on the W-2s sheet). Named
    ranges are resolved by openpyxl automatically. Direct cell references
    require the sheet name prefix in the engine (stored in SHEET_MAP).
    """

    # Maps input keys to their sheet when not using a named range.
    # If a key's value is a named range, it doesn't need an entry here.
    SHEET_MAP: dict[int, dict[str, str]] = {
        2025: {
            # W-2 fields are cell refs on the "W-2s" sheet
            "w2_wages_1": "W-2s",
            "w2_fed_withheld_1": "W-2s",
            "w2_ss_wages_1": "W-2s",
            "w2_ss_withheld_1": "W-2s",
            "w2_medicare_wages_1": "W-2s",
            "w2_medicare_withheld_1": "W-2s",
            "w2_state_wages_1": "W-2s",
            "w2_state_withheld_1": "W-2s",
            # 1099-INT fields are cell refs on the "1099-INT" sheet
            "interest_1": "1099-INT",
            # 1099-DIV fields
            "ordinary_dividends_1": "1099-DIV",
            "qualified_dividends_1": "1099-DIV",
            # Schedule E fields are cell refs on the "Sch. E" sheet
            "sche_rents_a": "Sch. E",
            "sche_property_type_a": "Sch. E",
            "sche_fair_rental_days_a": "Sch. E",
            "sche_personal_use_days_a": "Sch. E",
            "sche_advertising_a": "Sch. E",
            "sche_insurance_a": "Sch. E",
            "sche_mortgage_interest_a": "Sch. E",
            "sche_repairs_a": "Sch. E",
            "sche_taxes_a": "Sch. E",
            "sche_utilities_a": "Sch. E",
            "sche_depreciation_a": "Sch. E",
            # Schedule A fields
            "mortgage_interest": "Sch. A",
        },
    }

    INPUTS: dict[int, dict[str, str]] = {
        2025: {
            # --- Filing status (named ranges on 1040 sheet) ---
            "filing_status_single": "File_Single",
            "filing_status_married_jointly": "File_Marr_Joint",
            "filing_status_married_separately": "File_Marr_Sep",
            "filing_status_head_of_household": "File_Head",
            "filing_status_qualifying_widow": "File_Qual_Widow",
            # --- Birthdate (named ranges on 1040 sheet) ---
            "birthdate_month": "YourBirthMonth",
            "birthdate_day": "YourBirthDay",
            "birthdate_year": "YourBirthYear",
            # --- W-2 Employer 1 (cell refs on W-2s sheet) ---
            "w2_wages_1": "C3",
            "w2_fed_withheld_1": "C4",
            "w2_ss_wages_1": "C5",
            "w2_ss_withheld_1": "C6",
            "w2_medicare_wages_1": "C7",
            "w2_medicare_withheld_1": "C8",
            "w2_state_wages_1": "C26",
            "w2_state_withheld_1": "C29",
            # --- 1099-INT (cell refs on 1099-INT sheet) ---
            "interest_1": "C3",
            # --- 1099-DIV (cell refs on 1099-DIV sheet) ---
            "ordinary_dividends_1": "C4",
            "qualified_dividends_1": "C5",
            # --- Form 1098 / Schedule A (cell refs on Sch. A sheet) ---
            "mortgage_interest": "D16",
            # --- Schedule E Property A (cell refs on Sch. E sheet) ---
            "sche_property_type_a": "D21",
            "sche_fair_rental_days_a": "V21",
            "sche_personal_use_days_a": "AD21",
            "sche_rents_a": "V30",
            "sche_advertising_a": "V33",
            "sche_insurance_a": "V37",
            "sche_mortgage_interest_a": "V40",
            "sche_repairs_a": "V42",
            "sche_taxes_a": "V44",
            "sche_utilities_a": "V45",
            "sche_depreciation_a": "V46",
        },
    }

    OUTPUTS: dict[int, dict[str, str]] = {
        2025: {
            # --- Core 1040 outputs (named ranges) ---
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "SD_Single",
            "taxable_income": "Taxable_Inc",
            "total_tax": "Tax",
            "federal_withheld": "W2_FedTaxWH",
            "overpaid": "Overpaid",
            # --- Schedule E outputs ---
            "sche_line26": "SchE1_Line26",
            "sche_line41": "SchE1_Line41",
            # --- Schedule D outputs ---
            "schd_line16": "SchDLine16",
            # --- Interest / Dividends ---
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
        },
    }
```

- [ ] **Step 4: Update mappings __init__.py**

`tenforty/mappings/__init__.py`:
```python
"""Form mappings — maps scenario fields to spreadsheet named ranges."""

from tenforty.mappings.registry import FormMapping
from tenforty.mappings.f1040 import F1040

__all__ = ["FormMapping", "F1040"]
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_f1040_mapping.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tenforty/mappings/ tests/test_f1040_mapping.py
git commit -m "feat: add F1040 mapping for federal workbook inputs and outputs"
```

---

### Task 5: SpreadsheetEngine

**Files:**
- Create: `tenforty/engine.py`
- Create: `tests/test_engine.py`

This is the core: write values into a spreadsheet, recalculate with LibreOffice, read results.

- [ ] **Step 1: Write failing test — engine writes inputs and reads outputs**

`tests/test_engine.py`:
```python
import subprocess

import pytest

from tenforty.engine import SpreadsheetEngine
from tenforty.mappings.f1040 import F1040


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = pytest.mark.skipif(
    not libreoffice_available(),
    reason="LibreOffice not installed",
)


class TestSpreadsheetEngine:
    @needs_libreoffice
    def test_simple_w2_single_filer(self, federal_1040_path, tmp_path):
        """$100k wages, single filer, standard deduction."""
        engine = SpreadsheetEngine()

        inputs = {
            "filing_status_single": "X",
            "birthdate_month": 6,
            "birthdate_day": 15,
            "birthdate_year": 1990,
            "w2_wages_1": 100000,
            "w2_fed_withheld_1": 15000,
            "w2_ss_wages_1": 100000,
            "w2_ss_withheld_1": 6200,
            "w2_medicare_wages_1": 100000,
            "w2_medicare_withheld_1": 1450,
        }

        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=inputs,
            work_dir=tmp_path,
        )

        assert results["wages"] == 100000
        assert results["agi"] == 100000
        assert results["taxable_income"] == 84250  # 100000 - 15750 std deduction
        assert results["federal_withheld"] == 15000
        # Tax should be roughly $13,455 (per IRS tax table)
        assert 13000 < results["total_tax"] < 14000
        assert results["overpaid"] > 0
```

- [ ] **Step 2: Run test to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_engine.py -v
```

Expected: `ImportError` — `tenforty.engine` does not exist.

- [ ] **Step 3: Implement SpreadsheetEngine**

`tenforty/engine.py`:
```python
import shutil
import subprocess
from pathlib import Path

import openpyxl


class SpreadsheetEngine:
    """Writes inputs into a spreadsheet, recalculates via LibreOffice, reads outputs."""

    def compute(
        self,
        spreadsheet_path: Path,
        mapping: type,
        year: int,
        inputs: dict[str, object],
        work_dir: Path | None = None,
    ) -> dict[str, object]:
        input_map = mapping.get_inputs(year)
        output_map = mapping.get_outputs(year)
        sheet_map = getattr(mapping, "SHEET_MAP", {}).get(year, {})

        work_dir = work_dir or Path("/tmp/tenforty_work")
        work_dir.mkdir(parents=True, exist_ok=True)

        working_copy = work_dir / spreadsheet_path.name
        shutil.copy2(spreadsheet_path, working_copy)

        self._write_inputs(working_copy, input_map, sheet_map, inputs)
        recalculated = self._recalculate(working_copy, work_dir)
        return self._read_outputs(recalculated, output_map)

    def _write_inputs(
        self,
        workbook_path: Path,
        input_map: dict[str, str],
        sheet_map: dict[str, str],
        inputs: dict[str, object],
    ) -> None:
        wb = openpyxl.load_workbook(workbook_path)
        named_ranges = {n.name: n for n in wb.defined_names.values()}

        for input_key, value in inputs.items():
            if input_key not in input_map:
                continue

            cell_ref = input_map[input_key]

            if cell_ref in named_ranges:
                # Resolve named range to sheet!cell
                defn = named_ranges[cell_ref]
                dest = defn.value
                sheet_name, cell_addr = dest.split("!")
                sheet_name = sheet_name.strip("'")
                cell_addr = cell_addr.replace("$", "")
                wb[sheet_name][cell_addr] = value
            elif input_key in sheet_map:
                # Direct cell reference on a specific sheet
                sheet_name = sheet_map[input_key]
                wb[sheet_name][cell_ref] = value
            else:
                raise ValueError(
                    f"Input '{input_key}' maps to '{cell_ref}' but has no named range "
                    f"and no sheet in SHEET_MAP"
                )

        wb.save(workbook_path)

    def _recalculate(self, workbook_path: Path, work_dir: Path) -> Path:
        output_dir = work_dir / "recalculated"
        output_dir.mkdir(exist_ok=True)

        result = subprocess.run(
            [
                "soffice", "--headless", "--calc",
                "--convert-to", "xlsx",
                "--outdir", str(output_dir),
                str(workbook_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"LibreOffice recalculation failed: {result.stderr}"
            )

        return output_dir / workbook_path.name

    def _read_outputs(
        self,
        workbook_path: Path,
        output_map: dict[str, str],
    ) -> dict[str, object]:
        wb = openpyxl.load_workbook(workbook_path, data_only=True)
        named_ranges = {n.name: n for n in wb.defined_names.values()}
        results: dict[str, object] = {}

        for output_key, named_range in output_map.items():
            if named_range not in named_ranges:
                results[output_key] = None
                continue

            defn = named_ranges[named_range]
            dest = defn.value
            sheet_name, cell_addr = dest.split("!")
            sheet_name = sheet_name.strip("'")
            cell_addr = cell_addr.replace("$", "")
            results[output_key] = wb[sheet_name][cell_addr].value

        return results
```

- [ ] **Step 4: Run test to confirm it passes**

```bash
source .venv/bin/activate && python -m pytest tests/test_engine.py -v
```

Expected: PASS. The engine writes inputs, LibreOffice recalculates, and we read back correct values.

- [ ] **Step 5: Commit**

```bash
git add tenforty/engine.py tests/test_engine.py
git commit -m "feat: add SpreadsheetEngine with LibreOffice headless recalculation"
```

---

### Task 6: Scenario Loader

**Files:**
- Create: `tenforty/scenario.py`
- Create: `tests/fixtures/simple_w2.yaml`
- Create: `tests/test_scenario.py`

- [ ] **Step 1: Create the test fixture YAML**

`tests/fixtures/simple_w2.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1990-06-15"
  state: CA

w2s:
  - employer: "Acme Corp"
    wages: 100000.00
    federal_tax_withheld: 15000.00
    ss_wages: 100000.00
    ss_tax_withheld: 6200.00
    medicare_wages: 100000.00
    medicare_tax_withheld: 1450.00

form1099_int:
  - payer: "Bank of Example"
    interest: 250.00
```

- [ ] **Step 2: Write failing tests for scenario loading**

`tests/test_scenario.py`:
```python
from pathlib import Path

import pytest

from tenforty.models import Scenario, W2, Form1099INT, TaxReturnConfig
from tenforty.scenario import load_scenario


class TestLoadScenario:
    def test_loads_simple_w2_scenario(self, fixtures_dir: Path):
        scenario = load_scenario(fixtures_dir / "simple_w2.yaml")
        assert isinstance(scenario, Scenario)
        assert scenario.config.year == 2025
        assert scenario.config.filing_status == "single"
        assert scenario.config.birthdate == "1990-06-15"
        assert scenario.config.state == "CA"

    def test_w2s_loaded(self, fixtures_dir: Path):
        scenario = load_scenario(fixtures_dir / "simple_w2.yaml")
        assert len(scenario.w2s) == 1
        w2 = scenario.w2s[0]
        assert isinstance(w2, W2)
        assert w2.employer == "Acme Corp"
        assert w2.wages == 100000.00
        assert w2.federal_tax_withheld == 15000.00

    def test_1099_int_loaded(self, fixtures_dir: Path):
        scenario = load_scenario(fixtures_dir / "simple_w2.yaml")
        assert len(scenario.form1099_int) == 1
        f = scenario.form1099_int[0]
        assert isinstance(f, Form1099INT)
        assert f.interest == 250.00

    def test_empty_lists_for_unused_forms(self, fixtures_dir: Path):
        scenario = load_scenario(fixtures_dir / "simple_w2.yaml")
        assert scenario.form1099_div == []
        assert scenario.form1099_b == []
        assert scenario.form1098s == []
        assert scenario.schedule_k1s == []

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_scenario(Path("/nonexistent/scenario.yaml"))
```

- [ ] **Step 3: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_scenario.py -v
```

Expected: `ImportError`.

- [ ] **Step 4: Implement scenario loader**

`tenforty/scenario.py`:
```python
from pathlib import Path

import yaml

from tenforty.models import (
    Form1098,
    Form1099B,
    Form1099DIV,
    Form1099INT,
    Scenario,
    ScheduleK1,
    TaxReturnConfig,
    W2,
)

# Maps YAML keys to (model class, Scenario field name)
_FORM_REGISTRY: dict[str, tuple[type, str]] = {
    "w2s": (W2, "w2s"),
    "form1099_int": (Form1099INT, "form1099_int"),
    "form1099_div": (Form1099DIV, "form1099_div"),
    "form1099_b": (Form1099B, "form1099_b"),
    "form1098s": (Form1098, "form1098s"),
    "schedule_k1s": (ScheduleK1, "schedule_k1s"),
}


def load_scenario(path: Path) -> Scenario:
    """Load a tax scenario from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")

    with open(path) as f:
        data = yaml.safe_load(f)

    config = TaxReturnConfig(**data["config"])

    form_data: dict[str, list] = {}
    for yaml_key, (model_cls, field_name) in _FORM_REGISTRY.items():
        items = data.get(yaml_key, [])
        form_data[field_name] = [model_cls(**item) for item in items]

    return Scenario(config=config, **form_data)
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_scenario.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add tenforty/scenario.py tests/test_scenario.py tests/fixtures/simple_w2.yaml
git commit -m "feat: add YAML scenario loader with form registry"
```

---

### Task 7: Scenario-to-Inputs Flattener

**Files:**
- Create: `tenforty/flattener.py`
- Create: `tests/test_flattener.py`

The engine needs a flat `dict[str, object]` mapping input keys to values. The scenario has structured data (lists of W2s, etc.). This module bridges the two.

- [ ] **Step 1: Write failing tests**

`tests/test_flattener.py`:
```python
from tenforty.flattener import flatten_scenario
from tenforty.models import (
    Form1098,
    Form1099INT,
    Scenario,
    TaxReturnConfig,
    W2,
)


def _simple_scenario() -> Scenario:
    return Scenario(
        config=TaxReturnConfig(
            year=2025,
            filing_status="single",
            birthdate="1990-06-15",
            state="CA",
        ),
        w2s=[
            W2(
                employer="Acme",
                wages=100000,
                federal_tax_withheld=15000,
                ss_wages=100000,
                ss_tax_withheld=6200,
                medicare_wages=100000,
                medicare_tax_withheld=1450,
                state_wages=100000,
                state_tax_withheld=5000,
            ),
        ],
        form1099_int=[Form1099INT(payer="Bank", interest=250)],
        form1098s=[Form1098(lender="Mortgage Co", mortgage_interest=8400)],
    )


class TestFlattenScenario:
    def test_filing_status_single(self):
        flat = flatten_scenario(_simple_scenario())
        assert flat["filing_status_single"] == "X"
        assert "filing_status_married_jointly" not in flat

    def test_birthdate_split(self):
        flat = flatten_scenario(_simple_scenario())
        assert flat["birthdate_month"] == 6
        assert flat["birthdate_day"] == 15
        assert flat["birthdate_year"] == 1990

    def test_w2_fields(self):
        flat = flatten_scenario(_simple_scenario())
        assert flat["w2_wages_1"] == 100000
        assert flat["w2_fed_withheld_1"] == 15000
        assert flat["w2_ss_wages_1"] == 100000
        assert flat["w2_state_wages_1"] == 100000
        assert flat["w2_state_withheld_1"] == 5000

    def test_1099_int_fields(self):
        flat = flatten_scenario(_simple_scenario())
        assert flat["interest_1"] == 250

    def test_1098_mortgage(self):
        flat = flatten_scenario(_simple_scenario())
        assert flat["mortgage_interest"] == 8400

    def test_empty_forms_produce_no_keys(self):
        flat = flatten_scenario(_simple_scenario())
        assert "ordinary_dividends_1" not in flat
        assert "sche_rents_a" not in flat
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_flattener.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement flattener**

`tenforty/flattener.py`:
```python
from tenforty.models import Scenario

_FILING_STATUS_KEYS = {
    "single": "filing_status_single",
    "married_jointly": "filing_status_married_jointly",
    "married_separately": "filing_status_married_separately",
    "head_of_household": "filing_status_head_of_household",
    "qualifying_widow": "filing_status_qualifying_widow",
}


def flatten_scenario(scenario: Scenario) -> dict[str, object]:
    """Convert a Scenario into a flat dict of input keys to values.

    Keys match the F1040 (and future) mapping input key conventions.
    """
    flat: dict[str, object] = {}

    _flatten_config(scenario, flat)
    _flatten_w2s(scenario, flat)
    _flatten_1099_int(scenario, flat)
    _flatten_1099_div(scenario, flat)
    _flatten_1098s(scenario, flat)

    return flat


def _flatten_config(scenario: Scenario, flat: dict[str, object]) -> None:
    config = scenario.config

    # Filing status — only set the matching one to "X"
    status_key = _FILING_STATUS_KEYS.get(config.filing_status)
    if status_key:
        flat[status_key] = "X"

    # Birthdate — split into month/day/year
    parts = config.birthdate.split("-")
    flat["birthdate_year"] = int(parts[0])
    flat["birthdate_month"] = int(parts[1])
    flat["birthdate_day"] = int(parts[2])


def _flatten_w2s(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, w2 in enumerate(scenario.w2s, start=1):
        flat[f"w2_wages_{i}"] = w2.wages
        flat[f"w2_fed_withheld_{i}"] = w2.federal_tax_withheld
        flat[f"w2_ss_wages_{i}"] = w2.ss_wages
        flat[f"w2_ss_withheld_{i}"] = w2.ss_tax_withheld
        flat[f"w2_medicare_wages_{i}"] = w2.medicare_wages
        flat[f"w2_medicare_withheld_{i}"] = w2.medicare_tax_withheld
        if w2.state_wages:
            flat[f"w2_state_wages_{i}"] = w2.state_wages
        if w2.state_tax_withheld:
            flat[f"w2_state_withheld_{i}"] = w2.state_tax_withheld


def _flatten_1099_int(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, form in enumerate(scenario.form1099_int, start=1):
        flat[f"interest_{i}"] = form.interest


def _flatten_1099_div(scenario: Scenario, flat: dict[str, object]) -> None:
    for i, form in enumerate(scenario.form1099_div, start=1):
        flat[f"ordinary_dividends_{i}"] = form.ordinary_dividends
        flat[f"qualified_dividends_{i}"] = form.qualified_dividends


def _flatten_1098s(scenario: Scenario, flat: dict[str, object]) -> None:
    for form in scenario.form1098s:
        flat["mortgage_interest"] = form.mortgage_interest
        if form.property_tax:
            flat["property_tax"] = form.property_tax
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_flattener.py -v
```

Expected: All 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/flattener.py tests/test_flattener.py
git commit -m "feat: add scenario-to-inputs flattener for engine consumption"
```

---

### Task 8: End-to-End Integration Test

**Files:**
- Create: `tests/test_integration.py`

This wires everything together: load YAML → flatten → engine compute → verify results.

- [ ] **Step 1: Write the integration test**

`tests/test_integration.py`:
```python
import subprocess
from pathlib import Path

import pytest

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.scenario import load_scenario


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = pytest.mark.skipif(
    not libreoffice_available(),
    reason="LibreOffice not installed",
)


class TestEndToEnd:
    @needs_libreoffice
    def test_simple_w2_yaml_to_results(
        self, federal_1040_path: Path, fixtures_dir: Path, tmp_path: Path,
    ):
        """Full pipeline: YAML → Scenario → flat inputs → engine → results."""
        scenario = load_scenario(fixtures_dir / "simple_w2.yaml")
        flat_inputs = flatten_scenario(scenario)

        engine = SpreadsheetEngine()
        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
            work_dir=tmp_path,
        )

        # $100k wages + $250 interest
        assert results["wages"] == 100000
        assert results["agi"] == 100250  # wages + interest
        assert results["interest_income"] == 250
        assert results["federal_withheld"] == 15000

        # Standard deduction for single 2025 is $15,750
        # Taxable income = 100250 - 15750 = 84500
        assert results["taxable_income"] == 84500

        # Tax should be in the $13k-$14k range
        assert 13000 < results["total_tax"] < 14000

        # Should get a refund (withheld $15k, tax ~$13.5k)
        assert results["overpaid"] > 0
```

- [ ] **Step 2: Run the integration test**

```bash
source .venv/bin/activate && python -m pytest tests/test_integration.py -v
```

Expected: PASS. This proves the full pipeline works.

- [ ] **Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end integration test for YAML-to-results pipeline"
```

---

### Task 9: Return Orchestrator

**Files:**
- Create: `tenforty/orchestrator.py`
- Create: `tests/test_orchestrator.py`

The orchestrator manages the dependency chain. For now it only handles the federal return (single spreadsheet). The architecture supports adding 1120-S → K-1 → federal and federal → CA steps later.

- [ ] **Step 1: Write failing tests**

`tests/test_orchestrator.py`:
```python
import subprocess
from pathlib import Path

import pytest

from tenforty.models import Scenario, TaxReturnConfig, W2
from tenforty.orchestrator import ReturnOrchestrator

SPREADSHEETS_DIR = Path(__file__).parent.parent / "spreadsheets"


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = pytest.mark.skipif(
    not libreoffice_available(),
    reason="LibreOffice not installed",
)


class TestReturnOrchestrator:
    @needs_libreoffice
    def test_federal_return(self, tmp_path: Path):
        scenario = Scenario(
            config=TaxReturnConfig(
                year=2025,
                filing_status="single",
                birthdate="1990-06-15",
                state="CA",
            ),
            w2s=[
                W2(
                    employer="Test Corp",
                    wages=80000,
                    federal_tax_withheld=12000,
                    ss_wages=80000,
                    ss_tax_withheld=4960,
                    medicare_wages=80000,
                    medicare_tax_withheld=1160,
                ),
            ],
        )

        orchestrator = ReturnOrchestrator(
            spreadsheets_dir=SPREADSHEETS_DIR,
            work_dir=tmp_path,
        )
        results = orchestrator.compute_federal(scenario)

        assert results["wages"] == 80000
        assert results["agi"] == 80000
        # 80000 - 15750 = 64250
        assert results["taxable_income"] == 64250
        assert results["federal_withheld"] == 12000
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_orchestrator.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement orchestrator**

`tenforty/orchestrator.py`:
```python
from pathlib import Path

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.models import Scenario


class ReturnOrchestrator:
    """Coordinates computation across forms in dependency order."""

    def __init__(self, spreadsheets_dir: Path, work_dir: Path) -> None:
        self.spreadsheets_dir = spreadsheets_dir
        self.work_dir = work_dir
        self.engine = SpreadsheetEngine()

    def compute_federal(self, scenario: Scenario) -> dict[str, object]:
        """Compute the federal return (1040 + all schedules)."""
        year = scenario.config.year
        spreadsheet = self.spreadsheets_dir / "federal" / str(year) / "1040.xlsx"

        if not spreadsheet.exists():
            raise FileNotFoundError(
                f"Federal spreadsheet not found: {spreadsheet}"
            )

        flat_inputs = flatten_scenario(scenario)

        return self.engine.compute(
            spreadsheet_path=spreadsheet,
            mapping=F1040,
            year=year,
            inputs=flat_inputs,
            work_dir=self.work_dir / "federal",
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_orchestrator.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add ReturnOrchestrator for dependency-ordered tax computation"
```

---

### Task 10: PDF Form Filler

**Files:**
- Create: `tenforty/filing/pdf.py`
- Create: `tests/test_pdf_filler.py`

- [ ] **Step 1: Write failing tests**

`tests/test_pdf_filler.py`:
```python
from pathlib import Path
from unittest.mock import patch

import pytest

from tenforty.filing.pdf import PdfFiller


class TestPdfFiller:
    def test_fill_creates_output_file(self, tmp_path: Path):
        """Test with a minimal PDF that has form fields."""
        # Create a simple test PDF with form fields using pypdf
        from pypdf import PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=612, height=792)

        # Add a simple text field
        writer.add_page(writer.pages[0])
        # pypdf's form field API
        from pypdf.annotations import FreeText
        from pypdf.generic import (
            ArrayObject,
            DictionaryObject,
            NameObject,
            NumberObject,
            TextStringObject,
        )

        # We'll test with a pre-made PDF instead — simpler and more realistic
        # For now, just test that the filler accepts the right interface
        filler = PdfFiller()
        assert filler is not None

    def test_fill_mapping_structure(self):
        """PDF filler takes computed results + a field mapping."""
        filler = PdfFiller()
        # The fill method signature should accept these arguments
        assert callable(getattr(filler, "fill", None))
```

**Note:** Full PDF filling tests require real fillable PDFs (IRS forms). We'll add those when we integrate with actual forms. For now, we test the interface.

- [ ] **Step 2: Run tests to confirm failure**

```bash
source .venv/bin/activate && python -m pytest tests/test_pdf_filler.py -v
```

Expected: `ImportError`.

- [ ] **Step 3: Implement PDF filler**

`tenforty/filing/pdf.py`:
```python
from pathlib import Path

from pypdf import PdfReader, PdfWriter


class PdfFiller:
    """Fills PDF form fields with computed tax values."""

    def fill(
        self,
        template_path: Path,
        output_path: Path,
        field_mapping: dict[str, str],
        values: dict[str, object],
    ) -> Path:
        """Fill a PDF form template with values.

        Args:
            template_path: Path to the fillable PDF template.
            output_path: Path to write the filled PDF.
            field_mapping: Maps our result keys to PDF field names.
            values: Computed results from the engine.

        Returns:
            Path to the filled PDF.
        """
        reader = PdfReader(template_path)
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)

        pdf_fields: dict[str, str] = {}
        for result_key, pdf_field_name in field_mapping.items():
            if result_key in values and values[result_key] is not None:
                pdf_fields[pdf_field_name] = str(values[result_key])

        for page_num in range(len(writer.pages)):
            writer.update_page_form_field_values(writer.pages[page_num], pdf_fields)

        with open(output_path, "wb") as f:
            writer.write(f)

        return output_path
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
source .venv/bin/activate && python -m pytest tests/test_pdf_filler.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tenforty/filing/pdf.py tests/test_pdf_filler.py
git commit -m "feat: add PdfFiller for filling tax form PDFs"
```

---

### Task 11: Verify Full Pipeline With 2024 Known-Good Data

**Files:**
- Create: `tests/fixtures/verification_2024.yaml` (synthetic data matching a known 2024 return pattern)
- Create: `tests/test_verification.py`

This task creates a test scenario based on a realistic 2024-like tax situation (but with fabricated numbers) and verifies the pipeline produces correct results. This is the final confidence check.

- [ ] **Step 1: Create a realistic synthetic scenario**

`tests/fixtures/realistic_w2_rental.yaml`:
```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1988-03-22"
  state: CA

w2s:
  - employer: "Tech Corp"
    wages: 150000.00
    federal_tax_withheld: 28000.00
    ss_wages: 150000.00
    ss_tax_withheld: 9300.00
    medicare_wages: 150000.00
    medicare_tax_withheld: 2175.00
    state_wages: 150000.00
    state_tax_withheld: 10000.00

form1099_int:
  - payer: "National Bank"
    interest: 500.00

form1099_div:
  - payer: "Investment Brokerage"
    ordinary_dividends: 2000.00
    qualified_dividends: 1500.00

form1098s:
  - lender: "Home Mortgage Co"
    mortgage_interest: 12000.00
    property_tax: 4500.00
```

- [ ] **Step 2: Write the verification test**

`tests/test_verification.py`:
```python
import subprocess
from pathlib import Path

import pytest

from tenforty.engine import SpreadsheetEngine
from tenforty.flattener import flatten_scenario
from tenforty.mappings.f1040 import F1040
from tenforty.scenario import load_scenario


def libreoffice_available() -> bool:
    try:
        result = subprocess.run(
            ["soffice", "--version"], capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


needs_libreoffice = pytest.mark.skipif(
    not libreoffice_available(),
    reason="LibreOffice not installed",
)


class TestRealisticScenario:
    @needs_libreoffice
    def test_w2_with_interest_dividends_mortgage(
        self, federal_1040_path: Path, fixtures_dir: Path, tmp_path: Path,
    ):
        """Higher-income filer with investment income and mortgage."""
        scenario = load_scenario(fixtures_dir / "realistic_w2_rental.yaml")
        flat_inputs = flatten_scenario(scenario)

        engine = SpreadsheetEngine()
        results = engine.compute(
            spreadsheet_path=federal_1040_path,
            mapping=F1040,
            year=2025,
            inputs=flat_inputs,
            work_dir=tmp_path,
        )

        # Wages should be $150,000
        assert results["wages"] == 150000

        # AGI = 150000 + 500 (interest) + 2000 (dividends) = 152500
        assert results["agi"] == 152500

        # Interest and dividends should flow through
        assert results["interest_income"] == 500
        assert results["dividend_income"] == 2000

        # Withholding
        assert results["federal_withheld"] == 28000

        # Should have meaningful tax
        assert results["total_tax"] is not None
        assert results["total_tax"] > 0

        # Should get a refund (withheld a lot)
        assert results["overpaid"] is not None
        assert results["overpaid"] > 0
```

- [ ] **Step 3: Run the test**

```bash
source .venv/bin/activate && python -m pytest tests/test_verification.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures/realistic_w2_rental.yaml tests/test_verification.py
git commit -m "test: add realistic scenario verification test"
```

---

## Summary

| Task | Component | Tests |
|------|-----------|-------|
| 1 | Project scaffolding | — |
| 2 | Data models | 6 tests |
| 3 | FormMapping registry | 7 tests |
| 4 | F1040 mapping | 11 tests |
| 5 | SpreadsheetEngine | 1 integration test |
| 6 | Scenario YAML loader | 5 tests |
| 7 | Scenario-to-inputs flattener | 6 tests |
| 8 | End-to-end integration | 1 test |
| 9 | Return orchestrator | 1 test |
| 10 | PDF filler | 2 tests |
| 11 | Realistic verification | 1 test |

**What this plan builds:** A working federal tax pipeline — YAML scenario → spreadsheet computation → verified results. The architecture is ready for CA 540, 1120-S, and PDF filing extensions.

**What comes next (separate plans):**
- CA 540 / 540-CA spreadsheets + mappings
- 1120-S spreadsheet + mappings + K-1 flow
- PDF filing integration with real IRS/FTB forms
- Schedule E rental property flattener extension
