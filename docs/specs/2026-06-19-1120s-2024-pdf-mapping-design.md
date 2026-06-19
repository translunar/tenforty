# 2024 Form 1120-S + Schedule K-1 PDF Mappings — Design

**Date:** 2026-06-19

**Goal:** Add 2024 PDF field mappings for Form 1120-S and its Schedule K-1 so `PdfF1120S.get_mapping(2024)` (and the K-1 equivalent) resolve and a 2024 S-corp return emits its full corporate packet.

---

## Background / problem

The native 1120-S compute is year-agnostic and already tested. PDF emit, however, needs a per-year field map. `tenforty/mappings/pdf_f1120s.py` (`PdfF1120S`) and the Schedule K-1 mapping class use the established **five-registry** design (`_MAPPING`/`_AGGREGATIONS`/`_DERIVATIONS`/`_SUPPRESSED`/`_CHECKBOX_STATES`), keyed by year, but only **2025** exists. So `get_mapping(2024)` raises, and a 2024 return with an S-corp cannot emit the standalone 1120-S or K-1 PDFs (the compute and the K-1 → 1040 waterfall work; only the corporate-packet PDF rendering is missing).

The 2024 and 2025 forms differ structurally: the 2024 `f1120s.pdf` has **441** AcroForm fields vs **454** for 2025. The 2025 revision added a "Line 19 — Energy efficient commercial buildings deduction," which shifted subsequent field numbers. So the 2024 map cannot be copied from 2025; it must be built from the actual 2024 field names.

## Approach

Mirror the 2024 PDF-mapping work already done for the 1040-series forms: probe the real 2024 AcroForm field names and build each 2024 registry from them.

### Changes

- **`tenforty/mappings/pdf_f1120s.py`:** add `_MAPPING_2024`, `_AGGREGATIONS_2024`, `_DERIVATIONS_2024`, `_SUPPRESSED_2024`, `_CHECKBOX_STATES_2024`, built from a probe of `pdfs/federal/2024/f1120s.pdf` (441 fields). Mirror the 2025 compute-key → field structure, re-resolving every field path against the 2024 layout (the Line-19-Energy shift moves the deductions/tax/payments field numbers). Key all five getters by year (add the `2024` branch).
- **The Schedule K-1 mapping class** (the `f1120s_k1` mapping module): add the analogous 2024 registries from a probe of `pdfs/federal/2024/f1120s_k1.pdf`, keyed by year.
- No compute changes; no changes to the 2025 mappings.

### Procedure (execution-time, per form)

Probe field names:
```
.venv/bin/python -c "import pypdf; r=pypdf.PdfReader('pdfs/federal/2024/f1120s.pdf'); print('\n'.join(sorted((r.get_fields() or {}).keys())))"
```
For each compute key the 2025 mapping covers, locate the corresponding 2024 field. A wrong/guessed field name silently drops a value, so every 2024 field path must be confirmed present in the probe output.

## Validation

- **Partition invariant test for 2024:** every expected 1120-S compute key (and every K-1 compute key) is OWNED by exactly one of the five 2024 registries — the same invariant the 2025 mapping test enforces. A new/unplaced key fails loudly.
- **Synthetic 2024 S-corp emit test (`unittest.TestCase`):** build a synthetic 2024 scenario with an `s_corp_return` (synthetic entity/shareholder identity and numbers — no real data), run `run_full_return`, and assert the 2024 corporate packet emits (the `1120s` and `1120s_k1_*` paths exist / the combined `f1120s_2024_complete.pdf` is produced by the packet assembler).
- Every 2024 field path is verified against the actual PDF (no guessing); the field-path uniqueness invariant passes.
- No oracle/penny-parity needed — the 1120-S compute is native and already validated; this task only renders computed values onto the correct 2024 cells.
- Full suite green.

## Non-goals

- No compute changes; no changes to 2025 mappings.
- No tax years beyond 2024.
- The federal year-param consolidation is a separate spec; this one is pure PDF field mapping.
