"""Per-form Python compute modules.

Each form module exposes a `compute(...)` function returning a dict keyed
to PDF field names expected by the matching mapping in
`tenforty/mappings/pdf_<form>.py`, eliminating a separate translation
layer.

Two signatures coexist:

- `compute(scenario, upstream)` — for forms that need scenario data
  (identity, address, election fields). Used by `f4868.compute`.
- `compute(raw_1040, upstream)` — for the 1040 wrapper specifically,
  which thinly re-keys the raw XLSX engine output to PDF field names
  while the 1040 math still lives in the oracle workbook. The
  orchestrator owns engine invocation.

`upstream` is a dict keyed by form slug (e.g. `"f1040"`) carrying
previously-computed results from forms earlier in the dependency order.
Forms are computed in that order; the orchestrator collects each result
into `upstream` before invoking the next form.
"""
