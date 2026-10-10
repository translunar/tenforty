# Depreciation Audit Workbook — Design

**Date:** 2026-10-10
**Status:** awaiting review
**Origin:** Juno's ruling while preparing the TY2025 filing: "Why would I
want to submit a return to the IRS that I can't audit myself? The review
audit should be a feature." A package-side prototype
(`make_depreciation_audit.py`, private) proved the artifact; this spec
generalizes it into the engine.

## Purpose

A filer whose return computes MACRS depreciation from a
`depreciable_assets` block gets, with every emit, a spreadsheet in which
every computed figure is a live formula chaining from visible inputs and
rates, terminating in tie-out rows that compare the formula results
against the figures the engine actually printed on the forms. Opening the
workbook and seeing every tie-out row PASS is an audit of the filing's
depreciation math that requires no trust in tenforty: the auditor can
walk any figure back to `basis × rate` by clicking cells.

Success criteria:

- The workbook emits beside the forms on every full-asset-mode return,
  with no flag or option.
- Every computed cell is a spreadsheet formula over cells visible in the
  workbook; no computed value is pasted.
- Tie-out targets are the printed form values, so PASS means "this
  workbook reproduces my filing," not "this workbook is self-consistent."
- Every non-derivable input (basis, prior depreciation, claimed totals)
  carries a provenance label naming the scenario field it came from. The
  workbook never presents an attested fact as a derived one.
- A return whose workbook cannot be built does not emit (fail-closed).

## Scope

Depreciation only: the MACRS/4562 computation and, when a `form_3115:`
block is present, the §481(a) reconciliation. Auditing other areas of the
return (tax tables, credits, CA conformity) is explicitly out of scope
and would be separate features with their own specs. Stated-depreciation
returns (no `depreciable_assets` block) emit no workbook: there is no
engine math to audit, and the stated figure already carries its
acknowledgment.

## Contract

- **Trigger:** the return computed depreciation from `depreciable_assets`.
  No flag enables or disables it.
- **Artifact:** `depreciation_audit_<year>.xlsx`, written to the same
  output directory as the emitted forms and listed in the orchestrator's
  emitted dict under key `depreciation_audit`. The pdf-packet partition
  invariant requires every emitted key to be claimed: this key joins the
  explicit standalone-exception set in `classify_key` (alongside the
  f4868 extension and the 3115 signed duplicate) — review matter, never a
  packet member.
- **Format:** xlsx via openpyxl (already a core dependency; opens
  identically in LibreOffice, Excel, and Google Sheets). No LibreOffice /
  UNO involvement anywhere in this feature — writing is pure openpyxl,
  and verification is test-tier arithmetic (see Testing). Per Juno's
  ruling 2026-10-10: emission must not spawn or wait on a spreadsheet
  engine.
- **Failure:** any inability to express the resolved computation as the
  workbook refuses the whole emit (see Refusal).

## Architecture

One new module: `tenforty/audit/depreciation_workbook.py`, single entry
point:

```
write_depreciation_audit(resolved, printed, out_path) -> Path
```

- `resolved`: the depreciation resolver's existing output — per asset:
  table identity (A-1/A-2..A-5 quarter/A-6 month/15-yr 150DB), the rate
  for each recovery year, year-by-year amounts, convention, basis,
  prior-depreciation input, and any ceiling application. The workbook
  computes nothing: it transcribes inputs and rates into cells and
  expresses the arithmetic as formulas.
- `printed`: the figures the engine filled into the forms this emit —
  4562 line 17, each populated line 19 row's deduction, line 22, Sch E
  line 18; with a `form_3115:` block also line 26, the per-asset claimed
  totals, and the Sch E line 3 rents build-up. Passed from the
  orchestrator after form fill so the tie-outs target the as-printed
  values, not a recomputation.
- The orchestrator calls it once per return emit, after form fill,
  before the manifest.

The module owns all layout. Nothing in the forms layer knows the workbook
exists; nothing in the audit module recomputes tax.

## Workbook contents

Sheet order (Tie-outs first, so the verdict is the first thing an opener
sees):

1. **Tie-outs** — one row per printed figure: claim text, computed (a
   formula referencing the other sheets), printed-on-form (input), the
   difference, and `=IF(ABS(diff)<0.005,"PASS","FAIL")`. Rows: 4562 line
   17; each populated 19a–19i row; line 22; Sch E line 18; and with a
   3115: line 26 net §481(a) and Sch E line 3 (cash rents + adjustment).
2. **Assets** — the Evans-Ave-style table, one row per asset:
   description, in-service date, method, life, convention, current-year
   rate, basis, prior accumulated, current-year deduction
   (`=ROUND(MIN(basis*rate, basis-prior), 0)` — the asymmetric ceiling as
   a visible formula), accumulated after, provenance.
3. **Year-by-year** — per asset the resolver tabled: recovery-year rows,
   rate and `=basis*rate` per year, cumulative; the per-asset totals
   these sheets reference.
4. **481(a)** — only when `form_3115:` is present: per changed asset,
   claimed (input, from the 3115 asset rows) vs allowable (formula from
   Year-by-year), per-asset adjustment, net.

Provenance labels name scenario fields (`prior_depreciation`,
`acknowledges_prior_depreciation_as_stated`,
`form_3115.assets[n].total_depreciation_claimed`) wherever a cell is an
input rather than a formula.

## Refusal

One new registry entry, emit stage, whole-return:
`depreciation_audit_unbuildable`. It fires when the resolver's output
cannot be expressed in the workbook:

- an asset whose table identity the workbook has no grid for;
- a recovery year outside the table grid;
- a mirror mismatch: the Python evaluation of a formula cell's arithmetic
  (same inputs, same rule) differs from the resolver's amount for that
  cell by ≥ $0.005.

The refusal names the asset and field. U-1 standard: a firing proof per
trigger and twins proving the well-formed neighbor emits. Multi-activity
merged 4562s are out of scope here — governed by the parked
`f4562-one-activity-refusal` decision; the workbook renders whatever
single form the engine currently emits and ties to its printed values.

## Testing

No spreadsheet engine anywhere:

- **Red-first structural pins:** sheet names and order, header rows, one
  row per fixture asset, the Tie-outs row set, provenance labels present
  on every input cell.
- **Formula-string pins:** the exact formula text of every computed cell
  class, as literals (`=ROUND(MIN(G2*F2,G2-H2),0)` and kin), per sheet.
- **Mirror rule:** for every formula cell, the test evaluates the same
  arithmetic in Python over the same cell inputs and asserts equality
  with the resolver's figure to the cent. A wrong rate, wrong cell
  reference, or dropped ceiling fails without any spreadsheet running.
- **Refusal proofs:** each trigger fires on a minimal synthetic scenario;
  twins emit.
- **Mutation sweep:** rates, cell references, the ceiling `MIN`, the
  tie-out threshold, and the PASS/FAIL inversion — standard
  cleared-`__pycache__` discipline.
- Fixtures are synthetic throughout; the real-figure workbook stays
  package-side.

## Non-goals

- Auditing anything beyond depreciation (tax computation spine, credits,
  CA). Separate features.
- Replacing the package-side prototype for TY2025: that file is the
  filing-season artifact; this feature takes over from TY2026 emits.
- Any UNO/LibreOffice verification tier (ruled out 2026-10-10).
- Per-activity 4562 emission (parked design round owns it).
