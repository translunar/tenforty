# Year-Extension Harness — Design

**Date:** 2026-07-06

**Goal:** Make adding a tax year — forward (2026, 2027, …) or backfill (2023 and earlier) — a repeatable, machine-verified procedure instead of a bespoke multi-day port. A year becomes a self-contained data pack; a deterministic harness proves the pack complete and correct; an agent runbook sequences the work so any model can execute it without its claims being taken on faith.

---

## Background / problem

The compute logic is already year-agnostic (AST-guarded; penny-validated against the third-party XLS workbook at 2024 and 2025). What varies by year is data: params, blank PDFs, PDF field mappings, tax tables, the CA divergence catalog. But that data has no single source of truth for "which years are supported," no mechanical completeness check, and no anti-hallucination protocol for the transcription work. Consequences observed:

- `pdf_8959.py` and `pdf_f8949.py` have 2025 mappings only — the 2024 backfill is silently incomplete and nothing failed.
- The supported-year set is implied independently by `params.federal.load()`'s if-switch, each mapping's `_MAPPINGS` keys, the `pdfs/` directory contents, attestation year-bounds, and hardcoded error strings.
- Per-year work is duplicated wholesale: PDF mapping dicts cloned across years differing only in a root prefix; the parity battery hand-cloned per year with `_2024`-suffixed builders.
- Two param systems: federal `FederalParams` dataclass registry vs. CA per-year module dicts loaded by importlib.
- The federal production calculator's per-year dependency on the third-party XLS workbook is undecided ("port the spine?" open question in ARCHITECTURE.md), which blocks defining what a year port even requires.

Threat model for a new year, given year-agnostic logic: (1) transcribed param values are wrong (model hallucination or typo), (2) PDF field mappings are guessed rather than probed, (3) the pack is silently incomplete. Each needs a mechanical defense.

## Decision: native spine is production; XLS is a per-year optional oracle

The native federal spine is declared the production calculator. The XLS workbook is demoted to a per-year *optional* acceptance oracle:

- A year is "supported" when its pack (below) is complete. The workbook is not part of the pack; it is registered in the manifest when available (`workbook=True`).
- Scenarios outside spine scope (non-single filers, EIC-eligible) route to the workbook as today; for a year with no workbook they raise a clean `NotImplementedError` naming the gap, instead of failing on a missing file.
- `oracle/engine.py`, `oracle/flattener.py`, and the `forms/f1040.py` rekey shim stay, serving the acceptance gate and the out-of-scope fallback.
- Spine *scope* (single, non-EIC) does not widen in this work — that is a separate future workstream.

## 1. Architecture: the manifest and the year pack

### Manifest — `tenforty/years.py`

The single declaration of supported years:

```python
SUPPORTED = {
    2023: YearSupport(federal=True, california=True, workbook=True),
    2024: YearSupport(federal=True, california=True, workbook=True),
    2025: YearSupport(federal=True, california=True, workbook=True),
}

FEDERAL_FORMS = ("f1040", "sch_1", "sch_a", "sch_b", "sch_d", "sch_e",
                 "f4562", "f4868", "f8582", "f8949", "f8959", "f8995",
                 "f1120s", "f1120s_k1")
CALIFORNIA_FORMS = ("f540", "sch_ca", "sch_d_540")
```

The manifest declares **both dimensions of the support grid**: the year list and the form set per jurisdiction. Everything that today independently encodes year support is instead checked against the manifest. Declaring a year without completing its pack fails the completeness gate; completing a pack without declaring it also fails; adding a form to the form set is a one-line change that reddens every supported year until each year carries that form's pack pieces. No silent half-support in any direction.

### Year pack — what a supported year must have, by convention

| Piece | Federal | California |
|---|---|---|
| Params | `params/federal/yYYYY.py` | `params/california/yYYYY.py` |
| Param attestation | `tests/params_attestations/federal_yYYYY_attested.py` | `tests/params_attestations/california_yYYYY_attested.py` |
| Blank PDFs | `pdfs/federal/YYYY/*.pdf` | `pdfs/california/YYYY/*.pdf` |
| PDF mappings | year key in each `mappings/pdf_*.py` | same |
| Tax-table asset | `assets/tax_tables/federal/YYYY.csv` | `assets/tax_tables/california/YYYY.csv` |
| Boundary battery | generated from params (no per-year clone) | same |
| Divergence catalog | — | `spreadsheets/california/YYYY/{catalog.yaml, input_worksheet.fods}` |
| Workbook (optional) | `spreadsheets/federal/YYYY/1040.xlsx` | n/a |

"Add year Y" = run the runbook: fetch assets → scaffold the pack → transcribe params under the dual-transcription protocol → diff/probe mappings → gates green. Identical procedure forward or backfill.

### Params fields never get defaults

Every field on `FederalParams` / `CaliforniaParams` is required — no dataclass defaults, ever. A default would let an existing year silently pass with a possibly-wrong value when a new field is added; required fields are what turn a schema addition into an all-years red gate (every year's params module fails to construct until the new value is transcribed and attested for that year). A harness test asserts no params dataclass field carries a default, so the rule survives future editors. Values that happen to repeat across years (e.g. a floor percentage unchanged since 2024) are still written out explicitly in each year's module, with their citation.

## 2. Validation: correct without the workbook

### Layer 1 — dual-transcription protocol for params

Every param value is a transcription from an official publication (IRS Rev. Proc., FTB booklet). Two air-gapped transcriptions must agree:

- Agent A writes `params/<juris>/yYYYY.py` from the official source.
- Agent B — who never reads A's module — independently writes the attestation module: the same values, each carrying its citation (e.g. `# Rev. Proc. 2022-38 §3.01`).
- A harness test diffs the two field-by-field. Disagreement is surfaced for human adjudication, never auto-resolved.

The second pass may be a human with the publication open; the protocol requires only that it be independent. This mirrors the repo's oracle-isolation practice: one agent can hallucinate a value; two isolated transcriptions agreeing on the same wrong value is the failure mode this kills.

### Layer 2 — published tax-table oracle

The IRS publishes the complete tax table (incomes under $100k, $50 brackets, all four filing-status columns) in each year's 1040 instructions; the FTB publishes the CA equivalent. This is a per-year, official, machine-checkable oracle available for every year, past and future.

- `scripts/ingest_tax_table.py` parses the instructions PDF into `assets/tax_tables/<juris>/YYYY.csv`, enforcing structural sanity checks (row count, bracket monotonicity, column count). A garbled parse cannot emit a CSV.
- A gate test sweeps every row through the spine's tax function — thousands of exact-match assertions. Wrong bracket, rate, or rounding is caught mechanically.
- Above $100k, the same instructions publish the Tax Computation Worksheet thresholds; spot-checked at each bracket edge ±$1.

This is the XLS-independent backbone: it validates what the XLS parity gate validated, from a more authoritative source.

### Layer 3 — generated boundary battery

Battery builders become functions of the params dataclass and generate scenarios at the boundaries the params declare: each bracket edge, QBI threshold ±1, additional-Medicare threshold ±1, SALT cap edges, QDCGT breakpoints. A new year gets its battery for free. A coverage assertion enumerates the dataclass fields and fails if any param has no scenario exercising it — a newly added param cannot dodge testing. The battery runs against structural invariants always, and against the XLS when one is registered.

### Layer 4 — mapping validation: probe or nothing

`scripts/diff_pdf_fields.py` compares the new year's blank PDF to the prior year's (field names + widget rects):

- Verdict `identical` → the mapping auto-inherits; a machine check confirms every mapped field exists on the new PDF.
- Any other verdict → the affected fields are blocked until re-probed with `probe_pdf_fields.py`; the probe PDF is committed as evidence.

The existing partition-invariant, field-path-uniqueness, and round-trip emit tests apply to the new year automatically. There is no path by which a guessed field name reaches a mapping.

### Layer 5 — completeness gate

One fast `unittest.TestCase`, driven by the manifest: for every supported year × form — params present and attested (L1), tax-table asset present and swept (L2), battery generated (L3), blank PDF present and >50KB, mapping present with full widget partition (L4), attestation year-bounds cover the year — and unsupported years still raise everywhere. This is the test that would have caught the 2024 `pdf_8959`/`pdf_f8949` holes.

### Layer 6 — XLS acceptance gate, when available

For years with a registered workbook: the full penny-parity battery, run once at port completion and on demand thereafter (slow-marked). Redundant in coverage with layers 1–3 — which is what makes it a strong acceptance check: an independent implementation agreeing end-to-end.

### Layer 7 — filed-return reconciliation (existing, non-gating)

`scripts/reconcile_federal.py` / `scripts/reconcile_ca540.py` diff recomputed returns against an external, PII-isolated, never-committed record of what was actually filed. Mismatches are adjudication candidates — the filed return may be the wrong side — surfaced for human review, never auto-resolved and never gating CI.

### What the stack does not claim

Layers 1–5 cannot detect a legislative shape change — a new phaseout structure or a restructured form that the params schema cannot express. That risk is fenced procedurally: the runbook's first step is a delta review of the year's Rev. Proc. / form revisions against the params schema; anything that does not fit stops the port and escalates rather than being force-fitted (precedent: OBBBA turned the scalar SALT cap into a phaseout structure).

## 3. Simplification phase (runs first)

Six refactors, each landing as its own commit(s) with the full suite green. Pure behavior-preserving refactors; the 2024/2025 parity gates are the deep backstop.

- **3a. Unify CA params into the dataclass registry.** `constants/california_yYYYY.py` module-dicts become `params/california/yYYYY.py` with a frozen `CaliforniaParams` dataclass (standard_deduction, exemption_credit, dependent_exemption, agi_phaseout_threshold, rate_schedule, renter_credit thresholds/amounts), status-keyed by `FilingStatus.value` to match the federal convention. `forms/f540.py`'s importlib shim is replaced by `params.california.load(year)`. The 2021–2023 modules migrate as-is into a **compute-only tier** (`CALIFORNIA_COMPUTE_ONLY_YEARS` in the manifest): their 540 math is genuinely validated (FTB-published worked examples per year in the compute test oracles), but they have no PDF mappings, emit path, or divergence catalog — the manifest says so explicitly, and a year leaves the tier by completing its pack (Phase C does this for 2023).
- **3b. Discovery-based `load()`.** Both `params.federal.load` and `params.california.load` drop the if-switch: consult the manifest, then resolve `yYYYY` by module name. Adding a year's params touches zero existing lines.
- **3c. `SUPPORTED_YEARS` manifest** (`tenforty/years.py`) and migration of every hardcoded year list — `load()` errors, `f540.py`'s "2021-2025" string — to read from it. The per-form `test_*_unsupported_year_raises` lists migrate later, with the completeness gate: they cannot derive from the manifest until the 2024 mapping holes close (today `pdf_8959`/`pdf_f8949` support fewer years than the manifest declares — exactly the mismatch the gate will police). Exception: attestation `applies_in_years` sets stay explicit — they encode *law* scope (statutory windows like §461(l)), not *support* scope. The completeness gate instead asserts every supported year is covered by each attestation's window (or `None`), so a new year forces a deliberate per-attestation review rather than silent inheritance.
- **3d. De-duplicate PDF mapping dicts.** `PdfFormMapping` gains an inherit pattern: a year entry may be `_inherit(base_year, overrides, root=...)` where `root` performs the whole-tree prefix swap (`form1[0]` ↔ `topmostSubform[0]`) and `overrides` handles genuinely moved fields. Each mapping's first year stays a full explicit dict; subsequent years state only their delta.
- **3e. Dict-dispatch the 5-registry getters, then guard.** `pdf_f540.py` / `pdf_f1120s.py` getters move from `if year ==` branches to `_BY_YEAR: dict[int, ...]` lookup; the AST year-guard extends to all of `mappings/` and `forms/f540.py`. After this, `year ==` outside `params/` and `years.py` is a test failure.
- **3f. Parameterize the parity battery.** `BATTERY_2024`'s clone-builders are deleted; builders take a `FederalParams`; `battery_for(year)` generates the set. Acceptance: the 2024/2025 gates produce identical scenario sets before and after.

## 4. Tooling and runbook

All tooling is deterministic; agents operate it, never substitute for it.

| Tool | Job | Built-in verification |
|---|---|---|
| `scripts/fetch_year_assets.py` | Download blank form PDFs + instruction booklets from stable official URL schemes (`irs.gov/pub/irs-prior/f1040--YYYY.pdf`, FTB equivalents) into `pdfs/<juris>/YYYY/` | URLs pinned to irs.gov / ftb.ca.gov only; PDF magic-bytes + >50KB check at fetch time. Run by the user (the port's one manual step, plus the optional workbook download) |
| `scripts/ingest_tax_table.py` | Instructions PDF → `assets/tax_tables/<juris>/YYYY.csv` | Layer-2 structural sanity checks; refuses to emit a failing CSV |
| `scripts/diff_pdf_fields.py` | Field inventory (names + rects) of year Y vs Y−1 per form | Pure mechanical comparison; its verdict is what licenses mapping inheritance |
| `scripts/scaffold_year.py` | Generate the pack skeleton: params module with sentinel values, attestation stub, mapping inherit-stubs for `identical` forms, manifest entry | Sentinels are designed to fail the completeness gate — a scaffolded-but-unfilled year cannot pass |

**Runbook** — `docs/runbooks/add-tax-year.md`, the sequence for any year, either direction:

1. Delta review: the year's Rev. Proc. / form revisions vs the params schema (the legislative-shape fence). Stop and escalate if anything does not fit.
2. User runs `fetch_year_assets.py` (+ workbook download if available).
3. `scaffold_year.py`.
4. Dual-transcribe params (two air-gapped passes; Layer 1).
5. `ingest_tax_table.py` (Layer 2).
6. Diff / probe mappings (Layer 4).
7. Gates green: completeness, tax-table sweep, battery, mapping suite.
8. XLS acceptance gate once, if a workbook is registered (Layer 6).
9. Non-gating filed-return reconciliation, if a return was filed for that year (Layer 7).

A thin repo skill wraps the runbook so "add year YYYY" invokes it verbatim.

### Component ports: the transpose

The support grid is two-dimensional (year × component), so porting a new component to every supported year is the same procedure with the loop inverted — no new machinery. Worked example, adding EIC to the spine:

1. **Schema:** EIC parameters become new required fields on `FederalParams` (no defaults, per the rule above) → every supported year's params module fails to construct until that year's EIC values are dual-transcribed and attested.
2. **Battery:** the Layer-3 coverage assertion goes red until EIC boundary builders exist — written once, year-generic, generated for every year for free.
3. **Forms:** Schedule EIC joins `FEDERAL_FORMS` → completeness gate red for every year until each year's blank PDF is fetched and its mapping probed (diff / probe-or-nothing apply per year exactly as in a year port).
4. **Oracles:** the EIC table is itself a published per-year table in the 1040 instructions — the same `ingest_tax_table.py` mechanism yields a Layer-2 machine-checkable oracle for the new component; years with registered workbooks re-run the Layer-6 acceptance gate with the new scenarios in scope.
5. **Scope:** `_scenario_in_spine_scope` widens — one year-agnostic change, backstopped by the parity gates.

The runbook applies with steps 4–7 iterated per supported year instead of per form. Component math itself remains year-agnostic and AST-guarded; only its data is per-year, and the gates enumerate exactly which (year, piece) cells are missing.

## 5. Proof phases (after the simplification phase)

- **Phase A — close and verify 2024.** Add the missing 2024 `pdf_8959` / `pdf_f8949` mappings via diff→probe. First declare 2024 fully in the manifest and confirm the completeness gate goes red — proving the gate detects exactly this class of hole — then fix to green. Then run non-gating reconciliation of the 2024 federal + CA output against the filed 2024 returns (not yet done; the filed returns themselves may be wrong — mismatches are adjudication candidates in either direction).
- **Phase B — federal 2023, the full rep.** Every runbook step from scratch: Rev. Proc. 2022-38 dual-transcription, 2023 tax table, blank PDFs, mappings (the differ earns its keep — multiple 2023 forms differ from 2024), generated battery, and the XLS acceptance gate against the 2023 workbook — the one time this plan wires a new workbook, which also proves the acceptance-gate path itself.
- **Phase C — California 2023.** Migrate-and-attest the existing, never-validated 2023 CA constants against the FTB 2023 booklet (dual transcription); CA 2023 tax table; PDF mappings for f540 / sch_ca / sch_d_540 (blank 2023 PDFs already in-repo); port the divergence catalog + `.fods`; emit smoke test; filed-return reconciliation.

Phases A–C all terminate in Layer-7 reconciliation, so both 2024 and 2023 end verified against filed reality.

## Error handling

- Unsupported year → one error, sourced from the manifest, uniform everywhere.
- Supported year + out-of-spine-scope scenario + no registered workbook → `NotImplementedError` naming exactly what is missing.
- Fetch / ingest failures → hard stops; never degraded output.

## Testing

All gates are `unittest.TestCase` (pytest as runner only). Completeness gate, tax-table sweep, attestation diff, and mapping suites are fast; XLS acceptance and emit smokes are slow-marked as today. The AST year-guard extension (3e) is itself a test.

## Non-goals

- Widening spine scope (MFJ, EIC, etc.) — separate future workstream.
- New CA oracle branches for backfill years (per the CA-2024-port precedent, reconciliation stands in unless it surfaces bugs).
- Implementing the OBBBA >$500k SALT phaseout calculation (stays `NotImplementedError`).
- Backfill below 2023 — the harness makes it cheap, but no year below 2023 is in scope here.
- Automating acquisition of the third-party XLS workbook (user step, when desired).
