# tenforty Architecture & Agent Handbook

This document captures everything an agent or developer needs to work on tenforty effectively. It reflects the actual state of the repository — not aspirational plans.

## Core Concept

**tenforty is a harness, not a calculator.** Tax computations live in spreadsheets. The Python code orchestrates data flow, fills PDF forms, and verifies correctness. We never write tax math.

The verification approach: feed the same inputs to an independently-maintained Excel spreadsheet AND to IRS fillable PDFs. If both agree, we trust the result — without writing (or trusting) a single line of tax calculation code.

## Pipeline

```
scenario.yaml
    ↓ load_scenario()
Scenario (dataclasses)
    ↓ flatten_scenario()
dict[str, object]  (flat key-value pairs)
    ↓ SpreadsheetEngine.compute()
        ↓ openpyxl writes inputs to XLS cells
        ↓ soffice --headless recalculates (~18s)
        ↓ openpyxl reads computed outputs
dict[str, object]  (engine results)
    ↓ ResultTranslator.translate()
dict[str, object]  (PDF-namespace keys)
    ↓ PdfFiller.fill()
filled f1040.pdf
```

## Module Map

### Core Pipeline

| Module | Purpose | Key Types/Functions |
|--------|---------|-------------------|
| `models.py` | Dataclasses for tax documents | `W2`, `Form1099INT`, `Form1099DIV`, `Form1099B`, `Form1098`, `ScheduleK1`, `RentalProperty`, `TaxReturnConfig`, `Scenario`, `FilingStatus` |
| `scenario.py` | YAML → Scenario | `load_scenario(path)`. Uses `_FORM_REGISTRY` dict to map YAML keys to model classes. Add new form types here. |
| `flattener.py` | Scenario → flat dict | `flatten_scenario(scenario)`. One `_flatten_*` function per form type. **Raises NotImplementedError for unhandled form types** — prevents silent data loss. |
| `engine.py` | Spreadsheet computation | `SpreadsheetEngine.compute(path, mapping, year, inputs, work_dir)`. `_resolve_named_range(defn)` parses XLS named ranges. |
| `orchestrator.py` | High-level API | `ReturnOrchestrator.compute_federal(scenario)`. Finds the right XLS, flattens, computes. |
| `result_translator.py` | Engine keys → PDF keys | `ResultTranslator(spec).translate(results, scenario)`. Handles renames, expansions, scenario field extraction. |
| `filing/pdf.py` | Fill PDF forms | `PdfFiller.fill(template, output, mapping, values)`. **Must use `PdfWriter(clone_from=reader)` — `append_pages_from_reader` strips form fields.** |
| `__main__.py` | CLI | `python -m tenforty scenario.yaml [spreadsheets_dir]` |

### Mappings

| Module | Purpose | Notes |
|--------|---------|-------|
| `mappings/registry.py` | Base class | `FormMapping` with `get_inputs(year)`, `get_outputs(year)`, `inherit()` |
| `mappings/f1040.py` | XLS cell mapping | `F1040` — covers ALL sheets in the federal workbook (W-2s, 1099-INT, 1099-DIV, Sch. A, Sch. E, etc.). Has `INPUTS`, `OUTPUTS`, and `SHEET_MAP`. |
| `mappings/pdf_1040.py` | PDF field mapping | `Pdf1040` — 69 fields mapped to opaque IRS field names. **Does not inherit from FormMapping** (intentional — output-only, different pattern). |
| `translations/f1040_pdf.py` | Engine→PDF key bridge | `F1040_PDF_SPEC` — renames (`interest_income`→`taxable_interest`) and expansions (`agi`→`[agi, agi_page2]`). |

### Two Types of Cell References in F1040

1. **Named ranges** (e.g., `"File_Single"`, `"Adj_Gross_Inc"`) — resolved by openpyxl from the workbook's defined names. Used for filing status, birthdate, and output values.
2. **Direct cell refs** (e.g., `"C3"`, `"V33"`) — require a `SHEET_MAP` entry mapping the input key to a sheet name. Used for W-2 fields, 1099 fields, Schedule E expense lines.

The engine checks: is the value a named range? → resolve it. Is the key in SHEET_MAP? → use that sheet + the cell ref. Neither? → raise ValueError.

## XLS Spreadsheet Details

### Federal 2025

- File: `spreadsheets/federal/2025/1040.xlsx` (third-party, from incometaxspreadsheet.com)
- ODS copy: `spreadsheets/federal/2025/1040.ods` (pre-converted, opens faster in UNO)
- 874 named ranges
- ~60 sheets covering all common federal forms
- Key sheets: `1040`, `W-2s`, `1099-INT`, `1099-DIV`, `Sch. A`, `Sch. E`, `Sch. D`, `Tax Table`

### XLS Gotchas

- **Birthdate required**: The XLS won't compute the standard deduction without YourBirthMonth/Day/Year (needs to know if 65+).
- **Merged cells**: Some Schedule E cells (V21, AD21) are merged. openpyxl can't write to merged cells — must write to the top-left cell of the merge range. Fair rental days → AA21, personal use days → AF21.
- **W-2 state wages**: Cell C26 is NOT state wages (it's RRTA medicare tax). State wages = C28, state tax withheld = C29.
- **1099-INT/DIV cell refs**: The interest/dividend input cells are on specific columns for "Payer #1". Interest → D6 on 1099-INT sheet. Ordinary dividends → D6, qualified → D7, cap gain distributions → D8 on 1099-DIV sheet.
- **Tax uses IRS tax table rounding**: The XLS matches the IRS tax table ($50 brackets) rather than exact bracket math, so computed tax may differ by a few dollars from manual calculation.
- **LibreOffice recalculation**: `soffice --headless --calc --convert-to xlsx` forces a full recalculation. Takes ~18s for this large workbook.

## Testing

### Structure

- `tests/helpers.py` — Shared constants (`SPREADSHEETS_DIR`, `FIXTURES_DIR`, `F1040_PDF`), `libreoffice_available()`, skip decorators (`needs_libreoffice`, `needs_pdf`), `make_simple_scenario()`.
- `tests/invariants.py` — Structural assertion functions and `verify_pdf_round_trip()`.
- `tests/fixtures/` — Synthetic YAML scenarios (all amounts divisible by 50, all names from allowlist).

### Conventions

- All test classes inherit from `unittest.TestCase`.
- Use `self.assertEqual()`, `self.assertGreater()`, etc. — never bare `assert`.
- PEP8 typing: `dict[str, str]`, not `Dict[str, str]`.
- All imports at top of file. No inline imports.
- Tuples with 3+ items must be dataclasses.
- `FilingStatus` is a `str, Enum` — validates on construction, compares as string.

### Test Categories

| Category | Speed | Skip Condition | Examples |
|----------|-------|---------------|----------|
| Unit tests | <1s | None | `test_models.py`, `test_registry.py`, `test_flattener.py` |
| Integration tests | ~18s each | `needs_libreoffice` | `test_engine.py`, `test_integration.py` |
| E2E tests | ~18s each | `needs_libreoffice` | `test_e2e_simple_w2.py`, `test_e2e_itemized.py` |
| PDF round-trip | ~20s each | `needs_libreoffice` + `needs_pdf` | `test_round_trip.py`, `test_round_trip_max_coverage.py` |
| Intentionally RED | ~18s each | `needs_libreoffice` | `test_e2e_full_return.py` — tests for unimplemented forms |

### E2E tests cache results

Tests that call `compute_federal` multiple times with the same scenario use `setUpClass` to compute once:
```python
@classmethod
def setUpClass(cls):
    cls._results = orchestrator.compute_federal(cls._scenario)
```

### Structural Invariants

| Invariant | What it checks |
|-----------|---------------|
| `assert_agi_consistent` | AGI ≤ sum of all income sources (wages + interest + dividends + cap gain distributions) |
| `assert_all_income_accounted_for` | AGI ≥ wages + 50% of non-wage income (catches silently dropped forms) |
| `assert_taxable_income_consistent` | 0 ≤ taxable income ≤ AGI |
| `assert_tax_is_non_negative` | Tax ≥ 0 |
| `assert_refund_or_owed_consistent` | If overpaid > 0, payments > tax; if overpaid = 0, payments ≤ tax |
| `assert_withholding_matches_input` | Federal withholding in results = sum of W-2 withholding in scenario |
| `verify_pdf_round_trip` | Engine → translate → fill PDF → read back → all values match. Coverage gaps (cross-form keys) printed as info. |

## Personal Data Protection

### Pre-commit hook

`scripts/verify_no_personal_data.py` runs on every commit. Four checks:

1. **Denylist**: Rejects SSN/EIN patterns. User-specific patterns (real employer names) loaded from `scripts/personal_data_config.yaml` (gitignored).
2. **Allowlist**: YAML fixture employer/payer names must be from `ALLOWED_NAMES` set.
3. **Heuristic**: Dollar amounts in fixtures must be divisible by $50.
4. **Git history**: Scans commit messages for denylist patterns.

### Real data location

- Real scenario files: `~/Documents/Taxes/YYYY/scenario.yaml` — NEVER in the repo.
- The `.gitignore` covers `personal/`, `private/`, `scenario_real.yaml`, and `scripts/personal_data_config.yaml`.

## Known Limitations & Future Work

### Currently Working

- Federal 1040 (W-2, 1099-INT, 1099-DIV with cap gain distributions, 1098 mortgage/property tax, Schedule A itemized, Schedule E Part I rental property)
- PDF filling for f1040.pdf
- Round-trip PDF verification (15/69 fields verified)
- CLI entry point

### Intentionally RED Tests (forms not yet wired)

- `test_e2e_full_return.py` — 11 tests fail with `NotImplementedError`:
  - **1099-B** (capital gains from stock sales) — needs `_flatten_1099_b()` + 8949 cell mappings
  - **Schedule K-1** (S-corp pass-through) — needs `_flatten_k1s()` + Schedule E Part II cell mappings

### Not Yet Implemented

- California 540 / 540-CA (need own spreadsheets)
- Form 1120-S (S-corp return, separate spreadsheet)
- Form 8962 (Premium Tax Credit)
- Schedule PDF mappings (Schedule A, D, E PDFs)
- Playwright automation for freefilefillableforms.com

### Speed Optimization

- Current: ~18s per scenario (cold-start LibreOffice)
- `UnoEngine` exists using `unoconvert` but provides NO meaningful speedup (file-based conversion is still ~16-18s)
- **In-process UNO API achieves ~0.1s/scenario** (benchmarked, documented in `docs/superpowers/plans/2026-04-09-verification-and-speed.md` appendix). Requires: macOS code re-signing of LibreOffice's Python, running under LO's Python 3.12, keeping document open in memory.
- Prerequisite for in-process UNO on macOS:
  ```bash
  codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/LibreOfficePython"
  codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework"
  codesign --force --deep --sign - "/Applications/LibreOffice.app"
  ```

## How To

### Add a new tax year

1. Download new XLS → `spreadsheets/federal/YYYY/1040.xlsx`
2. Add `YYYY` key to `F1040.INPUTS` and `F1040.OUTPUTS` (use `inherit()` for minimal diffs)
3. Convert to ODS: `python scripts/convert_to_ods.py spreadsheets/federal/YYYY/1040.xlsx`
4. Download new f1040.pdf, label fields (fill with field names, render), update `Pdf1040._MAPPINGS`
5. Create `docs/coverage/YYYY-field-coverage.md`
6. Run full test suite

### Add a new form type

1. Add dataclass in `models.py`
2. Add field to `Scenario`
3. Add `_flatten_*` function in `flattener.py`
4. Add cell references to `F1040.INPUTS` and `F1040.SHEET_MAP`
5. Add output named ranges to `F1040.OUTPUTS`
6. Add to `_FORM_REGISTRY` in `scenario.py`
7. If the form has its own PDF, create a `Pdf*` mapping class and translation spec
8. Write tests (unit + e2e)
9. Remove the form from the `_reject_unhandled` check in `flattener.py`

### Debug a wrong value

1. Check the flattened keys: `flatten_scenario(scenario)` — is the value present?
2. Check the cell mapping: does `F1040.get_inputs(2025)[key]` point to the right cell?
3. Check the sheet: is the key in `F1040.SHEET_MAP`?
4. Open the XLS manually and check the cell — is it merged? Is it the right row/column?
5. Check the engine output: `orchestrator.compute_federal(scenario)` — does the value appear?
6. If the value is for a PDF, check the translation: does `F1040_PDF_SPEC` rename or expand it?

### Run the user's real taxes

```bash
python -m tenforty ~/Documents/Taxes/2025/scenario.yaml
```

The scenario file is outside the repo. Results print to terminal only. To generate a filled PDF:

```python
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.result_translator import ResultTranslator
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC

translator = ResultTranslator(F1040_PDF_SPEC)
translated = translator.translate(results, scenario)
PdfFiller().fill(Path("/tmp/f1040_2025.pdf"), Path("output.pdf"), Pdf1040.get_mapping(2025), translated)
```
