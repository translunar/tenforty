# Federal Estimated-Payments Input Channel — Design

**Goal:** Let a scenario state the estimated tax payments the filer ACTUALLY
made, and carry that number verbatim to Form 1040 line 26 (and everywhere
line 26 flows) — exactly like a W-2 box: transcribed, never computed,
never second-guessed.

**Explicitly NOT in scope:** computing required estimates, safe harbors,
or underpayment penalties (Form 2210). The filer's number is the number,
even if the filer's own estimate methodology was wrong — tenforty carries
what was paid. California needs nothing: the f540 compute already accepts
estimated payments as an input; FEDERAL is the gap.

## 1. Why

- The spine's `total_payments` is withholding-only, so a return with real
  quarterly payments cannot be represented (the 2021 reconcile carried a
  known estimated-payments channel gap for exactly this reason).
- The 1040-X assembler must currently REFUSE any filed return whose
  filed-values file carries `estimated_payments` (out-of-scope guard),
  because Column C could never reproduce line 26. With the channel, line
  13 of the 1040-X becomes a SOURCED three-column line and the guard
  retires — unblocking amendments of years that made estimated payments.

## 2. Input

`config`-level scenario field (it is a fact about payments, not a source
document): `estimated_tax_payments: float = 0.0` — total federal estimated
payments plus any prior-year overpayment applied. Loader fail-closed as
always. Negative → ValueError.

## 3. Flow (verbatim passthrough)

- Spine: 1040 line 26 = irs_round(estimated_tax_payments); total_payments
  (line 33) = line 25d withholding + line 26. `overpaid` and owed math
  pick it up through total_payments — no other change.
- Result keys: `estimated_tax_payments` (line 26) joins the result dict;
  `total_payments` semantics otherwise unchanged.
- PDF: 1040 line-26 cell mapped per year (2022–2025 packs; 2021 is
  compute-only and needs no PDF cell until its emit pack exists).
- Workbook parity: the workbook's line-26 input cell (per-year address,
  read from each year's own workbook) receives the value; parity on
  total_payments/overpaid then covers it. One battery scenario adds a
  nonzero estimated payment to an existing-shape return.
- 1040-X: line 13 becomes SOURCED (filed key `estimated_payments` /
  corrected result key), `estimated_payments` leaves the out-of-scope
  guard dict; the guard-propagation e2e migrates to a still-unmodeled
  guard key (`schedule_1a_deduction`). L15 total-payments columns pick it
  up through the existing total_payments sourcing.

## 4. Validation

- Unit: passthrough + rounding + fail-closed loader tests.
- Invariants: total_payments == federal_withheld + line 26 on every
  battery scenario; zero-field scenarios byte-identical to today.
- Workbook parity scenario (oracle-marked, gate-run).
- The 1040-X null self-amendment with nonzero estimated payments stays
  exactly null; A+B=C on lines 13/15.

## 5. Process

Executed with two unrelated warm-up hardening tasks riding the same plan
(followups-ledger items, no spec needed): the oracle-collection conftest
guard (TENFORTY_ORACLE_OK env flag; oracle-marked tests refuse to collect
without it) and the PII-scanner fail-open→fail-closed flip. Those two are
DISJOINT from tax code and start immediately on a branch off main; the
channel itself starts only after the f8962-ptc branch merges (it touches
the same spine/scenario/assembler surfaces).
