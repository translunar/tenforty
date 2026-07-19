# Native Filing Statuses (MFJ + HoH) Design

**Date:** 2026-07-19
**Status:** Draft for review
**Program:** "Retire the workbook" step 1 of 3 (statuses → dependents/CTC → EITC)

## 1. Goal

Run married-filing-jointly and head-of-household returns through the native
compute spine — federal 1040 and CA 540, tax year 2025 — so a plain
`pip install` user in those statuses gets a computed, emitted return with no
LibreOffice dependency. Today `_scenario_in_spine_scope` routes every
non-single scenario to the workbook path, which requires a local soffice
installation and exists to be a test oracle, not a product.

End state for this spec: the workbook path is no longer the *only* path for
MFJ/HoH in 2025. End state for the three-spec program: the workbook is a pure
test oracle, never a production fallback.

## 2. Scope

**In:**
- Filing statuses MARRIED_JOINTLY and HEAD_OF_HOUSEHOLD, tax year 2025,
  federal 1040 + CA 540, compute + emit + amendment paths.
- A declared support grid for (year × status) native-spine coverage, with a
  fail-closed completeness gate (see §4).
- Spouse identity emit (name/SSN on 1040 and 540) and the filing-status
  checkbox/radio widgets on both forms.

**Out (each with its enforcement mechanism):**
- **MFS:** stays workbook/refused. Avoids community-property (Form 8958),
  the PTC ineligibility rule, and halved-limit sprawl. The spine's status
  gate keeps raising for it.
- **QW/QSS:** deferred with MFS (mostly-MFJ params but eligibility rests on a
  qualifying child, unmodeled until the dependents spec).
- **EIC:** unchanged. The orchestrator's conservative EIC-ceiling routing
  gate stays exactly as is (it already reads the MFJ ceiling column, the
  widest, so it is conservative for every status). Possibly-EIC-eligible
  MFJ/HoH scenarios still route to the workbook.
- **Dependent-contingent items:** HoH eligibility is USER-ASSERTED, the same
  way SINGLE is asserted today. No CTC/8812, no dependent modeling — next
  spec.
- **SALT phaseout above $500k MAGI:** existing NotImplementedError stands.
- **Excess Social Security credit (Sch 3 line 11):** requires per-person W-2
  attribution the W2 model doesn't carry. Not computed today for single
  either; a loud guard refuses MFJ scenarios where any single conceptual
  earner pattern would trigger it — concretely: if total `ss_tax_withheld`
  exceeds one person's max and the scenario has >1 W-2, raise with a message
  naming the gap (an MFJ couple each under the cap is fine and must NOT
  raise; the guard fires only when a refund-bearing credit could be silently
  dropped, i.e. wages patterns the compute cannot disambiguate).
- **2021–2024 backfill:** architecture-ready (declare grid rows + fill params
  columns + battery rows) but not in this spec, per the 2025-first decision.

## 3. What the codebase already has (verified 2026-07-19)

- Federal params y2025 binds all five status constants; `standard_deduction`,
  `qbi_threshold`, `salt_cap_starting/floor` already carry all-status columns.
- `tax_from_table(taxable_income, year, filing_status)` is already
  status-keyed (published IRS table carries per-status columns).
- CA is nearly done: `f540.py` computes standard deduction, exemption credit,
  rate schedule, and renter's credit through per-status dict lookups, and
  `params/california/y2025.py` already carries MFJ/HoH columns (they rode in
  with the full-table FTB validation).
- `pdf_f540.py` maps the filing-status radio group for all five statuses and
  has spouse name/SSN slots reserved; `pdf_1040.py` has spouse name/SSN
  fields mapped in every year block.
- `TaxReturnConfig` carries `spouse_first_name/last_name/ssn`.

## 4. Support declaration and gates

`tenforty/years.py` (the single support-grid authority, per the year-harness
design) gains:

```python
NATIVE_SPINE_STATUSES: dict[int, tuple[FilingStatus, ...]] = {
    2021: (SINGLE,), ... 2024: (SINGLE,),
    2025: (SINGLE, MARRIED_JOINTLY, HEAD_OF_HOUSEHOLD),
}
```

Three enforcement points, all fail-closed:
1. **Spine gate** (`f1040_spine.py` and the orchestrator predicate): a
   (year, status) not in the grid behaves exactly as non-single does today —
   workbook route where the workbook supports it, NotImplementedError where
   it doesn't.
2. **Params completeness gate** (test-time, RED style): for every declared
   (year, status), every per-status params table must contain that column.
   Missing column = suite failure, not KeyError at runtime.
3. **Battery completeness gate:** every declared (year, status) must appear
   in the parity battery at least N times (see §8) — declaring support
   without exercising it is a gate failure.

## 5. Federal params work (dual-transcription discipline)

New/changed columns in `params/federal/y2025.py`, every value dual-transcribed
from Rev. Proc. 2024-40 / 2025 Form 1040 instructions under the existing
air-gapped attestation gate (transcriber B never reads the params modules;
this spec intentionally contains NO numeric values for them):

1. `ordinary_brackets` — **schema change** from a bare tuple to a per-status
   dict `{status: ((upper, rate), ...)}`. Params dataclass fields have no
   defaults (year-harness law), so this reddens 2021–2024 too; those years
   wrap their existing single schedule as `{_S: (...)}` — a mechanical
   re-keying of already-attested values, not new transcription. MFJ/HoH
   schedules are added for 2025 only.
2. `qdcgt_breakpoints` — add MFJ and HoH columns (2025).
3. `addl_medicare_threshold` — add all-status columns (2025) and **make
   f8959 read params instead of its module-level `_THRESHOLDS` dict** (two
   sources of truth today; the hardcoded dict is retired; other years gain
   the columns as part of the same schema tightening since the values are
   statutory, not indexed — cite IRC §3101(b)(2) in the attestation).
4. Tax-table sweep: extend the published-table oracle sweep to the MFJ and
   HoH columns for 2025 (same mechanism as the existing single-column sweep).

## 6. Federal compute changes

- Lift the SINGLE-only raises: `f1040_spine.py:211` and the QDCGT gate at
  `f1040_tax.py:48` become grid checks per §4.
- Widen `_scenario_in_spine_scope` (`orchestrator.py:462`): filing-status
  test becomes membership in `NATIVE_SPINE_STATUSES[year]`. The EIC gate
  below it is untouched.
- **Status audit:** enumerate every `scenario.config.filing_status` consumer
  and every params `[...status.value]` lookup in the spine's transitive
  closure (compute-emission discipline: surfaces you don't enumerate are
  surfaces you silently drop). Each consumer gets an explicit MFJ/HoH row in
  its unit tests. Known consumers as of this writing: sch_a (SALT cap),
  f1040_tax (brackets, QDCGT), spine (std deduction), f8995 (QBI threshold),
  f8959 (threshold), f8962 (see below), f540 family, mappings.
- **f8962 family size:** verify the applicable-figure/FPL derivation counts
  the spouse (tax family = filer + spouse when MFJ + dependents). If family
  size is currently hardcoded to 1 or derived only from dependents, fix as
  part of this spec; the 8962 monthly mechanics are otherwise
  status-independent for MFJ/HoH.
- **1095-A hard-refusal carve-out:** the existing rule "out-of-spine-scope
  scenario with a 1095-A raises rather than dropping PTC" must keep holding
  for the statuses that remain out of scope (MFS/QW).

## 7. CA 540

- Verify (not transcribe — they're already attested) the MFJ/HoH columns in
  `params/california/y2025.py`, and confirm `compute_ca_tax`'s published-cell
  validation already covered those schedule columns; add the sweep rows if it
  was single-scoped.
- CA has no workbook, so the CA hand-oracle
  (`tests/oracles/ca_540_reference.py`) gains MFJ and HoH cases **under the
  standard oracle-isolation rules**: air-gapped derivation from the 2025 FTB
  540 booklet with worked arithmetic in comments; divergences adjudicated
  toward the source.
- CA-specific status wrinkles in scope: per-status renter's-credit AGI
  thresholds and amounts (already parameterized), per-status exemption
  credit. CA law items NOT in scope: joint-vs-separate election asymmetries
  (CA requires matching federal status with narrow exceptions — refuse a
  ca540 whose status differs from the federal scenario's, with a message
  citing the mismatch).
- Amendment path: the Schedule X / amended-540 assembler consumes compute
  results and is status-agnostic; the existing amended-540 e2e gains an MFJ
  row to prove it.

## 8. Emit

- **Federal filing-status checkboxes:** `pdf_1040.py` has no filing-status
  mapping today (spouse fields exist; the status widgets were never wired —
  single packets shipped with the box unmarked). Probe the 2025 template's
  checkbox group (render-verified ON-states, per the marker-probe runbook —
  never inferred from a neighbor year), map all five states, and emit for
  SINGLE too — this fixes a live cosmetic gap in every packet built so far.
- **Spouse identity:** wire `spouse_first_name/last_name/ssn` through the
  orchestrator's identity block to the already-mapped PDF fields on 1040 and
  540, MFJ only. HoH emits no spouse fields.
- **Placement tests** (sentinel fill + read-back) for: each status widget
  state on both forms, spouse name/SSN fields. Presence tests are not
  acceptable per standing discipline.

## 9. Verification

- **Federal parity battery:** new battery scenarios — MFJ and HoH each in at
  least: wages-only; wages + interest/dividends + capital gains (QDCGT
  active); QBI K-1; itemized with SALT at cap; 8959-triggering wages; 1095-A
  reconciliation. Penny-parity against the 2025 workbook via the existing
  PARITY_KEYS gate (the workbook computes these statuses today — it is the
  oracle for exactly this migration). Any parity divergence is adjudicated,
  not allowlisted: the workbook has been wrong before (stray cells, shifted
  rows), so divergences route to team-lead with primary-source arithmetic.
- **CA:** hand-oracle cases per §7 + production-vs-oracle cross-checks of the
  full liability chain (the comparison whose absence hid the withholding
  omission).
- **Mutation checks:** the lifted gates and the new grid gate get
  neuter-the-branch tests — declaring 2025 MFJ support then breaking a params
  column must fail the completeness gate, not surface as a runtime KeyError.
- **Suite invocations:** exact commands, no ad-hoc flags, FIRST-run counts
  verbatim, per standing rules.

## 10. Rollout and sequencing

1. Support grid + gates (RED first: declaring 2025 MFJ with today's params
   must fail the completeness gate).
2. Federal params columns (attested) + schema re-key of `ordinary_brackets`.
3. Federal compute: lift gates, status audit, 8962 family size.
4. Federal parity battery green.
5. CA params verification + compute battery + hand-oracle extension.
6. Emit: checkbox probe + spouse wiring + placement tests.
7. Whole-branch review + full-suite boundary with count reconciliation.

Backfill of 2021–2024 statuses later = grid rows + attested columns +
battery rows; no code changes by design.

## 11. Open questions (resolved before implementation, none block review)

- Whether the 2025 workbook's MFJ/HoH paths have stray-cell defects like the
  2021/2022 vendor workbooks did — the parity battery will surface this;
  budget adjudication time.
- Whether `f8962`'s family-size derivation needs the dependents count now or
  can stay filer(+spouse) until the dependents spec (answer determines
  whether HoH 1095-A scenarios with dependents-in-name-only compute a wrong
  FPL percentage — if so, refuse those loudly rather than compute wrong).
