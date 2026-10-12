# Per-activity Form 4562 emission — design

Date: 2026-10-12
Status: approved (design round closed; see companion spec
`2026-10-12-sch-e-columns-bc-design.md` for the parallel branch)

## Motivation

tenforty emits one merged Form 4562 per return, flattening assets across
activities. That shape is wrong whenever more than one activity lists
assets: the IRS instructions require a separate Form 4562 for each
business or activity, and the form's own header box ("Business or
activity to which this form relates") can only name one. The earlier
attempt to guard the gap with a refusal (`merged_4562_across_activities`,
parked unmerged) collided with reviewed cross-activity mid-quarter
pooling tests: §168(d)(3) pools placed-in-service bases across the whole
return to *decide* the convention, while the forms *print* per activity.
The resolution is per-activity emission, not refusal.

## Rulings (standing)

- **Ruling A — which activities get a copy.** An activity gets a Form
  4562 copy only when its own assets require one: a current-year
  placement, the same instruction cite `is_required` already encodes,
  applied per activity. An activity with only prior-year assets gets no
  copy; its depreciation prints on its schedule line as today.
  Consequences: `merged_4562_with_override` is unreachable (an
  overridden activity can never have a current-year placement) and
  retires together with the parked `merged_4562_across_activities`.
- **Ruling B — pooled 40% visibility.** On a multi-activity return no
  printed copy shows why the convention is mid-quarter (the pooled
  bases span activities). The depreciation audit workbook's
  cross-activity 40% layout is therefore mandatory on every
  multi-activity workbook.

## Design

### Forms layer (`tenforty/forms/f4562.py`)

- `is_required_for(activity, tax_year)` — the existing current-year
  placement rule asked of one activity's assets. Return-level
  `is_required` becomes "any activity requires one".
- `compute_for(activity, tax_year, header, *, mid_quarter)` — one
  copy's computation: that activity's line 17, Part III Section B rows
  (with `printed_row_label` per year family), line 22, and the header
  box named from the activity itself (rental address verbatim; trimmed
  business description) — the `_business_or_activity` logic, now per
  copy. `mid_quarter` is a **required keyword with no default**,
  computed once by the orchestrator from the full scenario via
  `resolver.mid_quarter_applies`; this function never recomputes it.
  It joins the existing "answer is required everywhere" test battery.
- The merged `compute(scenario, upstream)` and the `_all_assets`
  read-path adapter are **deleted, not wrapped** (the adapter is
  self-documented as temporary).
- The resolver and `macrs.py` do not change. The 40% test stays
  taxpayer-wide in the one place it lives; the resolver's
  carried-answer view path keeps its single consumer. The form must
  NOT be routed through one-activity views (no header data; a
  misbuilt view silently recomputes the 40% test per activity; views
  cannot name the activity in refusal text).

### Copy identity

Copies are identified by the existing recon keys (`rental_0`,
`sch_c_0`, …). They name output files, appear in refusal text, and key
the audit hand-off. No second naming scheme; the Schedule E branch must
not renumber them.

### Orchestrator

- The 4562 block computes `mid_quarter_applies(scenario)` once, before
  the loop, then appends one `_FederalFormSpec` per qualifying activity
  (Ruling A), passing the same answer into every `compute_for` call.
- Output naming: exactly one copy → `f4562_{year}.pdf`, today's name,
  byte-for-byte identical output; two or more →
  `f4562_{year}_{recon_key}.pdf` each.
- Packet assembly stacks all copies at the position the single 4562
  occupies now (matches IRS attachment-sequence grouping).
- The audit hand-off (today one scalar bundle of line 17 / line 19 rows
  / line 22) becomes a list of per-copy bundles keyed by recon key,
  plus the return-wide 40% inputs (last-quarter and full-year bases in
  integer cents) so the workbook lays out the pooled test without
  recomputing it. This branch owns that interface and the workbook
  changes ride in it.

### Audit workbook

One `.xlsx` per return, unchanged for single-activity returns. On
multi-activity returns:

- Tie-outs stays first and covers the return: one line-22 check per
  copy against its schedule's printed line, the sum tied to total
  depreciation, and the mandatory pooled-40% section (Ruling B): each
  activity's last-quarter and full-year bases, the pooled fraction, and
  the threshold comparison, in live formulas.
- One Assets + Year-by-year tab pair per activity, mirroring that
  activity's printed copy exactly (today's single-pair layout, per
  activity).
- The exact-decimal mirror extends over all tabs and the pooled sheet;
  new fail-closed check: per-tab line-22 results equal the per-copy
  printed values from the hand-off.

### Refusals

- Retire `merged_4562_across_activities` (parked branch deleted) and
  `merged_4562_with_override` (unreachable under Ruling A). Each
  retirement removes the registry entry, its firing proof, and its
  twins in the same commit that makes it unreachable; the reviewer
  must demonstrate the previously-firing shape now emits correctly,
  not merely observe the deletion.
- No new refusals. Stated-mode, §179-history and
  override-with-placement refusals are unchanged.
- A refusal raised while computing one copy aborts the whole emit
  (fail-closed; never a packet with some copies missing). Refusal text
  names the activity by recon key and printed name.

### Cross-form pins (per copy)

- Header box equals the schedule's own naming line (the existing
  4562 ↔ Sch E line 1a pin, per activity; trimmed Sch C description
  for businesses).
- Line 22 equals the depreciation line that copy's schedule prints
  (Sch E line 18 column / Sch C line 13).

## Out of scope

§179 (no input exists; history refuses), listed property, amortization,
multi-rental copy tests (owned by the Schedule E branch post-rebase),
amendment-path 4562s (amendments carry none by standing ruling), CA
depreciation forms.

## Testing

Red-first anchors, written before implementation:

1. **Pooled-convention twin**: a rental+business return under 40%
   pooled where the business alone would exceed it — the business's
   copy prints half-year rows; and the mirror (pooled over, alone
   under, copy prints mid-quarter). This is the test that catches a
   per-activity recompute inside the form, which the resolver-level
   pooling tests cannot see.
2. **Byte-stability**: a single-activity scenario's 4562 is identical
   before and after the branch (filename and field values, pinned-emit
   equality style).
3. **Per-copy emit pins** extending the two existing emit-pin tests:
   line 22 per copy equals its schedule's printed line; header per
   copy; copy count equals qualifying-activity count; and Ruling A's
   negative with reachable negative space — a scenario containing an
   activity with only prior-year assets produces no copy for it while
   its schedule line still prints.
4. **Retirement proofs**: the shapes that fired both retired refusals
   now emit, asserted on real output; registry sweep shows no orphaned
   twins or proofs.

The three resolver-level taxpayer-wide pooling tests must not move;
they are acceptance tests for this design.

## Shared surfaces (parallel-branch ownership)

This branch owns: both refusal retirements' registry literals, the
f4562 read-path allowlist entries, the audit hand-off shape, recon-key
naming. The Schedule E branch owns: the `asset_mode_on_unprinted_rental`
narrowing, its own registry/allowlist edits, Sch E mapping keys.
CHANGELOG conflicts resolve by union at rebase; whichever branch merges
second re-runs the full gate on the rebased tree.

## Process

Worktree branch off main; unittest.TestCase style under the pytest
runner; visibly-red steps; suite baseline re-measured on a stashed
clean tree; mutation checks with bytecode cleared; fresh-eyes review;
double gate on main's venv before the serial merge. The pooling owner
reviews this spec for pooling correctness before planning.
