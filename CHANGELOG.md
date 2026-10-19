# Changelog

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
