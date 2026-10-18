# tenforty

An open-source US federal + California individual income tax preparation tool. Compute returns, cross-check against independent oracles, fill IRS / FTB PDFs.

## Mission

Tax compliance is functionally mandatory in the US, but the tools to do it correctly are gatekept: paywalled commercial software, deliberately complex IRS forms, expensive professional preparers. The cost of compliance falls disproportionately on people without resources to navigate the system. The status quo is designed to extract from the lower and middle classes while favoring the wealthy.

tenforty is open-source, transparent, and verifiable. Anyone can audit the math. Anyone can run it. The same compute path that handles a complex multi-state return with K-1 pass-throughs handles a simple W-2 + standard-deduction return.

## How it works

Three orchestrator entry points, one per return type:

- **Federal 1040** (`compute_federal` / `run_full_return`) — a native Python spine computes single-filer returns that cannot involve the Earned Income Credit. Every other return (any non-single filing status, or a filer who might qualify for EIC) is computed by a third-party Excel workbook ([incometaxspreadsheet.com](https://sites.google.com/view/incometaxspreadsheet/home)) driven through LibreOffice. The workbook also serves as the cross-check oracle for the native spine. Native Python fills the IRS PDFs either way.
- **Corporate 1120-S** (`compute_corporate` / `run_full_return`) — native Python compute (no third-party XLS exists for 1120-S); waterfalls synthesized K-1s into the federal 1040 pipeline.
- **California 540** (`run_full_california_return`) — native Python compute (no third-party XLS exists for CA); reads federal results downstream and applies state-specific divergences via Schedule CA (540).

Each form is cross-checked against an independent reference: either the third-party XLS (federal) or a hand-coded reference oracle on a separate git branch (1120-S, California). No single implementation is trusted in isolation.

Amended returns (Form 1040-X, CA Schedule X) are assembled by `run_amendment_packet` (Python API; there is no CLI subcommand for it).

For the structural picture (modules, oracle isolation, PDF mapping pattern), see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

### Prerequisites

- Python 3.12+
- LibreOffice (`brew install --cask libreoffice` on macOS) — only needed for returns the native spine does not cover (see above) and for the oracle tests
- The federal XLS workbooks from [incometaxspreadsheet.com](https://sites.google.com/view/incometaxspreadsheet/home) (already at `spreadsheets/federal/<year>/1040.xlsx`, 2021–2025)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
source .venv/bin/activate
PYTHONDONTWRITEBYTECODE=1 python -m pytest tests/ -m "not oracle" -q -n 4 --dist load
```

The fast tier runs in parallel on four pytest-xdist workers (installed by the
`dev` extra). Tests marked `oracle` drive LibreOffice and are excluded above;
the oracle tier always runs strictly serial (never with `-n`), because
LibreOffice (soffice) has a single global slot. They refuse to run unless `TENFORTY_ORACLE_OK=1` is set (see `tests/conftest.py`), so a bare `pytest tests/` cannot launch LibreOffice by accident.

### Prepare and file a return

The CLI has subcommands per return type:

```bash
# Federal 1040 only
python -m tenforty federal ~/Documents/Taxes/2025/scenario.yaml --output-dir ~/Documents/Taxes/2025/

# California 540 (downstream of federal)
python -m tenforty ca ~/Documents/Taxes/2025/scenario.yaml --output-dir ~/Documents/Taxes/2025/

# S-corporation: federal 1120-S + K-1s, plus CA 100S + K-1s when the scenario has a CA block
python -m tenforty scorp ~/Documents/Taxes/2025/scorp.yaml --output-dir ~/Documents/Taxes/2025/
```

The CA subcommand reads a separate `scenario.ca.yaml` file alongside the federal YAML by default (`<basename>.ca.yaml` convention) — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the federal-first downstream flow. Outputs are filled IRS / FTB PDFs in `--output-dir`.

A federal scenario file looks like this (abridged — the loader also requires an explicit answer to every scope-out attestation, e.g. `has_foreign_accounts`, `acknowledges_no_federal_amt`, `prior_year_itemized`; a missing one is refused with a message naming the field. [`tests/fixtures/simple_w2.yaml`](tests/fixtures/simple_w2.yaml) is the complete, loadable version of this scenario):

```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1990-06-15"
  state: CA
  has_foreign_accounts: false
  # ... one answer per scope-out attestation

w2s:
  - employer: "Employer Name"
    wages: 100000.00
    federal_tax_withheld: 15000.00
    ss_wages: 100000.00
    ss_tax_withheld: 6200.00
    medicare_wages: 100000.00
    medicare_tax_withheld: 1450.00

form1099_int:
  - payer: "Bank Name"
    interest: 250.00
```

## For agents

If you're an AI agent working on this codebase: read [CLAUDE.md](CLAUDE.md) for team norms, agent-protocol standards, and the feedback / partnership culture. Read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the structural picture.

## Contribution

### Code standards

These apply to anyone touching the code, human or agent.

- **No PII in fixtures.** Synthetic test data only — invented from scratch, not rounded real numbers. Allowlisted employer / payer names. Real personal tax data lives outside the repo (e.g. `~/Documents/Taxes/`); the repo never sees it. A pre-commit hook (`scripts/verify_no_personal_data.py`) enforces this.
- **No corner-cutting.** No tautology assertions (`assertEqual(0, 0)`, etc.). If a test can't be satisfied as written, fix the test or the code; don't reshape the assertion to pass.
- **All imports at file top.** No function-local imports.
- **Comments explain WHY, not WHAT.** Well-named code documents what; comments document the non-obvious why — a constraint, an invariant, a workaround for a specific bug, a reference to an external instruction.
- **No task-number references in production code or commit messages.** Internal task identifiers belong in plan documents only. Production code and commit messages describe the change in form-specific or behavior-specific terms.
- **Compute keys are semantic, not line-numbered.** `f1120s_total_tax`, not `f1120s_line_22_total_tax`. Line numbers belong in the PDF mapping module (form-revision-specific).
- **TDD with `unittest.TestCase`.** All tests subclass `unittest.TestCase`; pytest is the runner; never bare-function pytest tests.

### Verification approach

The core idea: **use independently-maintained systems as verification oracles.** Federal forms cross-check Python compute against the third-party XLS. 1120-S and California forms cross-check Python compute against hand-coded reference oracles on separate git branches (see Oracle isolation in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)).

Structural invariants (AGI ≤ income, tax ≥ 0, refund + owed = payments - tax, etc.) catch logical errors without knowing the "right" answer.

Round-trip PDF verification confirms the chain end-to-end: scenario → compute → fill PDF → read back → values match.

## Forms availability

Two columns matter and they are not the same thing. **Compute** means a forms-layer module (`tenforty/forms/`) produces the form's lines in the results. **Emit** means a registered PDF mapping (`tenforty/mappings/pdf_*.py`) plus a blank template actually prints the form. Gates ("when ...") decide whether a computed form attaches to a given return.

Every form listed below is Compute-and-Emit for **tax years 2021–2025**; no form has a year floor above 2021. (Policy: new features floor at TY2022 unless a later decision says otherwise; the only registered exception is the Schedule C family — Schedule C, Schedule SE, Schedule 2 — floored at TY2021. The sources of truth are `tenforty/years.py` and the mapping catalog; the completeness gate fails if a declared year lacks a template or mapping.) Years outside 2021–2025 are refused.

### Federal individual

| Form | Compute | Emit | Prints when |
|------|---------|------|-------------|
| Form 1040 | yes (native spine; workbook for non-single / EIC-possible filers) | yes | always |
| Schedule 1 | yes | yes | line 10 or line 26 nonzero |
| Schedule 2 | yes | yes, native path only | excess-APTC repayment, SE tax, or Additional Medicare Tax nonzero; workbook-path returns print the totals on the 1040 with no Schedule 2 |
| Schedule A | yes | yes | itemized total beats the standard deduction |
| Schedule B (Parts I–II) | yes | yes | interest or dividends ≥ $1,500 |
| Schedule C | yes, native single-filer path only (one per business) | yes (one PDF per business) | any Schedule C business |
| Schedule D | yes | yes | any 1099-B transactions |
| Schedule E Part I (rentals) and Part II (K-1s) | yes | yes | any rental property or K-1; Part II holds up to 4 K-1 rows |
| Schedule SE | yes, native single-filer path only | yes | self-employment tax nonzero |
| Form 4562 | yes (Part III lines 17, 19 and 22 only) | yes | some property was placed in service in the return year; in an ongoing year depreciation prints on Schedule E line 18 / Schedule C line 13 with no Form 4562 |
| Form 4868 | yes | yes | always |
| Form 8582 | yes | yes | passive loss or carryforward, or a net rental loss |
| Form 8949 | yes | yes | at least one lot off the Box A/D aggregate path |
| Form 8959 | yes (Parts I–II; Part III RRTA is zero) | yes | workbook says required, or Medicare wages over the threshold |
| Form 8962 | yes | yes | a 1095-A block with nonzero premium, SLCSP or APTC |
| Form 8995 | yes (simple path only) | yes | QBI deduction or QBI loss carryforward nonzero |
| Form 1040-X | yes | yes (Rev. December 2025, any amendable year 2021–2025) | `run_amendment_packet` |
| Form 3115 | presentation only | yes (Rev. December 2022) | a `form_3115:` block; automatic change no. 7 only; the §481(a) amount is stated, not computed |

### Federal corporate

| Form | Compute | Emit | Prints when |
|------|---------|------|-------------|
| Form 1120-S | yes | yes | scenario has an `s_corp_return` |
| Schedule K-1 (1120-S) | yes (per-shareholder fan-out) | yes | one per shareholder |

### California

| Form | Compute | Emit | Prints when |
|------|---------|------|-------------|
| Form 540 | yes | yes | always (`ca` subcommand) |
| Schedule CA (540) | yes | yes | always |
| Schedule D (540) | yes | yes, summary lines only | CA capital gains differ from federal; the transaction detail rows and their column totals are not printed |
| Schedule X (540) | yes | yes (per-year templates, 2021–2025) | `run_amendment_packet` |
| Form 100S | yes | yes | S-corp scenario with a CA block |
| Schedule K-1 (100S) | yes | yes | one per shareholder |

### Other artifacts

- `depreciation_audit_<year>.xlsx` — a formula-driven audit workbook, written beside the forms whenever a return computes depreciation from `depreciable_assets`.

### Computed but not (fully) printed

These are the places where a computed figure does not reach a printed line. Each is deliberate and registered in the mapping's suppressed set or guarded by a refusal.

| Item | What happens |
|------|--------------|
| Workbook-path returns (non-single or EIC-possible filers) | The workbook's 1040 line 17 can include AMT and its line 24 can include the net investment income tax, and it computes any EIC. Only the 1040 lines print; no Form 6251, Form 8960, Schedule 3 or EIC worksheet is emitted, and Schedule 2 is withheld because tenforty cannot reproduce those components |
| Form 540 total credits (exemption-credit-inclusive), PTET credit, final liability | Computed internally; line totals are printed through the form's own derivations, not as separate cells |
| Form 1120-S: built-in gains tax (2025); energy-efficient-buildings deduction, refundable credits and the Schedule B digital-asset question (2021–2022); Schedule K other-deductions mirror (2021–2023) | Computed or stated, but that year's template has no cell for it, so it is suppressed from the fill |
| Schedule D (540) transaction detail rows | Totals print; the per-row detail does not |
| Form 4562 Parts I, II, V and VI (§179, bonus, listed property, amortization) | Not computed (refused or attested out) |

### Not supported

tenforty does not model the forms below. A scenario that would need one is refused or must carry an explicit attestation; none is silently approximated. Where a number comes from a filer's own records (e.g. an S corporation's Form 4797 net gain) it is a stated input, not a computed one.

- **Federal credits and taxes:** Form 6251 (AMT; a scenario that could owe it needs `acknowledges_no_federal_amt`), Schedule 3 (not emitted), Form 8812 / child tax credit and EIC (the native spine computes neither; EIC-possible returns route to the workbook), Form 8863 (education credits), Form 2441, Form 8880, Form 5695, Form 1116, Form 8960 (NIIT), Form 5329, Form 2210, Schedule H.
- **Income and basis forms:** Form 1099-R / retirement distributions, Form 8606, Form 8889 (HSA), SSA-1099, W-2G, Form 4797, Schedule F, Form 6252, Form 8615, Form 8283, Form 8839.
- **Business forms:** Form 8995-A (over-threshold QBI; refused), Form 8829 (home office; refused), Form 6198 (at-risk; attestation), Form 7203 (S-corp basis; attestation, hand-attach), Form 461 (excess business loss; refused over threshold), 1120-S Schedules L, M-1, M-2, M-3 and Form 1125-A/E (attested out), Schedule E Part II continuation sheets (more than 4 K-1s; refused unless attested, and rows beyond D are dropped), Schedule B Part III / FBAR (a true `has_foreign_accounts` is refused).
- **California:** Schedule P (540) AMT, FTB 3853 (health-care coverage penalty; a stated coverage gap is refused), Form 540NR, Form 100X (CA S-corp amendment; the amended 100S and K-1 are emitted with a READ-FIRST note), and the other CA scope-outs enforced as attestations (NOL carryover, depreciation and IRA-basis divergences, RDP status, excess business loss carryover, §1031 personal property, worker reclassification, other-state tax credit, RRB, paid family leave; see `_CA_ATTESTATIONS` in `tenforty/attestations.py`).
- **Other states:** none.

## Project status

### Also working

- **Source-document attachments** — W-2 PDFs declared in the scenario are spliced into the filing packet behind the main form, with an emit-time gate.
- **Direct deposit** of a refund on Form 1040 and Form 540 (routing-number checksum enforced).
- **Estimated-payment, CA withholding and non-itemizer charitable channels.**
- **Per-business Schedule C** with asset-mode depreciation (Pub 946 MACRS tables, mid-quarter test) shared with Schedule E rentals.
- **Year-extension harness** — manifest-driven completeness gate, published-tax-table oracles, dual-transcription param attestation, add-tax-year runbook (`docs/runbooks/add-tax-year.md`).
- **Pre-commit personal-data scanner** and round-trip PDF verification.
- **5-registry mapping pattern** (mapping / aggregations / derivations / suppressed / checkbox-states) for every PDF form.

### Not yet implemented

- **Native MFJ, head-of-household and other non-single filing statuses.** These route to the workbook path and need LibreOffice. A design exists; it is not built.
- **Additional state returns** (every state besides California).
- **FreeFileFillableForms automation** (Playwright-driven submission pipeline).
- Everything in "Not supported" above.

### Limitations

- **Workbook-path returns refuse Schedule C and the self-employed health-insurance deduction.** A non-single or EIC-possible filer is computed by the vendor workbook, which tenforty has not wired for Schedule C, Schedule SE or Schedule 1 line 17; a scenario carrying either is refused rather than computed with the income or deduction silently dropped.
- **Schedule C features refused (not modeled).** A scenario that uses cost of goods sold / inventory, returns and allowances, home office, vehicle expenses, depletion, statutory-employee status, or a multi-business §162(l) self-employed health-insurance allocation is refused rather than computed or printed wrong. A Schedule C net loss computes only when `acknowledges_sch_c_all_investment_at_risk: true` (box 32a; Form 6198 is not modeled); an S corporation K-1 whose Schedule E Part II row nets to a loss gets line 28 column (e) checked and needs `acknowledges_form_7203_attached_separately: true` (Form 7203 is not produced — attach it by hand; the gate is enforced on the native single-filer compute path and at PDF emit, but a compute-only run on the workbook path, i.e. a non-single or EIC-possible filer, does not enforce it); and any return whose un-netted business losses exceed the §461(l) threshold is refused (Form 461 is not modeled). Schedule C, Schedule SE and Schedule 2 emit for tax years 2021–2025.
- **Digital-assets question (Form 1040).** Set `digital_assets: true` or `false` in the scenario `config` to answer the 1040's digital-assets question (2021: the virtual-currency question). It is optional for compute-only runs, but emitting a 1040 PDF for tax year 2022 or later with the field unset is refused — tenforty will not print a signed return with that box blank. The 1040 header (name, SSN, spouse, address) and the filing-status and line-7 "Schedule D not required" boxes are filled from the config and the return.

## License

MIT
