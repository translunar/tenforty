# tests/oracles — independent reference implementations

This directory holds **test-only** reference implementations used as cross-check
oracles for production math. Modules here are **not** imported from the
`tenforty/` package; they exist so the production code has something
independent to compare against.

The principle: the federal 1040 pipeline is already cross-checked against the
incometaxspreadsheet.com XLS oracle. For tax flows that aren't modeled in that
oracle (K-1 internals, Schedule E Part II row-level fan-out, QBI, passive-
activity rules, state-specific logic, pass-through entity returns), we need a
second oracle — one we can read, review, and update from primary IRS / FTB
source material. This directory is where those live.

## Current oracles (this branch)

| Module | Covers | Status |
|---|---|---|
| `f1120s_reference.py` | Federal Form 1120-S (main form lines 1-27) + Schedule B + Schedule K + Schedule K-1 per-shareholder — TY2025 | v1 scaffold implemented (2026-04-16). |

Planned / elsewhere:

- `ca_540_reference.py` — CA Form 540 + Schedule CA (540). Lives on branch
  `oracle/ca-540-reference`.
- `k1_reference.py` — Schedule K-1 (1120-S / 1065 / 1041) pass-through flows.
  Lives on branch `oracle/k1-reference`. The 1120-S oracle's K-1 output is
  designed to be consumable by this module (field names match the
  `ScheduleK1Like` protocol).

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
   comment naming the IRS instruction paragraph.
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

## f1120s_reference.py — Form 1120-S oracle

### Scope

**IN scope (v1):**

- Main form, Income section: lines 1a, 1b, 1c, 2, 3, 4, 5, 6.
- Main form, Deductions section: lines 7 through 19 individually, plus
  line 20 total.
- Main form, Ordinary Business Income: line 21.
- Main form, Tax and Payments: lines 22a, 22b, 22c, 23a, 23b, 23c, 23d,
  24, 25, 26, 27. Entity-level tax computation (§1375, §1374, §453A
  interest) is NOT internal to the oracle — caller supplies the
  pre-computed amounts on TaxAndPayments; oracle rolls them forward to
  total tax / amount owed / overpayment.
- Schedule B: pass-through of Yes/No questions and informational fields
  that gate downstream behavior (accounting method, business activity,
  ownership-disclosure flags, $250k small-entity gate, §163(j) flag,
  §448(c) three-year average receipts).
- Schedule K: entity-level totals for lines 1, 2, 3, 4, 5a, 5b, 6, 7,
  8a, and 17V. Line 1 (OBI) flows from main form line 21.
- Schedule K-1: per-shareholder pro-rata allocation of Schedule K items,
  by constant ownership percentage. Produces two parallel output shapes:
  (a) literal K-1 box-numbered values for form emission, and (b) a
  `ScheduleK1Like`-compatible dict for chaining into the K-1 oracle's
  `k1_to_expected_outputs`.

**OUT of scope (v1 — oracle raises or caller supplies):**

| Item | Disposition |
|---|---|
| Excess Net Passive Income Tax (§1375) | Caller provides amount on TaxAndPayments.excess_net_passive_income_or_lifo_tax |
| LIFO recapture tax (§1363(d)) | Same field; caller aggregates if both apply |
| Built-in Gains Tax (§1374) | Caller provides amount on TaxAndPayments.built_in_gains_tax |
| §453/§453A interest on deferred tax | Caller includes in same field or out of scope |
| Form 1125-A (COGS detail) | Caller provides line 2 aggregate |
| Form 1125-E (officer compensation detail) | Caller provides line 7 aggregate |
| Mid-year ownership changes / §1377(a)(2) closing-of-the-books | Oracle rejects non-constant ownership via `_gate_scope` |
| Schedule L (balance sheet) | Out of scope — informational only |
| Schedule M-1 (book/tax reconciliation) | Out of scope — informational only |
| Schedule M-2 (AAA / OAA / PTEP) | Out of scope — tracked outside oracle |
| Schedule M-3 (required when total assets ≥ $10M) | Out of scope |
| §163(j) business interest limit | Flag captured on Schedule B; not applied internally |
| §1231 gain/loss on K-1 (box 9) | Scope-out — oracle's K-1 `other_income` field is zero by construction |
| §179 deduction on K-1 (box 11) | Scope-out — same reason |
| K-1 credits (boxes 13A-13W, etc.) | Scope-out |
| Foreign-activity items | Scope-out |
| Collectibles gain (28%) / unrecaptured §1250 | Scope-out |

### Output contract

`compute_f1120s(inp: F1120SInput) -> dict` returns a flat dict with three
key families:

- `f1120s_line_<N>_<semantic>` — main form lines 1a through 27.
- `sch_b_line_<N>_<semantic>` — Schedule B answers (pass-through).
- `sch_k_line_<N>_<semantic>` — Schedule K entity-level totals.
- `sch_k1_<shareholder_id>_<field>` — per-shareholder K-1 values. The
  special key `sch_k1_<shareholder_id>_schedule_k1_like` holds a nested
  dict matching `ScheduleK1Like` exactly, for roundtrip integration.

### Ambiguities / verification queue

Items flagged for `ca-research` (IRS lookups) before the oracle moves
beyond v1 scaffold. None block v1 arithmetic, but some affect line
numbering and output-key stability:

1. **2025 line numbering on main-form Tax and Payments section.**
   The oracle currently uses `line_22a` / `22b` / `22c` / `23a` / `23b` /
   `23c` / `23d` / `24` / `25` / `26` / `27`, matching the 2023-2024
   structure. If IRS has renumbered for 2025 (e.g., if `25/26/27`
   become `24/25/26` or similar), output-dict keys will need renaming
   before production binds to them.

2. **2025 Schedule B line numbering.** The oracle currently uses
   `line_1` (accounting method), `line_2a/2b` (business activity / product),
   `line_3` (ownership in other entity), `line_4` (partnership/LLC ≥ 20%),
   `line_9` (small-entity $250k gate), `line_12` (§163(j) flag). These
   match 2023-2024; 2025 may differ.

3. **§448(c) gross receipts threshold for 2025.** Currently captured on
   Schedule B as a free-float input; no constant hard-coded inside the
   oracle. If production wants to derive the §163(j) flag internally,
   the threshold (inflation-adjusted annually — $30M in 2024) needs
   verification.

### Citation lineage

- IRS 2025 Form 1120-S and instructions (when released — oracle
  currently cites 2024 structure with `VERIFY` markers where 2025
  deviates).
- IRC §§1366, 1375, 1374, 1377, 453A, 163(j), 448(c).
- Treas. Reg. §1.1377-1(a)(2)(ii) — closing-of-the-books election for
  mid-year ownership changes (referenced as scope-out only).

### Integration with K-1 oracle

The per-shareholder `ScheduleK1Like` output dict is designed to be
passed directly into `tests.oracles.k1_reference.k1_to_expected_outputs`.
Roundtrip integration test is pending: requires merging in the
`oracle/k1-reference` branch (currently at commit e88f575) so the K-1
module is importable from this worktree.

Fields match the K-1 oracle's `ScheduleK1Like` protocol:

- `entity_name`, `entity_ein` — from 1120-S header.
- `entity_type` — fixed to `"s_corp"` by this oracle.
- `material_participation` — passed through from the per-shareholder
  input (not an entity-level determination).
- `ordinary_business_income`, `net_rental_real_estate`,
  `other_net_rental`, `interest_income`, `ordinary_dividends`,
  `qualified_dividends`, `royalties`, `net_short_term_capital_gain`,
  `net_long_term_capital_gain`, `qbi_amount` — all pro-rata allocations
  of the corresponding Schedule K entity totals.
- `other_income` — zero by construction (scope-out gate).
- `prior_year_passive_loss_carryforward` — zero by construction; the
  1120-S oracle does not know a shareholder's personal tax history. The
  downstream consumer overrides this field with the shareholder's
  actual carryforward before feeding into `k1_to_expected_outputs`.
