# tests/oracles — independent reference implementations

This directory holds **test-only** reference implementations used as cross-check
oracles for production math. Modules here are **not** imported from the
`tenforty/` package; they exist so the production code has something
independent to compare against.

The principle: the federal 1040 pipeline is already cross-checked against the
incometaxspreadsheet.com XLS oracle. For tax flows that aren't modeled in that
oracle (K-1 internals, Sch E Part II row-level fan-out, QBI, passive-activity
rules, state-specific logic), we need a second oracle — one we can read,
review, and update from primary IRS / state source material. This directory is
where those live.

## Current oracles

| Module | Covers | Status |
|---|---|---|
| `k1_reference.py` | Schedule K-1 (1120-S, 1065, 1041) → Sch E Part II, Sch B, Sch D, QBI (Form 8995), passive flag (Form 8582) | Implemented against team-lead's `ScheduleK1` schema (2026-04-15). |

Planned (future PRs, not part of this branch):

- `ca_540_oracle.py` — wraps OpenTaxSolver as a subprocess for CA 540 / Schedule CA cross-check (see closed #5 and the CA 540 planning issue).

## Design rules

1. **No imports from `tenforty/`.** If the oracle reused production logic, it
   wouldn't be independent and bugs in production would replicate into the
   oracle. The only exception is importing dataclasses like `ScheduleK1` that
   are schema-only (no behavior).
2. **`float` matches production.** Team-lead contract uses `float`; oracle
   follows suit. Sub-cent precision loss is accepted; comparison tests round
   to the nearest cent. If precision issues surface, revisit.
3. **No rounding inside the oracle.** Rounding is production's responsibility;
   the oracle reports unrounded arithmetic so sub-dollar divergences surface
   before IRS-style rounding hides them.
4. **Every rule cites its source.** Each calculation carries a `SOURCE:`
   comment naming the IRS instruction or reg paragraph. Annual refresh =
   diffing those citations against the following year's instructions.
5. **Out-of-scope is explicit.** Anywhere production might have a more complex
   path, the oracle either errors loudly or documents the limitation inline
   AND in this README (below).
6. **Document divergences, don't smooth them over.** If a second oracle (OTS,
   TaxVisor, etc.) disagrees with this module's reading of the instructions,
   flag the divergence here and let the team-lead adjudicate. Silent
   reconciliation defeats the independence principle.

## K-1 oracle scope

### In scope

- Schedule K-1 (Form 1120-S) boxes 1–8a, 5a/5b, 4, 17V (QBI)
- Schedule K-1 (Form 1065) boxes 1–9a, 5, 6a/6b, 20Z (QBI), 14A (self-employment)
- Schedule K-1 (Form 1041) boxes 1, 2a/2b, 3, 4a, 5, 6–8, 14I (QBI)
- Schedule E Part II column routing (g/h/i/j/k) on line 28
- Schedule B interest + ordinary dividends fan-out
- Schedule D short/long-term cap gain fan-out
- Form 8995 simple QBI (taxpayer below the income threshold)
- Form 8582 $25,000 special allowance for active-participation rental RE
- Passive/nonpassive classification (assumes production collects
  `material_participation` as a boolean on the scenario — no material-
  participation test reproduction)

### Out of scope for v1 (documented, deliberate)

- **28% collectibles gain** (1120-S box 8b / 1065 box 9b / 1041 box 4b).
  Feeds the 28% Rate Gain Worksheet, not a simple Schedule D line.
- **Unrecaptured §1250 gain** (1120-S box 8c / 1065 box 9c / 1041 box 4c).
  Feeds the Unrecaptured §1250 Gain Worksheet.
- **§1231 gain/loss** (1120-S box 9; 1065 box 10). Flows to Form 4797
  before reaching Schedule D/E. Production may or may not model 4797; oracle
  excludes.
- **Real estate professional exemption** (§469(c)(7)). Oracle accepts a
  caller-supplied flag; does not reproduce the 750-hour + >50% test.
- **Prior-year unallowed passive losses.** Form 8582 carries these on Part
  VIII column (c); oracle computes current-year limitation only. Production
  must track carryforwards separately.
- **SSTB limitation and wage/UBIA phase-in** above the QBI threshold.
  That's Form 8995-A territory; simple Form 8995 path assumes taxable income
  ≤ threshold.
- **QBI loss carryover.** Negative QBI carries forward (Form 8995 line 3);
  oracle computes current-year contribution only.
- **Grouping elections** (Rev. Proc. 2010-13, §469).
- **Self-employment tax** (Schedule SE from 1065 box 14A). In scope to flag
  the contribution; SE tax computation itself is not an oracle goal.
- **Excess business loss** (§461(l)) — applied after all other limitations;
  out of scope.
- **Basis and at-risk limitations.** Production must track shareholder /
  partner basis; oracle assumes amounts flowing in are already within basis.
  Per 2025 Instructions for Schedule K-1 (Form 1120-S): limitations are
  applied in order: basis → at-risk → passive → excess business loss →
  specific-item limits.
- **International K-1 items** (box 14 on 1120-S, box 16 on 1065, box 12 on
  1041). Form 1118 / 1116 territory.
- **AMT preferences** (box 15 on 1120-S, box 17 on 1065, box 12 on 1041).
  Form 6251.

## Citation lineage

Every rule in `k1_reference.py` cites one of:

- **2025 Instructions for Schedule K-1 (Form 1120-S)** —
  https://www.irs.gov/instructions/i1120ssk
- **2025 Partner's Instructions for Schedule K-1 (Form 1065)** —
  https://www.irs.gov/instructions/i1065sk1
- **2025 Beneficiary's Instructions for Schedule K-1 (Form 1041)** —
  https://www.irs.gov/instructions/i1041sk1
- **2025 Instructions for Schedule E (Form 1040)** —
  https://www.irs.gov/instructions/i1040se
- **2025 Instructions for Form 8995** —
  https://www.irs.gov/instructions/i8995
  Draft PDF: https://www.irs.gov/pub/irs-dft/i8995--dft.pdf
- **2025 Instructions for Form 8582** —
  https://www.irs.gov/instructions/i8582
- **IRC §469** (passive activity rules) and **§199A** (QBI).

## Second-oracle check: OpenTaxSolver (OTS)

Team-lead asked me to add OTS as a belt-and-suspenders second cross-check if
its coverage is meaningful for K-1 flows. **Verdict: not useful for this
scope.**

OTS's federal 1040 solver (`taxsolve_US_1040_YYYY.c`) treats K-1 pass-throughs
as **user-supplied pre-aggregated totals**:

- `S1_5` — a single scalar for "Rental real estate, royalties, partnerships,
  S corps" → Schedule 1 line 5.
- `D5` — a single scalar for K-1 short-term cap gains → Schedule D line 5.
- `D12` — a single scalar for K-1 long-term cap gains → Schedule D line 12.

There is no Schedule E Part II row-level fan-out, no passive/nonpassive
classification, no Form 8582, and no Form 8995 in OTS's model. The owner of
the return is expected to have done that math before feeding the number in.

So OTS cannot cross-check us on what this oracle actually covers. It can only
cross-check the *downstream* federal aggregate, which the federal XLS oracle
already covers. **OTS is not added as a second K-1 oracle.**

If a second oracle becomes important, candidates to re-investigate:

- **TaxVisor** — but same likely limitation: user-supplied K-1 totals, no
  Part II fan-out.
- **PolicyEngine `us` model** — has more structure; worth a look.
- **Hand-worked IRS example** — the 2025 Form 8582 instructions include a
  filled example; codify it as a fixture.

## Known ambiguities / open questions

1. **2025 QBI threshold (`QBI_SIMPLE_THRESHOLD_2025`).** IRS draft
   instructions for 2025 Form 8995 give `$197,300` (single) / `$394,600`
   (MFJ). Those are the *same* numbers published for 2023, which is
   implausible (inflation adjustments usually make them rise). Team-lead's
   brief stated `$241,950` (single) — that was the 2024 single threshold.
   **Action required:** CPA confirm the correct 2025 figures before any code
   consuming these constants merges. Marked `VERIFY` in source.

2. **MFS QBI threshold.** IRS instructions don't always spell out MFS
   separately; typically it's half of MFJ, but confirm against the 2025
   published values.

3. **1041 beneficiary "distributable" vs "distributed" flows.** Box 6–8 on a
   1041 K-1 report distributed amounts (§662 DNI rules), not entity-level
   income. The oracle treats box 6 as "ordinary business income equivalent"
   for fan-out, but nuances around simple vs complex trusts, §643 separate-
   share rules, and fiscal-year trust timing are not modeled. Probably fine
   for v1 given typical beneficiary use cases but flagging.

4. **Guaranteed payments on a 1065 K-1** (box 4a/4b/4c). These are NOT in
   box 1 (the instructions split them out) and flow to Schedule E as
   nonpassive *and* to Schedule SE for general partners. The oracle's
   current shape computes them separately from box 1; double-counting risk
   needs a test case.

5. **1065 box 14 self-employment earnings.** General partners owe SE tax on
   box 14A; limited partners generally do not (with exceptions). Production
   must carry the partner kind; oracle does not attempt to re-derive.

6. **Royalties — 1120-S box 6 vs 1041 box 5.** 1120-S box 6 is pure
   royalties to Schedule E line 4. 1041 box 5 is "other portfolio and
   nonbusiness income" which includes royalties plus annuities plus IRD. The
   normalized `ScheduleK1.royalties` field masks this variance. If a 1041
   K-1 reports box 5 income that is *not* royalties (e.g. an annuity or
   IRD), production must either (a) place it in a different normalized
   field or (b) reject, because the oracle will route it to Schedule E
   line 4 as if it were royalties. Flag to team-lead.

7. **Passive-flag semantics.** Team-lead brief describes the flag as "True
   if losses go to 8582". The implementation takes the broader reading —
   True whenever 8582 is in play for this activity, including positive
   passive income that could release prior-year suspended losses. If
   production's reading is narrower (strictly current-year loss), the
   oracle will report more `True`s than production and the comparison
   test needs to account. Documented inline in `passive_flag()`.

8. **Pre-8582 vs post-8582 Sch E Part II amounts.** The oracle reports the
   *raw* pre-limitation K-1 amounts in `sch_e_part_ii_row`. Form 8582
   aggregates across ALL passive activities and computes the allowable
   current-year loss, which is what actually lands on Schedule E line 28
   column (g). The oracle cannot compute the limitation without the full
   portfolio and MAGI. Production and test harness must agree on whether
   the Sch E values are pre- or post-limitation; this oracle picks pre-.

9. **`qualified_dividends` is a subset of `ordinary_dividends`**, not
   additive. The oracle deliberately does NOT add qualified to Schedule B
   — qualified affects the tax calculation via the Qualified Dividends
   and Capital Gain Tax Worksheet. Production must handle the same way.

## How to add to this directory

1. New module `tests/oracles/<form>_reference.py`.
2. Pure functions returning `Decimal` (or frozen dataclasses of `Decimal`).
3. Every numeric constant and every rule cites its IRS publication / line.
4. Update this README's "Current oracles" table and add a scope section.
5. Add a comparison test in `tests/` that fails loudly if the production
   value diverges. Follow the fail-loud-not-skip pattern established in
   the CA 540 plan: if the oracle can't run (e.g. a subprocess dep is
   missing), the test **fails**, not skips.

## How this oracle is consumed

Once the `ScheduleK1` schema lands, a companion test (not in this branch)
will look roughly like:

```python
from tests.oracles.k1_reference import (
    schedule_e_part_ii_row,
    qbi_contribution,
    passive_flag,
)

class TestK1OracleParity(unittest.TestCase):
    def test_schedule_e_placement_matches_oracle(self):
        k1 = synthetic_k1_scorp_ordinary_income_materially_participates()
        prod_row = flattener.place_k1_on_schedule_e(k1)
        oracle_row = schedule_e_part_ii_row(k1, "Synthetic Entity LLC")
        self.assertEqual(prod_row.column, oracle_row.column)
        self.assertEqual(prod_row.amount, oracle_row.amount)
```

Synthetic fixtures drive the comparison. All dollar amounts divisible by $50;
all entity names from the allowlist in `scripts/personal_data_config.yaml`
(see `scripts/verify_no_personal_data.py`).
