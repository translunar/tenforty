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

## 6. Declare the year

Add YYYY to the tuples in `tenforty/years.py` (and `WORKBOOK_YEARS` if
step 1's workbook happened). For California: port the divergence catalog
(`spreadsheets/california/YYYY/sch_ca_divergences-YYYY.catalog.yaml`, then
regenerate the `.fods` via `scripts/build_sch_ca_fods.py`) — conformity
changes are HUMAN JUDGMENT.
Check: `pytest tests/test_year_completeness_gate.py` green — this is the
"year is complete" bit flipping on. Attestation-window failures here mean
a law-scope review (see the gate's message), not a mechanical extension.

## 7. Full fast suite

    python -m pytest tests/ -q

## 8. Acceptance gate, if a workbook exists (Layer 6, slow)

    python -m pytest tests/test_f1040_spine_oracle.py -v

Penny-parity for every workbook year, including the new one.

## 9. Reconciliation, if a return was filed for YYYY (Layer 7)

    python scripts/reconcile_federal.py ...   # see script --help
    python scripts/reconcile_ca540.py ...

External, PII-isolated, non-gating. Mismatches are adjudication
candidates in either direction (the filed return may be the wrong side).
