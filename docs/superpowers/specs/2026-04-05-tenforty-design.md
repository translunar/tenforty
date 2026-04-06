# tenforty — Tax Preparation Harness

**Date:** 2026-04-05
**Status:** Draft
**Goal:** Build a testable, year-over-year maintainable harness for preparing federal, California, and S-corp tax returns.

## Problem

Filing taxes manually is error-prone and tedious. The user currently fills a federal XLS spreadsheet by hand, copies values into freefilefillableforms.com, and does California forms entirely by hand. There's no automated verification, no tests, and the process doesn't carry forward cleanly between years.

## Approach

**tenforty is a harness, not a calculator.** Tax computations live in spreadsheets (the natural tool for the job). The harness orchestrates: loading input data, writing it into spreadsheets, triggering recalculation via LibreOffice headless, reading computed results, and filling filing targets (web forms and PDFs).

A third-party XLS spreadsheet (from incometaxspreadsheet.com) handles all federal form calculations. For forms it doesn't cover (1120-S, K-1, California 540/540-CA), we create our own .xlsx files with formulas transcribed from IRS/FTB instructions. The same engine drives all spreadsheets.

## Architecture

### Three Layers

1. **Data layer** — typed Python structures representing tax inputs and outputs
2. **Computation layer** — the spreadsheet harness (write → recalculate → read)
3. **Filing layer** — Playwright for freefilefillableforms.com, pypdf for California PDFs

### Dependency Chain

Forms feed into each other in a specific order:

```
1120-S → K-1 → federal XLS (Schedule E, 1040) → CA 540 → CA 540-CA
```

The harness resolves this by running forms in dependency order, piping outputs from one into inputs of the next. K-1 values feed into the federal XLS's Schedule E inputs; 1040 results feed into California 540 inputs.

## Data Layer

### Input Documents

Tax inputs are represented as Python dataclasses organized by source document:

- `W2` — wages, withholding, SS/Medicare
- `Form1099INT` — interest income
- `Form1099DIV` — dividends (qualified vs ordinary)
- `Form1099B` — brokerage sales
- `Form1098` — mortgage interest
- `ScheduleK1` — pass-through income from S-corp
- Additional forms as needed

### Tax Return Config

Filing status, birthdate, dependents, state residency — things that don't come from a single document.

### Scenario File

A single YAML file bundles all inputs for one tax return:

```yaml
year: 2025
filing_status: single
birthdate: 1990-06-15
state: CA

w2s:
  - employer: "Acme Corp"
    wages: 100000
    federal_tax_withheld: 15000
    ss_wages: 100000
    ss_tax_withheld: 6200
    medicare_wages: 100000
    medicare_tax_withheld: 1450

form1099_int:
  - payer: "Bank of Example"
    interest: 250

# ... etc
```

For real taxes, this file lives in `~/Documents/Taxes/2025/scenario.yaml` — outside the repo entirely. For tests, synthetic scenarios live in `tests/fixtures/`.

## Computation Layer

### Spreadsheet Engine

A single `SpreadsheetEngine` class handles all spreadsheets uniformly:

1. Copies the source spreadsheet to a working location
2. Writes input values into named ranges via openpyxl
3. Recalculates formulas via `soffice --headless --calc --convert-to xlsx`
4. Reads computed output values from named ranges via openpyxl

```python
class SpreadsheetEngine:
    def compute(
        self,
        spreadsheet_path: Path,
        mapping: type[FormMapping],
        year: int,
        inputs: dict[str, object],
    ) -> dict[str, object]:
        ...
```

### Form Mappings

A shared `FormMapping` base class provides year-keyed lookup with inheritance for year-over-year deltas. Each mapping distinguishes **inputs** (what we write into the spreadsheet) from **outputs** (what we read back after recalculation):

```python
class FormMapping:
    """Base for all form mappings. Subclasses define INPUTS and OUTPUTS by year."""

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
        """Create a new year's mapping by overriding specific fields."""
        base = cls.INPUTS if source == "inputs" else cls.OUTPUTS
        return {**base[base_year], **overrides}
```

Each form mapping is pure data — a subclass with `INPUTS` and `OUTPUTS` dicts:

```python
class F1040(FormMapping):
    INPUTS = {
        2025: {
            'wages': 'W2_Wages_You',
            'filing_status_single': 'File_Single',
            'birthdate_month': 'YourBirthMonth',
            # ...
        },
    }
    OUTPUTS = {
        2025: {
            'agi': 'Adj_Gross_Inc',
            'taxable_income': 'Taxable_Inc',
            'total_tax': 'Tax',
            'refund': 'Overpaid',
            # ...
        },
    }
```

Usage: `F1040.get_inputs(2025)`, `F1040.get_outputs(2025)`, etc.

Note: `F1040` covers the entire federal workbook (all sheets), not just the 1040 sheet. The federal XLS is one workbook with schedules as separate sheets, all connected by cross-sheet formulas. A single mapping class covers all of them.

### Federal Forms Coverage

The F1040 mapping must cover inputs/outputs for at least these sheets in the federal XLS:

- **1040** — core return
- **W-2s** — wage input
- **1099-INT, 1099-DIV, 1099-B** — investment income inputs
- **Schedule 1** — additional income and adjustments
- **Schedule A** — itemized deductions (mortgage interest, SALT)
- **Schedule D + 8949** — capital gains/losses
- **Schedule E** — rental property income/loss
- **Schedule C** — self-employment income (1099-NEC)
- **Schedule SE** — self-employment tax

Additional sheets are mapped as needed. The XLS contains many more forms; we only map the ones actually used.

### Spreadsheets

- **Federal:** third-party XLS from incometaxspreadsheet.com. Covers 1040, Schedules A-F, SE, and most common forms. 874 named ranges provide stable cell references.
- **California 540 / 540-CA:** our own .xlsx files, formulas transcribed from FTB instructions.
- **1120-S:** our own .xlsx file, formulas transcribed from IRS instructions.

### Return Orchestrator

Coordinates the full computation across forms in dependency order:

1. Run 1120-S spreadsheet → extract K-1 outputs
2. Feed K-1 outputs + all other inputs into the federal XLS → extract 1040 results
3. Feed 1040 results + CA-specific inputs into CA 540 spreadsheet → extract CA results
4. Feed CA 540 results into CA 540-CA spreadsheet → extract final CA results

## Filing Layer

Filing is implemented in two phases. Phase 1 (pypdf) is sufficient for both federal and California. Phase 2 (Playwright) adds electronic filing but is not required.

### Phase 1: PDF Filling (pypdf)

Works for all jurisdictions — federal, California, and 1120-S all have fillable PDF forms available.

- Maps computed results to PDF form field names
- Outputs completed PDFs for review
- Verifies field values against spreadsheet-computed results
- Federal PDFs can be printed and mailed, or uploaded to freefilefillableforms.com manually

### Phase 2: Electronic Filing via Playwright (optional, future)

- Automates freefilefillableforms.com for federal electronic filing
- Maps computed results to web form fields (CSS selectors or labels)
- Reads back the site's own computed values and compares to our XLS results
- **Stops and flags discrepancies** — does not auto-submit
- Final submission is always manual
- Only pursued if Phase 1's manual upload is too painful

## Testing Strategy

### Unit Tests — Mapping Correctness

Given a synthetic scenario, assert the right values are written to the right cells. No LibreOffice needed — just verify openpyxl writes.

### Integration Tests — Computation Correctness

Given a synthetic scenario, run the full pipeline (write → LO recalculate → read) and assert output values match expected results. Canonical test scenarios:

- Simple W-2 single filer (standard deduction)
- Married filing jointly with dependents
- Rental property with Schedule E
- S-corp with 1120-S / K-1 flow
- California 540 with federal data

### Cross-Verification Tests — Filing Correctness

Fill freefilefillableforms.com with a test scenario via Playwright, read back computed values, assert they match XLS output. Catches mapping errors in the filing layer.

### Test Data

All fixtures use synthetic (fabricated) numbers. No personal data in the repo, ever.

## Repository Structure

```
tenforty/
├── tenforty/
│   ├── __init__.py
│   ├── models/                  # Dataclasses: W2, Form1099, Scenario, etc.
│   │   └── __init__.py
│   ├── mappings/
│   │   ├── __init__.py
│   │   ├── registry.py          # FormMapping base class
│   │   ├── f1040.py             # Federal 1040 mappings (all years)
│   │   ├── ca540.py             # California 540 mappings (all years)
│   │   └── f1120s.py            # Form 1120-S mappings (all years)
│   ├── engine.py                # SpreadsheetEngine — write, recalc, read
│   ├── orchestrator.py          # Return orchestrator — dependency ordering
│   ├── scenario.py              # YAML scenario loader
│   └── filing/
│       ├── __init__.py
│       └── pdf.py               # pypdf form filler (federal + CA + 1120-S)
├── spreadsheets/
│   ├── federal/
│   │   └── 2025/
│   │       └── 1040.xlsx        # Third-party XLS
│   ├── california/
│   │   └── 2025/
│   │       ├── 540.xlsx         # Our spreadsheet
│   │       └── 540ca.xlsx
│   └── business/
│       └── 2025/
│           └── 1120s.xlsx       # Our spreadsheet
├── tests/
│   ├── fixtures/                # Synthetic scenario YAML files
│   ├── test_mappings/
│   ├── test_engine/
│   └── test_filing/
├── pyproject.toml
└── .gitignore
```

### Year-Over-Year Maintenance

When 2026 arrives:

1. Download new federal XLS → `spreadsheets/federal/2026/1040.xlsx`
2. Add `2026` key to mapping dicts (use `inherit()` for minimal diffs)
3. Update CA and 1120-S spreadsheets for any form changes
4. Add new test fixtures for 2026-specific scenarios
5. 2025 files stay frozen — old years are never modified

## Dependencies

- **openpyxl** — read/write Excel files
- **PyYAML** — parse scenario files
- **pypdf** — fill PDF forms (federal, California, 1120-S)
- **playwright** — (Phase 2, optional) automate freefilefillableforms.com
- **pytest** — test framework
- **LibreOffice** — formula evaluation (system dependency, installed via `brew install --cask libreoffice`)

## Out of Scope

- Automated generation of spreadsheets from IRS form instructions (future work)
- State taxes other than California
- Tax situations beyond the user's current needs (trusts, estates, foreign income, etc.)
- Multi-user / SaaS features
- Rewriting the tax-preparation plugin's calculation scripts (superseded by the spreadsheet approach)
