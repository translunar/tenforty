# Schedule C / Schedule SE / Schedule 2 PDF emit — design

**Date:** 2026-10-03
**Status:** approved design, pre-plan
**Resolves:** the Schedule C emit refusal in `_federal_individual_emit_specs`
(deferred tickets (ee)/(ff)), plus the never-emitted Schedule 2 gap.

## Goal

Lift the orchestrator's fail-closed refusal for Schedule C returns by
completing what it guards against, so a return with
`schedule_c_businesses` can be emitted as a complete paper-filing packet:

1. **Thread `sch_c`/`sch_se` into the emit path's upstream state** so the
   Schedule 1, Form 8959, and Form 8995 fill computes receive the same
   upstream the native compute path gives them (tickets (ee)/(ff)).
2. **Emit three new forms:** Schedule C (one PDF per business),
   Schedule SE (one combined form), and Schedule 2 (new for all
   postures, not only Schedule C returns).
3. **Lift the refusal** once emitted output provably matches the native
   compute.

## Year coverage policy

**TY2022–TY2025.** This sets a new policy: new tenforty features floor
at TY2022 (decision 2026-10-03); existing TY2021 support is maintained
for bug fixes only. Consequences here:

- Schedule C / SE / 2 mappings and templates cover 2022–2025 only.
- A TY2021 scenario with `schedule_c_businesses` still **refuses at
  emit** with a clear year-floor message (not a mapping `KeyError`).
  Native compute remains year-unrestricted.
- TY2021 re-emits keep the legacy no-Schedule-2 convention (totals
  print on the 1040 with no detail form), exactly as shipped today.

## Component 1 — upstream threading (tickets (ee)/(ff))

In `_federal_individual_emit_specs` (`tenforty/orchestrator.py`), the
shared chokepoint both public emit entries route through
(`emit_pdfs` and `run_amendment_packet`):

- Compute `sch_c_results = form_sch_c.compute(scenario, upstream={})`
  once (it is a pure leaf, mirroring the native wiring at the
  compute-path call sites).
- Compute `sch_se_results = form_sch_se.compute(scenario,
  upstream={"sch_c": sch_c_results})`.
- Add both to the `upstream` dict that the Schedule 1, Form 8959, and
  Form 8995 spec blocks already pass to their `compute` calls. Those
  computes consume `sch_c`/`sch_se` keys on the native path today; no
  changes inside them.

The threading must mirror the native compute path's wiring **exactly**
— same upstream key names, same call order. California needs no new
forms: Schedule CA's business-income line is a Col A passthrough of
federal Schedule 1 results, which become correct once upstream is.
A test asserts the CA emit path's Schedule CA business-income line
matches the native compute for a Schedule C scenario.

Regression guard: an emit-path test asserts the emitted Schedule 1's
line 3 (business income) and line 15 (half-SE deduction) equal the
native `compute_federal` values for the same scenario — the exact
silent-disagreement bug the refusal existed to prevent.

## Component 2 — `forms/sch_2.py` (new form module)

Thin compute module in the house pattern
(`compute(scenario, upstream) -> dict`), reading the spine's
already-computed components from `upstream["f1040"]` results:

- Line 1 (AMT): blank/0 — AMT is unmodeled everywhere in tenforty.
- Line 2: excess-APTC repayment (the spine's f8962 repayment key).
- Line 3: Part I total = line 1 + line 2 (flows to 1040 line 17).
- Line 4: SE tax (the spine's `sch_se_line_12_se_tax` passthrough).
- Line 11: Additional Medicare Tax (the spine's f8959 total).
- Line 21: Part II total (flows into 1040 line 23 other taxes).

Output keys `sch_2_line_*`, named by form line. No arithmetic in the
mapping layer: the subtotal lines are computed and tested here. Exact
spine result-key names and any per-year line-number drift are
plan-level facts to pin against the code and the real templates, not
assumed.

**Emit gate** (`_should_emit_sch_2`): year ≥ 2022 AND any of
line 2 / line 4 / line 11 nonzero. Note this fires for existing
non-Schedule-C scenarios too (e.g. an APTC-repayment year, or a year
with Form 8959 tax): re-emitted 2022–2025 packets may gain a
Schedule 2 they previously lacked. That is the intended fix of a
pre-existing paper-filing gap (nonzero 1040 line 17/23 with no detail
schedule attached), not a regression. Existing oracle packet tests
that enumerate emitted files will need their expectations extended.

## Component 3 — Schedule C emit (per business)

- One `_FederalFormSpec` per entry in `scenario.schedule_c_businesses`,
  rendered from the same per-year template: output names
  `f1040sc_1_<year>.pdf`, `f1040sc_2_<year>.pdf`, … and emitted-dict
  keys `sch_c_1`, `sch_c_2`, … **Always indexed, including the
  single-business case** — uniform naming, no special case.
- Values come from `sch_c.compute`'s per-business dicts
  (`sch_c_line_7_gross_income`, `_28_total_expenses`,
  `_29_tentative_profit`, `_31_net_profit`) plus the 12 Part II
  expense-category amounts mapped to their lines (8–27a), plus header
  fields: proprietor name, SSN, line A (the business `description`),
  line B (principal business code — see model change).
- Fixed checkbox derivations, documented at the mapping site:
  accounting method = cash (line F), material participation = yes
  (line G). Both are invariants of what tenforty models — accrual
  accounting and passive sole-proprietorships are unmodeled, and the
  compute layer's refusal guards (COGS, depreciation, home office,
  vehicle, net loss, statutory employee) already fence the rest.
  Unfilled header items (business name/address, lines C/E, the 1099
  questions I/J) stay blank for hand-completion.
- **Model change:** `ScheduleCBusiness` gains
  `business_code: str = ""` (Schedule C line B, the 6-digit principal
  business activity code), filled verbatim; blank allowed (prints
  nothing). YAML schema picks it up through the existing field
  plumbing.

## Component 4 — Schedule SE emit

One form regardless of business count (`sch_se.compute` already
aggregates across businesses). Emit gate: `sch_se` output's
`sch_se_line_12_se_tax` is truthy — matching the IRS rule that
Schedule SE attaches only when SE tax is actually due (the
below-$400-net-earnings case computes zero and emits no form). All
output keys map directly; no mapping-layer arithmetic.

## Component 5 — mappings, templates, placement verification

- New mapping modules `pdf_sch_c.py`, `pdf_sch_se.py`, `pdf_sch_2.py`
  in `tenforty/mappings/`, each covering 2022–2025, registered in the
  catalog/registry like their peers.
- Twelve IRS templates downloaded into `pdfs/federal/<year>/`:
  `f1040sc.pdf`, `f1040sse.pdf`, `f1040s2.pdf` × 4 years.
- **Placement discipline (post-audit, no exceptions for new forms):**
  every mapped field is verified with the marker-probe instrument
  (`scripts/probe_pdf_fields.py`) and pinned in the golden field→line
  fixtures (`tests/fixtures/golden_field_lines.py`) with
  `test_mapping_line_identity.py` coverage for all twelve
  mapping-years.

## Component 6 — packet membership and ordering

`classify_key` in `tenforty/pdf_packet.py` claims the new key family —
`sch_2`, `sch_se`, and the indexed `sch_c_N` family — into the
`federal_individual` packet. Ordering follows the IRS attachment
sequence numbers (Schedule 2 is seq 02, immediately after Schedule 1;
Schedule C is seq 09; Schedule SE is seq 17), inserted into the
existing `ordered_members` convention. The partition invariant is
preserved: every emitted key claimed exactly once or standalone.

## Component 7 — lifting the refusal

The blanket `NotImplementedError` for `schedule_c_businesses` in
`_federal_individual_emit_specs` is replaced by:

- the TY2021 year-floor refusal (clear message naming the policy), and
- nothing else: the compute layer's own refusals (unmodeled Schedule C
  features, net loss) still fire before any PDF is produced, and they
  are the real guards.

The source-document emit gate (every W-2 needs `pdf:` or the
acknowledges flag) applies to Schedule C scenarios exactly as to all
others — no interaction changes.

## Non-goals

- **Amendment-flow verification for the new forms.** No selector work
  is needed: the changed-forms selector is payload-generic over
  whatever specs the shared chokepoint produces, so a 1040-X run whose
  corrected return adds or changes a Schedule C automatically selects
  and renders the new forms once they exist (and a TY2021 amendment
  hits the same year-floor refusal). What is deferred is verification
  only — oracle-tier amendment acceptance for a Schedule C amendment,
  and confirming the amendment packet family claims the new output
  files — because no real scenario requires it (the only live
  Schedule C years, 2024/2025, are original filings).
- Multi-year extension back to TY2021 (policy floor).
- The unmodeled Schedule C features (COGS, depreciation, home office,
  vehicle, losses, statutory employees) — refusals stand.
- AMT (Schedule 2 line 1) — stays blank, unmodeled.

## Testing

All tests subclass `unittest.TestCase`; pytest is the runner; fast
suite invocation is exactly
`.venv/bin/python -m pytest tests/ -q -m "not oracle"`.

- **Unit:** `forms/sch_2.py` compute (component presence/absence,
  subtotal arithmetic, gate conditions).
- **Mapping:** golden field→line identity entries for all twelve new
  mapping-years; marker-probe placement verification during
  development.
- **Fast-tier gate tests via real entry points:** TY2021 year-floor
  refusal; multi-business scenario emits N Schedule C specs + one SE;
  Schedule 2 gate fires/abstains correctly per component; compute-layer
  refusals still reach the emit caller.
- **Threading regression (fast where possible, oracle for fills):**
  emitted Schedule 1 line 3/15, 8959, 8995 values equal native compute;
  Schedule CA business-income passthrough correct.
- **Oracle tier (team-lead's soffice lane only):** end-to-end packet
  for a synthetic multi-business Schedule C scenario — packet contains
  the indexed Schedule C PDFs, SE, and Schedule 2 in attachment-sequence
  order; filled values match `compute_federal` to the dollar; existing
  packet-content expectations extended for newly-present Schedule 2.

All test scenarios are fully synthetic — no real figures, names, or
amounts resembling actual returns (standing PII rule).
