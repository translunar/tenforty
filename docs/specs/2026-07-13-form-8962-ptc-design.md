# Form 8962 (Premium Tax Credit) Component-Port — Design

**Goal:** Compute and emit Form 8962 — reconciliation of advance premium tax
credit (APTC) against entitled PTC — for every amendable federal year
(2021–2025), integrated into the 1040 spine via Schedule 3 line 9 (net PTC)
and Schedule 2 line 2 (excess-APTC repayment).

**Why now (two live demands):** the real 2024 federal amendment packet
currently REFUSES under the filed-file decomposition convention because the
filed return carries an excess-APTC repayment tenforty cannot model; and the
2021 return has an unreconciled APTC (Form 8962 was required and never
filed) whose resolution turns on the 2021 ARPA unemployment rule.

**Shape:** this is the designated first COMPONENT-PORT exercise — the
transpose of add-tax-year. Where a year-extension adds all forms for one
year, a component-port adds one form across all years, exercising the same
manifest/params/probe/oracle machinery along the other axis.

---

## 1. Scope

In scope:
- `forms/f8962.py`: pure monthly PTC computation (lines 1–29), all five
  years, params-driven.
- Year-stamped params: FPL table, applicable-figure table, repayment
  limitation table (`tenforty/params/f8962/<year>.yaml`).
- Scenario input: a new `form_1095a` block (monthly rows + flags), loader
  fail-closed.
- Spine integration: Schedule 3 line 9 / Schedule 2 line 2 flow into the
  1040 as printed; spine-scope predicate keeps 8962 scenarios native.
- Full PDF emit pack per year: 2022–2025 under the standard
  FEDERAL_FORMS × FEDERAL_YEARS gate, plus a 2021 slice (same precedent as
  the S-corp 2021 emit slice — 2021 is a compute-only year, but the filled
  2021 form is genuinely wanted for the late-8962 filing).
- Amendment integration: the amendment-side filed-values convention gains
  modeled f8962 keys, retiring the refusal that currently blocks a federal
  amendment whose filed return carried a repayment.

Out of scope (explicit, each with a refusal or a note):
- Tax family size > 1, any filing status the spine does not support, and
  dependents' MAGI (line 2b) — fail-closed refusal naming the limit.
- Policy allocations between taxpayers and the alternative marriage-year
  calculation (line 9 "Yes" path, Parts IV–V) — refusal.
- Multiple 1095-A forms for one year — refusal (v1 accepts exactly one
  policy's monthly rows).
- SE-health-insurance/PTC iterative interaction (Rev. Proc. 2014-41):
  the SE-health channel is itself ON HOLD; if a scenario ever claims both,
  refuse loudly rather than compute either non-iteratively.
- California FTB 3849/3895 state-subsidy reconciliation: dead program
  (2020–2021 only), and the user's own 3895 shows zero state subsidy every
  month — nothing to reconcile. CPA-awareness note only.
- Deadline/statute logic — as everywhere in tenforty.

## 2. Inputs — the `form_1095a` scenario block

```yaml
form_1095a:
  months:            # exactly 12 keys, jan..dec; uncovered months all-zero
    jan: {premium: 0, slcsp: 0, aptc: 0}
    ...
    dec: {premium: 0.00, slcsp: 0.00, aptc: 0.00}
  received_unemployment_2021: false   # legal ONLY when year == 2021
  tax_exempt_interest: 0.00           # optional MAGI addition
```

- Monthly-always: the annual line-11 shortcut is NOT modeled; the monthly
  grid (lines 12–23) is the general case and the uniform year is just
  twelve equal rows. (Decided against annual-only because real coverage is
  frequently partial-year — including the user's own anchor year.)
- Loader fail-closed like every scenario block: unknown keys raise; the
  12-month map must be complete (absent month ≠ zero month — the filer
  states every month).
- `received_unemployment_2021: true` outside year 2021 is a ValueError
  (the flag encodes a one-year statute, not a preference).
- MAGI = AGI + tax-exempt interest (+ the other statutory additions ONLY
  as refusal guards until modeled: nontaxable social security and excluded
  foreign income are absent from the spine's scope — if a scenario carries
  a channel for them someday, the 8962 module must be revisited; a code
  comment marks the seam).

## 3. Params — three year-stamped tables

`tenforty/params/f8962/<year>.yaml`, dual-transcription attestation (two
blind transcribers, official IRS instructions for THAT year, verbatim-or-
None), like all params:

- `fpl_table`: the federal poverty guideline for household size 1, 48
  contiguous states + DC. TRANSCRIPTION TRAP (named in the attestation
  brief): Form 8962 for tax year N uses the guideline PUBLISHED IN YEAR
  N−1 (e.g., TY2021 uses the 2020 guideline). Alaska/Hawaii tables are out
  of scope (CA filer); the table records the "other 48" figure only, with
  the poverty-table checkbox (line 4 box c) hardwired accordingly.
- `applicable_figure_table`: FPL% → applicable figure. 2021–2022 carry the
  ARPA shape (0.0 floor through 150%, 8.5% ceiling, NO 400% cliff);
  2023–2025 carry the IRA-extended shape (same structure). The table is
  transcribed per year regardless of shape similarity — never copied
  across years.
- `repayment_limitation_table`: FPL band → cap (single-filer column), used
  only when household income < 400% FPL; at ≥ 400% the repayment is
  uncapped.
- 2021 only: `unemployment_rule: true` — any week of unemployment
  compensation received/approved during 2021 caps the line-5 FPL
  percentage at 133 (which drives the applicable figure to the year's
  floor). Absent from every other year's params; the compute refuses if
  the scenario flag is set but the year's params lack the rule.

## 4. Compute — `forms/f8962.py`

Pure function over (scenario block, spine results, params). Lines as
printed:

1. Household income (lines 1–3): MAGI per §2; tax family size 1.
2. Line 5 FPL% = household income / FPL, floor-rounded per instructions;
   2021 UI rule overrides to 133 when flagged.
3. Line 7 applicable figure from the table; line 8a/8b contribution
   (annual, then monthly = 8a/12, each rounded per instructions).
4. Monthly grid (lines 12–23): per month, column (d) max assistance =
   max(0, slcsp − monthly contribution); column (e) PTC =
   min(premium, (d)); column (f) = APTC as stated.
5. Line 24 total PTC, line 25 total APTC, line 26 net PTC =
   max(0, 24 − 25) → Schedule 3 line 9.
6. Line 27 excess APTC = max(0, 25 − 24); line 28 cap from the repayment
   table when line 5 < 400 (blank at ≥ 400); line 29 repayment =
   min(27, 28 or ∞) → Schedule 2 line 2.
7. Zero-coverage year (all-zero months): every output zero, form not
   emitted (the _should_emit predicate treats an absent/all-zero block as
   no-8962, matching how the other conditional forms gate).

Rounding: whole-dollar IRS rounding at the line boundaries the
instructions specify — the oracle battery pins the exact spots (monthly
cells round per-cell, per the printed form).

## 5. Manifest, emit, gate

- `f8962` joins FEDERAL_FORMS: the completeness gate then demands
  template + probe + mapping for every FEDERAL_YEAR (2022–2025),
  RED-then-allowlist lifecycle with work-owed comments, exactly like every
  form addition.
- The 2021 slice ships additionally (compute-only year): template + probe
  + mapping for 2021 outside the automatic gate demand, with an explicit
  gate test asserting the 2021 pack's presence (loud, not silent extra) —
  the S-corp 2021-slice precedent.
- Marker-probe regime unchanged: paths from each year's own get_fields;
  checkbox A (the UI box) and the line-10 monthly-path handling certified
  per template; filled-emit read-back with distinctive values, checkbox
  state both ways for 2021 (the only year A is legitimately checked).
- Emit joins the changed-forms selector universe automatically (it is a
  mapped federal form with payloads), so an amendment that changes AGI
  selects the corrected 8962 as an attachment — the exact 2024 use case.

## 6. Amendment integration

- The filed-values decomposition convention (amendment.py docstring)
  gains the modeled keys: a filed 8962 repayment is recorded as its own
  filed key feeding 1040-X line arithmetic through the modeled Schedule 2
  path, not parked under the `other_taxes` refusal guard.
- The 1040-X assembler's line disposition is NOT changed by this spec:
  total_tax (line 11) already includes Schedule 2 line 2's effect once the
  spine models it. The refusal guard on `other_taxes` remains for
  everything else unmodeled.
- Column C for an amendment of a year with a 1095-A requires the
  form_1095a block in the corrected scenario — the loaders' fail-closed
  behavior makes an accidental omission a refusal (all-zero months is an
  explicit statement, absent block on a year whose filed return had a
  8962 is caught by the filed-key consistency check).

## 7. Validation

- **Oracle**: hand-coded per year from that year's official Form 8962
  instructions, under full oracle isolation (oracle author reads ONLY the
  instructions; battery author sees only signatures; never edit the oracle
  toward the implementation; mutation checks required).
- **Battery invariants** (every case, every year): PTC ≤ premiums,
  monthly and total; line 26 and line 29 never both nonzero; repayment ≤
  cap whenever line 5 < 400; all-zero block → all-zero outputs and no
  emit; UI-flag monotonicity for 2021 (setting the flag never decreases
  PTC); A(nnual totals) of the monthly grid equal the sums of the cells.
- **Table-sweep**: the applicable-figure interpolation is exercised across
  every FPL band boundary per year (the 2062-bin-sweep discipline from
  the tax-table work, scaled to this table's size).
- **External anchors** (USER STEP, real figures never in the repo): the
  user's real 2024 (filed WITH a Form 8962 repayment — tenforty must
  reproduce the filed repayment from the actual 1095-A monthly data,
  which simultaneously validates the 2024 amendment's Column A) and real
  2021 (partial-year coverage, UI flag set, expected result: net PTC and
  repayment both exactly zero — APTC was advanced at exactly the
  entitlement).
- **Amendment e2e**: with 8962 modeled, the previously-refusing federal
  amendment case (filed repayment under a guard key) is replaced by a
  passing case using the modeled keys; the refusal test itself moves to a
  different still-unmodeled guard key so the guard stays exercised.

## 8. Process

- Spec committed genericized (scanner must pass); implementation plan in
  gitignored docs/plans/ per house convention.
- Executed by packet-builder on a fresh branch `f8962-ptc` off merged main
  (e08b579), subagent-driven, task boundaries verified by team-lead as
  usual; params attestation and oracle isolation air-gaps per house
  regime.
- USER STEPS at the end: transcribe the real 1095-A monthly rows for 2021
  and 2024 into the external scenario files (drafting assistance allowed,
  user verifies against the PDFs); run the two anchors; then the 2024
  federal amendment packet unblocks and the 2021 late-8962 question gets
  its machine-checked answer for the CPA.
