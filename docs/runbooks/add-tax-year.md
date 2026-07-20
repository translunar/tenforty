# Add a Tax Year (either direction: next year or backfill)

The support grid is year × form. This runbook adds a YEAR. To add a
COMPONENT across years instead, run the same steps with the loop
inverted — see the design spec's "Component ports: the transpose"
(docs/specs/2026-07-06-year-extension-harness-design.md).

Every step ends in a machine check. If a check goes red, the port is not
done — no step may be satisfied by weakening its check.

## 0. Delta review (the legislative-shape fence) — HUMAN JUDGMENT

Read the year's Rev. Proc. (federal) / FTB booklet "What's New" section
(California) against the params schema (`params/federal/__init__.py`,
`params/california/__init__.py`) and form-revision list. Question: does
anything this year NOT FIT the existing dataclass shapes or form set?
(Precedent: OBBBA turned the scalar SALT cap into a phaseout structure.)
If yes: STOP — that's a schema/design change to spec first, not a port.

## 1. Fetch assets — USER STEP (downloads)

    python scripts/fetch_year_assets.py --jurisdiction federal --year YYYY
    python scripts/fetch_year_assets.py --jurisdiction california --year YYYY

Optional: download the year's XLS workbook from incometaxspreadsheet.com
to spreadsheets/federal/YYYY/1040.xlsx (enables the acceptance gate).
Check: every file passed the fetcher's PDF validation.

## 2. Scaffold

    python scripts/scaffold_year.py --jurisdiction federal --year YYYY
    python scripts/scaffold_year.py --jurisdiction california --year YYYY

Check: stubs exist; params import raises (fail-closed).

## 3. Dual-transcribe params (Layer 1)

Transcriber A fills `params/<juris>/yYYYY.py` from official publications,
every value cited. Transcriber B — AIR-GAPPED: never reads A's module,
any params y-module, or tests/ — fills the attestation stub the same way.
Check: `pytest tests/test_params_attestation.py` green. Disagreement →
human adjudication, never edit-to-agree.

## 4. Ingest the tax table (Layer 2)

    python scripts/ingest_tax_table.py --jurisdiction federal --year YYYY
    python scripts/ingest_tax_table.py --jurisdiction california --year YYYY

Check: `pytest tests/test_tax_table_oracle.py` green — the published
table and the transcribed brackets now cross-validate each other.

## 5. Diff / probe mappings (Layer 4)

For each form (stems in `tenforty/mappings/catalog.py`):

    python scripts/diff_pdf_fields.py \
        --old pdfs/<juris>/PREV/<stem>.pdf --new pdfs/<juris>/YYYY/<stem>.pdf

IDENTICAL → add the year to the mapping via `inherit_pdf_fields` (or
point at the shared payload). CHANGED → probe
(`python scripts/probe_pdf_fields.py --pdf pdfs/<juris>/YYYY/<stem>.pdf`),
render, read markers, write the year's mapping from what you SEE, and
commit the probe PDF as evidence. Never type a field name you didn't
probe or inherit.
Check: `pytest tests/test_mapping_fields_on_template.py` green.

RENUMBERING TRAP (the reason the marker-probe is mandatory for CHANGED
forms): the IRS reassigns EXISTING field names to different lines between
years, so a mapped path can EXIST on the new template at the WRONG line.
Path existence, `diff_pdf_fields` name-set equality, and `/Rect` coordinate
matching are NOT evidence — a wrong-but-existing path passes all of them.
Only a rendered-position read (or a filled-emit read-back) is evidence.
  SECOND-ORDER COROLLARY (subtler, and it bites cross-year inheritance):
  an IDENTICAL field-NAME inventory across two years does NOT imply an
  identical field-to-LINE assignment. A form can keep every field name and
  still shift which line each sits on (e.g. Form 1120-S Schedule K: line 16a
  "Tax-exempt interest income" is f3_42 in 2023 but f3_43 in 2024/2025 —
  same 48-name inventory, one-field line shift). So "the differ says
  IDENTICAL, therefore inherit is safe" is only true for a payload you have
  filled-emit-verified on THAT year's own template. When you correct one
  year's cell against another's, filled-emit BOTH templates before trusting
  either — an adjudication is a hypothesis until each render confirms it.

## 6. Declare the year

Add YYYY to the tuples in `tenforty/years.py` (and `WORKBOOK_YEARS` if
step 1's workbook happened). For California: copy the prior-year packaged
divergence catalog to
`tenforty/params/california/divergences/yYYYY.yaml`, do a conformity review
against the new year's FTB Pub 1001, and adjust rows (ids stay stable across
years) until the schema gates pass — conformity changes are HUMAN JUDGMENT.
There is no `.fods` regeneration: the catalog YAML is the single
runtime-loaded source of truth (see the CA divergence catalog redesign,
docs/specs/2026-07-19-ca-divergence-catalog-redesign.md §3).
Check: `pytest tests/test_year_completeness_gate.py` green — this is the
"year is complete" bit flipping on. Attestation-window failures here mean
a law-scope review (see the gate's message), not a mechanical extension.

## 7. Full fast suite

    python -m pytest tests/ -q

## 8. Acceptance gate, if a workbook exists (Layer 6, slow)

PRISTINE-WORKBOOK smoke FIRST (before wiring the year): a vendor workbook
is an oracle only after it is proven blank. Open the untouched download and
verify every data-entry region is empty (e.g. scan the F8949 lot columns
AJ–AP on 8949A/8949B — they must hold only header text, no stray numbers)
and that computed outputs sit at their zero/base state. Distributed vendor
files ship with stray example data left in otherwise-empty cells (a TY2023
workbook carried a hardcoded -2,800 at 8949A!AP115, the last row of the
box-D sum range, which silently understated capital gain). Anything nonblank
in a data-entry region is junk to clear (surgical, documented) — NOT a rule
difference.

Then wire the year (`F1040.INPUTS/OUTPUTS[YYYY] = inherit(PREV, {})`,
`SHEET_MAP[YYYY] = dict(SHEET_MAP[PREV])`) and run the native-vs-oracle
cell-drift smoke over one scenario before the full gate: a residual
mismatch you cannot attribute to a moved cell is a STOP-and-report.

    python -m pytest tests/test_f1040_spine_oracle.py -v

Penny-parity for every workbook year, including the new one.

## 9. Reconciliation, if a return was filed for YYYY (Layer 7)

    python scripts/reconcile_federal.py ...   # see script --help
    python scripts/reconcile_ca540.py ...

External, PII-isolated, non-gating. Mismatches are adjudication
candidates in either direction (the filed return may be the wrong side).
