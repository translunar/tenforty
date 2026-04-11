# tenforty

A tax preparation harness that uses spreadsheets as the computation engine and verifies results through multiple independent paths.

## Why this exists

Filing US taxes by hand is error-prone. Tax software is expensive and opaque. LLM-generated tax code is fast to write but hard to trust — how do you know the calculations are right?

tenforty takes a different approach: **don't write tax calculations at all.** Instead, delegate computation to an existing, battle-tested Excel spreadsheet maintained by a human tax expert, and use Python to orchestrate the data flow, fill PDF forms, and verify everything matches.

The key insight: the IRS publishes fillable PDFs. A third-party maintains an Excel spreadsheet with every federal form. If we feed the same inputs to both and they agree, we have high confidence the results are correct — without writing (or trusting) a single line of tax math.

## How it works

```
scenario.yaml → SpreadsheetEngine → ResultTranslator → PdfFiller → filled 1040.pdf
     │                  │                                    │
     │           LibreOffice headless              IRS fillable PDF
     │           recalculates the XLS              template
     │                  │                                    │
     └──────────────────┴────── round-trip verifier ─────────┘
                                (values must match)
```

1. **Scenario file** (YAML) describes your tax situation: W-2s, 1099s, 1098s, filing status
2. **SpreadsheetEngine** writes inputs into the third-party XLS, triggers LibreOffice to recalculate, reads computed results
3. **ResultTranslator** maps engine output keys to PDF field names
4. **PdfFiller** fills the IRS's fillable PDF forms with the computed values
5. **Round-trip verifier** reads the filled PDF back and asserts every value matches what the engine computed

## Quick start

### Prerequisites

- Python 3.12+
- LibreOffice (`brew install --cask libreoffice`)
- The 2025 federal XLS from [incometaxspreadsheet.com](https://sites.google.com/view/incometaxspreadsheet/home) (already included at `spreadsheets/federal/2025/1040.xlsx`)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests that require LibreOffice (~18s each) are skipped if it's not installed. Tests that require the IRS f1040 PDF template are skipped if it's not at `/tmp/f1040_2025.pdf`.

### Prepare a tax return

Create a scenario file (e.g., `~/Documents/Taxes/2025/scenario.yaml`):

```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1990-06-15"
  state: CA

w2s:
  - employer: "Employer Name"
    wages: 100000.00
    federal_tax_withheld: 15000.00
    ss_wages: 100000.00
    ss_tax_withheld: 6200.00
    medicare_wages: 100000.00
    medicare_tax_withheld: 1450.00

form1099_int:
  - payer: "Bank Name"
    interest: 250.00
```

Run the pipeline:

```python
from pathlib import Path
from tenforty.scenario import load_scenario
from tenforty.orchestrator import ReturnOrchestrator

scenario = load_scenario(Path("~/Documents/Taxes/2025/scenario.yaml").expanduser())
orchestrator = ReturnOrchestrator(
    spreadsheets_dir=Path("spreadsheets"),
    work_dir=Path("/tmp/tenforty"),
)
results = orchestrator.compute_federal(scenario)

for key in ["wages", "agi", "taxable_income", "total_tax", "overpaid"]:
    print(f"  {key}: ${float(results[key]):,.0f}")
```

### Fill a PDF

```python
from tenforty.filing.pdf import PdfFiller
from tenforty.mappings.pdf_1040 import Pdf1040
from tenforty.result_translator import ResultTranslator
from tenforty.translations.f1040_pdf import F1040_PDF_SPEC

translator = ResultTranslator(F1040_PDF_SPEC)
translated = translator.translate(results, scenario)

filler = PdfFiller()
filler.fill(
    template_path=Path("/tmp/f1040_2025.pdf"),
    output_path=Path("~/Documents/Taxes/2025/f1040_draft.pdf").expanduser(),
    field_mapping=Pdf1040.get_mapping(2025),
    values=translated,
)
```

## For agents

If you're an AI agent pointed at this repository, here's how to orient:

### Architecture

- `tenforty/models.py` — Dataclasses for tax documents (W2, Form1099INT, Form1099DIV, Form1099B, Form1098, ScheduleK1, Scenario)
- `tenforty/scenario.py` — Loads YAML scenario files into model instances
- `tenforty/flattener.py` — Converts structured Scenario into flat `dict[str, object]` for the engine. **Raises NotImplementedError if the scenario contains form types it can't handle yet** (prevents silent data loss)
- `tenforty/engine.py` — SpreadsheetEngine: writes inputs to XLS via openpyxl, recalculates via `soffice --headless`, reads outputs. Core function: `_resolve_named_range(defn)` parses XLS named ranges
- `tenforty/mappings/` — Maps between our key names and spreadsheet cells / PDF fields:
  - `registry.py` — `FormMapping` base class with `get_inputs(year)`, `get_outputs(year)`, `inherit()`
  - `f1040.py` — Federal 1040 XLS mapping (INPUTS, OUTPUTS, SHEET_MAP). Covers W-2, 1099-INT/DIV, Schedule A, Schedule E cells
  - `pdf_1040.py` — IRS f1040.pdf field mapping (69 fields mapped to opaque PDF field names like `topmostSubform[0].Page1[0].f1_47[0]`)
- `tenforty/result_translator.py` — Bridges engine output keys to PDF field keys. Handles renames (one-to-one), expansions (one-to-many), and scenario field extraction
- `tenforty/translations/f1040_pdf.py` — Concrete translation spec for federal 1040
- `tenforty/orchestrator.py` — Coordinates computation across forms in dependency order
- `tenforty/filing/pdf.py` — Fills PDF forms via pypdf. Must use `PdfWriter(clone_from=reader)` (not `append_pages_from_reader`)

### Testing

- `tests/helpers.py` — Shared constants, `libreoffice_available()`, skip decorators
- `tests/invariants.py` — Structural assertions (`assert_agi_consistent`, `assert_tax_is_non_negative`, etc.) and `verify_pdf_round_trip` for end-to-end verification
- `tests/fixtures/` — Synthetic YAML scenarios (all dollar amounts divisible by 50, all employer names from an allowlist)
- `scripts/verify_no_personal_data.py` — Pre-commit hook scans for personal data leaks (denylist, allowlist, heuristics, git history)

### Key patterns

- **Year-keyed mappings**: `F1040.get_inputs(2025)` returns the 2025 mapping. Add `2026` key for next year.
- **Two types of cell references**: Named ranges (e.g., `"File_Single"`) resolved by openpyxl, and direct cell refs (e.g., `"C3"`) that need a `SHEET_MAP` entry to know which sheet they're on.
- **Flattener rejects unknown forms**: If you add a new form type to the Scenario model, you must also add a `_flatten_*` function or the flattener will raise `NotImplementedError`.
- **Personal data never enters the repo**: Real tax data lives in `~/Documents/Taxes/`. Test fixtures use synthetic data. A pre-commit hook enforces this.

### Adding a new tax year

1. Download the new XLS → `spreadsheets/federal/YYYY/1040.xlsx`
2. Add `YYYY` key to `F1040.INPUTS` and `F1040.OUTPUTS` (use `inherit()` for minimal diffs)
3. Download the new IRS f1040.pdf, label fields, update `Pdf1040._MAPPINGS`
4. Update `docs/coverage/YYYY-field-coverage.md`

### Adding a new form (e.g., Schedule C)

1. Add cell references to `F1040.INPUTS` and `SHEET_MAP`
2. Add output named ranges to `F1040.OUTPUTS`
3. Add a model in `models.py`, a `_flatten_*` function in `flattener.py`
4. If it has its own PDF, create a `PdfScheduleC` mapping and translation spec
5. Write e2e test with a fixture that exercises the form

## Verification approach

The core idea: **use independently-maintained systems as verification oracles.**

| System | Maintained by | Role |
|--------|--------------|------|
| Federal XLS spreadsheet | Third-party tax expert (updated annually) | Primary computation engine |
| IRS fillable PDFs | The IRS | Output format + secondary verification |
| Our Python code | Us | Orchestration, data flow, testing — no tax math |

The round-trip verifier proves the chain is unbroken: engine → translator → PDF filler → read back. If any mapping is wrong, the verifier catches it.

Structural invariants (AGI = income - adjustments, tax >= 0, refund + owed = payments - tax) catch logical errors without knowing the "right" answer.

The pre-commit hook catches personal data leaks before they reach git history.

## Project status

**Working:** Federal 1040 pipeline (W-2, 1099-INT, 1099-DIV with capital gain distributions, 1098 mortgage/property tax, Schedule A itemized deductions). PDF filling and round-trip verification for the 1040.

**In progress:** Schedule D/8949 (capital gains from stock sales), Schedule E Part II (K-1 pass-through from S-corp). Tests are written but RED — the flattener correctly rejects these form types until implementation is complete.

**Planned:** California 540/540-CA, Form 1120-S, Form 8962 (Premium Tax Credit), Playwright automation for freefilefillableforms.com.

## License

MIT
