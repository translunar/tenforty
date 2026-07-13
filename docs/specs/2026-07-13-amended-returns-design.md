# Amended-Return Support: Form 1040-X + CA Amended 540 / Schedule X — Design

**Goal:** Given a supported filed year and a corrected picture of that year,
produce the complete, fileable amendment packet — federal Form 1040-X with
its changed-forms attachment subset, and California's complete amended
Form 540 with Schedule X.

**Premise:** tenforty already computes both sides of every amendment. The
filed-values file (used by the reconciliation drill) is the 1040-X's
Column A; a corrected-scenario run is Column C; Column B is subtraction.
No new tax math exists anywhere in this design — only reading,
already-validated computation, and arithmetic over the two.

---

## 1. Scope

In scope:
- `forms/f1040x.py`: Form 1040-X assembly — three-column line skeleton
  (income/deductions/tax/credits/payments/refund-or-owed), Part II
  explanation passthrough, line-18 original-refund handling.
- CA sibling (`forms/schedule_x.py`): Schedule X assembly over an amended
  540 run; the amended 540 itself is the existing f540 emit of the
  corrected scenario (CA files the COMPLETE corrected return).
- Amendment-case input files (external, never in the repo — see §2).
- Changed-forms selector for the federal attachment subset (§4).
- Mixed-keying template concept in the manifest (§5): revision-keyed
  1040-X, year-keyed Schedule X.
- PDF emit for 1040-X and Schedule X under the marker-probe regime.
- Packet assembler: gathers the amendment forms + attachments + a printed
  packet manifest listing exactly what mails.

Out of scope (explicit):
- Deadline/statute-of-limitations logic (§6511 windows) — ENTIRELY out;
  no computation and no advisory text. The user and their CPA own timing.
- Interest and penalty computation — returns file clean; agencies bill.
- E-file/MeF formats — paper packets only.
- Amending years without full tenforty federal support — the amendable
  set is DERIVED from the manifest (§5); no special-casing.
- Amended entity returns as a DIFF exercise. FEDERAL: the 1120-S has no
  separate "-X" form — it amends by re-filing the COMPLETE corrected
  return with box H(4) "Amended return" checked and amended-marked K-1s.
  CALIFORNIA (corrected during implementation — the original draft of
  this section wrongly claimed FTB retired Form 100X and that the 100S
  carries an amended-return checkbox; template probes proved no such
  checkbox exists on any 2021–2025 Form 100S, and the current FTB Form
  100X instructions say "Use Form 100X to amend a previously filed
  Form 100, Form 100S, or Form 100W"): a CA S-corp amendment files on
  Form 100X, a revision-keyed three-column form tenforty does NOT yet
  support — deferred to a followup, needed only if an already-filed
  100S must be corrected. The K-1 (100S) amended mark DOES exist on the
  printed schedule and IS mapped. The complete-corrected-return emit
  already exists (S-corp packet), so the emitted amended-marked
  100S + K-1s serve as the corrected-return basis for a
  preparer-completed 100X; the packet manifest says so explicitly.
  What IS in scope (§4a): the marks that exist on the printed forms —
  1120-S box H(4), amended K-1 (1120-S), amended K-1 (100S).
- Multiple sequential amendments of the same year beyond what Column A
  as-last-adjusted supports: the filed-values file is defined as "as
  originally filed OR as last adjusted"; maintaining that file across
  successive amendments is a user responsibility, documented in the
  amendment-case file format.

## 2. Inputs — the amendment case

Per amended year, alongside the existing external reconciliation files in
the user's documents tree (never the repo):

- `scenario.amended.yaml` — the COMPLETE corrected truth for the year,
  same schema as scenario.yaml. Full file, not a patch: no new grammar,
  trivially auditable (the amended file IS the corrected return), robust
  to multi-change amendments.
- `federal_filed_<year>.yaml` / `ca_filed_<year>.yaml` — Column A, as
  filed or as last adjusted. Already exist for reconciled years. These
  are now load-bearing legal inputs; the reconciliation review drill is
  their provenance discipline.
- `amendment.yaml` — what math cannot derive:
  - `explanation`: the 1040-X Part II / Schedule X explanation text (user/CPA words),
  - `original_refund_received`: bool + amount context for 1040-X line 18
    (original-return overpayment received or applied),
  - `prior_amendment`: optional note that Column A reflects a prior
    adjustment,
  - CA analogues (Schedule X payment/refund context lines).

Loaders are fail-closed (unknown-key ValueError), matching the scenario
loader contract.

## 3. Architecture — the diff assembler

`forms/f1040x.py` orchestrates, computes nothing new:

1. Column C: run scenario.amended.yaml through the EXISTING orchestrator
   (run_full_return / run_full_california_return).
2. Column A: READ from the filed-values file. A consistency guard REFUSES
   to assemble if a required Column-A key is absent — it never substitutes
   a recomputed value for a missing filed one.
3. Column B = C − A per line, mapped onto the 1040-X fixed line skeleton.
4. Refund/owed tail: line 18 (original overpayment) from amendment.yaml,
   then the form's prescribed arithmetic to amount-owed / refund lines.
   Per the Dec-2025 revision's actual layout: three columns exist for
   lines 1-15 only (line 9 reserved — never mapped); lines 16-23 are
   single-column; the explanation is Part II (page 2).
5. Explanation text passes through verbatim to Part II.
6. Out-of-scope refusal guards: amounts tenforty cannot recompute (EIC;
   TY2025 Schedule 1-A deductions) are NOT mapped — if the filed values
   carry a nonzero amount for one, assembly raises
   OutOfScopeAmendmentError naming the reason rather than emitting a
   blank where the filed return had a value.

The CA path mirrors it: corrected 540 run (the amended 540 emit) +
Schedule X assembled from filed CA values, the corrected run, and
amendment.yaml.

## 4. Changed-forms selector (federal attachments)

Federal paper amendments attach ONLY forms that changed or are new.
Selection is MACHINE-DERIVED, never hand-listed:

- Run the as-filed scenario AND the corrected scenario through emit
  payload generation (no PDF rendering needed for selection).
- A form is selected if any of its mapped payload values differ, or if it
  is present in the corrected run and absent from the as-filed run.
- The packet manifest prints the selection with a one-line per-form
  reason (changed / new), so the user sees exactly what mails.

Caveat documented in the module: selection compares tenforty-vs-tenforty
runs, so a form the FILED return included erroneously (that tenforty
never emits) cannot be selected; the packet manifest notes this class and
defers to the preparer.

CA ignores the selector — the amended 540 is always the complete return,
plus changed schedules per FTB practice (selector output reused as a
suggestion list for CA schedule attachments).

## 4a. Entity amended-return marks (small scope)

Additions to the EXISTING S-corp mappings, not new machinery:

- `SCorpReturn` gains `amended_return: bool = False` (and the existing
  K-1 allocation emit gains the per-K-1 amended mark when it is set).
- Mappings — the THREE marks that exist on the printed forms: 1120-S
  box H(4) checkbox; K-1 (1120-S) "Amended K-1" checkbox; K-1 (100S)
  amended checkbox. (The Form 100S itself has NO amended-return
  checkbox on any supported year — see the §1 correction; the CA
  filing vehicle is Form 100X, out of scope.) Each mark is
  probe-certified per year like any mapped field, with checkbox state
  read-back in the filled-emit tests.
- The Part-III-style explanation attachment for an amended 1120-S is a
  preparer-supplied page in the mailing packet, not a generated form —
  noted in the packet manifest, out of emit scope.
- Filing an amended FEDERAL entity return = the normal S-corp packet
  run with the flag set and corrected inputs. No diff assembler; the
  IRS receives the complete corrected return. For CALIFORNIA, the same
  flagged run produces the amended-marked 100S + K-1s that accompany a
  preparer-completed Form 100X; the packet manifest states that 100X
  itself is not emitted.

## 5. Manifest — the year-agnostic form family

New concept in `tenforty/years.py`:

- `AMENDMENT_FORMS: tuple[str, ...] = ("f1040x", "schedule_x")`, a MIXED
  tier — each form encodes its agency's actual publication model:
  - `f1040x` is REVISION-keyed: one current IRS revision (Rev. 12-2025)
    covers all amendable years; a text write-in field carries which
    calendar year is being amended (the Dec-2025 revision has no year
    checkboxes).
  - `schedule_x` is YEAR-keyed: FTB publishes Schedule X per taxable year
    (year-specific beginning TY2023; per-year files exist for all
    amendable years at forms/<year>/<year>-540-x.pdf), so it carries
    per-year templates/probes/mappings like every other CA form.
- `amendable_years()` is DERIVED: the years with full federal support
  (Column C requires a full run); CA amendable years likewise derive from
  CA support. No hand-maintained amendable list.
- Completeness gate demands the amendment pack ONCE (template + probe +
  mapping + compute module), not per year — the gate's first
  revision-keyed (rather than year-keyed) entry.
- VERIFY-not-assume item: the current-revision 1040-X's usability for the
  earliest amendable year is confirmed during template validation (the
  form supports several prior years; the validation step reads the
  form's own year checkboxes/entries and asserts coverage, recorded in
  the fetch commit).

## 6. Emit + validation

Emit: marker-probe regime unchanged — probe the 1040-X and Schedule X
templates, correspondence tables with printed labels, existence gate,
filled-emit read-back with distinctive values. Field paths read from the
template's own field listing (get_fields), never inferred (the
namespace-contamination lesson).

Validation — no third-party oracle exists, and none is needed, because
the assembly is arithmetic over two already-validated runs. The battery
is INVARIANT-based:

1. Column arithmetic: A + B = C on every line, every test case.
2. Self-amendment round trip: amending a scenario to ITSELF yields
   all-zero Column B, an empty changed-forms selection, and a
   refund/owed tail of zero — the null amendment is exactly null.
3. Refund-tail cases: original refund received vs applied vs zero;
   owed-to-refund and refund-to-owed sign flips.
4. Selector tests: value change selects a form; a new form selects; an
   untouched form does not; selection reasons render in the manifest.
5. Fail-closed guards: missing Column-A key refuses assembly; unknown
   amendment.yaml key raises.
6. External anchor (USER STEP, real figures never in the repo): the
   pending real 2024 amendments — federal (omitted capital-gain
   distributions + SDI SALT claim) and CA (state-tax disallowance +
   unemployment exclusion) — are the first live packets. The acceptance
   test IS the user's actual amendment, reviewed by the user and their
   CPA before filing.

## 7. Process

- Spec committed genericized (scanner must pass); implementation plans in
  gitignored `docs/plans/` per house convention.
- Executed by the S-corp packet teammate on a fresh branch AFTER the
  s-corp-packet branch passes user review and merges — this work consumes
  shared orchestrator surfaces and should build on the merged state.
- The 2024 live-packet run is a USER STEP routed through the team lead:
  the user drafts/approves scenario.amended.yaml content (with teammate
  drafting assistance from her documents), reviews the emitted packet,
  and owns filing.
- Deliberately NOT scheduled: amending 2021/2022/2023 — those wait on
  the CPA calls (SE-health, QBI window, S-corp cascade) that determine
  whether and what to amend.
