# tenforty Architecture & Agent Handbook

This document captures everything an agent or developer needs to work on tenforty effectively. It reflects the actual state of the repository — not aspirational plans.

## Core Concept

tenforty computes US federal + California individual income tax returns. Each form has at least two independent implementations, and they're cross-checked. No single implementation is trusted in isolation.

**Production calculators, by form:**
- **Federal 1040 spine** (1040, Sch 1, Sch A, Sch D, Sch E, etc.): a third-party Excel spreadsheet (incometaxspreadsheet.com). Native Python `forms/sch_*.compute` modules are PDF-emit helpers + cross-checkers.
- **Form 1120-S** (S-corp): native Python. Wired via `compute_corporate`.
- **California 540 + Sch CA + Sch D 540 + Sch P 540**: native Python. Wired via `run_full_california_return`.

**Cross-checkers, by form:**
- Federal forms: native Python `forms/*.compute` produces `oracle_*` keys; structural-invariant assertions; round-trip PDF verification.
- Form 1120-S: hand-coded reference oracle on `oracle/f1120s-reference`.
- California forms: hand-coded reference oracles on `oracle/ca-540-reference`, `oracle/ca-sch-d-540-reference`, `oracle/ca-sch-p-540-reference`.

**Oracle isolation.** Reference oracles live on separate git branches and are air-gapped from implementation. Implementers don't read oracle source; cross-checks are run separately; tie-breaking between implementation and oracle is a CPA-domain adjudication, not a code-domain one. This prevents convergent bugs.

**XLS dependency.** The federal spine's production calculator is a third-party spreadsheet. Whether to port it to native Python — demoting the XLS to oracle-only — is open. Most federal forms already have native Python compute used as PDF-emit helpers and cross-checkers; a port is mostly wiring + replacing the rekey shim in `forms/f1040.py`. Cost is bounded (days, not months); whether vendor-risk insurance justifies the investment is undecided.

## Pipeline

Three orchestrator entry points, one per return type. All start from a `Scenario` (loaded via `scenario.load_scenario`).

### Federal 1040 (XLS-driven)

```
Scenario
    ↓ flatten_scenario()
flat input dict
    ↓ SpreadsheetEngine.compute()
raw engine output
    ↓ form_1040.compute()                 [rekey shim]
1040 results dict
    ↓ _emit_pdfs_internal()               [per-form compute + PdfFiller.fill]
filled federal PDFs
```

`compute_federal(scenario)` runs the first three steps. `run_full_return(scenario)` runs all four.

### Corporate 1120-S (native Python)

```
Scenario.s_corp_return
    ↓ form_f1120s.compute()
1120-S results + synthesized K-1s
    ↓ append K-1s to effective Scenario
flows into Federal 1040 pipeline
```

`compute_corporate(scenario)` runs 1120-S in isolation. `run_full_return(scenario)` waterfalls 1120-S → 1040 when `scenario.s_corp_return` is set.

### California (native Python, downstream of federal)

```
Scenario + ca.yaml
    ↓ run_full_california_return()
verify ca.yaml, build effective CA540Return
    ↓ compute_federal()                   [federal pipeline above]
    ↓ sch_ca.compute()                    [federal-vs-CA divergences]
    ↓ sch_d_540.compute()                 [federal pass-through]
    ↓ f540.compute()                      [CA tax + credits + final liability]
    ↓ _emit_ca_pdfs_internal()
filled CA PDFs
```

## Module Map

### Core pipeline

| Module | Purpose | Key entry points |
|--------|---------|-----------------|
| `models.py` | Dataclasses for tax inputs and results | `Scenario`, `TaxReturnConfig`, `FilingStatus`, `W2`, `Form1099*`, `ScheduleK1`, `RentalProperty`, `SCorpReturn`, `CA540Return`, `CASchCAAdjustment`, ... |
| `scenario.py` | YAML → `Scenario` | `load_scenario(path)`. `_FORM_REGISTRY` maps YAML keys to model classes; add new forms here. |
| `oracle/flattener.py` | `Scenario` → flat input dict for the XLS engine | `flatten_scenario(scenario)`. Raises `NotImplementedError` on unhandled forms (prevents silent data loss). |
| `oracle/engine.py` | Spreadsheet computation | `SpreadsheetEngine.compute(...)`. Resolves named ranges and direct cell refs against the workbook. |
| `orchestrator.py` | Entry points | `compute_federal`, `compute_corporate`, `run_full_return`, `run_full_california_return`. Internal: `_compute_1040_pipeline`, `_emit_pdfs_internal`, `_emit_ca_pdfs_internal`. |
| `attestations.py` | Year-bounded scope-out registry | `_FEDERAL_ATTESTATIONS`, `_SCORP_ATTESTATIONS`, `_CA_ATTESTATIONS`, `validate_load_time(scenario)`, `enforce_compute_time(...)`. |
| `years.py` | Year-support manifest | `FEDERAL_YEARS`, `CALIFORNIA_YEARS`, `FEDERAL_FORMS`, `describe`. |
| `filing/pdf.py` | PDF fill | `PdfFiller.fill(...)`. Use `PdfWriter(clone_from=reader)` — `append_pages_from_reader` strips form fields. |
| `__main__.py` | CLI subcommands | `tenforty federal \| ca \| fods <path> [...]` |

The `oracle/` package houses `engine.py` and `flattener.py` — the XLS subsystem. The naming anticipates the post-TY2025 port decision (XLS demoted to cross-check oracle only); for now they do production work for `compute_federal`, and they'll stay in `oracle/` pending that decision. If the port doesn't happen, they should move back to `tenforty/` root.

### Forms (`forms/`)

One module per IRS/FTB form. Two roles:
- **Production calculator** — when no XLS exists for the form (1120-S, all CA forms). The orchestrator wires these into `compute_federal` / `compute_corporate` / `run_full_california_return`.
- **PDF-emit helper + cross-checker** — when the XLS handles the production math (federal 1040 spine: 1040 rekey shim, sch_a, sch_b, sch_d, sch_e, sch_e_part_ii, sch_1, f8949, f8959, f8582, f8995, f4562, f4868). Called at PDF emit time; produces `oracle_*` keys for cross-check.

`forms/depreciation/` has shared MACRS helpers.

### Mappings (`mappings/`)

| Module | Purpose |
|--------|---------|
| `registry.py` | Base `FormMapping` class with `inherit()` for year-over-year deltas |
| `f1040.py` | XLS cell mapping — `INPUTS`, `OUTPUTS`, `SHEET_MAP` for the `compute_federal` pipeline |
| `pdf_*.py` | PDF field mappings, one per form, exposing the 5-registry pattern |

### 5-registry PDF mapping pattern

Each `pdf_*.py` exposes five `@classmethod` getters per year:
- `get_mapping(year)` — compute-key → PDF-field mapping
- `get_aggregations(year)` — multi-key composition (e.g., first + last name → taxpayer_name)
- `get_derivations(year)` — computed-from-results lambdas
- `get_suppressed(year)` — fields intentionally rendered blank
- `get_checkbox_states(year)` — XFA appearance-state names per checkbox value

`PdfFiller.fill` consumes all five; the partition `(mapping ∪ aggregations ∪ derivations ∪ suppressed)` must cover every addressable widget on the PDF.

### Params (`params/`)

- `params/federal/yYYYY.py` — per-year `FederalParams` (brackets, deductions, thresholds, SALT structure, SS wage base). No field defaults — adding a schema field forces every year to supply a cited value.
- `params/california/yYYYY.py` — per-year `CaliforniaParams` (brackets, exemption credit, standard deduction, renter's credit).
- Both `load(year)` functions gate on `tenforty/years.py` (the support manifest) and resolve year modules by name; adding a year touches zero load() lines.

### Year-support manifest (`years.py`)

Single source of truth for supported years (`FEDERAL_YEARS`, `CALIFORNIA_YEARS`, `CALIFORNIA_COMPUTE_ONLY_YEARS`, `WORKBOOK_YEARS`) and form sets (`FEDERAL_FORMS`, `CALIFORNIA_FORMS`). Error messages and test parameterizations derive from it. CA 2021–2023 are compute-only: 540 math validated against FTB worked examples, no PDF emit.

### Two cell-reference styles in the XLS

1. **Named ranges** (e.g. `Adj_Gross_Inc`, `Additional_Income`, `File_Single`) — defined in the workbook, resolved by openpyxl. Used for filing status flags, schedule totals, and the AGI-adjacent outputs that the rekey shim consumes.
2. **Direct cell refs** (e.g. `C28`, `D6`) — require a `SHEET_MAP` entry mapping the input/output key to a sheet name. Used for W-2 fields, 1099 line items, Schedule E expense rows.

The engine resolves named ranges first; if not a named range, looks up `SHEET_MAP` for the cell ref; otherwise raises.

### Compute output keys (native-Python forms)

Forms whose math is in Python (production calculators for 1120-S and California; PDF-emit helpers + cross-checkers for federal 1040 spine forms) return a flat `dict[str, object]` whose keys are the public API surface consumed by the PDF mapping module.

**Convention:** compute output keys use semantic-noun basenames, never IRS/FTB line numbers. Examples: `f1120s_total_tax`, `f1120s_sch_k_ordinary_business_income`, `f540_ca_tax`, `sch_ca_ca_agi`. Not `f1120s_line_22_total_tax`, not `f540_line_64_ca_tax`.

**Why:** line numbers belong in the PDF mapping module, which is form-revision-specific. The 2025 1120-S renumbered its entire Tax/Payments block relative to 2024 (22a→23a, 22→23c, 23→24, 24→26, 26→27, 27→28a) — proof that line numbers are anti-durable for compute keys. Embedding them in the cross-revision API surface would force breaking changes on every IRS/FTB renumbering.

**Local-variable exception:** internal locals in helper functions (e.g. `line_1a`, `line_22a` inside `_compute_income`) keep IRS-line-numbered names. They mirror form arithmetic during computation and aren't part of the public API; line-numbered locals make the math read like the form instructions.

## Federal-first downstream state returns

State returns (currently California) compute downstream of the federal return. The federal pipeline produces results; the state pipeline reads those results and applies state-specific divergences.

### Inputs

- A `Scenario` (federal inputs, loaded via `scenario.load_scenario`).
- A separate CA YAML file (`<basename>.ca.yaml` by convention) — contains the `ca540:` block with state-specific inputs (estimated payments, use tax, voluntary contributions, divergence worksheet rows, named single-amount fields). Loaded into `Scenario.ca540` as a `CA540Return` dataclass.

The federal YAML and CA YAML are kept as separate files so the user can edit CA divergences without re-running federal compute, and to keep federal-first downstream-only flow explicit.

### Pipeline shape (`run_full_california_return`)

1. Load + validate CA YAML; build effective `CA540Return`.
2. Run federal pipeline (`compute_federal`).
3. `sch_ca.compute(ca540, federal_results)` — federal-vs-CA divergences.
4. `sch_d_540.compute(federal_results, config)` — federal pass-through, gated by attestation.
5. `f540.compute(...)` — CA tax + credits + final liability.
6. Header-merge taxpayer name/SSN into result dict.
7. `_emit_ca_pdfs_internal` fills the three CA PDFs.

### Sch CA generic kernel

`forms/sch_ca.compute` produces line-by-line federal-vs-CA divergences from three input classes:
- **Auto-derived** — kernel computes from federal results alone (e.g. social security subtraction).
- **Named `CA540Return` fields** — single-amount values not on federal forms (RRB tier-1/2, PFL amounts).
- **Worksheet rows** — multi-row user entries in `ca540.divergences[]`, each carrying `{ca_section, ca_line, federal_amount, addition_amount, subtraction_amount, source_note}`.

Worksheet rows can be authored manually in YAML, or generated as a multi-tab `.fods` (OpenDocument Flat XML Spreadsheet) — one tab per Sch CA line that admits additions or subtractions — that the user opens in LibreOffice, fills in, and saves. tenforty reads the filled `.fods` back and converts to the YAML form. The generator + reader are planned but not yet implemented.

### CA-specific scope-out attestations

The kernel scopes out areas it doesn't fully implement (CA AMT, §1202 QSBS, §1031 like-kind exchanges, kiddie tax, lump-sum distributions, etc.). Each scope-out is a year-bounded attestation in `_CA_ATTESTATIONS` (TY2021-2025); some have `applies_in_years` to limit to specific years (e.g. §461(l) excess-business-loss). Users must affirm each scope-out at scenario load; otherwise the loader raises with a substantive `load_error` pointing at the workaround.

## Oracle isolation

Reference oracles live on separate git branches and are air-gapped from implementation. Implementers don't read oracle source. This prevents convergent bugs — an implementation that's wrong in the same way as its checker isn't actually checked.

### Oracle branches

| Branch | Form |
|--------|------|
| `oracle/k1-reference` | Schedule K-1 |
| `oracle/f1120s-reference` | Form 1120-S |
| `oracle/ca-540-reference` | CA Form 540 + Sch CA (540) |
| `oracle/ca-sch-d-540-reference` | CA Sch D (540) |
| `oracle/ca-sch-p-540-reference` | CA Sch P (540) |
| `oracle/ca-100s-reference` | CA Form 100S (S-corp) |

Each branch carries a hand-coded `tests/oracles/<form>_reference.py` plus internal-consistency tests for the oracle itself. The XLS workbook plays the same checker role for federal 1040 spine forms (and is also the production calculator there, until the port).

### Process

- **Implementers** don't read `tests/oracles/*`, oracle branches, or adjudication notes; don't import oracle modules. Integration tests call public oracle helpers (`compute_ca_540(ca_input)`, etc.) as black-box functions.
- **Cross-checks** run as integration tests in branches that include both implementation and oracle — typically only at integration / merge time.
- **Reviewers** read the oracle output and compare to native compute output. Disagreements surface as bug reports at field-name / structural level; specific values and formulas don't leak from oracle to implementer.

### Tie-breaking

When implementation and oracle disagree, the reviewer **does not consult IRS/FTB instructions** to break ties. That's a CPA-domain adjudication, not a code-domain one. Process: surface the disagreement, propose competing readings of the tax rule, let a separate CPA pass decide. If the reviewer runs to the source every disagreement, the oracle's role as an independent check collapses.

### History

The oracle-branch pattern emerged accidentally — oracles started intended to live alongside production code, but ended up on separate branches for non-architectural reasons. The result turned out to be a feature: branch-level separation enforces the air-gap mechanically.

## Compute-once discipline

Each form's `compute()` runs at most once per orchestration. When compute output is consumed by multiple downstream callers (e.g. an emit step plus another form's compute), running it twice risks divergence between the two callers' views. A single canonical run with the result merged into the orchestrator's results dict gives downstream consumers a single source of truth.

### Pattern

When a form's compute output is needed by multiple consumers:

1. Lift the compute call into `_compute_1040_pipeline` (or `run_full_california_return` for state forms).
2. Merge its output into the result dict the orchestrator returns.
3. Have the emit pipeline read those keys from the passed-in `results` instead of recomputing.

### Sidecar pattern for non-PDF data

When a form's compute produces both PDF render values AND structured downstream data (e.g. K-1 fan-out tables, depreciation schedules), the convention is to return a `(pdf_dict, sidecar_dataclass)` tuple. The orchestrator stores the sidecar as a typed value in the upstream-state dict (e.g. `upstream["k1_fanout"]`) so downstream consumers read structured data rather than re-parsing PDF strings.

Example: `forms/sch_e_part_ii.compute(scenario, upstream) -> tuple[dict, K1FanoutData]`. The fan-out is consumed by Sch E (rolls up totals), Form 8582 (passive activity loss), Form 8995 (QBI deduction), and Sch D (K-1 capital gain distributions).

### Enforcement

`TestComputeOnceDiscipline` (in the test suite) instruments key form `compute()` functions and asserts call-count == 1 across a representative orchestration. Any new form lifted into the compute pipeline should be added to this test.

### Migration status

Most federal 1040 spine forms still run their `compute()` only at PDF emit time. The discipline applies primarily to forms already lifted into the compute pipeline (currently `sch_e_part_ii` for K-1 fan-out; `sch_e` lifts as part of the per-line-breakdowns work). The eventual federal-spine port would lift every form into the compute pipeline.

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
- **LibreOffice recalculation**: `soffice --headless --calc --convert-to xlsx` forces a full recalculation. Takes ~18s for this large workbook (cold start). Each `compute_federal` call pays this cost; an in-process UNO API path achieves ~0.1s but requires the macOS codesign workaround (see Speed Optimization).
- **`total_tax` means IRS Form 1040 LINE 16 on EVERY path — one key, one meaning**: both the native spine and the workbook OUTPUT (← the `Tax_SubTotal` named range) emit line-16 tax, tax before Schedule 2. Each line of the tax band now has its OWN key, so nothing has to be inferred from a total: line 17 is `schedule2_tax` (← `Schedule2_Tax`), line 18 is `tax_plus_schedule2` (← `Tax`), line 24 (total tax liability) is `tax_liability_line24` (← `Tot_Tax`). **This was NOT always so, and the old rule was the reverse** — the workbook's `total_tax` used to point at `Tax`, which is line 18, so one key meant line 16 on the spine and line 18 on the workbook. No test noticed, because each path was only ever compared against itself; the emitted 1040 printed an overstated line 16, and 1040-X line 6 double-counted the excess-APTC repayment. A parity-only duplicate key `total_tax_line16` existed to let the cross-path battery compare like with like; it is RETIRED, and its absence from every year's resolved OUTPUTS is pinned by `tests/test_f1040_mapping.py::TestF1040TaxBandOutputsEveryYear`. Do not re-introduce a second key for line 16 — a duplicate is precisely how one name regrows two meanings.
  - **How Form 4868 is served now** (the reason the workbook OUTPUT used to point at full liability): 4868 line 4 is 1040 **line 24**, per the form's own instruction, and `forms/f4868.py` reads `tax_liability_line24`, never `total_tax`. The two paths are handled ASYMMETRICALLY and deliberately. On the **workbook** path it HARVESTS line 24 whole from the `Tot_Tax` named range, which is present in all five shipped workbooks (`=SUM(<line 22>, <line 23>)`); it does not rebuild it. Only on the **native** path does it COMPOSE from parts (`compose_line_24`), because the spine has no line-22/23/24 producer — and that composition is knowingly incomplete (no AMT, no NIIT); see the `total_tax_liability_line_24` docstring.
  - **The old bullet's two objections were real; both are addressed.** (a) *"Pointing the fallback OUTPUT at pure line 16 understates a fallback filer's 4868 balance due."* Correct at the time, and moot now: the fallback path's 4868 no longer derives its balance from `total_tax` at all — line 4 carries line-24 total-tax-liability semantics, harvested from `Tot_Tax` on exactly that path. The harvest is strictly MORE complete than the old `Tax` reading, which was only line 18 and omitted Schedule 2 Part II and the line-21 credit offset. (b) *"Pure line 16 surfaces `None` where `Tax`'s SUM numeric-coerces a blank `Tax_SubTotal`."* Right about the mechanism, wrong about the remedy. `Tax_SubTotal`'s formula (2025 `'1040'!AL96`, and the same shape in all five years) evaluates to `""` under `IF(OR(Birthday_Needed, FilingStatusError), "", ...)` — that blank is the workbook REFUSING to compute, not a zero. `Tax`'s enclosing `SUM(Tax_SubTotal, <line-17 cell>)` silently coerced it to 0, which was itself the defect: it converted a refusal into a plausible-looking number on a filed form. The refusal is now READ, not coerced — `forms/f1040.py::workbook_refusal` inspects the `deduction_diagnostic` caption (← the `Deduction` named range) and raises before any harvested tax figure is consumed. Say it plainly: the old bullet preferred a silent wrong answer to a loud `None`, and that was the wrong trade.
  - Sites: `mappings/f1040.py` OUTPUTS (explicit 2024 + 2025 blocks; 2023←2024←…←2021 by `F1040.inherit`), `forms/f1040.py::workbook_refusal`, `forms/f4868.py`, `tests/test_f1040_mapping.py::TestF1040TaxBandOutputsEveryYear`, `tests/test_f1040_spine_oracle.py` (the parity loop now compares `total_tax` to `total_tax` with no remap). Note the fallback path is entered by any return outside the spine's v1 scope — non-single filers **and** possible-EIC returns, not MFJ alone (`orchestrator._scenario_in_spine_scope`). (Fork opened 2026-07-14; closed 2026-08-17.)

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

## Speed

For project status (what's shipped, what's planned), see [README.md](../README.md) § Project status. This section covers the operational performance of the XLS engine.

- `oracle/engine.py` (default): cold-start LibreOffice via `soffice --headless --calc --convert-to xlsx`. ~18s per scenario.
- `oracle/uno_engine.py`: warm `unoserver` daemon. ~2-3s per scenario when the daemon is running. Start via `scripts/start_unoserver.sh`.
- An in-process UNO API path achieves ~0.1s/scenario but requires running under LibreOffice's bundled Python 3.12 plus a macOS code-signing dance:
  ```bash
  codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/LibreOfficePython"
  codesign --force --sign - "/Applications/LibreOffice.app/Contents/Frameworks/LibreOfficePython.framework"
  codesign --force --deep --sign - "/Applications/LibreOffice.app"
  ```
- Practical sweet spot: `unoserver` daemon (~2-3s) is fast enough for development iteration without the codesign workaround.

## How To

This section covers extending the codebase. For running an actual tax return as a user, see [README.md](../README.md) § Quick Start.

### Add a new tax year

See `docs/runbooks/add-tax-year.md` — the machine-checked port procedure (both directions).

### Add a new form type

1. Add the form's data model in `models.py` as a dataclass; add a list / optional field to `Scenario`.
2. Add a `_flatten_*` function in `oracle/flattener.py`. Route as INPUTS to the XLS (if there's a third-party XLS sheet for the form) or add a native-Python compute step in the orchestrator pipeline.
3. Register the form in `_FORM_REGISTRY` in `scenario.py` so the YAML loader can recognize it.
4. If native-Python: add `forms/<form>.py` with a `compute()` returning `dict[str, object]`. Register the call in the orchestrator.
5. PDF mapping: create `mappings/pdf_<form>.py` exposing the 5-registry pattern.
6. Tests: unit tests for compute, mapping partition tests, and at least one e2e test that exercises the form end-to-end.
7. Hand-coded reference oracle: create on a new `oracle/<form>-reference` branch; air-gap from implementation.

### Add a state return

1. Identify the state's required forms; fetch each year's PDF templates into `pdfs/<state>/YYYY/`.
2. Add per-year params to `tenforty/params/<state>/yYYYY.py` (brackets, deductions, phaseouts), gated by a `load(year)` function against `tenforty/years.py`, mirroring `params/california/`.
3. Build a `run_full_<state>_return` orchestrator entry point on `ReturnOrchestrator`, mirroring `run_full_california_return`. State compute is downstream of federal: read federal results, apply state-specific divergences, run state forms.
4. Native-Python form modules in `forms/` (state forms typically have no third-party XLS).
5. State-specific scope-out attestations in `attestations.py` as a year-bounded registry, mirroring `_CA_ATTESTATIONS`.
6. PDF mappings: one `mappings/pdf_<form>.py` per state form, 5-registry pattern.
7. Hand-coded reference oracles: one `oracle/<state>-<form>-reference` branch per state form.
8. Add a `tenforty <state>` CLI subcommand in `__main__.py`.

### Debug a wrong value

1. Identify which compute path produced the value: federal XLS path (`compute_federal`) or native-Python form (`forms/<form>.compute`)?
2. Federal XLS path: check the flattened input via `flatten_scenario(scenario)`. Check the cell mapping in `F1040.INPUTS` (and `SHEET_MAP` for direct cell refs). Check the corresponding OUTPUTS entry. Open the XLS manually if needed; verify the cell is the right row/column and not merged.
3. Native-Python form: read `forms/<form>.py` compute body. Trace inputs from upstream (the `upstream` dict) and from `scenario`. Add a print or a debugger checkpoint.
4. Cross-check against the oracle: does the corresponding `tests/oracles/<form>_reference` module produce a different value? If yes, surface as a bug report at the field-name / structural level (per oracle isolation rules).
5. PDF render path: check the relevant `mappings/pdf_<form>.py` to see whether the compute key flows to the right PDF widget and whether suppression / aggregation / derivation rules apply.
