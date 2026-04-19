# tests/oracles — independent reference implementations

This directory holds **test-only** reference implementations used as cross-check
oracles for production math. Modules here are **not** imported from the
`tenforty/` package; they exist so the production code has something
independent to compare against.

## Current oracles (this branch)

| Module | Covers | Status |
|---|---|---|
| `f100s_reference.py` | CA FTB Form 100S — S Corporation Franchise or Income Tax Return — TY2025 | v0: scaffold. Structure verified via ca-research 2026-04-19 consolidated answer; TDD in progress. |

## Design rules (shared across oracles)

1. **No imports from `tenforty/`.**
2. **`float` matches production.** Sub-cent precision loss accepted; harness
   rounds at compare time.
3. **No rounding inside the oracle.**
4. **Every rule cites its source** via inline `SOURCE:` comment.
5. **Out-of-scope is explicit.** Either `_gate_scope` raises, or the field is
   explicitly documented as caller-supplied.
6. **Document divergences, don't smooth them over.**
7. **Iron laws 1/2/3/4** (no PII in fixtures, raise on scope-outs,
   `unittest.TestCase`, imports at top) apply.
8. **No VERIFY markers in v1.** Pre-clear structural questions with
   ca-research before coding.

---

## f100s_reference.py — CA Form 100S oracle

### Purpose

California S corporations file Form 100S to compute entity-level franchise or
income tax and report shareholder pass-through items on Schedule K / K-1.
This oracle consumes the same inputs and produces an independent signed tax
amount plus per-shareholder K-1 allocations, so divergences are caught before
they reach a filed return.

### Key structural facts (ca-research 2026-04-19, verbatim form face)

- **Two-layer design:** Schedule F (Side 4) computes trade/business OBI
  (parallels federal 1120-S page 1). Main form (Side 1-2) applies state
  adjustments to Schedule F OBI → net income for tax purposes → tax.
- **Schedule F line 19 ≠ federal 1120-S line 19.** CA Schedule F line 19
  is travel/entertainment. Federal line 19 is §179D. CA has NO §179D named
  line — it goes on Schedule F line 20 "Other deductions."
- **Tax = greater of 1.5% × net income OR $800 minimum franchise tax.**
  First-year corporations exempt from the $800 floor (R&TC §23153(f)).
  Financial S-corps use 3.5% (R&TC §23186).
- **Line 26 credit floor:** After credits, tax cannot go below minimum
  franchise tax + QSub annual taxes.
- **§199A QBI does NOT exist on CA.** No Schedule K line, no K-1 box.
- **§179 CA cap: $25,000** (vs federal ~$1.22M). Phase-out starts $200,000.
- **§168(k) bonus depreciation: 0% on CA.** CA does not conform.
- **State/local taxes NOT deductible:** Added back on main form line 2.

### Schedule F — Trade or Business Income (Side 4, lines 1-22)

| Line | Semantic |
|---|---|
| 1a | Gross receipts or sales |
| 1b | Less returns and allowances |
| 1c | Balance (1a − 1b) |
| 2 | Cost of goods sold (from Schedule V line 8) |
| 3 | Gross profit (1c − 2) |
| 4 | Net gain (loss) — attach schedule |
| 5 | Other income (loss) — attach schedule |
| 6 | Total income (loss) = 3 + 4 + 5 |
| 7 | Compensation of officers — attach schedule |
| 8 | Salaries and wages |
| 9 | Repairs and maintenance |
| 10 | Bad debts |
| 11 | Rents |
| 12 | Taxes |
| 13 | Interest |
| 14a | Depreciation (attach Form 3885A) |
| 14b | Less depreciation reported elsewhere |
| 14c | Balance (14a − 14b) |
| 15 | Depletion |
| 16 | Advertising |
| 17 | Pension, profit-sharing |
| 18 | Employee benefit programs |
| 19a | Travel — total |
| 19b | Travel — deductible amount (used in computation) |
| 20 | Other deductions — attach statement |
| 21 | Total deductions (7 through 20) |
| 22 | OBI (line 6 − line 21) → main form Side 1 line 1 |

### Main Form Side 1-2 — State Adjustments + Tax (lines 1-45)

**State Adjustments — Additions (lines 1-8):**

| Line | Semantic |
|---|---|
| 1 | OBI from Schedule F line 22 |
| 2 | Foreign/domestic/CA tax deducted (add back) |
| 3 | Interest on government obligations |
| 4 | Net capital gain from Schedule D (100S) |
| 5 | Depreciation and amortization adjustments |
| 6 | Portfolio income |
| 7 | Other additions — attach schedule(s) |
| 8 | Total additions (1 through 7) |

**State Adjustments — Deductions (lines 9-13):**

| Line | Semantic |
|---|---|
| 9 | Dividends received deduction (Schedule H) |
| 10 | Water's-edge dividend deduction (Schedule H) |
| 11 | Charitable contributions |
| 12 | Other deductions — attach schedule(s) |
| 13 | Total deductions (9 through 12) |

**Net Income (lines 14-20):**

| Line | Semantic |
|---|---|
| 14 | Net income (loss) after state adjustments = line 8 − line 13 |
| 15 | Net income (loss) for state purposes (= line 14 if no apportionment) |
| 16 | R&TC §23802(e) deduction |
| 17 | NOL deduction |
| 18 | EZ/TTA/LAMBRA NOL carryover deduction |
| 19 | Disaster loss deduction |
| 20 | Net income for tax purposes = line 15 − (16 + 17 + 18 + 19) |

**Taxes (lines 21-30):**

| Line | Semantic |
|---|---|
| 21 | Tax: rate% × line 20 (at least min franchise tax if applicable) |
| 22-23 | Credit name / code / amount (2 slots) |
| 24 | Additional credits |
| 25 | Total credits (22 + 23 + 24) |
| 26 | Balance = line 21 − line 25 (floor: min franchise tax + QSub taxes) |
| 27 | Tax from Schedule D (100S) — built-in gains |
| 28 | Excess net passive income tax |
| 29 | Pass-through entity elective tax |
| 30 | Total tax = 26 + 27 + 28 + 29 |

**Payments (lines 31-36):**

| Line | Semantic |
|---|---|
| 31 | Overpayment from prior year allowed as credit |
| 32 | Estimated tax / QSub payments |
| 33 | Withholding (Forms 592-B / 593) |
| 34 | Amount paid with extension |
| 35 | Amounts paid for PTE elective tax |
| 36 | Total payments (31 through 35) |

**Use Tax / Balance (lines 37-45):**

| Line | Semantic |
|---|---|
| 37 | Use tax |
| 38 | Payments balance (if line 36 > line 37) |
| 39 | Use tax balance (if line 37 > line 36) |
| 40 | Franchise or income tax due (if line 30 > line 38) |
| 41 | Overpayment (if line 38 > line 30) |
| 42 | Amount credited to next year estimated tax |
| 43 | Refund (line 41 − line 42) |
| 44a | Penalties and interest |
| 44b | Estimate penalty exception check |
| 45 | Total amount due |

### Schedule K (100S) — Shareholder Pro-Rata Share Items

4-column format: (a) pro-rata share items, (b) federal K amount, (c) CA
adjustment, (d) CA-law total.

| Line | Semantic |
|---|---|
| 1 | OBI |
| 2 | Net rental real estate income (loss) |
| 3a/b/c | Other gross rental income / expenses / net |
| 4 | Interest income |
| 5 | Dividends |
| 6 | Royalties |
| 7 | Net short-term capital gain (loss) |
| 8 | Net long-term capital gain (loss) |
| 9 | Net IRC §1231 gain (loss) |
| 10a/b | Other portfolio income (loss) / Other income (loss) |
| 11 | IRC §179 expense deduction |
| 12a-f | Deductions: cash charitable, noncash charitable, investment interest, §59(e)(2), portfolio, other |
| 13a-d | Credits: low-income housing, rental RE, other rental, other |
| 14 | Total withholding allocated to shareholders |
| 15a-f | AMT items |
| 16a-d | Shareholder basis items: tax-exempt interest, other tax-exempt, nondeductible expenses, property distributions |
| 17a-d | Other information: investment income, investment expenses, dividend distributions from E&P, other |
| 18a-e | Other state taxes |
| 19 | Reconciliation income (loss) |

**No §199A QBI line** — federal K line 15 (§199A) has no CA equivalent.

### Schedule K-1 (100S)

Lines 1-18 mirror Schedule K. Additional:
- Column (e): California source amounts and credits (multi-state)
- Line 16e: Repayment of loans from shareholders (CA-specific)
- Table 1: Nonbusiness income from intangibles
- Table 2: Shareholder's pro-rata share of business income and factors

### OUT of scope (v1 — caller supplies pre-aggregated or raise)

| Item | Disposition |
|---|---|
| Schedule R (apportionment) | Scope-out; oracle assumes CA-only S-corp (line 15 = line 14). |
| Schedule D (100S) built-in gains tax | Caller-supplied (line 27). |
| Excess net passive income tax | Caller-supplied (line 28). |
| PTE elective tax computation | Caller-supplied (line 29). |
| Schedule L, M-1, M-2 | Informational; scope-out. |
| Schedule V (COGS detail) | Caller supplies aggregate (Schedule F line 2). |
| Use tax (lines 37-39) | Scope-out; oracle assumes use_tax = 0. |
| Financial S-corp 3.5% rate | Supported via `is_financial_s_corp` flag. |
| QSub annual taxes | Supported via `num_qsubs` input. |
| Schedule K lines 9, 13a-d, 15a-f, 18a-e | Scope-out (v1 core items only). |
| K-1 Table 1 / Table 2 | Scope-out (multi-state / nonbusiness sourcing). |

### Output contract

`compute_f100s(inp: F100SInput) -> dict` returns a flat dict of:

- `f100s_schf_line_<N>_<semantic>` — Schedule F per-line values (lines 1-22).
- `f100s_line_<N>_<semantic>` — main form per-line values (lines 1-45).
- `f100s_sch_k_line_<N>_<semantic>` — Schedule K entity-level totals.
- `f100s_sch_k1_<shareholder_id>_line_<N>_<semantic>` — per-shareholder raw K-1 box values.
- `f100s_sch_k1_<shareholder_id>_ca_540_carry_in` — convenience dict mapping to CA 540 oracle input fields.
- `f100s_tax` — entity-level tax (line 21).
- `f100s_total_tax` — total tax including additional entity taxes (line 30).

### Tax computation rules

| Parameter | Value | R&TC |
|---|---|---|
| Regular S-corp rate | 1.5% | §23802(a) |
| Financial S-corp rate | 3.5% | §23186 |
| Minimum franchise tax | $800 | §23153 |
| First-year exemption | No $800 floor | §23153(f) |
| QSub annual tax | $800 per QSub | §23802(b)(5) |
| Credit floor | Min franchise tax + QSub taxes | Form face line 26 |

### CA-federal conformity deltas (key)

| Federal provision | CA treatment | R&TC |
|---|---|---|
| §199A QBI deduction | Not adopted | By omission |
| §168(k) bonus depreciation | 0% | §17250 |
| §179 expense limit | $25,000 (phase-out at $200k) | §17255 |
| State/local tax deduction | Not deductible; added back line 2 | — |
| §1400Z-2 Opportunity Zones | Not adopted | By omission |
| §1202 QSBS exclusion | Not adopted | By omission |

### Citation lineage

- FTB 2025 Form 100S form face (TaxFormFinder mirror; FTB.ca.gov returned
  HTTP 403 to direct retrieval during research; ca-research extracted
  verbatim line text).
- FTB 2025 Form 100S instructions booklet.
- R&TC §23800-23811 (S-corp election and rules), §23802(a)/(e) (tax rate /
  deduction), §23153 (minimum franchise tax), §23153(f) (first-year
  exemption), §23186 (financial S-corp), §23802(b)(5) (QSub tax),
  §23809 (built-in gains), §23811 (excess passive income), §24416 (NOL),
  §17255 (§179 CA cap), §17250 (§168(k) non-conformity), §19900 (PTE
  elective tax), §25128.7 (single-sales-factor apportionment).
- SB 711 (2025 conformity date): §17024.5(a) / §23051.5(a).

### Integration with other oracles

- **Federal 1120-S oracle** (`f1120s_reference.py`): 100S Schedule F
  parallels federal 1120-S page 1. Many 100S inputs are federal-carry-in
  values; field names mirror where they overlap.
- **CA 540 oracle** (`ca_540_reference.py`): 100S K-1 output feeds into
  shareholder-level CA 540 return. The `ca_540_carry_in` convenience dict
  maps K-1 fields to CA 540 oracle input contract.
- **Sch P (540) oracle** (`sch_p_540_reference.py`): Schedule K line 15
  AMT items may feed into Sch P adjustments at the shareholder level.
