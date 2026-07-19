# CA Divergence Catalog Redesign

**Date:** 2026-07-19
**Status:** Draft for review
**Replaces:** the FODS worksheet round-trip (docs/specs/2026-05-02-fods-worksheet-design.md)

## 1. Problem

The Schedule CA divergence machinery has one catalog's worth of knowledge
split across four hand-synchronized surfaces:

1. The per-year catalog YAML (~200 rows) — read only by a dev-time generator.
2. The generated blank `.fods` worksheets — committed, but runtime never
   reads them; users copy and hand-edit them in LibreOffice.
3. The runtime importer — parses the user's edited copy with minidom,
   collapses each tab to two SUM totals, and discards every description and
   citation.
4. The kernel's own hardcoded auto-divergence tuples
   (`_FEDERAL_AUTO_DIVERGENCES`, `_CA540_AUTO_DIVERGENCES`) — synced to the
   catalog by a hand-maintained "Drop rules applied" comment.

Routing is by free-form string labels ("Part I §B 7") that must match
exactly across all four surfaces; a drift silently drops amounts. The
user-facing workflow requires LibreOffice in a product whose distribution
goal is "no LibreOffice." And the deepest problem is discoverability:
users who don't already know California diverges from federal treatment
never find out — the catalog can't reach them.

## 2. Design

**The catalog becomes the single runtime-loaded source of truth. User
divergences become scenario YAML validated against it. The scenario's own
shape nominates divergences the user must address.**

### 2.1 Catalog schema

Each row in `sch_ca_divergences-<year>.catalog.yaml` gains a stable
**`id`** (kebab-case, unique within the year, stable across years so
docs/scenarios port cleanly) and optional mechanism fields:

```yaml
- id: non-ca-muni-interest
  sch_ca_line: "Part I §A 2"
  section_title: "Taxable interest"
  description: "Interest from non-California municipal bonds (taxable to CA)"
  direction: "Add"
  common: true
  pub1001_page: 8
  ircrtc: "R&TC §17143"
  triggers: [has_tax_exempt_interest]   # optional; names from the registry
  gate: true                            # triggered ⇒ must be addressed
  derivable_via: "Form1099INT.state_of_issue"  # optional; future auto path
- id: unemployment-compensation
  ...
  auto: {federal_key: sch_1_line_7_unemployment}  # kernel derives the amount
```

- **`auto`** rows replace the kernel's hardcoded tuples: the kernel reads
  the named federal-results key (or named `CA540Return` field, e.g.
  `{ca540_field: pfl_amount}`) and fires when it is positive. The "Drop
  rules applied" comment is retired; auto rows simply live in the catalog.
- **`triggers`** name predicates from a closed, code-side registry (§2.4).
- **`gate: true`** marks entries that, when triggered, must be addressed
  before a CA return computes (§2.5). Auto rows never gate (they self-apply).
- **`derivable_via`** documents which not-yet-modeled scenario field would
  let this row become `auto` — the migration map. Informational only.
- Existing fields (`description`, `pub1001_page`, `ircrtc`) become
  load-bearing: they flow into validation errors, refusal messages, the
  resolved snapshot, and the packet manifest.

Which entries get which triggers/gates is **authoring work done against
Pub 1001 under source-verification discipline at implementation time** —
this spec deliberately assigns none. The initial trigger set must be
narrow and high-confidence (signals the schema actually carries, e.g.
tax-exempt interest, K-1 presence, rental depreciation); it widens only as
the input schema gains detail. Over-eager gating is a bug: a false
positive costs user trust the same way a silent drop costs correctness.

### 2.2 Scenario input

`CA540Return` / the `.ca.yaml` gains:

```yaml
divergences:
  - id: non-ca-muni-interest
    amount: 412
    note: "Vanguard national muni fund, non-CA portion per fund letter"
reviewed:              # triggered entries the filer examined and zeroed
  - prop22-wage-reclass
```

The loader validates every `id` — in `divergences` AND in `reviewed` —
against the year's catalog at load time, before any compute: unknown id is
a hard error with a nearest-match suggestion. (A typo'd `reviewed` id
would still fail safe by direction — the gate would refuse rather than
silently clear — but the user deserves "you misspelled X" at load, not a
confusing "you must address X" refusal later.) `CASchCAAdjustment` keeps its
role as the internal materialized form; the loader builds it from
(id, amount) + catalog metadata, so direction/line/description/citation
can never disagree with the catalog. `DivergenceSource` gains `CATALOG_AUTO`
/ `USER` values as needed to keep the resolved snapshot honest about origin.

### 2.3 Kernel

`forms/sch_ca.py` loads the year's catalog (packaged data, fail-closed on
missing/malformed), derives auto rows, merges user rows, and routes by the
catalog's `sch_ca_line` — which now exists in exactly one place. A
schema-level test enumerates the catalog's line labels against the known
Schedule CA line set per year, so a typo is a suite failure, not a dropped
amount. Part II itemized is untouched (separate path, out of scope).

### 2.4 Trigger registry

A code-side mapping `TRIGGER_PREDICATES: dict[str, Callable[[Scenario], bool]]`
— named, unit-tested predicates (`has_tax_exempt_interest`, `has_k1`,
`has_rental_depreciation`, …). No expression language in YAML: the catalog
references predicates by name only; an unknown name is a catalog-load
error. Adding a predicate is a code change with tests, which is the right
friction for something that controls a refusal gate.

### 2.5 Acknowledgment gate

At CA compute time: for every catalog entry with `gate: true` whose
triggers fire against the scenario, the entry must appear in `divergences`
(with an amount) or in `reviewed`. Otherwise the return refuses with a
message listing each unaddressed entry — id, description, Pub 1001 page,
R&TC citation, and the trigger that fired. The refusal is the education.
Zero-trigger scenarios are unaffected; a scenario with no CA-relevant
signals computes exactly as before.

### 2.6 Manifest trail

The packet manifest's CA section reports three buckets, each row with
description + citation:

- **Auto-applied** (catalog `auto` rows that fired, with amounts)
- **User-supplied** (from `divergences`, with notes)
- **Reviewed and not applicable** (triggered entries in `reviewed`)

This preserves for the CPA/preparer what today dies inside the fods file:
what was considered, what was dismissed, and why the numbers are what they
are.

## 3. Retirements

- `scripts/build_sch_ca_fods.py`, `tenforty/forms/sch_ca_fods.py`, the
  committed blank `.fods` files (all years), `discover_fods_divergences`
  and the `.ca.fods` runtime path, and the fods template tests.
- The kernel's `_FEDERAL_AUTO_DIVERGENCES` / `_CA540_AUTO_DIVERGENCES`
  tuples (subsumed by catalog `auto` rows).
- The half-wired Sch D 540 worksheet import (amounts parsed and surfaced
  but never computed — a false affordance). `CASchD540Adjustment` stays in
  the schema for the future compute follow-up; it simply stops being
  populated from a worksheet nobody's numbers flow out of.
- Runbook "add a tax year" step 6 loses the fods regeneration; a new
  year's CA work becomes: copy catalog → conformity review against the new
  Pub 1001 → adjust rows/ids → done.

Breaking change for any `.ca.fods` user (pre-1.0: changelog note + error
message pointing at the YAML format when a `.ca.fods` file is discovered —
detect-and-explain for one release rather than silent ignore).

## 4. Verification

- **Catalog gates (per year):** ids unique and kebab-case; every
  `sch_ca_line` in the known line set; every trigger name in the registry;
  every `auto` key resolvable (federal key exists in the results
  vocabulary / field exists on `CA540Return`); `auto` and `gate` mutually
  exclusive per row.
- **Behavior preservation:** the existing CA battery and the reconciled
  filed-return scenarios (2021–2025) must produce identical results before
  and after the auto-row migration — the hardcoded-tuple retirement is a
  refactor, proven by the strongest regression anchors we have.
- **Mutation checks:** neuter an auto catalog row → battery goes red
  (proves the catalog is load-bearing, not decorative); remove a trigger
  from a gated row → its refusal test fails.
- **Refusal-path tests:** per gated trigger — fires, message carries
  citation, `reviewed` clears it, amount clears it.
- **Loader tests:** unknown id (with suggestion), duplicate id, id from
  the wrong year — each exercised in both `divergences` and `reviewed`.

## 5. Sequencing

Lands **before** the native-filing-statuses implementation (independent
code surfaces, but the statuses work's CA battery and hand-oracle cases
should be authored in id format, not the string-label format this spec
retires). Single implementation plan; the catalog id/field authoring for
all five years is the largest single task and is source-verification work,
not code.

## 6. Deferred (explicitly out)

- Interview mode (`ca-interview`) for trigger-less common divergences.
- Publishing the catalog as a browsable reference page.
- Sch D 540 divergence *compute* (the retired import path's missing half).
- Any trigger sourced from schema fields that don't exist yet (box 12
  codes, 1099-R, …) — recorded via `derivable_via` as they become real.
