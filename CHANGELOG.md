# Changelog

## 0.2.7 — 2026-10-21

Feature release: the earned income credit prints on Form 1040, and a new
footing guard refuses any 1040 whose printed payments section does not
add up.

### Added

- **EIC prints on line 27.** For workbook-routed returns (2021–2025),
  the earned income credit is harvested from the workbook and printed on
  Form 1040 line 27, and total other payments and refundable credits on
  line 32 — previously both lines were blank and the credit appeared
  only inside the line-33 total.
- **Fast- and oracle-tier EIC batteries.** Synthetic childless-EIC
  scenarios (plateau, phase-out, over-ceiling) pin the harvest mapping;
  oracle tests verify the emitted 1040's payment lines foot.

### Behavior change

- **New refusal: line 32 must foot.** Emit now checks that the printed
  line-32 component lines sum to the printed line-32 total, and refuses
  (with an explanation) instead of emitting a 1040 whose visible numbers
  don't add up. Previously such a return emitted silently inconsistent.
- **The footing guard outranks the Schedule 3 acknowledgment.** For
  workbook-routed drafts carrying a net premium tax credit, the
  acknowledgment flag no longer permits an unfooted payments section —
  it covers a missing schedule, not self-contradictory printed
  arithmetic.

## 0.2.6 — 2026-10-21

Feature release: contested-position elections (phase 2 of the registry
shipped in 0.2.2). One optional scenario key gains meaning; no existing
computed output changes.

### Added

- **Contested positions can now be elected.** The `positions:` scenario
  key is consulted at compute time. The first live position is
  `qbi-sehi-shareholder-reduction` — whether a >2% S-corp shareholder's
  self-employed health insurance deduction reduces QBI (the IRS's informal
  FAQ says yes; the AICPA and the regulation's text argue no; no binding
  authority resolves it). A return whose shape reaches the question must
  elect a side:

  ```yaml
  positions:
    qbi-sehi-shareholder-reduction: irs-faq    # or: no-reduction
  ```

  `irs-faq` subtracts the SEHI from that K-1's QBI row before the
  Form 8995 totals (no zero floor); `no-reduction` leaves QBI unchanged.
  Without an election the shape still refuses, with the controversy
  explained.
- **Results record the consulted positions.** When a position actually
  fires, the results dict carries `positions_consulted` (slug, choice,
  reached), so a return's output states which contested elections shaped
  it. Absent when no position was reached.

### Behavior change

- The SEHI-alongside-K-1-QBI shape, hard-refused since 0.2.2, computes
  again when an election is given. Multiple K-1s with QBI under `irs-faq`
  refuse rather than inventing a pro-rata split the guidance never states.

### Internal

- The election-consultation scan fails loudly on aliased imports and on
  local bindings that shadow `election()`, instead of silently missing
  them.

## 0.2.5 — 2026-10-20

Verification release: Schedule E graduates. No scenario-schema changes.

### Verified forms

- **Schedule E (Supplemental Income and Loss) is now a verified form**
  (two independent blind declarations, machine-compared, adjudicated
  against the official paper; runtime gate enforced). Tax year 2021 keeps
  its existing refusal; its derivations surface is exempted through the
  new per-year exemption mechanism rather than silently skipped.

### Internal

- New anchor vocabulary `LabelRelation.ROW_ABOVE_LABEL` for a field whose
  row sits immediately above a print-once label row (Schedule E line 29b);
  a print-once violation refuses loudly instead of falling through.
- The placement checker resolves NearField targets that are option lines
  through the shared option-widget ruling.
- `DERIVATION_YEAR_EXEMPTIONS`: per-(jurisdiction, form, year) exemptions
  from the derivations-surface completeness gate, each guarded against
  staleness in both directions (an exempt year must be genuinely empty
  and a sibling year non-empty).
- Scenario-conditional fill-site cells are normalized at the producer:
  the orchestrator writes values only, so declared specs stay statically
  resolvable.
- The depreciation single-read-path guard allowlists the Schedule E
  declaration's line-18 key-suffix table (it names keys and reads no
  amounts), mirroring the existing entry for the PDF mapping's sibling
  table.

## 0.2.4 — 2026-10-20

Verification release: Schedule B graduates. No scenario-schema changes.

### Verified forms

- **Schedule B (Interest and Ordinary Dividends) is now a verified form**
  (two independent blind declarations, machine-compared, adjudicated
  against the official paper; runtime gate enforced). Line 3 — which
  tenforty's model can never populate — is documented as such pending the
  zero-lines attestation design.

### Fixed

- Schedule B line 6 prints in its own box on 2022–2025 forms (it
  previously landed in the wrong column).
- The dividend payer grid enforces the form's 15-row cap.

### Internal

- New anchor vocabulary `FieldRelation.SAME_ROW_LEFT_OF`; Schedule B payer
  rows 2..N are declared under positional locators, anchored left of
  their amount cells.
- Full-payer-grid emit battery (5 new manifest rows).

## 0.2.3 — 2026-10-19

Verification release: Form 8959 graduates. No scenario-schema changes.

### Verified forms

- **Form 8959 (Additional Medicare Tax) is now a verified form** (two
  independent declarations, machine-compared, adjudicated against the
  official paper; runtime gate enforced). Lines 2, 3, 14 and 23 — which
  tenforty's model can never populate — are documented as such pending a
  zero-lines attestation design.

### Internal

- `tenforty/declarations/forms.py` gains a single `MODULES` registry
  mapping each form to its declaration module, with duplicate refusal and
  identity pins (fixes an importlib guess that broke on numeric form
  names).
- New Schedule E emit battery: 35 scenarios exercising the full Schedule E
  surface (multi-property columns, royalties, Part II rows), feeding the
  in-flight Schedule E declaration lane.

## 0.2.2 — 2026-10-19

Verification release: Schedule D graduates, and two protections land for
cases where the law or the model has a known gap. No scenario-schema
breaks; two new optional scenario keys.

### Verified forms

- **Schedule D is now a verified form** (two independent declarations,
  machine-compared, adjudicated against the official paper; runtime gate
  enforced).

### Fixed

- **Schedule D line 21 now prints.** The capped allowed capital loss —
  which Form 1040 line 7 has always used — never printed on Schedule D
  itself. It now prints in loss years only (as a magnitude inside the
  form's preprinted parentheses) and stays blank in gain years, as the
  form directs.

### New protections

- **Net premium tax credit returns refuse PDF emission** unless the
  scenario states `acknowledges_schedule_3_not_produced: true`. tenforty
  has no Schedule 3 yet, so 1040 lines 31/32 cannot print and a page with
  a net PTC would not foot; the attested emit is for draft/review use and
  says so. Computing the return is unaffected. Schedule 3 support is
  queued.
- **Contested-positions registry (phase 1)** and a new top-level
  `positions:` scenario key. The first registered position is
  `qbi-sehi-shareholder-reduction`: whether a >2% S-corp shareholder's
  self-employed health insurance deduction reduces QBI (the IRS's informal
  FAQ says yes; the AICPA and the regulation's text argue no; no binding
  authority resolves it). In this release every election is refused at
  load ("registered but not yet consulted"): the mechanism that will
  consult it ships in a later release.

### Behavior change

- **SEHI alongside K-1 QBI now refuses instead of silently reducing.**
  Earlier releases silently took the IRS FAQ side on the contested
  question above (reducing the QBI deduction). The shape now refuses with
  the controversy explained, until elections are wired.

### Development

- The inventory extractor's declarations registry gains a single
  form→module source (MODULES), unblocking numerically named forms.


## 0.2.1 — 2026-10-19

Verification release: the first graduations from the emit-verification
harness. No scenario-schema changes.

### Verified forms

- **Schedule 1 and Schedule 2 are now verified forms.** Every printed line
  is declared against the official IRS form (two independent declarations,
  machine-compared, adjudicated against the paper), and a runtime gate now
  refuses an emit whose printed output would not match the declaration —
  a wrong or missing line refuses loudly instead of filing quietly.

### Fixed

- **Schedule 1 line 8z (other income) now foots.** A nonzero 8z previously
  printed a total with no supporting detail. Now each 1099-G-type income
  prints its own row; with one type the description is written in, and
  with two or more a statement page is attached and referenced
  ("See statement"), so line 9 always equals what the page shows.
- **Amendment packets refuse rather than emit a partial Schedule 1.**
  A 1040-X whose changed Schedule 1 would need a statement attachment
  refuses with an explanation instead of emitting a packet missing it.

### Development

- The fast test tier runs under pytest-xdist (`-n 4`): ~6 minutes instead
  of ~20. Oracle-tier runs remain strictly serial (single LibreOffice
  slot); README and runbooks carry the warning.


## 0.2.0 — 2026-10-17

Input-schema release: the native filing-statuses round and the FTB 3532
(head-of-household) round. Every break fails loudly at load with a message
naming the fix; nothing is silently reinterpreted.

### Breaking: scenario schema

- **`FilingStatus` renamed** to the IRS's own wording: `married_jointly` →
  `married_filing_jointly`, `married_separately` →
  `married_filing_separately`. The retired strings are refused with a
  pointer to the replacement (never accepted as aliases); other unknown
  strings get a did-you-mean suggestion.
- **`spouse_birthdate` is required for MFJ** scenarios (it drives the
  spouse's age-based standard deduction and CA senior exemption). It must
  be absent for single / head-of-household filers.
- **`W2.owner`** (`taxpayer` | `spouse`) attributes each W-2 for the
  per-owner excess-social-security computation on multi-W2 returns.
- **`config.head_of_household` is required for HoH filers.** A CA
  head-of-household packet without FTB 3532 is silently incomplete, so the
  block records the Part I marital-status facts and the qualifying person
  (name, SSN, birthdate, relationship, residency days, gross income).
  A pre-0.2.0 HoH scenario fails at load naming the block and FTB 3532;
  it never emits a 540 that FTB would re-status. Minimal example:

  ```yaml
  config:
    filing_status: head_of_household
    head_of_household:
      marital_status: unmarried
      lived_with_spouse_periods: []
      separation_decree_kind: null
      qualifying_person:
        first_name: "Ada"
        last_name: "Example"
        ssn: "123456789"
        birthdate: "2012-03-07"
        relationship: child_or_stepchild
        full_time_student: null
        permanently_disabled: null
        gross_income: 0
        days_lived_with_you: 365
        claimed_as_dependent: false
  ```

  `claimed_as_dependent` is always required; `true` refuses until the
  dependents work lands (0.2.1+).

### Behavior changes

- Aged filers (65+) now receive the additional federal standard deduction
  and the CA senior exemption credit in every supported year.
- TY2025 aged native filers are refused pending Schedule 1-A support,
  rather than computed without it.
- TY2025 federal HoH emits refuse for a filer separated under a
  `legal_separation` decree (the end-of-year-household fact the 2025 form
  requires is not captured by the schema).

### Added

- Native-spine support for all filing statuses, with per-status CA
  parameters (exemption credits, AGI phaseout thresholds) transcribed per
  year.
- FTB 3532 (Head of Household Filing Status Schedule) emitted with every
  CA head-of-household 540 packet.
- Age-based inputs (`birthdate`, `spouse_birthdate`) on the native spine.
