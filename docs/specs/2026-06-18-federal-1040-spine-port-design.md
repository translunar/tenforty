# Federal 1040 Spine Port — Native Python Compute

**Date:** 2026-06-18

**Goal:** Replace the third-party Excel workbook as the *production* federal 1040 compute with a native Python "spine," validated penny-exact against the workbook (which becomes a test-only oracle). Prove the full pattern — spine + runtime cutover + year-parameterization — end-to-end on tax years **2025 and 2024**, so 2023/2022/2021 backfill becomes pure repetition.

**Drivers (ranked):** backfill enablement and correctness transparency, co-equal; removing the LibreOffice runtime dependency is a welcome side effect.

---

## Background / current architecture

- The federal 1040 *spine* — total income → AGI → deduction selection → taxable income → **the tax figure** → QBI interaction → additional taxes → totals → refund/owed — is computed entirely by the third-party `incometaxspreadsheet.com` workbook, evaluated via LibreOffice (`tenforty/oracle/engine.py`). `tenforty/forms/f1040.py` is currently a ~98-line re-keying shim over the workbook's named-range outputs.
- The feeding schedules — **Schedule 1, A, B, D, E and Forms 8949, 8959, 8995, 8582** — are **already native Python, already cross-checked against the workbook** through the `tests/test_*_oracle.py` harness. Form 1120-S and all California forms are native and consume federal results downstream.
- So "port the spine" means: port the 1040 core arithmetic plus the tax calculation, then have the schedules feed the Python spine instead of the workbook. Most of it is sums and subtractions; the genuinely hard parts are the **Qualified Dividends & Capital Gain Tax (QDCGT) Worksheet** and the **QBI interaction ordering**.

## Scope (this spec)

The spine covers exactly one path — the common resident-wage-earner-with-investments-and-rental case — and guards everything else:

1. **Native 2025 federal 1040 spine** for **filing status = single**, implementing the **QDCGT Worksheet**, the **QBI interaction** (taxable income before/after the §199A deduction), and the **Additional Medicare Tax** line on Schedule 2. Consumes the existing native schedule outputs.
2. **Per-year parameters layer** (`tenforty/params/federal/<year>.py`): standard deduction, tax-rate schedules, QDCGT 0/15/20% breakpoints, Additional-Medicare and QBI thresholds, SALT cap. Populate **2025 and 2024**.
3. **Runtime cutover:** `orchestrator._compute_1040_pipeline` calls the native spine instead of `self.engine.compute(...)`. The workbook / `soffice` path moves to **test-only** oracle cross-checks.
4. **Full 2024 backfill:** 2024 params; a re-probed `F1040` oracle `OUTPUTS`/`INPUTS` mapping (the 2024 workbook has 789 named ranges vs. ~874 for 2025 — drift is expected and confined to the oracle mapping); 2024 IRS PDF field mappings for all 13 federal forms; an emitted 2024 federal packet (reuses the packet assembler from `pdf_packet.py`).
5. **2024 reconciliation report:** diff the recomputed 2024 return against an externally-prepared prior-year return (kept outside the repo, PII-isolated), line by line, triaged into "recompute is right / prior filing was wrong" (amendment candidate) vs. "investigate the port." A deliverable, **not** a validation gate.

## Non-goals (guarded, not built)

Blunt `NotImplementedError` (or an existing attestation) for every path outside the scoped case — **no speculative abstraction** (no tax-worksheet dispatcher, no credits registry, no multi-filing-status generality):

- Filing statuses other than single.
- Tax tables (taxable income < $100k) and the Schedule D Tax Worksheet (28% / unrecaptured §1250 gains).
- Federal AMT / Form 6251 (see validation note for why a guard is provably safe here).
- Credits beyond the scoped case (no CTC/dependents path, no foreign tax credit, no education credits); Schedule 3 essentially empty.
- Net Investment Income Tax / Form 8960 (below the $200k single threshold for the scoped case).
- Backfill years 2021–2023 (separate follow-on specs; 2021 is the long pole — ARPA-era Premium Tax Credit / Form 8962, expanded CTC / Schedule 8812, recovery rebate credit).

When a guarded path is eventually needed, refactor **then**, with the oracle harness in place to do it safely.

## Architecture

- **`tenforty/params/federal/<year>.py`** — pure data; the single thing that differs between years.
- **`tenforty/forms/f1040_tax.py`** — the QDCGT Worksheet as straight-line Python, called directly (no dispatcher). Other tax-calc methods are guarded stubs.
- **`tenforty/forms/f1040.py`** — rewritten from shim into the spine: mirrors 1040 line numbers, commented with statutory / worksheet references, consumes a `params` object plus the native schedule results, and returns the same PDF-ready key set the workbook path produces today.
- **Year-seam guarantee:** the tax math is **year-agnostic** — everything year-specific is read from the `params` object. A structural test asserts there are **no `if year == …` branches** in the spine / tax modules. That is what makes it a seam: identical proven logic, swapped params.

## Validation — a single gate

**The gate:** penny-exact parity between the Python spine and the year's workbook, given identical flattened inputs, for both 2025 and 2024, across a small scenario set covering the branches the scoped case hits — the canonical return shape plus the QDCGT 15→20% boundary, the QBI threshold, the Additional-Medicare boundary, and a zero-tax / refund-vs-owe pair. Reuses the existing oracle test pattern. All scenario fixtures use synthetic identities and synthetic numbers.

This one gate transitively covers what would otherwise be separate tests:

- **Params correctness** — a wrong bracket or threshold breaks parity.
- **AMT-is-zero** — if the workbook applied any AMT for a scenario, `total_tax` would not match, so the guard's safety is proven by parity rather than asserted. (No dedicated AMT test needed.)

**Not a gate:** the 2024 reconciliation report — its purpose is surfacing prior-filing discrepancies, which are *expected* to differ.

## Components / files

- Create: `tenforty/params/federal/2025.py`, `tenforty/params/federal/2024.py`, `tenforty/forms/f1040_tax.py`
- Rewrite: `tenforty/forms/f1040.py`
- Modify: `tenforty/orchestrator.py` (`_compute_1040_pipeline` cutover); `tenforty/mappings/f1040.py` (add 2024 `OUTPUTS`/`INPUTS`); per-year federal PDF mappings for 2024 emit
- Assets already fetched: `spreadsheets/federal/2024/1040.xlsx`; `pdfs/federal/2024/*.pdf` (13 forms)
- Tests: spine unit tests; `f1040_tax` QDCGT unit tests; 2025 + 2024 workbook-parity oracle tests; the structural no-`if year` test; a CA / 1120-S regression confirming the cutover leaves downstream results unchanged. All `unittest.TestCase`.

## Risks

- **QDCGT Worksheet rounding** — must match the workbook's IRS half-up rounding exactly (`irs_round`). Highest-risk arithmetic.
- **QBI interaction ordering** — taxable-income-before-QBI is derived (no single named range today); replicate carefully.
- **2024 PDF field-name drift** — every federal form's field names may differ from 2025; the 2024 mappings are fresh per-form probes (mechanical but grindy).
- **Named-range drift** (789 vs. 874) — only affects the 2024 oracle `OUTPUTS` mapping; the core spine ranges are confirmed present.

## Sequence

1. 2025 params + `f1040_tax` QDCGT + spine, to penny-parity vs. the 2025 workbook (cutover gated behind the parity test).
2. Flip `_compute_1040_pipeline` to native; workbook → test-only.
3. 2024 params + 2024 oracle mapping; penny-parity vs. the 2024 workbook (proves the seam).
4. 2024 PDF mappings + emit the 2024 packet.
5. 2024 reconciliation report.
