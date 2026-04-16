# tests/oracles — independent reference implementations

This directory holds **test-only** reference implementations used as cross-check
oracles for production math. Modules here are **not** imported from the
`tenforty/` package; they exist so the production code has something
independent to compare against.

The principle: the federal 1040 pipeline is already cross-checked against the
incometaxspreadsheet.com XLS oracle. For tax flows that aren't modeled in that
oracle (K-1 internals, Schedule E Part II row-level fan-out, QBI, passive-
activity rules, state-specific logic), we need a second oracle — one we can
read, review, and update from primary IRS / FTB source material. This
directory is where those live.

## Current oracles

| Module | Covers | Status |
|---|---|---|
| `ca_540_reference.py` | CA FTB Form 540 + Schedule CA (540) Part I and Part II — TY2025 | Implemented against FTB 2025 booklet (2026-04-15). |

Planned (future PRs, not part of this branch):

- `k1_reference.py` — Schedule K-1 (1120-S / 1065 / 1041) pass-through flows. Exists on branch `oracle/k1-reference`; will merge independently.

## Design rules (shared across oracles)

1. **No imports from `tenforty/`.** If the oracle reused production logic, it
   wouldn't be independent and bugs in production would replicate into the
   oracle.
2. **`float` matches production.** Sub-cent precision loss is accepted; the
   comparison harness rounds to the nearest cent before comparing.
3. **No rounding inside the oracle.** Rounding is production's responsibility;
   the oracle reports unrounded arithmetic so sub-dollar divergences surface
   before IRS/FTB-style rounding hides them.
4. **Every rule cites its source.** Each calculation carries a `SOURCE:`
   comment naming the FTB/IRS instruction paragraph.
5. **Out-of-scope is explicit.** Anywhere production might have a more
   complex path, the oracle either errors loudly via `_gate_scope` or
   documents the limitation inline AND in this README.
6. **Document divergences, don't smooth them over.** If a second oracle
   disagrees with this module's reading of the instructions, flag the
   divergence here and let the CPA adjudicate. Silent reconciliation defeats
   the independence principle.
7. **Iron laws 1/2/3/4** (see `.claude/skills/code-review/SKILL.md`) apply to
   this directory unchanged: no PII, raise on scope-outs, unittest.TestCase,
   imports at top.

---

## CA 540 oracle scope

### In scope (TY2025)

- Form 540 lines 12–19 (income → CA AGI → deduction → taxable income)
- Form 540 lines 31–35 (tax, exemption credits with AGI phaseout, total tax
  before special credits)
- Form 540 lines 40, 43–48 (simple nonrefundable credits: dependent care
  with $100k AGI gate; renter's credit with hard AGI cliff; other special
  credits are accepted as a pre-computed sum from the caller)
- Form 540 lines 61–64 (AMT is scope-gated; BHST is computed from taxable
  income > $1M; other taxes / recapture are accepted from the caller)
- Form 540 lines 71–78 (payments, with individual credits accepted from the
  caller; oracle does not compute EITC / YCTC / FYTC from FTB 3514)
- Form 540 lines 91–115 (use tax, overpaid vs owed, refund / amount due)
- Schedule CA (540) Part I line-by-line aggregation for columns B / C into
  line 27 (line 14 / line 16 on Form 540)
- Schedule CA (540) Part II itemized deduction recomputation through
  lines 4, 5e, 7, 10, 14, 15, 16, 17, 18, 22, 25, 26, 28, 29, 30 (CA SALT
  add-back, pre-TCJA mortgage-interest cap, CA-allowed charitable ≤30%/50%
  differences, nonfederally-declared casualty, 2%-floor misc deductions,
  AGI-based itemized phaseout)

### Out of scope — gated by `_gate_scope` (raises NotImplementedError)

- AMT / Schedule P (540)
- Schedule G-1 (qualified lump-sum distribution alt tax for pre-1/2/1936 DOB)
- FTB 5870A (accumulation distribution from certain trusts)
- FTB 3800 / FTB 3803 (kiddie tax and parent election for child's interest)
- NOL deductions (FTB 3805V / 3805Z / 3807 / 3809)
- FTB 3461 excess business loss adjustment
- FTB 3853 ISR penalty (line 92)
- FTB 5805 / 5805F underpayment penalty

### Out of scope — silently skipped (caller responsibility)

- EITC / YCTC / FYTC computation (FTB 3514) — caller passes precomputed values
- Motion Picture Credit refundable portion (FTB 3541) — caller passes value
- Dependent-care credit amount (FTB 3506) — caller passes value; oracle
  enforces the federal-AGI $100k eligibility gate
- Other special credits in lines 43–45 — caller passes sum
- RDP pro-forma federal AGI (FTB Pub 737 worksheet) — caller passes the
  appropriate federal AGI figure
- Real data extraction from W-2 / 1099 documents — caller passes totals

## Input / output contract

See the docstrings in `ca_540_reference.py`. Briefly:

- **Input**: `CA540Input` — nested frozen dataclasses grouped by topic
  (Demographics, FederalCarryIn, SchCAPartIAdjustments,
  SchCAPartIIAdjustments, Form540Payments, Form540Credits, Form540OtherTaxes,
  Form540Misc, ScopeOut). Every field is required so nothing silently
  defaults to zero.
- **Output**: flat `dict[str, float | bool]` keyed by
  `f540_line_<N>_<semantic>` and
  `schca_part_<N>_line_<M>_<col>_<semantic>`. Unrounded float arithmetic.
  The harness chooses its own tolerance and rounding policy when diffing.

## Citation lineage

Every rule in `ca_540_reference.py` cites one of:

- **FTB 2025 Form 540 Booklet** — https://www.ftb.ca.gov/forms/2025/2025-540-booklet.html
- **FTB 2025 California Tax Table (PDF)** — verified locally against the
  published 2025 tax-table PDF; the tax-rate-schedule bracket boundaries
  (Schedules X / Y / Z) have been reproduced row-by-row against first-party
  FTB output and are therefore first-party-verified for TY2025.
- **FTB 2025 Schedule CA (540) Instructions** — https://www.ftb.ca.gov/forms/2025/2025-540-ca-instructions.html
- **FTB 2025 Tax Rate Schedules** — https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf
- **R&TC §17043** — Behavioral Health Services Tax (Mental Health Services
  Tax, renamed by SB 711 effective TY2025). Statutory; threshold not indexed.
- **SB 711 (2025 Conformity Act)** — federal IRC conformity date moved to
  1/1/2025; name change to "Behavioral Health Services Tax"; alimony sunset
  rules for post-2025 agreements; §1031 real-property-only conformity.

Values cross-referenced against commercial sources (TurboTax, NerdWallet,
Plante Moran, TaxFormFinder) where first-party PDF access was blocked by
HTTP 403: standard deduction, exemption-credit per-person amounts
(including the MFJ/QSS line 7 preprint idiosyncrasy), AGI phaseout
thresholds, and renter's-credit AGI cliffs. Three independent commercial
sources agree on each.

## Known ambiguities / open questions

Raise any of these to the CPA **abstractly** (without quoting FTB language
or proposing a numeric answer) so that the oracle's independent reading is
not influenced by the production design pass.

1. ~~**Constants tagged `VERIFY`.**~~ **RESOLVED 2026-04-16** —
   standard deduction ($5,706 / $11,412), exemption-credit amounts ($153
   per person for personal / senior / blind — Form 540 line 7 face preprint
   reads "[count] × $153" so MFJ/QSS with count 2 is exactly 2 × $153 =
   $306, no rounding quirk; $475 per dependent), AGI phaseout thresholds
   ($252,203 / $378,310 / $504,411), and renter's-credit cliffs
   ($52,421 / $104,842) cross-referenced against Spidell 2025 Pocket
   Reference (CA-specific authoritative commercial source) plus three
   independent commercial sources each (Plante Moran state advisory,
   TurboTax, NerdWallet, TaxFormFinder). **Tax rate schedule bracket
   boundaries** (Schedules X / Y / Z) additionally verified row-by-row
   against the first-party FTB 2025 Tax Table PDF — four spot checks
   across the Single column at different brackets all reproduced the
   printed whole-dollar tax to the nearest dollar. `VERIFY` tags removed.

2. ~~**Tax table vs rate schedule discrepancy.**~~ **RESOLVED 2026-04-15** —
   switching rule is a hard cutoff at Form 540 line 19 **≤ $100,000 uses
   the tax table**, **> $100,000 uses the rate schedules**. The FTB tax
   table uses one $50-wide bracket ($1–$50) then all-$100-wide brackets
   ($51–$150, $151–$250, …) through the top at $99,951–$100,000; printed
   tax is the rate-schedule result at the bracket midpoint rounded to
   whole dollars. The oracle applies the rate schedule directly in both
   ranges and reports unrounded arithmetic, by design.

   **Harness tolerance contract:** when line 19 ≤ $100,000, compare line
   31 (and anything downstream — total tax, refund, balance due) with a
   **$5 absolute tolerance** to absorb the midpoint quantization (worst
   case: $50 × 9.3% = $4.65). When line 19 > $100,000, use the normal
   cent-exact tolerance; both oracle and production apply the rate
   schedule without quantization. `TAX_TABLE_CUTOFF_2025 = $100,000` is
   confirmed.

3. ~~**Dependent standard deduction worksheet.**~~ **RESOLVED 2026-04-16** —
   ca-research verified the 5-line FTB Standard Deduction Worksheet for
   Dependents (line 1 = federal earned income + $450, line 2 = $1,350 CA
   floor, line 3 = greater of 1 and 2, line 4 = filing-status cap
   $5,706/$11,412, line 5 = lesser of 3 and 4). The $450 add-on is
   unindexed (fixed since TY2023); $1,350 is indexed from TY2024's $1,300.
   The oracle's `Demographics` dataclass was extended with a
   `dependent_earned_income: float` field (per federal Pub 501 definition:
   wages/tips/net SE compensation; excludes interest, dividends, gains,
   pensions, non-taxable scholarships). The field is read only when
   `can_be_claimed_as_dependent` is True; producers may pass 0.0 in the
   non-claimable case. Five new unit tests cover the four worksheet
   branches (not claimable, zero earned, earned below tie point, earned
   above cap).

4. ~~**Renter's-credit AGI basis.**~~ **RESOLVED 2026-04-16** —
   ca-research verified against the FTB Form 540 Booklet Nonrefundable
   Renter's Credit Qualification Record (Question 2, verbatim): cliff
   applies at "California adjusted gross income the amount on line 17".
   The oracle now uses Form 540 line 17 for the gate, pulled from the
   income dict already computed upstream in `compute_ca_540`. No new
   input field needed — line 17 is lexically available before the
   credits step. Added a new unit test exercising a $60k federal AGI /
   $50k CA AGI case (single, $10k Social Security Sch CA subtraction)
   that correctly gets the $60 credit; previously would have been
   denied.

5. ~~**Line 74 semantics.**~~ **RESOLVED 2026-04-16** — three-step
   evolution: **≤ TY2023** Excess California SDI (or VPDI) Withheld;
   **TY2024** "Reserved for future use" (SB 951 removed the SDI wage
   cap effective 1/1/2024, so excess SDI no longer occurs within a
   single employer; multi-employer excess is handled via EDD, not on
   Form 540); **TY2025+** Refundable Program 4.0 California Motion
   Picture and Television Production Credit, sourced from FTB 3541
   line 25 (R&TC §17053.98.1, authorized by AB 132 (2024), effective
   for tax years beginning on or after 1/1/2025). Lines 75–77 remain
   unchanged (EITC / YCTC / FYTC from FTB 3514).

   Oracle stance for TY2025 (in scope): line 74 accepts the caller-
   precomputed Program-4.0 MPC amount via the existing "caller passes
   precomputed refundable-credit values" rule (oracle doesn't compute
   FTB 3541). Legacy fixtures that label line 74 as "excess SDI" will
   silently map to the MPC slot under TY2025 semantics, producing
   wrong results — document this risk in any fixture-migration notes.

6. ~~**MFJ edge cases in the exemption-count worksheet.**~~
   **RESOLVED 2026-04-16** — ca-research extracted the FTB line 7
   worksheet verbatim: "Yes" on line 6 (primary claimable) means enter 0
   for single/MFS/HOH, 0 for MFJ if both spouses claimable, **1 for MFJ
   if only one spouse claimable**. Lines 8 (blind) and 9 (senior) each
   carry the warning "Do not claim this credit if someone else can claim
   you as a dependent" — applied per-spouse so a non-claimable MFJ
   spouse retains their own senior/blind credit. Line 10 (dependent)
   drops when the entire filing unit is claimable.

   Oracle updates:
   - `Demographics` extended with `spouse_can_be_claimed_as_dependent:
     bool` (only meaningful for MFJ; producers should pass False for
     non-MFJ statuses).
   - `_count_exemptions` rewritten to apply the four cases cleanly:
     MFJ both-claimable / one-claimable / neither-claimable, plus the
     non-MFJ primary-claimable path.
   - Senior / blind counted per-spouse with per-spouse claimable gating.
   - Dependent count dropped only when the entire unit is claimable.
   - Seven new unit tests cover the MFJ permutations (only-primary,
     only-spouse, both, non-claimable-spouse-retains-senior,
     both-claimable-drops-deps, one-claimable-keeps-deps).

7. ~~**§461(l) excess business loss scope.**~~ **RESOLVED 2026-04-16** —
   TY2025 CA thresholds confirmed at **$313,000** (single / MFS / HOH)
   and **$626,000** (MFJ / RDP-joint), matching the federal §461(l)
   thresholds magnitude-wise. CA's non-conformity is structural: CA did
   not adopt the CARES §2304 suspension and has not followed ARPA/IRA
   extensions, so disallowed EBL becomes a CA-specific excess business
   loss carryover (distinct from the NOL pool). Entry points are
   Schedule CA (540) line 8p column B/C and line 8z column B
   (prior-year carryover).

   Oracle stance: scope-gate remains correct. Computing CA §461(l)
   requires the FTB 3461 line-by-line logic plus per-taxpayer CA EBL
   carryover tracking across years — both out of scope here. The gate
   applies to any non-zero `excess_business_loss_adjustment`; callers
   with prior-year CA EBL carryover must either compute the line 8z
   adjustment upstream and pass it via the existing Sch CA line-8z
   column B field, or flag the scenario as out-of-scope.

8. ~~**AMT constants.**~~ **RESOLVED 2026-04-16** (captured for future
   scope expansion; oracle continues to scope-gate AMT entirely).
   TY2025 Schedule P (540) constants per FTB 2025 instructions:
   - **Rate**: 7.0% (R&TC §17062; statutorily stable since TY1991).
   - **Exemption amounts**: $90,048 single / HOH; $120,065 MFJ / QSS /
     RDP-joint; $60,029 MFS / RDP-separate.
   - **Phaseout**: 25% exemption reduction per $1 of AMTI over the
     start threshold. Starts: $337,678 single / HOH; $450,238 MFJ /
     QSS; $225,115 MFS. Complete-phaseout (exemption = 0) points
     self-consistent with start + exemption × 4: $697,870, $930,498,
     $465,231 respectively.

   Keeping the scope-gate is the correct call. Bringing AMT into scope
   additionally requires: ~20 Schedule P Part I CA-vs-federal
   adjustments (SALT, §67(g) misc deductions, depreciation deltas, ISO
   / NQSO timing, private-activity bond interest, etc.); Part III
   credit-ordering logic (Section A / A2 / B / C limitation tiers);
   and the CA-vs-federal AMTI reconstruction starting from federal
   Form 6251 line 4. These constants are a starting point but need
   direct-from-FTB re-verification when AMT lands in scope — the
   current values come from WebSearch snippets, not first-party PDF
   reads.

## How to add to this directory

1. New module `tests/oracles/<form>_reference.py`.
2. Pure functions or frozen dataclasses. No imports from `tenforty/`.
3. Every numeric constant and every rule cites its FTB/IRS publication.
4. Update this README's "Current oracles" table and add a scope section.
5. Add a comparison test in `tests/` that fails loudly if production diverges.
   Follow the `unittest.TestCase` pattern (iron law 3); synthetic fixtures
   only (iron law 1).
