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

One channel: the attachment rides on the model entry it evidences. There is
deliberately **no** free-floating attachment list — a document type tenforty
doesn't model is income tenforty can't compute, so no packet for such a
return exists to attach it to. If a document type is ever modeled (1099-R,
W-2G, 8949 summary statements), its attachment arrives the same way: a `pdf`
field on that model's entry.

`W2` gains an optional `pdf` field:

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
- it also joins the **california** packet iff that W-2 has `state == "CA"`
  and `state_tax_withheld > 0` (the existing CA-attribution channel;
  unattributed withholding W-2s are already refused at load for CA returns).
  The routing is derived from the W-2's own data, not from whether a CA
  return is present — a `california` routing is simply inert when no CA
  forms are emitted, since a packet only assembles when it has at least one
  emitted member.

`pdf` names *the evidence document for this W-2*, whatever form it takes —
normally the employer's Copy B, but a Form 4852 substitute is equally valid
here when the issuer copy is missing or wrong (tenforty attaches it
verbatim; the 4852's own preparation is out of scope).

Paths resolve relative to the scenario YAML's directory, so real scenarios
point into the user's document folders and no personal file ever needs to
live near the repo.

## Models and loading

- `W2` gains `pdf: str | None = None` (loader-resolved to an absolute `Path`
  on the loaded object).
- New frozen dataclass `SourceDocument` in `models.py`: `path: Path`,
  `kind: str` (only `"w2"` today; future models add kinds), `packets:
  tuple[str, ...]`. W-2 `pdf` fields are normalized into these records at
  load — with packets derived from the routing rules above — so packet
  assembly consumes one uniform, already-routed channel and needs no model
  knowledge.
- `Scenario` gains `source_documents: list[SourceDocument]` (default empty)
  carrying the normalized records.
- `load_scenario` validation, fail closed with a clear message naming the
  offending W-2 entry: path exists; file opens under `pypdf` and has
  ≥ 1 page.

## Packet assembly

`pdf_packet.py` gains a `source_documents` parameter alongside the existing
`emitted` dict (threaded through `assemble_all`). Attachments enter through
their own channel; the emitted-key partition invariant and `classify_key` are
untouched.

**Placement:** within each packet, source documents are inserted immediately
after the main form's pages (1040 / 540) and before the first schedule —
mirroring the "Attach Form(s) W-2 here" staple point on page 1. Within the
block, documents appear in `w2s` declaration order; future kinds append
after `w2` in a fixed kind order.

**Manifest:** each attachment contributes one console line — filename,
kind, page count, and the comma-joined names of the packets it joined
(only packets actually assembled).

**Compute-only years:** packets cannot be assembled at all, so neither the
splice nor the gate ever runs there; declared source documents are simply
unused. No refusal beyond what compute-only already imposes.

## Warn + attest gate (emit-time, not load-time)

New `TaxReturnConfig` flag `acknowledges_no_source_documents: bool = False`,
named in the existing `acknowledges_*` family.

**Trigger:** at packet-emit time, **any** `W2` with no `pdf`. The IRS
attachment rule for W-2s is not withholding-conditional — Copy B attaches
for every W-2 (the withholding condition applies to W-2G/1099-R, which are
out of scope). When triggered and the flag is not set, packet emission
**refuses** with an error naming each employer whose W-2 is missing and the
flag that overrides.

`pdf` stays optional at the schema layer precisely because this gate exists:
compute-only scenarios must load and compute without attachment paths, and
the mandatory-ness is enforced at the moment a filing packet is actually
produced.

This gate deliberately lives at emit, not in the load/compute `Attestation`
registry: compute-only scenarios (the entire synthetic test corpus, comps
runs) declare W-2 withholding constantly and must not be forced to carry
attachment flags. Only a scenario that is actually producing filing packets
is held to the attachment standard. Existing emit-path tests set the flag
(one line per fixture) or attach synthetic PDFs.

Per the attestation-audit norm, the refusal must be *proved able to fire*: a
test constructs a W-2 with no `pdf` (including a zero-withholding one), runs
the emit path, and asserts the refusal — not merely that the flag exists.

## Testing

Synthetic PDFs only, generated in-test with `pypdf.PdfWriter` blank pages in
temp directories — no real documents in or near the repo. All tests subclass
`unittest.TestCase`. Coverage:

- placement: attachment block lands between main-form pages and first
  schedule; intra-block kind ordering; declaration-order stability
- routing: W-2 pdf → federal always; → california iff CA withholding
  attributed and `ca540` present; no CA routing without CA withholding
- load failures: missing file, non-PDF file, zero-page PDF — each refused
  with the W-2 entry named
- gate: refusal fires for any W-2 without pdf, including zero-withholding;
  flag clears it; compute-only scenarios unaffected
- manifest: attachment lines present with filename/kind/pages/packet
- partition invariant: unchanged behavior for emitted keys with attachments
  present

## Out of scope this round

- Appending a copy of the assembled federal return behind the 540 (FTB
  federal-copy rule) — user assembles manually; candidate follow-on.
- Generating W-2/1099 facsimiles, or preparing Form 4852 (an existing 4852
  PDF may be attached via a W-2's `pdf` field).
- Parsing attachment contents for any purpose.
- Any attachment channel for unmodeled document types (1099-R, W-2G,
  brokerage statements). Income tenforty can't model can't be computed, so
  no packet exists to attach evidence to; if such a type is modeled later,
  its attachment arrives as a `pdf` field on that model, like the W-2.
- Entity (1120-S) and extension (4868) packets — no attachment rules needed
  there today.
- Amendment (1040-X) packets: the amendment pipeline has its own packet
  manifest and its own "attachments" concept (changed forms), and paper
  1040-X filings also want W-2 copies — a follow-on once this lands in the
  regular emit path. To avoid collision with that existing term, this
  feature is named "source documents" throughout the code.
