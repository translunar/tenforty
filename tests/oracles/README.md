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
| `sch_p_540_reference.py` | CA FTB Schedule P (540) — CA AMT + Credit Limitations for CA residents — TY2025 | v0: scaffold. Structure verified via ca-research 2026-04-16 consolidated answer; TDD in progress. |

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

## sch_p_540_reference.py — CA Schedule P (540) oracle

### Purpose

California imposes its own Alternative Minimum Tax under R&TC §17062 and a
parallel credit-limitation mechanism that caps many nonrefundable credits at
the excess of regular tax over TMT. Schedule P (540) is where residents
compute both. Production will eventually emit a full Sch P; this oracle
consumes the same inputs and produces an independent signed AMT amount plus
per-credit caps, so divergences are caught before they reach a filed return.

### Key structural facts (ca-research 2026-04-16, verbatim form face)

- **CA AMT does NOT start from federal Form 6251.** Sch P (540) line 15 is
  CA taxable income (Form 540 line 19), and every per-line adjustment
  uses CA basis — not federal. Callers must not pipe federal 6251
  numbers into this oracle.
- **No adjustments-vs-preferences split on the CA form.** Lines 1-13 are
  all aggregated into a single "Total Adjustments and Preferences"
  bucket at line 14. The federal §56/§57 distinction is collapsed here.
  (FTB 3510 separates deferral vs exclusion when computing the credit.)
- **`itemized_deduction_used` is the structural branch point.** If the
  taxpayer itemized, line 1 = 0 and lines 2-7 carry itemized add-backs.
  If not, line 1 = standard deduction (from Form 540 line 18) and the
  oracle skips to line 6. Get this branch right or everything cascades
  wrong.
- **Line 2 "fed Form 1040 line 11b" is stale form-face text.** Federal
  1040 hasn't had line 11b since TY2019; current line 11 = AGI. FTB
  has left the stale reference in place for 6 years. Treat as fed AGI.
- **Line 18 thresholds ≠ Part II exemption-phaseout thresholds.**
  Numerically similar (single = ½ MFJ, HoH = ¾ MFJ) but statutorily
  distinct: §17077 (itemized-deduction haircut) vs §17062 (AMT
  exemption). Kept as separate constants.

### Part I — AMTI build-up (lines 1-21)

| Line | Semantic |
|---|---|
| 1 | If itemized: go to 2. If std-ded: enter std ded from Form 540 line 18, skip to line 6. |
| 2 | Medical/dental: smaller of fed Sch A line 4, or 2.5% × fed AGI. |
| 3 | Personal-property + real-property taxes. |
| 4 | Certain home-mortgage interest not used to buy/build/improve. |
| 5 | Miscellaneous itemized deductions. |
| 6 | Refund of personal/real-property taxes (negative; state income-tax refund excluded). |
| 7 | Investment interest expense adjustment. |
| 8 | Post-1986 depreciation (CA basis). |
| 9 | Adjusted gain or loss (CA basis). |
| 10 | ISO / CQSO bargain-element. |
| 11 | Passive-activity adjustment (CA basis). |
| 12 | Beneficiaries of estates and trusts (Sch K-1 (541) line 12a). |
| 13 | Other adjustments/preferences sub-items a-l, summed: circulation, depletion, installment sales, intangible drilling, long-term contracts, loss limitations, mining, patron's, pollution control, R&E, tax shelter farm, related. |
| 14 | **Total Adjustments and Preferences.** Sum of lines 1-13. |
| 15 | CA taxable income (Form 540 line 19). |
| 16 | NOL deductions from Sch CA (540) Part I §B lines 9b1/9b2/9b3 col B (positive). |
| 17 | AMTI exclusion per R&TC §17062.5 small-business carve-out (negative). |
| 18 | High-AGI itemized-deduction haircut. Only if itemizing AND fed AGI > filing-status threshold. R&TC §17077. TY2025 thresholds: $252,203 single/MFS, $378,310 HoH, $504,411 MFJ/QSS. |
| 19 | Combine lines 14-18. |
| 20 | AMT-NOL deduction. **Capped at 90% of line 19** per R&TC §17276.20 — caller-supplied, oracle asserts the cap and raises on violation. |
| 21 | **AMTI** = line 19 − line 20. MFS special threshold: $479,188 (= MFS complete-phaseout point; consistency check with Part II). |

### Part II — Exemption + TMT + AMT (lines 22-26)

TY2025 exemption amounts (R&TC §17062, CA-indexed independently of IRC §55(d)):

| Filing status | Phaseout begins | Exemption |
|---|---|---|
| single, hoh | $347,808 | $92,749 |
| mfj, qss | $463,745 | $123,667 |
| mfs | $231,868 | $61,830 |

**Phaseout rate: 25%** of excess AMTI over threshold. Complete phaseout at
threshold + 4 × exemption. Self-consistency check: MFS complete-phaseout =
$231,868 + 4 × $61,830 = $479,188 (matches line-21 MFS footnote). ✓

**Line 24 TMT rate: 7.0% flat** per R&TC §17062(a). No bracket split.

**Line 26 AMT = max(0, line 24 − line 25)**. Line 25 = Form 540 line 31
(regular tax before credits). Line 26 → Form 540 line 61 (subject to
Part III Section C reduction if solar carryovers apply).

### Part III — Credit Limitations (lines 1-25)

Three sections, **processed sequentially per-line** (not aggregate):

- **Section A** — credits limited to excess tax (line 1 − line 2, floor 0):
  - Line 4: Code 162 Prison inmate labor (FTB 3507)
  - Line 5: Code 232 Child/Dep care (FTB 3506)
  - Lines 6-9: blank code/credit slots for taxpayer-filled
  - Line 10: **Code 188 Prior-year AMT credit** — computed on FTB 3510,
    applied here. See scope-out below.
- **Section B** — credits that can reduce below TMT:
  - Line 12: Code 170 Joint custody HoH
  - Line 13: Code 173 Dependent parent
  - Line 14: Code 163 Senior HoH
  - Line 15: Nonrefundable renter's credit
  - Lines 16-19: blank code/credit slots
  - Line 20: **Code 187 Other State Tax Credit (OSTC)** — statutory
    below-TMT carve-out per R&TC §18001
  - Line 21: **Code 242 PTE Elective Tax Credit** — statutory
    below-TMT carve-out per R&TC §17052.10
- **Section C** — credits that reduce AMT itself:
  - Line 23: Code 180 Solar energy carryover
  - Line 24: Code 181 Commercial solar energy carryover
  - Line 25: **Adjusted AMT** → Form 540 line 61 (overrides Part II line 26)

**Business credit aggregate cap** (footnote, R&TC §17039.3): sum of
business credits in Sections A+B column (b) cannot exceed $5M. Out of
scope for v1 unless specific business-credit inputs are supplied.

### OUT of scope (v1 — caller supplies pre-aggregated or raise)

| Item | Disposition |
|---|---|
| AMT-NOL (line 20) | Attested; caller supplies post-90%-cap value. Oracle asserts `amt_nol_deduction ≤ 0.90 × line_19` and raises. |
| Sch P (540NR) non/part-year residents | Separate oracle, future work. |
| FTB 3510 year-over-year AMT-credit computation | Separate oracle; Sch P only applies the credit at Part III line 10. |
| §59(e) optional write-offs | Scope-out. |
| Foreign Tax Credit AMT adjustment | Scope-out. |
| Farming/fishing income averaging | Scope-out. |
| Business credit $5M aggregate cap (SB 167) | Scope-out unless business credits supplied. |

### Output contract

`compute_sch_p_540(inp: SchP540Input) -> dict` returns a flat dict of:

- `schp_540_line_<N>_<semantic>` — per-line intermediate values mirroring
  the TY2025 form face (lines 1-21 Part I, 22-26 Part II, Part III
  line numbers 1-25 with section prefix).
- `schp_540_amti` — line 21 value.
- `schp_540_tentative_minimum_tax` — line 24 value.
- `schp_540_amt_due` — AMT amount flowing to Form 540 line 61 (line 25
  of Part III if solar carryovers, else line 26 of Part II). Zero when
  regular tax ≥ TMT.
- `schp_540_credit_caps` — per-credit dict: `{credit_code: {uncapped, capped}}`.
- `schp_540_amt_credit_carryforward_added_this_year` — current-year
  contribution to next year's AMT credit carryforward (needed by future
  FTB 3510 oracle).

Stable integration points: `schp_540_amt_due` (scalar to Form 540 line 61)
and `schp_540_credit_caps` (consumed by CA 540 credit-ordering logic).

### Citation lineage

- FTB 2025 Sch P (540) form face + instructions (PDF; FTB.ca.gov returned
  HTTP 403 to direct retrieval during research; ca-research extracted
  via a cached mirror with verbatim line text).
- R&TC §17062 (CA AMT imposition), §17062.5 (small-business exclusion),
  §17052.5 (solar-credit AMT-reduction allowance), §17052.10 (PTE credit
  below-TMT), §17077 (high-AGI itemized haircut), §17276.20 (AMT-NOL 90%
  cap), §17039 (credit-ordering), §17039.3 (business-credit $5M cap),
  §18001 (OSTC below-TMT).
- FTB 3510 instructions (TY2025) for the Sch P ↔ 3510 compute/apply split.
- IRC §§55, 56, 57, 58, 59 (federal AMT reference only).

### Integration with CA 540 oracle

Consumer: `ca_540_reference.compute_ca_540` on branch
`oracle/ca-540-reference`. Currently `ScopeOut.amt_preferences_present`
scope-gates AMT. Once this oracle ships:

1. CA 540 oracle accepts Sch P input (AMTI adjustment per-line amounts,
   AMT-NOL post-cap, prior-year AMT credit available).
2. CA 540 oracle calls `compute_sch_p_540(...)` and populates Form 540
   line 61 from `schp_540_amt_due`.
3. CA 540 oracle feeds `schp_540_credit_caps` into its credit-ordering
   logic so nonrefundable credits respect the Part III caps.

Inputs this oracle consumes (mirror of CA 540 types):

- `filing_status: Literal["single", "mfj", "mfs", "hoh", "qss"]` —
  matches `ca_540_reference.FilingStatus`.
- `federal_agi: float` (for line 2 + line 18 gate).
- `ca_taxable_income: float` (Form 540 line 19 → Sch P line 15).
- `ca_regular_tax_before_credits: float` (Form 540 line 31 → Sch P line 25).
- `total_tax_before_credits: float` (Form 540 line 35 → Sch P Part III
  line 1).
- `itemized_deduction_used: bool`.
- `standard_deduction_amount: float` (Form 540 line 18 if not itemizing).
- `ca_nol_deductions_9b: float` (Sch CA (540) Part I §B 9b1+9b2+9b3 col B).
- `amti_exclusion_amount: float` (§17062.5 small-business exclusion).
- `amt_nol_deduction_post_90pct_cap: float` (attested; oracle guards cap).
- `prior_year_amt_credit_available: float` (attested from prior FTB 3510).
- Per-line Part I adjustment inputs (lines 2-13 sub-items).
- Per-credit Part III amounts with credit codes.
