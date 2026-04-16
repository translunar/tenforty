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
| `sch_d_540_reference.py` | CA FTB Schedule D (540) — federal↔CA capital-gain delta for Sch CA (540) Part I line 7 — TY2025 | v1: lines 4-12 implemented; 6-category FTB delta catalog covered. |

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
several named non-conformity deltas enumerated by the FTB. This oracle
implements lines 4 through 12 of Schedule D (540) directly and exposes a
single aggregate number — the signed CA-minus-federal capital-gain delta —
that the CA 540 oracle places on Schedule CA (540) Part I Section A line 7a
column B (subtractions) or column C (additions) depending on sign.

Note: CA does not bifurcate short-term and long-term capital gains; all
dispositions flow together on Sch D (540) at ordinary CA rates.

### Scope (v1 — FTB-enumerated delta catalog)

Per the FTB 2025 Sch D (540) instructions, the enumerated nonconformity
items are:

1. **IRC §1045 / §1202 — Qualified Small Business Stock.** CA does not
   conform to either the rollover deferral (§1045) or the gain exclusion
   (§1202). R&TC §18152.
2. **IRC §1400Z-1 / §1400Z-2 — Qualified Opportunity Zone Funds.** CA does
   not conform to either the gain deferral or the exclusion on reinvestment
   in a QOF. R&TC §17158.3.
3. **IRC §1221 — Patents, inventions, models, designs, secret formulas.**
   TCJA removed creator-held examples from the federal capital-asset
   definition (so federal treats the gain as ordinary). CA did not conform
   — these remain capital assets for CA creator-taxpayers.
4. **Basis differences (catch-all).** FTB framing per the 2025 instructions:
   compute the original basis under California law in effect when acquired,
   then adjust under CA law during ownership. This bucket absorbs bonus
   depreciation nonconformity (§168(k)), the much lower CA §179 cap,
   ACRS/MACRS history differences, and ISO AMT basis tracking.

### Per-transaction input shape

Callers fold all of the above into the signed `Transaction.ca_gain_or_loss`
amount on a per-disposition basis. The oracle does not recompute basis,
federal exclusion percentages, or §1202 acquisition-date fractions — the
caller determines the CA-recognized number and the oracle aggregates it.
The federal aggregate is supplied separately as
`SchD540Input.federal_1040_line_7a_capital_gain`, matching how the form
instructs the taxpayer to transcribe 1040 line 7a onto Sch D (540) line 10.

### Not in the delta catalog (conforming / covered via basis)

Per ca-research 2026-04-16 consolidated answer:

- **IRC §1091 wash sales.** CA conforms; no primary delta source. Deltas
  can arise cascading from item 4 (basis differences).
- **IRC §453 installment sales.** CA conforms to the method; reporting is
  on FTB 3805E (analog of Form 6252). Deltas folded into item 4.

### OUT of scope (v1 — caller supplies pre-aggregated or raise)

| Item | Disposition |
|---|---|
| Schedule D-1 (540) like-kind §1031 / §1231 recapture | Scope-out; caller supplies the delta pre-aggregated |
| Passive-activity-loss interaction on cap-gain dispositions | Scope-out; handled on Sch P (540), not here |
| Collectibles (28%) / unrecaptured §1250 CA treatment | Scope-out (v1); CA treats as ordinary anyway |
| Mark-to-market §475(f) trader elections | Scope-out |
| PFIC gains (Form 8621) | Scope-out — federal-only complexity |
| IRC §1062 qualified-farmland sale (new TY2025, P.L. 119-21) | Scope-out pending FTB 2026 conformity guidance (SB 711 etc.) |
| IRC §139L rural lender interest exclusion (new TY2025, P.L. 119-21) | Scope-out pending FTB 2026 conformity guidance |

### Output contract

`compute_sch_d_540(inp: SchD540Input) -> dict` returns a flat dict of:

- `schd_540_line_<N>_<semantic>` — mirrors the 2025 form face for lines
  4-12 (intermediate values).
- `schd_540_ca_fed_delta_to_sch_ca_line_7` — signed float. Positive = CA
  recognizes MORE gain than federal (Sch CA col C addition). Negative =
  CA recognizes LESS gain than federal (Sch CA col B subtraction). Zero
  = identity case. Consumer takes the absolute value and routes by sign.

This is the sole stable integration point with the CA 540 oracle. Line-
level keys are stable but may surface additional intermediate values as
the oracle grows.

### Citation lineage

- FTB 2025 Schedule D (540) form + instructions.
- FTB Pub 1001 (Supplemental Guidelines to California Adjustments).
- R&TC §§17024.5 (conformity date), 17158.3 (OZ non-conformity),
  18152 (§1202 non-conformity).
- IRC §§1045, 1091, 1202, 1221, 1400Z-1, 1400Z-2, 453, 1031, 1211(b).

### Integration with CA 540 oracle

The consumer is `ca_540_reference.compute_ca_540` on the
`oracle/ca-540-reference` branch. It reads
`schd_540_ca_fed_delta_to_sch_ca_line_7` and populates
`SchCAPartIAdjustments.line_7_col_b_capital_gain_subtractions` (when
the delta is negative — CA recognizes less gain) or the corresponding
col-C additions field (when positive). Field-name stability across the
two oracles is load-bearing.
