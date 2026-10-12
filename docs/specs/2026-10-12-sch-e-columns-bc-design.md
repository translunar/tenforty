# Schedule E property columns B and C — design

Date: 2026-10-12
Status: approved (design round closed; see companion spec
`2026-10-12-per-activity-4562-design.md` for the parallel branch)

## Motivation

Schedule E support is v1 single-property: only column A fills, from
`scenario.rental_properties[0]`, and a second rental that lists assets
hits the `asset_mode_on_unprinted_rental` refusal. The form carries
three property columns (A/B/C) per page. This spec takes Schedule E to
the full one-page shape: up to three rental properties, each in its own
column, with the totals lines summing across columns. Together with
per-activity Form 4562 emission (the companion spec) this completes the
multi-activity end-to-end bar: two rentals plus a Schedule C business
emit a complete packet.

## Design

### Scope

- Up to 3 rental properties, columns A/B/C on one page.
- A fourth rental hits a new staged refusal (registry entry, firing
  proof, twins — house style). Multi-page Schedule E is a later
  feature.

### Forms layer (`tenforty/forms/sch_e.py`)

- The column-A field list generalizes to a per-column mapping: the
  existing expense/income keys per property slot
  (`sch_e_property_{a,b,c}_…`), filled by iterating
  `scenario.rental_properties` in order (recon keys `rental_0/1/2` —
  the order and keys must not be renumbered; the companion branch
  names 4562 copies with them).
- Lines 1a/1b/2 per property row; lines 23a–26 totals sum across the
  filled columns.
- Line 18 (depreciation) per column comes from the resolver exactly as
  column A does today, with the taxpayer-wide `mid_quarter` answer
  passed down — never recomputed per property.
- Rounding: any new sums follow the combined-before-rounding rule the
  existing single-line attestation documents, and no new bare-float
  products (use `tenforty.rounding` helpers where a product feeds a
  printed line).

### Refusals

- `asset_mode_on_unprinted_rental` narrows: today it fires for any
  rental after the first that lists assets; it becomes the
  fourth-rental refusal (new name reflecting the new boundary, new
  firing proof and twins, old entry retired in the same commit with
  reviewer-confirmed unreachability).
- Fail-closed behavior unchanged: a refusal while computing any column
  aborts the whole emit.

### Interaction with per-activity 4562 (post-rebase obligations)

This branch owns the tests that only become reachable once both
branches exist: a rental B or C with a current-year placement gets its
own 4562 copy, named by its recon key, whose line 22 ties to that
property's column line 18. Until this branch lands, the 4562 branch
tests on rental-A + Schedule C shapes only.

## Out of scope

More than 3 rentals (refused), royalty properties, multi-page
Schedule E, Parts II–V changes beyond the totals lines, fair-rental /
personal-use day prorations beyond what column A supports today.

## Testing

1. **Column mapping pins** for B and C against the pixel-stamped
   template anchors (literal-path widget pins, per year family).
2. **Totals**: lines 23a–26 equal the across-column sums on a
   three-property synthetic scenario; single-property returns produce
   byte-identical output to today (pinned-emit equality).
3. **Fourth-rental refusal**: staged with firing proof; the
   three-property shape emits, the four-property shape refuses with
   text naming the fourth property's recon key.
4. **Depreciation per column**: each column's line 18 equals the
   resolver's amount for that property under the return-wide 40%
   answer; a scenario constructed so one property alone would flip the
   convention proves the answer is not recomputed per column.
5. **Post-rebase 4562 copy tests** (this branch, after rebasing onto
   the per-activity 4562 merge): copies exist for B/C placements, recon
   keys name them, line 22 ties per column.

## Shared surfaces (parallel-branch ownership)

This branch owns: the `asset_mode_on_unprinted_rental` narrowing, its
registry/allowlist edits, the Sch E mapping keys. The 4562 branch owns:
both merged-form refusal retirements, f4562 allowlist entries, the
audit hand-off shape, recon-key naming. The registry literals and
read-path allowlist live in files both branches edit: like CHANGELOG,
those conflicts resolve by union at rebase, and the second-to-merge
branch re-runs the registry consistency tests on the union before its
gate; whichever branch merges second re-runs the full gate on the
rebased tree.

## Process

Worktree branch off main; unittest.TestCase style under the pytest
runner; visibly-red steps; suite baseline re-measured on a stashed
clean tree; mutation checks with bytecode cleared; fresh-eyes review;
double gate on main's venv before the serial merge (second merge is
serial after the 4562 branch or before it — whichever is ready first;
the other rebases).
