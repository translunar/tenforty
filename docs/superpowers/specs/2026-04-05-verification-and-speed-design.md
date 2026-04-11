# Round-Trip PDF Verification + Engine Speed Improvements

**Date:** 2026-04-05
**Status:** Draft
**Goal:** Verify that XLS-computed values match filled PDF field values across any tax situation, speed up the engine, and track field coverage per tax year.

## Problem

We have no automated way to verify that the values the XLS engine computes actually end up in the correct PDF form fields. We verify individual fields manually, but a mapping error (wrong cell reference, wrong PDF field name) could go undetected for any field we haven't explicitly tested. We also need this verification to scale to diverse tax situations — not just one person's return.

Additionally, the engine is slow (~20s per scenario) because it cold-starts LibreOffice for every computation, making it impractical to test many scenarios.

## Design

### 1. Round-Trip PDF Verifier

A test helper function that takes a scenario, runs the full pipeline, and asserts every filled PDF field matches the engine's computed value.

**Steps:**
1. Run engine on scenario → `dict[str, object]` of results
2. Run translator → `dict[str, object]` with PDF-namespace keys
3. Fill PDF template
4. Read back every field from the filled PDF
5. For each key in the translated results that has an entry in the PDF mapping, assert `pdf_value == str(translated_value)`
6. Collect any translated keys that have no PDF mapping entry (coverage gaps)
7. Report mismatches and gaps

**Signature:**
```python
def verify_pdf_round_trip(
    test: unittest.TestCase,
    results: dict[str, object],
    scenario: Scenario,
    translation_spec: TranslationSpec,
    pdf_mapping_cls: type,  # e.g., Pdf1040
    pdf_template: Path,
    year: int,
    work_dir: Path,
) -> None:
```

**What it catches:**
- PDF field mapped to wrong XLS cell (value mismatch)
- Translator renaming to a nonexistent PDF key (field left blank)
- Engine producing a value that never reaches the PDF (missing translator/mapping entry)
- PdfFiller silently failing to write a field

**Where it lives:** `tests/invariants.py` alongside the existing structural invariants.

### 2. LibreOffice Speed Optimization

**Status: File-based daemon (`unoconvert`) does NOT provide meaningful speedup.**

We implemented and tested a `UnoEngine` that uses `unoconvert` to talk to a running `unoserver` daemon. Result: the conversion still takes ~16-18s because the bottleneck is LibreOffice parsing/exporting the large XLSX, not process startup. The daemon eliminates ~2s of startup overhead — negligible.

**What does work: in-process UNO API (~0.1s/scenario).** We benchmarked opening the spreadsheet once via UNO, then setting cells + `calculateAll()` directly in memory. Results: 0.03s per recalculation after a one-time 7-10s file open. This requires running under LibreOffice's Python 3.12 (which has the `uno` module). See the plan appendix for full technical details.

**Current approach:** Accept ~18s per scenario. Mitigate via:
- Cache `compute_federal` results in tests (already done — each e2e class computes once)
- Fewer, broader test scenarios rather than many narrow ones
- Future: implement the in-process UNO approach (Option A in plan appendix) when speed becomes a blocker

### 3. Max-Coverage Test Fixtures

Two synthetic scenarios designed to populate as many 1040 fields as possible:

**Fixture A: "Every income source"**
- W-2 wages
- 1099-INT interest
- 1099-DIV ordinary + qualified dividends + capital gain distributions
- 1099-B short-term and long-term sales (when implemented)
- Schedule K-1 rental income (when implemented)
- Exercises: 1040 lines 1-11, Schedule B, Schedule D, Schedule E, Schedule 1

**Fixture B: "Every deduction and credit"**
- High W-2 income
- Mortgage interest + property tax (itemized, Schedule A)
- State income tax (SALT)
- Exercises: 1040 lines 12-24, Schedule A, Schedule 2

Both fixtures grow as we implement more form support. The round-trip verifier runs on each.

### 4. Per-Year Field Coverage Checklist

A markdown file per tax year (`docs/coverage/2025-field-coverage.md`) that lists every field across all forms with a checkbox. Checked = we have a test that verifies this field through the round-trip verifier.

**Structure:**
```markdown
# 2025 Field Coverage

## f1040 (Form 1040)

### Page 1 — Income
- [x] wages — Line 1a (W-2 box 1)
- [ ] household_employee_income — Line 1b
- [ ] tip_income — Line 1c
...
- [x] taxable_interest — Line 2b
- [x] qualified_dividends — Line 3a
- [x] ordinary_dividends — Line 3b
...
- [x] agi — Line 11

### Page 2 — Tax and Credits
- [x] standard_deduction — Line 12e
- [x] taxable_income — Line 15
- [x] total_tax — Line 16
...

## Schedule A
- [x] mortgage_interest — Line 8a
- [x] property_tax — Line 5b
- [ ] charitable_cash — Line 12
...

## Schedule D
- [x] schd_line16 — Line 16
...
```

**Key properties:**
- One file per tax year
- Uses engine/PDF key names as identifiers (e.g., `wages`, `agi`, `taxable_interest`)
- Each entry includes the form line number for human reference
- Checked means a round-trip test covers this field
- Year-over-year maintenance: generate the new year's checklist from the new XLS named ranges + new PDF field inventory, then work through it

**Generation:** The initial checklist is built manually from the XLS named ranges and PDF field inventories. A future optimization is a script that auto-generates it from the XLS + PDF metadata and checks coverage by analyzing which fields the round-trip tests actually fill.

### Follow-On Work (Not in This Spec)

- **Fuzz-generated scenarios:** Random valid scenarios run through the round-trip verifier. Natural extension once the verifier and daemon mode are working.
- **`formulas` library graduation:** Pure-Python formula evaluation as a fast alternative to LibreOffice. Verified by differential testing: run same scenario through both engines, assert results match. Once confidence is high enough, use `formulas` as default with LibreOffice as oracle.

## Dependencies

- **unoserver** or **python-pptx UNO bridge** — for LibreOffice daemon communication (needs investigation during implementation)
- Existing: openpyxl, pypdf, pytest
