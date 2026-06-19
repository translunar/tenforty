# Federal Year-Param Consolidation — Design

**Date:** 2026-06-19

**Goal:** Make `FederalParams` the single source of truth for federal year-specific parameters. Route the feeding schedules (`sch_a`, `f8995`, `sch_1`) through it so they compute the correct values for any supported year, and delete the now-redundant federal `tenforty/constants/y2025.py`.

---

## Background / problem

The spine port introduced `tenforty/params/federal/` (`FederalParams`, loaded by year). But three feeding schedules still read a separate, pre-existing, hardcoded-2025 module, `tenforty/constants/y2025.py`:

- `forms/f8995.py` → `y2025.QBI_THRESHOLD`
- `forms/sch_a.py` → `y2025.SALT_CAP_STARTING`, `SALT_CAP_FLOOR`, `SALT_PHASEOUT_THRESHOLD`, `SALT_PHASEOUT_RATE`, `MEDICAL_AGI_FLOOR_PCT`
- `forms/sch_1.py` → `y2025.PRIOR_YEAR_SALT_CAP`

Two consequences:

1. **Year-leak:** these schedules use 2025 values for every year. A 2024 return that itemizes SALT would apply the 2025 OBBBA $40k cap instead of the correct 2024 flat $10k cap — over-deducting. (It does not affect the canonical single filer, who takes the standard deduction in 2024, but it is a real backfill bug.)
2. **Duplication with conflicting values:** `constants/y2025.STANDARD_DEDUCTION[SINGLE] = 15_000` while `params/federal/y2025.standard_deduction[SINGLE] = 15_750` (the IRS-correct value the spine uses). Two systems, one stale.

The current parity gates (2025 and 2024) pass only because the battery scenarios do not exercise the itemized-SALT / QBI-threshold / prior-year-refund paths.

## Approach

Consolidate onto `FederalParams`. Year differences live entirely in data (per-year param modules), never in `if year ==` branches in schedule logic — the same year-seam discipline the spine already follows.

### FederalParams additions (`tenforty/params/federal/__init__.py`, populated in `y2024.py` and `y2025.py`)

All dicts keyed by `FilingStatus.value` (string), matching the existing `FederalParams` convention.

- `medical_agi_floor_pct: float` — Schedule A medical-expense AGI floor (7.5% for both 2024 and 2025).
- `prior_year_salt_cap: dict[str, int]` — the SALT cap that applied in the year a state refund originated, used by the Sch 1 tax-benefit-rule. A 2025 return looks back to 2024 ($10k / $5k MFS); a 2024 return looks back to 2023 ($10k / $5k MFS).
- A **year-aware SALT-cap structure** replacing the current scalar `salt_cap` field:
  - `salt_cap_starting: dict[str, int]` — headline cap.
  - `salt_phaseout_threshold: int | None` — MAGI where the cap begins shrinking; **`None` means the year has no phaseout (flat cap)**.
  - `salt_phaseout_rate: float` — shrink rate above the threshold.
  - `salt_cap_floor: dict[str, int]` — the cap's lower bound.

  Year data:
  - **2024:** `starting = {single:10_000, mfj:10_000, hoh:10_000, qw:10_000, mfs:5_000}`, `phaseout_threshold = None`, `rate = 0.0`, `floor = same as starting`. Flat $10k / $5k cap, no income dependence.
  - **2025:** `starting = {single/mfj/hoh/qw:40_000, mfs:20_000}`, `phaseout_threshold = 500_000`, `rate = 0.30`, `floor = {…:10_000, mfs:5_000}`. OBBBA structure.

  The existing scalar `salt_cap` field is removed; audit its current readers (the spine and any test) and migrate them to derive the effective cap from the structure (for the no-phaseout / under-threshold case this is just `salt_cap_starting`).

### Schedule rewires

Each schedule loads params by year via `tenforty.params.federal.load(scenario.config.year)` — no `if year ==` branches.

- **`f8995.py`:** read `params.qbi_threshold[status]` instead of `y2025.QBI_THRESHOLD`. (Behavior identical for 2025; correct for 2024 = 191,950.)
- **`sch_a.py`:** read `medical_agi_floor_pct` and the SALT structure from params. Make the cap **phaseout-year-aware**:
  - `salt_phaseout_threshold is None` (2024) → effective cap = `salt_cap_starting[status]` (flat); never raise on high MAGI.
  - threshold set (2025) → below threshold, cap = `salt_cap_starting[status]`; **at/above threshold, keep the existing scoped-out behavior — raise `NotImplementedError`** (the OBBBA phaseout calculation remains unimplemented; see Non-goals).
- **`sch_1.py`:** read `params.prior_year_salt_cap[status]` instead of `y2025.PRIOR_YEAR_SALT_CAP`.

### Orchestrator + cleanup

- Audit every `constants.y2025` reference in `tenforty/orchestrator.py`; migrate to `FederalParams` (or remove if dead — e.g. a now-unused `STANDARD_DEDUCTION` reference).
- Delete `tenforty/constants/y2025.py`. **Keep** `tenforty/constants/california_yYYYY.py` — the California constants are a separate system, out of scope.

## Validation

- Both penny-parity gates (2025 and 2024) stay green — the consolidation must not change any value the spine already matches against the workbook.
- The standard-deduction conflict resolves to the IRS-correct $15,750 (confirm the stale $15,000 was either unused or its readers now use `FederalParams`).
- New `unittest.TestCase` tests: the year-aware SALT cap returns the flat $10k for a 2024 itemizer and $40k for a 2025 under-$500k itemizer; `sch_a`/`f8995`/`sch_1` read year-correct values for matched 2024 vs 2025 scenarios.
- Extend the no-`if year` AST guard (`tests/test_spine_year_agnostic.py`) to also scan `sch_a.py`, `f8995.py`, `sch_1.py` — they may load params *by* year but must contain no `year ==` branches.
- Full suite green.

## Non-goals

- The OBBBA >$500k SALT phaseout **calculation** stays unimplemented for 2025 (raise `NotImplementedError` above $500k). Only the data shape is added now; computing the shrink is a guarded follow-up (no in-scope filer exceeds $500k).
- California constants (`constants/california_yYYYY.py`) are untouched.
- No new tax years beyond 2024/2025.
