"""PDF field mapping for FTB 2025 Schedule D (540).

Mirrors the five-registry design from `pdf_f540.py` and `pdf_sch_ca.py`.
`sch_d_540.compute()` now emits three keys driven by worksheet entries:
`sch_d_540_net_capital_gain` (federal Sch D net, line 16),
`sch_d_540_total_subtractions` (line 12a subtraction total → Sch CA Col B),
and `sch_d_540_total_additions` (line 12b addition total → Sch CA Col C).

- `_MAPPING_2025` — direct compute_key → PDF-field-path. Five entries:
  the three compute outputs (line 8 net gain/loss, line 12a subtraction
  total, line 12b addition total) plus two `[PLANNED]`
  orchestrator-supplied keys (filer name on line above row 1, filer SSN
  in the box to its right).
- `_AGGREGATIONS_2025` — empty for Sch D (540). The form has no PDF cell
  that receives a sum of multiple compute keys; per-row column totals
  (lines 4, 5, 7) are within-form arithmetic and are SUPPRESSED in v1
  rather than synthesised at fill time.
- `_DERIVATIONS_2025` — two entries: line 10 (federal Sch D net)
  passthrough and line 11 (CA gain from line 8 / loss from line 9).
  Lines 10 and 11 display the federal and CA net capital gain so that
  the §A line 7a flow-through to Schedule CA reads correctly.
- `_SUPPRESSED_2025` — extended SP3 SUPPRESSED semantics: includes
  (a) all 110 detail-row cells (rows 1a..1v columns a–e) — these are
  per-transaction inputs that v1 does not enumerate; the federal Sch D
  worksheet is the source of truth, and (b) line 2 K-1 net (d/e), line 3
  capital gain distributions, lines 4–7 (within-form sums of the
  detail rows + carryover), line 9 ($3,000/$1,500 loss limit; v1
  defers loss-limit display to consumers reading the federal Sch D).
  Lines 12a/12b are no longer suppressed — they are driven by
  `sch_d_540_total_subtractions` and `sch_d_540_total_additions` in
  `_MAPPING_2025`.
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
    has a small fixed set of compute keys (federal net, CA net,
    subtraction total, addition total, plus orchestrator-supplied
    header keys); the partition that matters here is which PDF cells
    the filler is responsible for vs. silently leaving blank.
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
    # `sch_d_540_net_capital_gain` = irs_round(federal Sch D line 16).
    "sch_d_540_net_capital_gain":   "540 sch D - 4018",
    # Page 4 — Lines 12a/12b: federal-state divergence delta routed to
    # Schedule CA (540) §A line 7a Col B/C. Driven by worksheet entries
    # accumulated in `sch_d_540.compute()`.
    "sch_d_540_total_subtractions": "540 sch D - 4022",  # line 12a → Sch CA Col B
    "sch_d_540_total_additions":    "540 sch D - 4023",  # line 12b → Sch CA Col C
}


# No PDF cell on Sch D (540) receives a sum of multiple compute keys
# at fill time. Within-form sums (lines 4, 5, 7) are SUPPRESSED in v1
# rather than synthesised; the federal Sch D worksheet is the source of
# truth for individual transactions and within-form totals.
_AGGREGATIONS_2025: dict[str, tuple[str, ...]] = {}


# PDF cells whose value is derived from compute outputs at fill time.
# Derivation lambdas consume compute keys via `c[...]`. Keys may be
# either widget-mapped (also appearing as a value in `_MAPPING_2025`)
# or compute-only (emitted by `sch_d_540.compute()` for derivation use
# without a direct PDF cell, e.g. `sch_d_540_federal_net`).
_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 10 — federal Sch D line 16 (pre-CA-divergence). Distinct
    # from line 8 (CA net = federal_net − subs + adds) when worksheet
    # entries exist; equal otherwise.
    "540 sch D - 4020": lambda c: c["sch_d_540_federal_net"],
    # Line 11 — California gain from line 8 or loss from line 9. v1
    # does not implement a separate CA loss-limit; consumes the CA
    # net (line 8) directly.
    "540 sch D - 4021": lambda c: c["sch_d_540_net_capital_gain"],
}


# PDF cells with no direct compute backing on the 2025 form. Two subsets:
#   (a) detail rows 1a..1v columns a–e (110 cells) — per-transaction
#       inputs not enumerated by v1; federal Sch D worksheet is the
#       source of truth.
#   (b) within-form sums (lines 2, 3, 4, 5, 6, 7, 9) — derivable from
#       (a) but v1 does not enumerate transactions, so suppression is
#       the honest v1 behaviour rather than rendering 0 in a sum cell.
# Lines 12a/12b are NOT suppressed; they are mapped in `_MAPPING_2025`
# and driven by worksheet entries via `sch_d_540.compute()`.
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
})


# The 2025 Sch D (540) PDF has no /Btn widgets; all 125 named widgets
# are /Tx. No checkbox states are required.
_CHECKBOX_STATES_2025: dict[str, str] = {}


PdfSchD540._MAPPINGS = {2025: _MAPPING_2025}
