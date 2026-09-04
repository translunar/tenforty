# Schedule C + Schedule SE Compute Support — Design Spec

**Status:** approved direction (compute-first); plan pending
**Date:** 2026-09-04

## Goal

Native computation of sole-proprietor returns: Schedule C net profit and
Schedule SE self-employment tax, wired through the 1040 spine, QBI, and the
CA conformity chain — **numbers first, PDF emission deferred**. This lets
tenforty answer entity-classification questions (S-corp vs. disregarded
LLC vs. sole prop) and later emit amended returns for a reclassification,
once the follow-on mapping unit lands.

## Architecture

Two new form modules following existing patterns:

- `tenforty/forms/sch_c.py` — models on `f1120s.py`: consumes structured
  P&L-category inputs, produces line-keyed dict ending in net profit
  (Sch C line 31). Per-business; multiple businesses supported as a list.
- `tenforty/forms/sch_se.py` — models on `f8959.py`: small standalone
  computation feeding the spine. Needs per-year Social Security wage-base
  params (2021–2025) under `tenforty/params/`.

PDF mappings (`pdf_sch_c.py`, `pdf_sch_se.py`) are **explicitly out of
scope** — a follow-on unit. Compute keys must therefore be mapping-ready:
named by form line (`sch_c_line_31`, `sch_se_line_12`, …), one key per
printable line, so the mapping unit adds no compute changes.

## Scope

### In

1. **Input surface** (`models.py`): new dataclass `ScheduleCBusiness` with
   `description`, `gross_receipts`, and expense-category fields mirroring
   Sch C Part II lines that a P&L export covers (advertising, insurance,
   legal/professional, office, rent, supplies, taxes/licenses, travel,
   deductible meals, utilities, wages, other_expenses). New list field
   `schedule_c_businesses` on `TaxReturnConfig`, default empty.
2. **Refusals for unmodeled Sch C features** — nonzero input raises
   `NotImplementedError` (hard refuse, no attestation): cost of goods
   sold / inventory, depreciation (line 13), home office (8829), vehicle
   expenses, depletion, statutory-employee flag, returns & allowances.
   Every refusal must be reachable and covered by a test that proves it
   fires (U-1 discipline).
3. **Schedule SE**: sum of net profits across businesses × 92.35%;
   no SE tax (and no half-deduction) when net earnings < $400; Social
   Security portion coordinated with existing `W2.ss_wages` against the
   per-year wage base; Medicare 2.9% uncapped. Optional methods, church
   income, and farm income are refused.
4. **Spine wiring** (`f1040_spine.py`, `sch_1.py`):
   - Sch 1 line 3 (business income) ← sum of Sch C line 31.
   - Sch 1 line 15 ← half-SE-tax deduction (replaces the hardcoded 0 at
     `sch_1.py:100`).
   - Schedule 2 line 4 (SE tax) → 1040 line 23 other-taxes aggregation,
     alongside the existing 8959 handling.
   - Form 8959: SE income enters the Additional-Medicare base per the
     8959 Part II computation (currently wages-only).
5. **QBI**: each Schedule C business contributes a QBI component =
   net profit − allocable half-SE-tax deduction − allocable SE health
   insurance, aggregated in `f8995.py` alongside existing K-1 components.
6. **§162(l) interaction**: once a Schedule C exists, the existing
   `self_employed_health_insurance_deduction` passthrough is no longer
   safely unlimited. When `schedule_c_businesses` is nonempty and the
   claimed deduction exceeds the earned-income limit (net profit −
   half-SE-tax for the business), **refuse** with a message explaining
   the split (allowed portion vs. excess to Sch A medical). With no
   Schedule C present, current passthrough behavior is unchanged.
7. **Workbook path**: fail closed — nonzero Schedule C activity raises
   `NotImplementedError` at the workbook orchestrator entry, same pattern
   as the SE-health guard (ticket (dd) precedent). Native path is truth.
8. **California**: **no new CA forms.** CA has no separate Schedule C or
   SE form; sole-prop income and the half-SE deduction flow into CA
   through federal AGI via the existing Sch CA chain, and CA conforms to
   both. CA's QBI nonconformity is already handled (QBI never enters CA).
   One verification task: confirm no Sch CA adjustment line is required
   for the supported (post-refusal) input surface, and register any
   divergence found in the usual acknowledgment machinery.
9. **Amendment**: prove (test-only, per the SE-health precedent) that the
   1040-X pipeline carries Schedule C / SE fields through Column C.

### Out

- PDF mappings for Sch C and Sch SE (follow-on unit).
- CA Form 568 (SMLLC return) — hand-filed if ever needed.
- COGS, depreciation, home office, vehicle, depletion, optional SE
  methods, church/farm income (all refused, above).
- Estimated-tax penalty computation.

## Testing

- All tests subclass `unittest.TestCase`; pytest runner; synthetic values
  only — no real figures, ever.
- Hand-derived oracles for Schedule SE and the QBI component follow the
  oracle-isolation discipline (oracle author air-gapped from
  implementation).
- Every refusal proven able to fire; every new assertion mutation-checked
  (neuter the branch, watch the test go red).
- Wage-base coordination gets explicit cases: wages below, straddling,
  and above the base; the <$400 threshold gets a boundary case.

## Errata (2026-09-04 plan review)

- **§1**: `schedule_c_businesses` attaches to `Scenario` (loaded via
  `_FORM_REGISTRY`), not `TaxReturnConfig` — every received-document list
  in the codebase lives at Scenario level; the spec's original placement
  was wrong.
- **§3**: no new params module — `ss_wage_base` already exists in
  `FederalParams` for all five years.
- **Refusals, two additions**: (a) a business whose Schedule C line 31 is
  **negative** (net loss) refuses — at-risk limitation (line 32), QBI
  loss netting/carryforward, and excess-business-loss rules are
  unmodeled, and a silently-floored loss would corrupt both AGI and QBI;
  (b) **two or more businesses combined with a nonzero SE-health
  deduction** refuses — §162(l)'s limit is the earned income of the
  business under which the plan is established, and plan-establishment
  designation is unmodeled, so the aggregate limit is only lawful in the
  single-business case.
