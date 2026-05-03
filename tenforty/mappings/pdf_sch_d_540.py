"""PDF field mapping for FTB 2025 Schedule D (540).

Mirrors the five-registry design from `pdf_f540.py` and `pdf_sch_ca.py`.
The Sch D (540) v1 surface is intentionally narrow because v1 gates
federal-state divergence (§1202 QSBS, §1045 QSBS rollover, §1400Z QOZ
deferrals, pre-1987 inherited basis, Peace Corps principal residence)
behind the
`acknowledges_no_ca_sch_d_federal_state_divergence` attestation. With
the attestation True, `sch_d_540.compute()` emits exactly one key —
`sch_d_540_net_capital_gain` — equal to federal Sch D net (line 16).

- `_MAPPING_2025` — direct compute_key → PDF-field-path. Three entries:
  the single compute output (line 8 net gain/loss) plus two `[PLANNED]`
  orchestrator-supplied keys (filer name on line above row 1, filer SSN
  in the box to its right).
- `_AGGREGATIONS_2025` — empty for Sch D (540). The form has no PDF cell
  that receives a sum of multiple compute keys; per-row column totals
  (lines 4, 5, 7) are within-form arithmetic and are SUPPRESSED in v1
  rather than synthesised at fill time.
- `_DERIVATIONS_2025` — two entries: line 10 (federal Sch D net)
  passthrough and line 11 (CA gain from line 8 / loss from line 9).
  Under the v1 zero-divergence attestation, line 10 == line 8 ==
  line 11; the form still benefits from displaying these explicitly so
  the §A line 7a flow-through to Schedule CA (lines 12a/12b) reads
  correctly as zero rather than blank.
- `_SUPPRESSED_2025` — extended SP3 SUPPRESSED semantics: includes
  (a) all 110 detail-row cells (rows 1a..1v columns a–e) — these are
  per-transaction inputs that v1 does not enumerate; the federal Sch D
  worksheet is the source of truth, (b) line 2 K-1 net (d/e), line 3
  capital gain distributions, lines 4–7 (within-form sums of the
  detail rows + carryover), line 9 ($3,000/$1,500 loss limit; v1
  defers loss-limit display to consumers reading the federal Sch D),
  and (c) lines 12a/12b (federal-state divergence delta routed to
  Sch CA §A line 7a Col B/C; structurally zero under the v1 no-
  divergence attestation, suppressed rather than rendered as 0 to
  avoid noise on a divergence-only cell).
- `_CHECKBOX_STATES_2025` — empty for Sch D (540). The 2025 form has
  no /Btn widgets; all 125 named widgets are /Tx text widgets.

Field paths come from a direct probe of
`pdfs/california/2025/sch_d_540.pdf` via pypdf on 2026-04-29.
Tooltip-verified (`/TU` annotations on each widget identify line +
column). The flat naming convention is `'540 sch D - PRRR'` where P is
page index (1–4) and RRR is per-page sequence; pypdf reports all 125
widgets as named (no unnamed visual placeholders observed).
"""

from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping


class PdfSchD540(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for FTB Schedule D (540).

    Five-registry design (see module docstring). The partition invariant
    enforced by the mapping test is over PDF field names: every named
    widget on the 2025 form is OWNED by exactly one of `_MAPPING_<year>`
    (as a value), `_AGGREGATIONS_<year>` (as a key),
    `_DERIVATIONS_<year>` (as a key), or `_SUPPRESSED_<year>`. This
    differs from f540's compute-key-side partition because Sch D (540)
    v1 has only one compute key in scope; the partition that matters
    here is which PDF cells the filler is responsible for vs. silently
    leaving blank.
    """

    _FORM_NAME = "Schedule D (540)"
    _MAPPINGS: dict[int, dict[str, str]] = {}  # populated below after _MAPPING_2025

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        if year == 2025:
            return _AGGREGATIONS_2025
        raise ValueError(f"No Schedule D (540) aggregations for year {year}")

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year == 2025:
            return _DERIVATIONS_2025
        raise ValueError(f"No Schedule D (540) derivations for year {year}")

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year == 2025:
            return _SUPPRESSED_2025
        raise ValueError(f"No Schedule D (540) suppressions for year {year}")

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        if year == 2025:
            return _CHECKBOX_STATES_2025
        raise ValueError(f"No Schedule D (540) checkbox states for year {year}")


# Direct 1:1 mappings — compute keys with a direct PDF cell + [PLANNED]
# orchestrator-supplied keys reserved for T18/T19 wiring.
_MAPPING_2025: dict[str, str] = {
    # Page 1 — Header ([PLANNED]: orchestrator-supplied)
    "sch_d_540_taxpayer_name":      "540 sch D - 1001",
    "sch_d_540_taxpayer_ssn":       "540 sch D - 1002",
    # Page 4 — Line 8: Net gain or (loss). Combine line 4 and line 7.
    # This is the sole compute output of `sch_d_540.compute()` —
    # `sch_d_540_net_capital_gain` = irs_round(federal Sch D line 16).
    "sch_d_540_net_capital_gain":   "540 sch D - 4018",
}


# No PDF cell on Sch D (540) receives a sum of multiple compute keys
# at fill time. Within-form sums (lines 4, 5, 7) are SUPPRESSED in v1
# rather than synthesised; the federal Sch D worksheet is the source of
# truth for individual transactions and within-form totals.
_AGGREGATIONS_2025: dict[str, tuple[str, ...]] = {}


# PDF cells whose value is derived from compute outputs at fill time.
#
# Convention: derivation lambdas consume compute keys but do not own
# them. Keys referenced via `c[...]` must already appear in
# `_MAPPING_2025`, `_AGGREGATIONS_2025`, or `_SUPPRESSED_2025`. (The
# only consumed key here, `sch_d_540_net_capital_gain`, is owned in
# `_MAPPING_2025`.) Derivations that need federal-results passthrough
# read from a separate compute key reserved by the orchestrator.
_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 10 — federal Form 1040 line 7a (federal Sch D net). Under
    # the v1 zero-divergence attestation this equals line 8; we
    # consume `sch_d_540_net_capital_gain` directly rather than
    # introducing a separate orchestrator-supplied key for the
    # federal value.
    "540 sch D - 4020": lambda c: c["sch_d_540_net_capital_gain"],
    # Line 11 — California gain from line 8 or loss from line 9. With
    # zero divergence and no separate loss-limit treatment in v1,
    # this is the same value as line 10 (and line 8).
    "540 sch D - 4021": lambda c: c["sch_d_540_net_capital_gain"],
}


# PDF cells with no direct compute backing on the 2025 form. Three
# subsets:
#   (a) detail rows 1a..1v columns a–e (110 cells) — per-transaction
#       inputs not enumerated by v1; federal Sch D worksheet is the
#       source of truth.
#   (b) within-form sums (lines 2, 3, 4, 5, 6, 7, 9) — derivable from
#       (a) but v1 does not enumerate transactions, so suppression is
#       the honest v1 behaviour rather than rendering 0 in a sum cell.
#   (c) lines 12a/12b — federal-state divergence delta. Structurally
#       zero under the v1 no-divergence attestation; suppressing
#       avoids rendering "0" on a divergence-only cell that, when
#       blank, signals "no divergence" more clearly to a human reader.
_SUPPRESSED_2025: frozenset[str] = frozenset({
    # (a) Detail rows 1a..1f (page 1, 1003..1032 = 30 cells)
    "540 sch D - 1003", "540 sch D - 1004", "540 sch D - 1005",
    "540 sch D - 1006", "540 sch D - 1007",
    "540 sch D - 1008", "540 sch D - 1009", "540 sch D - 1010",
    "540 sch D - 1011", "540 sch D - 1012",
    "540 sch D - 1013", "540 sch D - 1014", "540 sch D - 1015",
    "540 sch D - 1016", "540 sch D - 1017",
    "540 sch D - 1018", "540 sch D - 1019", "540 sch D - 1020",
    "540 sch D - 1021", "540 sch D - 1022",
    "540 sch D - 1023", "540 sch D - 1024", "540 sch D - 1025",
    "540 sch D - 1026", "540 sch D - 1027",
    "540 sch D - 1028", "540 sch D - 1029", "540 sch D - 1030",
    "540 sch D - 1031", "540 sch D - 1032",
    # (a) Detail rows 1g..1m (page 2, 2001..2035 = 35 cells)
    "540 sch D - 2001", "540 sch D - 2002", "540 sch D - 2003",
    "540 sch D - 2004", "540 sch D - 2005",
    "540 sch D - 2006", "540 sch D - 2007", "540 sch D - 2008",
    "540 sch D - 2009", "540 sch D - 2010",
    "540 sch D - 2011", "540 sch D - 2012", "540 sch D - 2013",
    "540 sch D - 2014", "540 sch D - 2015",
    "540 sch D - 2016", "540 sch D - 2017", "540 sch D - 2018",
    "540 sch D - 2019", "540 sch D - 2020",
    "540 sch D - 2021", "540 sch D - 2022", "540 sch D - 2023",
    "540 sch D - 2024", "540 sch D - 2025",
    "540 sch D - 2026", "540 sch D - 2027", "540 sch D - 2028",
    "540 sch D - 2029", "540 sch D - 2030",
    "540 sch D - 2031", "540 sch D - 2032", "540 sch D - 2033",
    "540 sch D - 2034", "540 sch D - 2035",
    # (a) Detail rows 1n..1t (page 3, 3001..3035 = 35 cells)
    "540 sch D - 3001", "540 sch D - 3002", "540 sch D - 3003",
    "540 sch D - 3004", "540 sch D - 3005",
    "540 sch D - 3006", "540 sch D - 3007", "540 sch D - 3008",
    "540 sch D - 3009", "540 sch D - 3010",
    "540 sch D - 3011", "540 sch D - 3012", "540 sch D - 3013",
    "540 sch D - 3014", "540 sch D - 3015",
    "540 sch D - 3016", "540 sch D - 3017", "540 sch D - 3018",
    "540 sch D - 3019", "540 sch D - 3020",
    "540 sch D - 3021", "540 sch D - 3022", "540 sch D - 3023",
    "540 sch D - 3024", "540 sch D - 3025",
    "540 sch D - 3026", "540 sch D - 3027", "540 sch D - 3028",
    "540 sch D - 3029", "540 sch D - 3030",
    "540 sch D - 3031", "540 sch D - 3032", "540 sch D - 3033",
    "540 sch D - 3034", "540 sch D - 3035",
    # (a) Detail rows 1u..1v (page 4, 4001..4010 = 10 cells)
    "540 sch D - 4001", "540 sch D - 4002", "540 sch D - 4003",
    "540 sch D - 4004", "540 sch D - 4005",
    "540 sch D - 4006", "540 sch D - 4007", "540 sch D - 4008",
    "540 sch D - 4009", "540 sch D - 4010",
    # (b) Line 2 — K-1 net (d) loss / (e) gain
    "540 sch D - 4011",
    "540 sch D - 4012",
    # (b) Line 3 — Capital gain distributions (1099-DIV box 2a)
    "540 sch D - 4013",
    # (b) Lines 4–7 — within-form column totals + 2024 carryover
    "540 sch D - 4014",  # line 4: total 2025 gains (Σ col e)
    "540 sch D - 4015",  # line 5: total 2025 loss (Σ col d)
    "540 sch D - 4016",  # line 6: CA capital loss carryover from 2024
    "540 sch D - 4017",  # line 7: total 2025 loss (line 5 + line 6)
    # (b) Line 9 — smaller of loss / $3,000 / $1,500 MFS
    "540 sch D - 4019",
    # (c) Lines 12a/12b — federal-state divergence delta routed to
    # Schedule CA (540) §A line 7a Col B/C. Structurally zero under
    # the v1 zero-divergence attestation; rendering "0" on a
    # divergence-only cell would add noise.
    "540 sch D - 4022",  # line 12a: line 10 − line 11 (Col B add to Sch CA)
    "540 sch D - 4023",  # line 12b: line 11 − line 10 (Col C add to Sch CA)
})


# The 2025 Sch D (540) PDF has no /Btn widgets; all 125 named widgets
# are /Tx. No checkbox states are required.
_CHECKBOX_STATES_2025: dict[str, str] = {}


PdfSchD540._MAPPINGS = {2025: _MAPPING_2025}
