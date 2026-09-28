# Source-Document Attachments in Emitted Packets — Design

**Date:** 2026-09-27
**Status:** Draft for review

## Goal

A paper-filed return is not just the forms tenforty computes: the IRS wants
W-2 Copy B (and W-2G / 1099-R when they show federal withholding) attached to
the 1040, and the FTB wants withholding documents attached to the 540 when
they show California withholding. Today `pdf_packet.py` assembles only the
forms tenforty itself emitted; the taxpayer's real issued documents have no
way into a packet. This feature lets a scenario declare those PDFs and has
packet assembly splice them in at the right position, with a warn-and-attest
gate so a forgotten W-2 cannot silently ship.

Explicitly **not** the goal: generating W-2/1099 facsimiles from scenario
data. Those are issuer documents; a taxpayer-produced copy is not a valid
attachment (the lawful substitute is Form 4852, out of scope). tenforty
attaches the real files it is pointed at and never parses their contents.

## YAML surface

Two channels, split by whether tenforty models the underlying document.

**Modeled documents (W-2 today):** the attachment rides on the model entry it
evidences. `W2` gains an optional `pdf` field:

```yaml
w2s:
  - employer: "Acme Corp"
    wages: 50000
    federal_tax_withheld: 6000
    state_wages: 50000
    state_tax_withheld: 2500
    state: CA
    pdf: "W-2 Acme 2024.pdf"        # resolved relative to the scenario YAML
```

Routing is derived from declared data — no PDF parsing:

- every W-2 `pdf` joins the **federal_individual** packet;
- it also joins the **california** packet iff the scenario has a `ca540`
  return and that W-2 has `state == "CA"` and `state_tax_withheld > 0`
  (the existing CA-attribution channel; unattributed withholding W-2s are
  already refused at load for CA returns).

**Unmodeled documents:** a top-level `source_documents:` list for anything
tenforty has no model for:

```yaml
source_documents:
  - path: "1099-R Broker 2024.pdf"
    kind: 1099r                      # w2g | 1099r | other
  - path: "Form 4852 substitute.pdf"
    kind: other
    packets: [federal, california]   # optional; default [federal]
```

- `kind` is required: `w2g`, `1099r`, or `other`. `kind: w2` is **rejected**
  here — W-2s must ride on their `w2s` entry so routing and validation stay
  data-driven.
- `packets` defaults to `[federal]`. Adding `california` is the user's
  explicit statement that the document shows CA withholding; tenforty cannot
  verify this and does not try. Declaring `california` when the scenario has
  no `ca540` is a load error.
- If tenforty later models a document type (e.g. 1099-R), its attachment
  migrates to the model-entry channel and the kind is retired from this list.

Both channels resolve `path`/`pdf` relative to the scenario YAML's directory,
so real scenarios point into the user's document folders and no personal file
ever needs to live near the repo.

## Models and loading

- `W2` gains `pdf: str | None = None` (loader-resolved to an absolute `Path`
  on the loaded object).
- New frozen dataclass `SourceDocument` in `models.py`: `path: Path`,
  `kind: str` (`"w2g" | "1099r" | "other"`), `packets: tuple[str, ...]`.
  W-2 attachments are normalized into `SourceDocument(kind="w2")` records
  internally at load, so packet assembly consumes one uniform channel.
- `Scenario` gains `source_documents: list[SourceDocument]`
  (default empty) carrying the normalized union of both channels.
- `load_scenario` validation, fail closed with a clear message naming the
  offending entry: path exists; file opens under `pypdf` and has ≥ 1 page;
  `kind` in the allowed set; `packets` values in `{federal, california}`;
  `california` only when `ca540` is present.

## Packet assembly

`pdf_packet.py` gains a `source_documents` parameter alongside the existing
`emitted` dict (threaded through `assemble_all`). Attachments enter through
their own channel; the emitted-key partition invariant and `classify_key` are
untouched.

**Placement:** within each packet, source documents are inserted immediately
after the main form's pages (1040 / 540) and before the first schedule —
mirroring the "Attach Form(s) W-2 here" staple point on page 1. Order within
the block: `w2` (in `w2s` declaration order), then `w2g`, `1099r`, `other`
(each in declaration order).

**Manifest:** each attachment contributes a line per packet it joins:
filename, kind, page count, packet name. Documents attached against the
grain (any `other`, or a `california` routing on an unmodeled kind) carry a
note that tenforty did not verify the attachment rule — a warning, never a
block.

**Compute-only years:** packets cannot be assembled at all; if source
documents are declared, the existing "attachment emit unavailable" note in
the manifest also lists them as declared-but-unassembled. No refusal beyond
what compute-only already imposes.

## Warn + attest gate (emit-time, not load-time)

New `TaxReturnConfig` flag `acknowledges_no_source_documents: bool = False`,
named in the existing `acknowledges_*` family.

**Trigger:** at packet-emit time, any `W2` with `federal_tax_withheld > 0`
and no `pdf` — or, for a CA return, any W-2 with CA-attributed
`state_tax_withheld > 0` and no `pdf`. When triggered and the flag is not
set, packet emission **refuses** with an error naming each employer whose
W-2 is missing and the flag that overrides.

This gate deliberately lives at emit, not in the load/compute `Attestation`
registry: compute-only scenarios (the entire synthetic test corpus, comps
runs) declare W-2 withholding constantly and must not be forced to carry
attachment flags. Only a scenario that is actually producing filing packets
is held to the attachment standard. Existing emit-path tests set the flag
(one line per fixture) or attach synthetic PDFs.

Per the attestation-audit norm, the refusal must be *proved able to fire*: a
test constructs a withholding W-2 with no `pdf`, runs the emit path, and
asserts the refusal — not merely that the flag exists.

## Testing

Synthetic PDFs only, generated in-test with `pypdf.PdfWriter` blank pages in
temp directories — no real documents in or near the repo. All tests subclass
`unittest.TestCase`. Coverage:

- placement: attachment block lands between main-form pages and first
  schedule; intra-block kind ordering; declaration-order stability
- routing: W-2 pdf → federal always; → california iff CA withholding
  attributed and `ca540` present; `source_documents` default `[federal]`;
  explicit `california` honored
- load failures: missing file, non-PDF file, zero-page PDF, `kind: w2` in
  `source_documents`, `california` without `ca540` — each refused with the
  entry named
- gate: refusal fires (withholding W-2, no pdf, no flag); flag clears it;
  CA-withholding variant fires for CA returns; compute-only scenarios
  unaffected
- manifest: attachment lines present with filename/kind/pages/packet;
  unverified-rule note on `other`
- partition invariant: unchanged behavior for emitted keys with attachments
  present

## Out of scope this round

- Appending a copy of the assembled federal return behind the 540 (FTB
  federal-copy rule) — user assembles manually; candidate follow-on.
- Generating W-2/1099 facsimiles or Form 4852 support.
- Parsing attachment contents for any purpose.
- Modeling 1099-R / W-2G data (their attachments use the unmodeled channel).
- Entity (1120-S) and extension (4868) packets — no attachment rules needed
  there today.
