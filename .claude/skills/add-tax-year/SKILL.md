---
name: add-tax-year
description: Port tenforty to a new tax year (forward or backfill) — fetch assets, dual-transcribe params, ingest tax tables, diff/probe mappings, flip the completeness gate green. Use when asked to add/support/backfill a tax year.
---

Follow `docs/runbooks/add-tax-year.md` exactly, in order. Non-negotiables:
- Steps 0 and 6's California catalog are human-judgment gates — surface, don't improvise.
- Step 1 downloads and any workbook fetch are USER-approved actions.
- Step 3's transcriber B is air-gapped (no params y-modules, no tests/) — a leaked value voids the attestation.
- Red checks are never satisfied by weakening the check.
