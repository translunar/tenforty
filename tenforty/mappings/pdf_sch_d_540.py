"""PDF field mapping for FTB Schedule D (540) — TY2024 and TY2025.

Mirrors the five-registry design from `pdf_f540.py` and `pdf_sch_ca.py`.
`sch_d_540.compute()` now emits three keys driven by worksheet entries:
`sch_d_540_net_capital_gain` (federal Sch D net, line 16),
`sch_d_540_total_subtractions` (line 12a subtraction total → Sch CA Col B),
and `sch_d_540_total_additions` (line 12b addition total → Sch CA Col C).

TY2025 registries (`_*_2025`):
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

TY2024 registries (`_*_2024`):
- Same five-registry design and same five compute keys as 2025.
- Different field-naming scheme: `'540D - NNNN'` (no 'sch' segment,
  page-less numbering) vs. 2025's `'540 sch D - PRRR'`.
- Different page layout: all 22 detail rows 1a..1v fit on page 1
  (1003..1112), followed by lines 2–7 (1113..1119), then lines 8–12
  on page 2 (2001..2006). 125 named widgets total, all /Tx.
- `_SUPPRESSED_2024` covers (a) 110 detail-row cells (1003..1112),
  (b) within-form sums / carryover / loss-limit cells (1113..1119,
  2002) — 118 entries total.

Field paths come from a direct probe of the respective form PDFs via
pypdf. Tooltip-verified (`/TU` annotations on each widget identify
line + column). Probed 2025 on 2026-04-29; 2024 on 2026-06-19.
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
        if year not in _AGGREGATIONS_BY_YEAR:
            raise ValueError(f"No Schedule D (540) aggregations for year {year}")
        return _AGGREGATIONS_BY_YEAR[year]

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in _DERIVATIONS_BY_YEAR:
            raise ValueError(f"No Schedule D (540) derivations for year {year}")
        return _DERIVATIONS_BY_YEAR[year]

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year not in _SUPPRESSED_BY_YEAR:
            raise ValueError(f"No Schedule D (540) suppressions for year {year}")
        return _SUPPRESSED_BY_YEAR[year]

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        if year not in _CHECKBOX_STATES_BY_YEAR:
            raise ValueError(f"No Schedule D (540) checkbox states for year {year}")
        return _CHECKBOX_STATES_BY_YEAR[year]


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


# ---------------------------------------------------------------------------
# TY2024 registries
# Field-naming scheme: '540D - NNNN' (no page prefix, no 'sch' segment).
# Probed from pdfs/california/2024/sch_d_540.pdf on 2026-06-19.
# ---------------------------------------------------------------------------

# Direct 1:1 mappings — same five compute keys as 2025, different PDF
# field paths. 2024 form layout: page 1 = header + all detail rows +
# lines 2–7; page 2 = lines 8–12.
_MAPPING_2024: dict[str, str] = {
    # Page 1 — Header ([PLANNED]: orchestrator-supplied)
    "sch_d_540_taxpayer_name":      "540D - 1001",
    "sch_d_540_taxpayer_ssn":       "540D - 1002",
    # Page 2 — Line 8: Net gain or (loss). Combine line 4 and line 7.
    # `sch_d_540_net_capital_gain` = irs_round(federal Sch D line 16).
    "sch_d_540_net_capital_gain":   "540D - 2001",
    # Page 2 — Lines 12a/12b: federal-state divergence delta routed to
    # Schedule CA (540) §A line 7a Col B/C. Driven by worksheet entries
    # accumulated in `sch_d_540.compute()`.
    "sch_d_540_total_subtractions": "540D - 2005",  # line 12a → Sch CA Col B
    "sch_d_540_total_additions":    "540D - 2006",  # line 12b → Sch CA Col C
}


# No PDF cell on Sch D (540) 2024 receives a sum of multiple compute
# keys at fill time. Within-form sums (lines 4, 5, 7) are SUPPRESSED.
_AGGREGATIONS_2024: dict[str, tuple[str, ...]] = {}


# PDF cells whose value is derived from compute outputs at fill time.
# Lambda bodies are identical to 2025; only the field-name keys differ.
_DERIVATIONS_2024: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 10 — federal Sch D line 16 (pre-CA-divergence). Distinct
    # from line 8 (CA net = federal_net − subs + adds) when worksheet
    # entries exist; equal otherwise.
    "540D - 2003": lambda c: c["sch_d_540_federal_net"],
    # Line 11 — California gain from line 8 or loss from line 9. v1
    # does not implement a separate CA loss-limit; consumes the CA
    # net (line 8) directly.
    "540D - 2004": lambda c: c["sch_d_540_net_capital_gain"],
}


# PDF cells with no direct compute backing on the 2024 form. Two subsets:
#   (a) detail rows 1a..1v columns a–e (1003..1112 = 110 cells) — per-
#       transaction inputs not enumerated by v1; federal Sch D worksheet
#       is the source of truth.
#   (b) within-form sums and carryover (1113..1119 = lines 2–7, 7 cells)
#       + line 9 loss limit (2002, 1 cell) — derivable from (a) but v1
#       does not enumerate transactions, so suppression is the honest v1
#       behaviour rather than rendering 0 in a sum cell.
# Lines 12a/12b are NOT suppressed; they are mapped in `_MAPPING_2024`
# and driven by worksheet entries via `sch_d_540.compute()`.
_SUPPRESSED_2024: frozenset[str] = frozenset(
    # (a) Detail rows 1a..1v (page 1, 1003..1112 = 110 cells)
    {f"540D - {n}" for n in range(1003, 1113)}
    # (b) Within-form sums / carryover / loss-limit (1113..1119 + 2002)
    | {f"540D - {n}" for n in range(1113, 1120)}
    | {"540D - 2002"}
)


# The 2024 Sch D (540) PDF has no /Btn widgets; all 125 named widgets
# are /Tx. No checkbox states are required.
_CHECKBOX_STATES_2024: dict[str, str] = {}


# ---------------------------------------------------------------------------
# TY2023 registries
# Field-naming scheme: bare zero-padded numbers ('1001', '2001', ...), no
# '540D'/'540 sch D' prefix — a third distinct FTB naming scheme. Each widget
# carries a descriptive /TU tooltip identifying its line; the mapping below was
# read from those tooltips on the 2023 template (probe committed as
# pdfs/california/2023/sch_d_540.probe.pdf) and filled-emit-verified: distinct
# values written to lines 8/10/11/12a/12b render on the correct lines of page 2.
# Layout matches 2024 (page 1 = header + detail rows 1a..1v + lines 2-7;
# page 2 = lines 8-12); only the field names differ.
# ---------------------------------------------------------------------------
_MAPPING_2023: dict[str, str] = {
    "sch_d_540_taxpayer_name":      "1001",  # /TU "Name or Names as shown on return"
    "sch_d_540_taxpayer_ssn":       "1002",  # /TU "Social Security Number ..."
    "sch_d_540_net_capital_gain":   "2001",  # /TU "Line 8 . Net gain or (loss)..."
    "sch_d_540_total_subtractions": "2005",  # /TU "Line 12 a. ... Sch CA §A line 7 col B"
    "sch_d_540_total_additions":    "2006",  # /TU "Line 12 b. ... col C"
}
_AGGREGATIONS_2023: dict[str, tuple[str, ...]] = {}
_DERIVATIONS_2023: dict[str, Callable[[Mapping[str, object]], object]] = {
    "2003": lambda c: c["sch_d_540_federal_net"],       # /TU "Line 10 . ... federal ... line 7"
    "2004": lambda c: c["sch_d_540_net_capital_gain"],  # /TU "Line 11 . California gain ..."
}
# Detail rows 1a..1v + within-form sums/carryover (1003..1119) and the line-9
# loss limit (2002) — no direct compute backing, same as 2024/2025.
_SUPPRESSED_2023: frozenset[str] = frozenset(
    {f"{n}" for n in range(1003, 1120)} | {"2002"}
)
_CHECKBOX_STATES_2023: dict[str, str] = {}


# ---------------------------------------------------------------------------
# TY2021 registries
# Field-naming scheme: "Text Field N" — a FOURTH distinct FTB naming scheme,
# disjoint from 2023's bare zero-padded numbers and 2024/2025's prefixed
# schemes. 2021 fresh air-gapped probe, controller-reconciled against the
# 2021 template (CA "Text Field N" namespace differs from 2023). Five
# compute-backed direct cells (header name/SSN, line 8 net gain, line 12a/12b
# Sch CA deltas) plus two derivations (lines 10/11 federal/CA net) are wired.
# Suppression is not populated for 2021.
# ---------------------------------------------------------------------------
_MAPPING_2021: dict[str, str] = {
    "sch_d_540_taxpayer_name":      "Text Field 2",
    "sch_d_540_taxpayer_ssn":       "Text Field 3",
    "sch_d_540_net_capital_gain":   "Text Field 121",  # Line 8
    "sch_d_540_total_subtractions": "Text Field 125",  # Line 12a (col B, Subtractions)
    "sch_d_540_total_additions":    "Text Field 126",  # Line 12b (col C, Additions)
}
_AGGREGATIONS_2021: dict[str, tuple[str, ...]] = {}
# Form-internal computed cells ported from 2023 (rc=1, layout differs but
# lines 10/11 are present on the 2021 form). Target boxes re-placed from the
# 2021 template's own /TU tooltips and visually confirmed on the probe render
# (page 2): Field 123 sits on printed Line 10, Field 124 on printed Line 11.
_DERIVATIONS_2021: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 10 — /TU "Enter the gain or (loss) from federal Form 1040 or
    # 1040-SR, line 7." The FEDERAL net capital gain/loss (pre-CA-divergence).
    # Formula carried from 2023, verified against the 2021 printed form.
    "Text Field 123": lambda c: c["sch_d_540_federal_net"],
    # Line 11 — /TU "Enter the California gain from line 8 or (loss) from
    # line 9." The CALIFORNIA net capital gain/loss. Formula carried from
    # 2023, verified against the 2021 printed form.
    "Text Field 124": lambda c: c["sch_d_540_net_capital_gain"],
}
_CHECKBOX_STATES_2021: dict[str, str] = {}


# ---------------------------------------------------------------------------
# TY2022 registries — INHERITED from 2023 by field-tree identity.
# 2022 field tree is IDENTICAL to 2023 (diff_pdf_fields, controller-verified);
# fields-on-template gate re-verifies every path against the 2022 template,
# emit round-trip verifies values land.
# ---------------------------------------------------------------------------
_MAPPING_2022 = _MAPPING_2023
_AGGREGATIONS_2022 = _AGGREGATIONS_2023
_DERIVATIONS_2022 = _DERIVATIONS_2023
_SUPPRESSED_2022 = _SUPPRESSED_2023
_CHECKBOX_STATES_2022 = _CHECKBOX_STATES_2023


PdfSchD540._MAPPINGS = {
    2021: _MAPPING_2021, 2022: _MAPPING_2022,
    2023: _MAPPING_2023, 2024: _MAPPING_2024, 2025: _MAPPING_2025,
}

# Year-keyed dispatch tables for the four registries above — replaces
# `if year == <literal>` branching with membership-gated dict lookup.
_AGGREGATIONS_BY_YEAR: dict[int, dict[str, tuple[str, ...]]] = {
    2021: _AGGREGATIONS_2021, 2022: _AGGREGATIONS_2022,
    2023: _AGGREGATIONS_2023, 2024: _AGGREGATIONS_2024, 2025: _AGGREGATIONS_2025,
}
_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2021: _DERIVATIONS_2021, 2022: _DERIVATIONS_2022,
    2023: _DERIVATIONS_2023, 2024: _DERIVATIONS_2024, 2025: _DERIVATIONS_2025,
}
_SUPPRESSED_BY_YEAR: dict[int, frozenset[str]] = {
    2022: _SUPPRESSED_2022,
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _CHECKBOX_STATES_2021, 2022: _CHECKBOX_STATES_2022,
    2023: _CHECKBOX_STATES_2023, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}
