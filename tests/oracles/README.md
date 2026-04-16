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
  (FTB.ca.gov returned HTTP 403 to the research WebFetch; authoritative text
  was read through the taxformfinder.org mirror, and the 3% TY2024→TY2025
  indexing pattern was cross-checked. Constants tagged `VERIFY` need CPA
  confirmation before downstream production consumes them.)
- **FTB 2025 Schedule CA (540) Instructions** — https://www.ftb.ca.gov/forms/2025/2025-540-ca-instructions.html
- **FTB 2025 Tax Rate Schedules** — https://www.ftb.ca.gov/forms/2025/2025-540-tax-rate-schedules.pdf
- **R&TC §17043** — Behavioral Health Services Tax (Mental Health Services
  Tax, renamed by SB 711 effective TY2025). Statutory; threshold not indexed.
- **SB 711 (2025 Conformity Act)** — federal IRC conformity date moved to
  1/1/2025; name change to "Behavioral Health Services Tax"; alimony sunset
  rules for post-2025 agreements; §1031 real-property-only conformity.

## Known ambiguities / open questions

Raise any of these to the CPA **abstractly** (without quoting FTB language
or proposing a numeric answer) so that the oracle's independent reading is
not influenced by the production design pass.

1. **Constants tagged `VERIFY`.** Standard deduction, exemption-credit
   amounts, renter's-credit cliff, AGI phaseout thresholds, and tax rate
   schedule bracket boundaries were extracted from a mirror of the FTB
   booklet PDF after direct FTB.ca.gov access returned HTTP 403 to the
   research agent. The values are consistent with 3% indexing from published
   TY2024 figures, but direct-from-FTB confirmation of each specific number
   is still required before a production path uses these constants.

2. **Tax table vs rate schedule discrepancy.** FTB requires use of the tax
   table (p. 69–74 of the booklet) for line 19 ≤ $100,000 and the rate
   schedule above. The tax table uses $50-bracket midpoints rather than
   exact bracket math; the oracle applies the rate schedule directly in
   both cases. This introduces a ≈$3 tolerance for line 31 when line 19 is
   below $100,000. The harness must either (a) replicate the tax-table
   midpoint logic, or (b) accept a small tolerance.

3. **Dependent standard deduction worksheet.** The FTB worksheet inherits
   the federal "earned income + $450" base before applying the CA $1,350
   floor and filing-status cap. The oracle's Demographics dataclass does
   not currently expose dependent earned income as an input — the oracle
   uses the CA $1,350 floor directly (capped at the filing-status base).
   If a production scenario involves a dependent with substantial earned
   income, this will underestimate the CA standard deduction. Extend
   Demographics before merging if the scenario requires it.

4. **Renter's-credit AGI basis.** FTB's renter's-credit instruction says the
   cliff applies at "CA AGI" (Form 540 line 17). The oracle currently uses
   federal AGI as a conservative stand-in because line 17 is computed in the
   same pipeline and adding it as a separate input creates a circular
   dependency. In cases where col B/C adjustments materially change CA AGI
   vs federal AGI, the renter's credit result may be wrong by ±$60–$120.
   Flag to CPA whether this is acceptable for the harness scenarios or
   whether the oracle should accept post-computation CA AGI as an override.

5. **Line 74 semantics.** Historical Form 540 line 74 was "Excess SDI";
   TY2024+ the line is "Refundable Program 4.0 Motion Picture Credit" (SDI
   wage base is now unlimited, so excess SDI is handled separately via
   EDD). Legacy references to line 74 as excess SDI will produce wrong
   results.

6. **MFJ edge cases in the exemption-count worksheet.** The FTB worksheet
   for line 7 has specific logic when (a) MFJ and line 6 "can be claimed as
   dependent" is checked, (b) how senior/blind credits interact with being
   claimable. The oracle implements the documented simplified reading
   (claimable-as-dependent zeroes all three of personal/senior/blind); rare
   MFJ-with-both-claimable edge cases may diverge. Raise to CPA if a
   scenario hits this.

7. **§461(l) excess business loss scope.** CA doesn't conform to federal
   CARES/ARPA/IRA extensions to §461(l); the limitation is TY2025 ≈$313k
   single / $626k MFJ. The oracle gates this to raise if the caller sets
   the `excess_business_loss_adjustment` field. Production must separately
   decide how to compute the CA-only §461(l) deferral.

8. **AMT constants.** Schedule P (540) thresholds, exemption amounts, and
   phaseout ranges for TY2025 were NOT captured in the TY2025 research
   pass because the oracle scope-gates AMT entirely. When AMT eventually
   lands in scope, those constants will need a fresh VERIFY pass.

## How to add to this directory

1. New module `tests/oracles/<form>_reference.py`.
2. Pure functions or frozen dataclasses. No imports from `tenforty/`.
3. Every numeric constant and every rule cites its FTB/IRS publication.
4. Update this README's "Current oracles" table and add a scope section.
5. Add a comparison test in `tests/` that fails loudly if production diverges.
   Follow the `unittest.TestCase` pattern (iron law 3); synthetic fixtures
   only (iron law 1).
