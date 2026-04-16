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
| `sch_d_540_reference.py` | CA FTB Schedule D (540) — federal↔CA capital-gain delta for Sch CA (540) Part I line 7 — TY2025 | v0 scaffold only; delta catalog pending ca-research. |

Planned / elsewhere:

- `ca_540_reference.py` — CA Form 540 + Schedule CA (540). Lives on branch
  `oracle/ca-540-reference`. Consumes this oracle's output dict key
  `schd_540_ca_fed_delta_to_sch_ca_line_7` on
  `SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions`.
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

---

## sch_d_540_reference.py — CA Schedule D (540) oracle

### Purpose

California generally conforms to federal capital-gain treatment but with
several named non-conformity deltas. This oracle computes a single
aggregate number — the CA-minus-federal capital-gain delta — that the
CA 540 oracle places on Schedule CA (540) Part I line 7 column B
(subtractions) or column C (additions) depending on sign. It does NOT
produce a full line-by-line Schedule D (540); it produces the net
adjustment the downstream 540 oracle needs.

### Scope (v1 — delta categories)

**IN scope (pending ca-research verification):**

- Basis differences between federal and CA (e.g., pre-1987 depreciation
  differences; differing §179 basis; differing depreciation methods on
  assets with federal/CA book divergence).
- §1202 qualified-small-business-stock gain: federal partial exclusion
  under IRC §1202 is NOT allowed by California — R&TC §18152. CA
  recognizes the full gain.
- §1400Z-2 Opportunity Zone deferrals / exclusions: California does NOT
  conform — R&TC §17158.3. CA recognizes gain in the year deferred
  federally.
- Installment-sale method differences where federal and CA use
  different reporting methods.
- CA-side capital loss carryover, which tracks separately from the
  federal figure due to prior-year conformity deltas.

**OUT of scope (v1 — oracle raises or caller supplies):**

| Item | Disposition |
|---|---|
| Schedule D-1 (540) like-kind §1031 exchanges (real-property only, post-TCJA) | Scope-out; caller supplies the delta pre-aggregated |
| Wash-sale timing conformity (IRC §1091 / R&TC §18031) | Verification queue |
| Passive-activity-loss interaction on cap-gain dispositions | Scope-out; handled on Sch P (540), not here |
| Collectibles (28%) / unrecaptured §1250 CA treatment | Verification queue |
| Mark-to-market §475(f) trader elections | Scope-out |
| PFIC gains (Form 8621) | Scope-out — federal-only complexity |
| Qualified Opportunity Fund dispositions post-deferral | Scope-out pending ca-research |
| S-corp pass-through capital gains from K-1 box 7/8a | Accepted as input; not recomputed here |

### Output contract

`compute_sch_d_540(inp: SchD540Input) -> dict` returns a flat dict
including at least:

- `schd_540_ca_fed_delta_to_sch_ca_line_7` — signed float. Positive = CA
  recognizes MORE gain than federal (column C addition). Negative = CA
  recognizes LESS gain than federal (column B subtraction). The CA 540
  oracle takes the absolute value and routes by sign.

Additional keys may surface for line-level transparency but the delta
key above is the sole stable integration point.

### Verification queue (pending ca-research)

Items flagged for `ca-research` before the oracle moves beyond v0
scaffold. The delta catalog itself is the blocking question.

1. **Complete delta-category catalog for TY2025.** Named items:
   basis differences, §1202 QSBS, §1400Z-2 OZ, installment-sale method
   divergence, wash-sale timing. Any other commonly-encountered item
   for a 540 filer with investment accounts + rental-property sales?
2. **Schedule D (540) 2025 line numbering.** Older FTB forms used
   lines 1 through 14 on the schedule proper. 2025 line numbers
   need verification before output keys stabilize. If 2025 renumbers,
   output-dict keys require renaming.
3. **CA capital-loss carryover year-over-year tracking rules.**
   Confirm that the CA carryover is just the prior-year CA Schedule D
   line-8 residual (or equivalent 2025 line), and that the oracle's
   single `ca_capital_loss_carryover` input is sufficient to represent
   carryover state.
4. **Schedule D-1 (540) boundary.** Confirm the boundary between what
   flows via Schedule D (540) vs. Schedule D-1 (540) for TY2025 — the
   §1031 narrowing post-TCJA changed this, and the oracle currently
   assumes D-1 is caller's responsibility.

### Citation lineage

- FTB Schedule D (540) instructions (2025 — pending release; v0 cites
  2024 with `VERIFY` markers).
- FTB Pub 1001 (Supplemental Guidelines to California Adjustments).
- R&TC §§17024.5 (conformity date), 17158.3 (OZ non-conformity), 18031
  (wash sales), 18152 (§1202 non-conformity).
- IRC §§1091, 1202, 1400Z-2, 453, 1031.

### Integration with CA 540 oracle

The consumer is `ca_540_reference.compute_ca_540` on the
`oracle/ca-540-reference` branch. It reads
`schd_540_ca_fed_delta_to_sch_ca_line_7` and populates
`SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions` (when
the delta is negative — CA recognizes less gain) or the corresponding
col-C additions field (when positive). Field-name stability across the
two oracles is load-bearing.
