# S-Corp Return Packet: CA Form 100S + Schedule K-1 (100S) — Design

**Goal:** Extend tenforty's existing federal 1120-S support with a California
S-corporation form family — Form 100S and Schedule K-1 (100S) — so the library
can produce a complete, fileable S-corp return set (federal 1120-S + K-1,
CA 100S + K-1(100S)) for any supported year, including multi-year backfill.

**Target years:** 2021–2025. Federal 1120-S is already supported for
2022–2025; this workstream adds a *federal S-corp-only slice* for 2021 (see
§4) and the full CA family for all five years.

**Status quo:** `tenforty/forms/f1120s.py` computes the federal 1120-S main
form (lines 1–28), Schedule B pass-through, Schedule K totals, and
per-shareholder K-1 allocations from `Scenario.s_corp_return`, with
attestation-gated scope-outs (§1375/§1374/§453; Sch L, M-1, M-2, M-3 out of
scope). PDF mappings exist (`pdf_f1120s.py`, `pdf_f1120s_k1.py`) for
2022–2025. There is no California S-corp support of any kind.

---

## 1. Scope

In scope:
- `forms/f100s.py`: Form 100S compute — CA net income derived from federal
  1120-S ordinary income plus CA adjustments; franchise tax at the CA S-corp
  rate with the minimum-franchise-tax floor; estimated-payment application;
  balance due / overpayment.
- `forms/f100s_k1.py`: Schedule K-1 (100S) per-shareholder allocation,
  mirroring the federal K-1 allocation machinery.
- CA S-corp params (per-year, attested): franchise tax rate, minimum
  franchise tax, first-year minimum-tax exemption rule, estimate schedule.
- PDF emit for 100S and K-1 (100S), 2021–2025, under the marker-probe regime.
- Federal 2021 S-corp slice: 1120-S + K-1 (1120-S) compute and emit for 2021
  (2021 template revisions), declared ONLY for the S-corp form set.

Out of scope (matching the federal 1120-S precedent; enforced by attestation
gates, not silently ignored):
- Balance-sheet and reconciliation schedules: CA Schedule L / M-2 analogues.
  Attestation field gates the corresponding thresholds; exceeding them raises.
- Penalties and interest: returns are produced clean; taxing agencies bill.
- Built-in gains / excess-net-passive-income taxes beyond the existing
  scope-out passthrough fields (caller supplies amounts).
- Water's-edge, combined reporting, QSub, multi-state apportionment: the
  design assumes a single-state (CA-only) S-corp. An attestation asserts
  100% CA apportionment; anything else raises.
- Form 100-ES generation (estimate vouchers) — a followup, not this spec.

## 2. Architecture

Two new compute modules follow the established form-module pattern
(compute(scenario, upstream) with load-time + compute-time attestation
gates):

- `forms/f100s.py` consumes the federal `f1120s` outputs through the
  orchestrator's upstream mechanism (the same pattern `sch_ca` uses to
  consume federal AGI). It never recomputes federal figures.
  Line flow: federal ordinary income → CA additions (state franchise/income
  tax deducted federally; depreciation conformity delta from the CA
  adjustment inputs) → CA subtractions → CA net income → tax = max(rate ×
  net income, minimum tax, with the first-year exemption rule applied per
  the attested params) → payments → balance/refund.
- `forms/f100s_k1.py` allocates Schedule K-1 (100S) line items per
  shareholder using the existing `K1Allocation` machinery; CA column values
  derive from the 100S adjustments, federal column mirrors the federal K-1.

New params: a `CAScorpParams` dataclass in the CA params registry, one
y-module per year, fields with NO defaults (schema additions force all-years
red), each figure dual-transcribed and attested from FTB primary sources
(Form 100S booklet / R&TC).

Scenario schema: `s_corp_return` gains an optional `ca` sub-block
(estimated payments made, prior-year overpayment applied, CA-specific
adjustment inputs, apportionment attestation). Loader is fail-closed on
unknown keys, consistent with the existing loader contract.

## 3. The federal↔CA interlock

- 100S CA-income line ≡ federal 1120-S line 21 (ordinary business income):
  pinned by an invariant test across all supported years.
- State franchise tax deducted on the federal side must be added back on the
  100S. The compute models the addback from an explicit input
  (state_tax_deducted_federally) rather than inferring it, because cash-basis
  timing means the deduction year is the payment year, not the return year.
- The franchise tax is NOT circular: the addback removes it from CA income,
  so CA tax does not depend on itself.

## 4. Federal 2021 S-corp slice

2021 joins the manifest ONLY for S-corp forms. Explicitly NOT added by THIS
workstream: 1040 spine, tax tables, workbook parity, or any individual-return
form for 2021 — a separate compute-only backfill workstream covers the
individual-return family for 2021 via a FEDERAL_COMPUTE_ONLY_YEARS tier.
The two are disjoint by form set: that tier excludes S-corp forms (they stay
coupled to FEDERAL_YEARS until SCORP_FEDERAL_YEARS from §5 lands), and this
workstream owns ALL 2021 S-corp work — compute declaration, templates,
mappings, emit. Neither blocks the other; the years.py edits are sequenced
through the team lead.
The year×form grid in `tenforty/years.py` already supports per-form-set year
declarations; this is the first use of a partial-year slice and doubles as a
design validation of the grid.

Required for the slice: 2021-revision 1120-S and K-1 templates fetched and
marker-probed; 1120-S compute checked for any year-dependent constants
(expected: none or trivially few — the S-corp return has no tax tables or
inflation-indexed spine; any found go through the attested-params path).

## 5. Manifest

`tenforty/years.py` gains:
- `SCORP_FEDERAL_YEARS = (2021, 2022, 2023, 2024, 2025)` (supersedes the
  implicit coupling of S-corp forms to FEDERAL_YEARS),
- `CA_SCORP_YEARS = (2021, 2022, 2023, 2024, 2025)`,
- form-set entries for `f100s`, `f100s_k1`.

Completeness gate, fields-on-template gate, and `battery_for(year)` extend
automatically once the manifest declares the forms. The years.py edit is a
known cross-team collision point and is sequenced through the team lead.

## 6. PDF emit

FTB templates (Form 100S, Schedule K-1 (100S)) fetched per year from
ftb.ca.gov (standing download approval), then the binding marker-probe
methodology: stamp every field with its own name, render via poppler, read
printed positions against line labels, build the correspondence table, then
the existence gate and filled-emit read-back with distinctive values.
Path existence, differ output, and /Rect coordinates are not evidence.

Risk: FTB business-entity PDFs may not all be fillable AcroForms. If any
year's template is not, that year×form drops to compute-only with an
explicit KNOWN_GAPS entry — it does not block the rest of the family.

## 7. Validation

The seven-layer regime adapts as follows:

1. Dual-transcription attestation — unchanged, applied to CAScorpParams and
   any 2021 federal S-corp constants.
2. Published-oracle layer — NO third-party workbook exists for the 1120-S or
   100S. Substitute: a hand-coded oracle module (the k1_reference.py
   pattern) written under the oracle-isolation regime — its author reads
   ONLY official FTB/IRS instructions and never the implementation, the
   plans, or the tests. It covers franchise-tax computation including the
   minimum-tax floor and first-year exemption, K-1 (100S) allocation, and
   the addback arithmetic, over a scenario battery.
3. Battery coverage — battery_for(year) extended with S-corp scenarios
   (profit, loss, minimum-tax floor binding, first-year, estimated-payment
   over/under).
4. Fields-on-template — unchanged.
5. Completeness gate — unchanged, driven by the manifest.
6. Penny parity vs workbook — NOT AVAILABLE for this family (no workbook).
   Recorded in KNOWN_GAPS with the hand-coded oracle as the named substitute.
7. Non-gating reconciliation vs independently-prepared returns — a USER STEP
   with real data held externally (never in the repo). For the initial
   backfill this includes a dual-preparation diff against a previously
   self-prepared federal 1120-S.

## 8. Testing

All tests subclass unittest.TestCase (pytest as runner only). New test
modules per compute module, mapping-test modules per PDF mapping, invariant
tests for the interlock (§3), oracle-battery tests (layer 2), and emit tests
per year. Existing suite conventions (exact invocations, no ad-hoc flags)
apply.

## 9. Process

- Branch `s-corp-packet`, fresh worktree off the `year-simplification` tip;
  executed by a dedicated teammate via subagent-driven development.
- Implementation plans live in gitignored `docs/plans/` (local-only); this
  spec is committed (genericized — no personal data; the pre-commit scanner
  must pass).
- USER STEPS routed through the team lead: template downloads outside
  standing-approval hosts, attestation adjudications, the external
  reconciliation, and all real-figure scenario/filed-value files (which
  live outside the repo).
- Open facts that can reshape scope, tracked as USER STEPS, not blockers to
  starting: (a) IRS business transcript pull — confirms S-election status
  and which returns were actually processed; (b) per-year financials
  assembly (unknown size; first task is a records inventory); (c)
  verification of the CA first-year minimum-tax exemption rule for the
  entity's first year.
