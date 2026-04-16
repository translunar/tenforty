# tests/oracles — independent reference implementations

This directory holds **test-only** reference implementations used as cross-check
oracles for production math. Modules here are **not** imported from the
`tenforty/` package; they exist so the production code has something
independent to compare against.

The principle: the federal 1040 pipeline is already cross-checked against the
incometaxspreadsheet.com XLS oracle. For tax flows that aren't modeled in that
oracle (state-specific logic, per-state conformity deltas, pass-through entity
returns, K-1 fan-out), we need a second oracle — one we can read, review, and
update from primary IRS / FTB source material. This directory is where those
live.

## Current oracles (this branch)

| Module | Covers | Status |
|---|---|---|
| `sch_p_540_reference.py` | CA FTB Schedule P (540) — CA AMT + Credit Limitations for CA residents — TY2025 | v0: scope scaffold only; line-numbering and FTB specifics pending ca-research Q1 before any impl. |

Planned / elsewhere:

- `ca_540_reference.py` — CA Form 540 + Schedule CA (540). Lives on branch
  `oracle/ca-540-reference`. Consumes this oracle's `schp_540_amt_due` on
  Form 540 line 61 (AMT), replacing the current scope-out.
- `sch_d_540_reference.py` — CA Sch D (540). Lives on branch
  `oracle/ca-sch-d-540-reference`.
- `f1120s_reference.py` — Federal Form 1120-S. Lives on branch
  `oracle/f1120s-reference`.
- `k1_reference.py` — Schedule K-1 pass-through flows. Lives on branch
  `oracle/k1-reference`.

## Design rules (shared across oracles)

1. **No imports from `tenforty/`.** If the oracle reused production logic, it
   wouldn't be independent and bugs in production would replicate into the
   oracle.
2. **`float` matches production.** Sub-cent precision loss is accepted; the
   comparison harness rounds to the nearest cent before comparing.
3. **No rounding inside the oracle.** Rounding is production's responsibility;
   the oracle reports unrounded arithmetic so sub-dollar divergences surface
   before IRS-style rounding hides them.
4. **Every rule cites its source.** Each calculation carries a `SOURCE:`
   comment naming the FTB instruction paragraph or IRC / R&TC citation.
5. **Out-of-scope is explicit.** Anywhere production might have a more
   complex path, the oracle either errors loudly via `_gate_scope` or
   documents the limitation inline AND in this README.
6. **Document divergences, don't smooth them over.** If a second oracle
   disagrees with this module's reading of the instructions, flag the
   divergence here and let the CPA adjudicate. Silent reconciliation defeats
   the independence principle.
7. **Iron laws 1/2/3/4** (no PII in fixtures, raise on scope-outs,
   `unittest.TestCase`, imports at top) apply to this directory unchanged.
8. **No VERIFY markers in v1.** Pre-clear structural questions with
   ca-research before coding so v1 ships clean.

---

## sch_p_540_reference.py — CA Schedule P (540) oracle

### Purpose

California imposes its own Alternative Minimum Tax under R&TC §17062 and a
parallel credit-limitation mechanism that caps many nonrefundable credits at
the excess of regular tax over TMT. Schedule P (540) is where residents
compute both. Production will eventually emit a full Sch P; this oracle
consumes the same inputs and produces an independent signed AMT amount plus
per-credit caps, so divergences are caught before they reach a filed return.

CA AMT is conceptually similar to federal AMT (Form 6251) but diverges on:

- Per-item CA↔federal conformity on specific adjustments and preferences
  (e.g., §168 depreciation differences, ISO AMT basis, passive-activity
  loss recomputation under CA basis tracking).
- Exemption amounts and phaseout thresholds (CA-indexed; FTB publishes
  annually).
- AMT rate (historically 7.00%, not pegged to IRC §55(b)).
- Credit-limitation caps that apply to CA-specific credits (some carved
  out of the cap by statute — Sch P Part III lists them explicitly).

### Scope (v1 — FTB-verified line structure, pending ca-research Q1)

**Part I — Adjustments and Preferences (AMTI build-up):**
The oracle accepts per-adjustment input on the residents' form (itemized-
deduction interaction, depreciation nonconformity, ISO bargain-element,
passive-activity loss recomputation, §57 tax-exempt PAB interest, etc.)
and sums to AMTI. The specific per-line input catalog is pending
ca-research confirmation so the v1 shape matches the FTB TY2025 form face
exactly.

**Part II — Exemption + TMT + AMT-owed:**
- Exemption amount by filing status with phaseout at the published
  threshold.
- TMT = (AMTI − exemption) × CA AMT rate, non-negative.
- AMT = max(0, TMT − regular-tax-before-credits).

**Part III — Credit Limitations:**
- For each credit on the Part III list, cap at (regular-tax − TMT) unless
  statutorily exempt.
- Emit both the uncapped and capped amount per credit so production's
  ordering decisions stay inspectable.

**AMT credit carryforward tracking:**
- Current-year contribution to AMT credit carryforward (if AMT > 0 this
  year).
- Prior-year AMT credit offset availability (caller supplies the prior
  carryforward; oracle applies the current-year offset limit).
- Clear boundary against Form 3510 (separate future oracle).

### OUT of scope (v1 — caller supplies pre-aggregated or raise)

| Item | Disposition |
|---|---|
| AMT-NOL (alternative minimum tax net operating loss) | Attested-out; caller supplies pre-computed AMTI impact |
| Sch P (540NR) — nonresident / part-year version | Separate oracle, future work |
| Form 3510 (prior-year AMT credit detail beyond offset) | Separate oracle, future work |
| Farming/fishing income averaging interaction | Scope-out (v1) |
| §59(e) optional write-offs | Scope-out (v1) |
| Foreign tax credit AMT adjustment | Scope-out (v1) |

### Output contract (pending Q1 line-numbering confirmation)

`compute_sch_p_540(inp: SchP540Input) -> dict` returns a flat dict of:

- `schp_540_line_<N>_<semantic>` — mirrors the TY2025 Sch P (540) form
  face for all line-level intermediates.
- `schp_540_amti` — AMTI total (float; unrounded).
- `schp_540_tentative_minimum_tax` — TMT (float; unrounded).
- `schp_540_amt_due` — signed float; the AMT amount that flows to Form
  540 line 61. Zero when regular tax exceeds TMT.
- `schp_540_credit_caps` — per-credit dict: `{credit_name: {uncapped, capped}}`.
- `schp_540_amt_credit_carryforward_added_this_year` — contribution to
  next year's AMT credit carryforward.

Stable integration points: `schp_540_amt_due` and `schp_540_credit_caps`.
Line-level keys are stable but may surface additional intermediate values
as the oracle grows.

### Citation lineage

- FTB 2025 Schedule P (540) form + instructions.
- R&TC §17062 (CA AMT imposition), §17039 (credit limitations by order
  and class), §17024.5 (conformity date references).
- IRC §§55, 56, 57, 58, 59 (federal AMT; relevant for per-item
  conformity analysis).

### Integration with CA 540 oracle

The consumer is `ca_540_reference.compute_ca_540` on the
`oracle/ca-540-reference` branch. Currently, `ScopeOut.alternative_minimum_tax`
is attested-out there. Once this oracle ships, that scope-out flips: CA 540
reads `schp_540_amt_due` and populates Form 540 line 61 directly. The
credit-cap output also feeds ordering and application of nonrefundable
credits in the CA 540 pipeline.

Field-name stability across the two oracles is load-bearing. Inputs this
oracle consumes from the CA 540 side:

- `federal_agi` (float)
- `filing_status` (CA filing status string)
- `regular_tax_before_credits` (float; CA regular tax from Form 540
  line 31 before nonrefundable credits)
- `federal_amti_from_6251` (float; caller supplies federal-side AMTI as
  a starting reference — oracle recomputes CA-side from adjustments)
- Further inputs pending Q1.
