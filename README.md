# tenforty

An open-source US federal + California individual income tax preparation tool. Compute returns, cross-check against independent oracles, fill IRS / FTB PDFs.

## Mission

Tax compliance is functionally mandatory in the US, but the tools to do it correctly are gatekept: paywalled commercial software, deliberately complex IRS forms, expensive professional preparers. The cost of compliance falls disproportionately on people without resources to navigate the system. The status quo is designed to extract from the lower and middle classes while favoring the wealthy.

tenforty is open-source, transparent, and verifiable. Anyone can audit the math. Anyone can run it. The same compute path that handles a complex multi-state return with K-1 pass-throughs handles a simple W-2 + standard-deduction return.

## How it works

Three orchestrator entry points, one per return type:

- **Federal 1040** (`compute_federal` / `run_full_return`) — uses a third-party Excel spreadsheet ([incometaxspreadsheet.com](https://sites.google.com/view/incometaxspreadsheet/home)) for production math; native Python orchestrates the workbook, fills IRS PDFs, and cross-checks results.
- **Corporate 1120-S** (`compute_corporate` / `run_full_return`) — native Python compute (no third-party XLS exists for 1120-S); waterfalls synthesized K-1s into the federal 1040 pipeline.
- **California 540** (`run_full_california_return`) — native Python compute (no third-party XLS exists for CA); reads federal results downstream and applies state-specific divergences via Schedule CA (540).

Each form is cross-checked against an independent reference: either the third-party XLS (federal) or a hand-coded reference oracle on a separate git branch (1120-S, California). No single implementation is trusted in isolation.

For the structural picture (modules, oracle isolation, PDF mapping pattern), see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Quick start

### Prerequisites

- Python 3.12+
- LibreOffice (`brew install --cask libreoffice` on macOS)
- The 2025 federal XLS from [incometaxspreadsheet.com](https://sites.google.com/view/incometaxspreadsheet/home) (already at `spreadsheets/federal/2025/1040.xlsx`)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
source .venv/bin/activate
python -m pytest tests/ -v
```

Tests that require LibreOffice (~18s each) are skipped if it's not installed.

### Prepare and file a return

The CLI has subcommands per return type:

```bash
# Federal 1040 only
python -m tenforty federal ~/Documents/Taxes/2025/scenario.yaml --output-dir ~/Documents/Taxes/2025/

# California 540 (downstream of federal)
python -m tenforty ca ~/Documents/Taxes/2025/scenario.yaml --output-dir ~/Documents/Taxes/2025/
```

The CA subcommand reads a separate `scenario.ca.yaml` file alongside the federal YAML by default (`<basename>.ca.yaml` convention) — see [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the federal-first downstream flow. Outputs are filled IRS / FTB PDFs in `--output-dir`.

A federal scenario file looks like:

```yaml
config:
  year: 2025
  filing_status: single
  birthdate: "1990-06-15"
  state: CA

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

## Project status

### Currently working

**Federal 1040 spine:**
- Form 1040 (W-2, 1099-INT, 1099-DIV with capital gain distributions, 1099-G unemployment + state refunds, 1099-B with capital gain transactions, 1098 mortgage/property tax)
- Schedule 1 (additional income + adjustments, with per-line breakdowns)
- Schedule A (itemized deductions, including OBBBA SALT cap)
- Schedule B (interest + dividend reporting)
- Schedule D (capital gains)
- Schedule E Part I (rental real estate + royalties)
- Schedule E Part II (K-1 pass-through, with `K1FanoutData` sidecar feeding Sch D, Form 8582, Form 8995)
- Form 8949 (capital gain transaction detail)
- Form 8959 (Additional Medicare Tax)
- Form 8995 (QBI deduction, simplified)
- Form 8582 (passive activity loss limitations)
- Form 4562 (depreciation — straight-line MACRS)
- Form 4868 (extension)

**Federal corporate:**
- Form 1120-S (S-corp return + per-shareholder Schedule K-1 fan-out)

**California:**
- Form 540 (CA individual return + tax + credits + final liability)
- Schedule CA (540) (federal-vs-CA divergence kernel: auto-derived divergences + named `CA540Return` fields + multi-row worksheet rows)
- Schedule D (540) (capital gains, federal pass-through gated by attestation)
- 13 year-bounded CA-specific scope-out attestations (AMT, §1202 QSBS, §1031 like-kind, kiddie tax, lump-sum distributions, RRB, PFL, etc.)

**PDF emit + verification:**
- PDF filling for every form listed above (federal + CA)
- Round-trip PDF verification
- 5-registry mapping pattern (mapping / aggregations / derivations / suppressed / checkbox-states)
- Pre-commit personal-data scanner
- Year-extension harness: manifest-driven completeness gate, published-tax-table oracles, dual-transcription param attestation, add-tax-year runbook

**CLI:**
- `tenforty federal <path>` and `tenforty ca <path>` subcommands

### Not yet implemented

- **Form 6251** (federal AMT). Not yet modeled. A scenario that would owe AMT will silently underreport — to be addressed by adding the form to the data model and compute pipeline.
- **Schedule C** (self-employment). Not yet modeled. Self-employment income flows have no representation in the `Scenario` schema.
- **Form 8962** (Premium Tax Credit). Marketplace health insurance reconciliation.
- **`.fods` worksheet generator** for user-friendly editing of California-vs-federal divergences (one tab per Sch CA line of additions/subtractions). Worksheet rows currently authored manually in YAML.
- **Additional state returns** (every state besides California).
- **FreeFileFillableForms automation** (Playwright-driven submission pipeline).

## License

MIT
