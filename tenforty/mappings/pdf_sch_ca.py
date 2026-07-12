"""PDF field mapping for FTB 2025 Schedule CA (540).

Mirrors the five-registry design from `pdf_f540.py` (and SP2's
`pdf_f1120s.py`):

- `_MAPPING_2025` — direct compute_key → PDF-field-path. v1 covers all
  20 Part I lines fed by federal compute keys via
  `_FEDERAL_TO_SCH_CA_COL_A_MAP` (Section A 1z/2/3/4/5b/6/7, Section B
  1/3/4/5/6/7/8z, Section C 11/13/15/17/20/21), with Col A federal-amount
  passthrough widgets and per-line Col B (subtractions) / Col C
  (additions) widgets where the form has them. Plus the Line 27 Col A
  federal-AGI passthrough and Line 27 Col B/C totals, and 2 [PLANNED]
  orchestrator-supplied keys (taxpayer name + SSN on page 1) reserved
  for future wiring.
- `_AGGREGATIONS_2025` — empty for Sch CA. Per-line and total sums are
  emitted directly by the kernel; no PDF cell receives a sum of
  multiple compute keys at fill time.
- `_DERIVATIONS_2025` — empty for Sch CA v1. No within-form arithmetic
  beyond the kernel-emitted totals is wired in v1.
- `_SUPPRESSED_2025` — extended SP3 SUPPRESSED semantics: includes
  (a) `sch_ca_ca_agi` (transit-only; flows to f540 line 13 via
  `f540_ca_agi`, no Sch CA cell for it) and (b) per-line
  subtractions/additions keys for which the form omits the corresponding
  column widget (CA-conformance: e.g., §A 6 Social Security has no Col C
  because federal taxes 0–85 % but CA taxes none — addition is
  impossible; §C 21 Student loan interest has no Col B because CA
  conforms fully — subtraction is impossible). Worksheet divergences
  routed to these column-omitted positions still contribute to the line
  27 totals via `sch_ca_total_subtractions` / `sch_ca_total_additions`.
- `_CHECKBOX_STATES_2025` — empty for Sch CA. The single /Btn widget
  on page 5 (`540ca_form - 5000 CB`, page-5 Col B header checkbox) is
  out-of-scope for v1.

Field paths come from the probe artifact at
`docs/plans/sp3-t14-sch-ca-probe.md` (gitignored). Widget→line
assignments are tooltip-verified (`/TU` annotations on each widget
in the source PDF). pypdf reports flat field names with a leading
`540ca_form - <page><seq>` prefix (matching the f540 convention of
flat names rather than the IRS XFA `topmostSubform[0].PageN[0]....`
form).
"""

from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping


class PdfSchCa(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for FTB Schedule CA (540).

    Five-registry design (see module docstring). The partition invariant
    enforced by the mapping test is that every expected compute key from
    `sch_ca.compute()` is OWNED by exactly one of `_MAPPING_<year>`,
    `_AGGREGATIONS_<year>`, or `_SUPPRESSED_<year>`. Derivations consume
    compute keys but do not own them.
    """

    _FORM_NAME = "Schedule CA (540)"
    _MAPPINGS: dict[int, dict[str, str]] = {}  # populated below after _MAPPING_2025

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        if year not in _AGGREGATIONS_BY_YEAR:
            raise ValueError(f"No Schedule CA (540) aggregations for year {year}")
        return _AGGREGATIONS_BY_YEAR[year]

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in _DERIVATIONS_BY_YEAR:
            raise ValueError(f"No Schedule CA (540) derivations for year {year}")
        return _DERIVATIONS_BY_YEAR[year]

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year not in _SUPPRESSED_BY_YEAR:
            raise ValueError(f"No Schedule CA (540) suppressions for year {year}")
        return _SUPPRESSED_BY_YEAR[year]

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        if year not in _CHECKBOX_STATES_BY_YEAR:
            raise ValueError(f"No Schedule CA (540) checkbox states for year {year}")
        return _CHECKBOX_STATES_BY_YEAR[year]


# Direct 1:1 mappings — compute keys with a direct PDF cell + [PLANNED]
# orchestrator-supplied keys reserved for future wiring. Widget IDs are
# tooltip-verified against the 2025 PDF /TU annotations.
_MAPPING_2025: dict[str, str] = {
    # Page 1 — Taxpayer header ([PLANNED]: orchestrator-supplied)
    "sch_ca_taxpayer_name":                       "540ca_form - 1000",
    "sch_ca_taxpayer_ssn":                        "540ca_form - 1001",
    # Page 1 §A line 1z — Sum of wages 1a–1i (federal 1040 line 1z)
    "sch_ca_line_part_i_a_1z_col_a":              "540ca_form - 1027",
    "sch_ca_line_part_i_a_1z_subtractions":       "540ca_form - 1028",
    "sch_ca_line_part_i_a_1z_additions":          "540ca_form - 1029",
    # Page 1 §A line 2 — Taxable interest (federal 1040 line 2b)
    "sch_ca_line_part_i_a_2_col_a":               "540ca_form - 1031",
    "sch_ca_line_part_i_a_2_subtractions":        "540ca_form - 1032",
    "sch_ca_line_part_i_a_2_additions":           "540ca_form - 1033",
    # Page 1 §A line 3 — Ordinary dividends (federal 1040 line 3b)
    "sch_ca_line_part_i_a_3_col_a":               "540ca_form - 1035",
    "sch_ca_line_part_i_a_3_subtractions":        "540ca_form - 1036",
    "sch_ca_line_part_i_a_3_additions":           "540ca_form - 1037",
    # Page 1 §A line 4 — IRA distributions (federal 1040 line 4b)
    "sch_ca_line_part_i_a_4_col_a":               "540ca_form - 1039",
    "sch_ca_line_part_i_a_4_subtractions":        "540ca_form - 1040",
    "sch_ca_line_part_i_a_4_additions":           "540ca_form - 1041",
    # Page 1 §A line 5b — Pensions/annuities (incl. RRB Tier 1/2)
    "sch_ca_line_part_i_a_5b_col_a":              "540ca_form - 1043",
    "sch_ca_line_part_i_a_5b_subtractions":       "540ca_form - 1044",
    "sch_ca_line_part_i_a_5b_additions":          "540ca_form - 1045",
    # Page 1 §A line 6 — Social Security benefits (no Col C — CA never
    # taxes more than federal taxes; addition impossible)
    "sch_ca_line_part_i_a_6_col_a":               "540ca_form - 1047",
    "sch_ca_line_part_i_a_6_subtractions":        "540ca_form - 1048",
    # Page 1 §A line 7a — Capital gain or (loss)
    "sch_ca_line_part_i_a_7_col_a":               "540ca_form - 1049",
    "sch_ca_line_part_i_a_7_subtractions":        "540ca_form - 1050",
    "sch_ca_line_part_i_a_7_additions":           "540ca_form - 1051",
    # Page 1 §B line 1 — Taxable refunds (no Col C — CA never taxes
    # state refunds; addition impossible)
    "sch_ca_line_part_i_b_1_col_a":               "540ca_form - 1052",
    "sch_ca_line_part_i_b_1_subtractions":        "540ca_form - 1053",
    # Page 1 §B line 3 — Business income or (loss)
    "sch_ca_line_part_i_b_3_col_a":               "540ca_form - 1056",
    "sch_ca_line_part_i_b_3_subtractions":        "540ca_form - 1057",
    "sch_ca_line_part_i_b_3_additions":           "540ca_form - 1058",
    # Page 1 §B line 4 — Other gains
    "sch_ca_line_part_i_b_4_col_a":               "540ca_form - 1059",
    "sch_ca_line_part_i_b_4_subtractions":        "540ca_form - 1060",
    "sch_ca_line_part_i_b_4_additions":           "540ca_form - 1061",
    # Page 1 §B line 5 — Rental/royalties/partnership/S-corp
    "sch_ca_line_part_i_b_5_col_a":               "540ca_form - 1062",
    "sch_ca_line_part_i_b_5_subtractions":        "540ca_form - 1063",
    "sch_ca_line_part_i_b_5_additions":           "540ca_form - 1064",
    # Page 1 §B line 6 — Farm income
    "sch_ca_line_part_i_b_6_col_a":               "540ca_form - 1065",
    "sch_ca_line_part_i_b_6_subtractions":        "540ca_form - 1066",
    "sch_ca_line_part_i_b_6_additions":           "540ca_form - 1067",
    # Page 1 §B line 7 — Unemployment compensation (no Col C — UI
    # excluded by CA; addition impossible)
    "sch_ca_line_part_i_b_7_col_a":               "540ca_form - 1068",
    "sch_ca_line_part_i_b_7_subtractions":        "540ca_form - 1069",
    # Page 2 §B line 8z — Other income (write-in catch-all)
    "sch_ca_line_part_i_b_8z_col_a":              "540ca_form - 2038",
    "sch_ca_line_part_i_b_8z_subtractions":       "540ca_form - 2039",
    "sch_ca_line_part_i_b_8z_additions":          "540ca_form - 2040",
    # Page 3 §C line 11 — Educator expenses (no Col C — CA conforms
    # fully; addition impossible)
    "sch_ca_line_part_i_c_11_col_a":              "540ca_form - 3010",
    "sch_ca_line_part_i_c_11_subtractions":       "540ca_form - 3011",
    # Page 3 §C line 13 — HSA deduction (no Col C — CA disallows HSA;
    # subtractions only, addition impossible)
    "sch_ca_line_part_i_c_13_col_a":              "540ca_form - 3015",
    "sch_ca_line_part_i_c_13_subtractions":       "540ca_form - 3016",
    # Page 3 §C line 15 — Deductible part of self-employment tax (no
    # Col C — federal/CA conform; addition impossible)
    "sch_ca_line_part_i_c_15_col_a":              "540ca_form - 3019",
    "sch_ca_line_part_i_c_15_subtractions":       "540ca_form - 3020",
    # Page 3 §C line 17 — Self-employed health insurance (no Col C —
    # CA conforms; addition impossible)
    "sch_ca_line_part_i_c_17_col_a":              "540ca_form - 3022",
    "sch_ca_line_part_i_c_17_subtractions":       "540ca_form - 3023",
    # Page 3 §C line 20 — IRA deduction
    "sch_ca_line_part_i_c_20_col_a":              "540ca_form - 3029",
    "sch_ca_line_part_i_c_20_subtractions":       "540ca_form - 3030",
    "sch_ca_line_part_i_c_20_additions":          "540ca_form - 3031",
    # Page 3 §C line 21 — Student loan interest deduction (no Col B —
    # CA permits MORE than federal; subtraction impossible)
    "sch_ca_line_part_i_c_21_col_a":              "540ca_form - 3032",
    "sch_ca_line_part_i_c_21_additions":          "540ca_form - 3033",
    # Page 4 line 27 — Part I Total: Col A federal AGI passthrough
    # + Col B total subtractions + Col C total additions
    "sch_ca_federal_agi":                         "540ca_form - 4032",
    "sch_ca_total_subtractions":                  "540ca_form - 4033",
    "sch_ca_total_additions":                     "540ca_form - 4034",
}


# Per-line and total sums are kernel-emitted; no PDF cell receives a
# sum of multiple compute keys at fill time.
_AGGREGATIONS_2025: dict[str, tuple[str, ...]] = {}


# No within-form derivations in v1. Sch D (540) capital-gain pass-through
# and Part II itemized-adjustment sums are deferred to a later phase.
_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {}


# Compute keys with no direct PDF cell on the 2025 form.
#
# Extended SUPPRESSED semantics (SP3 calibration): includes
# (a) keys with no fillable cell (transit-only OR form-no-cell case)
# AND (b) keys consumed only by derivations (none in Sch CA v1).
_SUPPRESSED_2025: frozenset[str] = frozenset({
    # Transit value — flows to f540 line 13 via f540_ca_agi mapping;
    # Sch CA itself has no PDF cell for combined CA AGI (line 27 emits
    # federal AGI in Col A and the sum-of-divergences in Col B/C; CA AGI
    # = federal AGI − Σ subtractions + Σ additions is computed on f540).
    "sch_ca_ca_agi",
    # Form column-omissions: lines for which the 2025 PDF lacks the
    # corresponding column widget. CA-conformance shape: most §A/§B
    # subtraction-only lines (federal-broader-than-CA exclusions) lack
    # Col C; §C line 21 (CA-broader-than-federal) lacks Col B.
    # Worksheet divergences routed to these positions still flow
    # through `sch_ca_total_subtractions` / `sch_ca_total_additions`.
    "sch_ca_line_part_i_a_6_additions",
    "sch_ca_line_part_i_b_1_additions",
    "sch_ca_line_part_i_b_7_additions",
    "sch_ca_line_part_i_c_11_additions",
    "sch_ca_line_part_i_c_13_additions",
    "sch_ca_line_part_i_c_15_additions",
    "sch_ca_line_part_i_c_17_additions",
    "sch_ca_line_part_i_c_21_subtractions",
})


# All v1 checkboxes are out-of-scope. The single /Btn widget on the
# 2025 form (page 5 Col B section header) has no compute key wired.
_CHECKBOX_STATES_2025: dict[str, str] = {}


PdfSchCa._MAPPINGS = {2025: _MAPPING_2025}  # updated below after _MAPPING_2024


# ---------------------------------------------------------------------------
# 2024 registries — probed from pdfs/california/2024/sch_ca.pdf
#
# Probe confirmed: the 2024 form uses the SAME `540ca_form - NNNN` prefix
# and IDENTICAL sequence numbers for all mapped fields as the 2025 form.
# Column structure (which lines have Col B / Col C widgets) is also
# identical. Tooltip-verified via the Step-3 probe; see task-3-report.md.
# ---------------------------------------------------------------------------

# Direct 1:1 mappings — tooltip-verified against 2024 PDF /TU annotations.
# Sequence numbers match 2025 exactly (confirmed by probe).
_MAPPING_2024: dict[str, str] = {
    # Page 1 — Taxpayer header ([PLANNED]: orchestrator-supplied)
    "sch_ca_taxpayer_name":                       "540ca_form - 1000",
    "sch_ca_taxpayer_ssn":                        "540ca_form - 1001",
    # Page 1 §A line 1z — Sum of wages 1a–1i (federal 1040 line 1z)
    "sch_ca_line_part_i_a_1z_col_a":              "540ca_form - 1027",
    "sch_ca_line_part_i_a_1z_subtractions":       "540ca_form - 1028",
    "sch_ca_line_part_i_a_1z_additions":          "540ca_form - 1029",
    # Page 1 §A line 2 — Taxable interest (federal 1040 line 2b)
    "sch_ca_line_part_i_a_2_col_a":               "540ca_form - 1031",
    "sch_ca_line_part_i_a_2_subtractions":        "540ca_form - 1032",
    "sch_ca_line_part_i_a_2_additions":           "540ca_form - 1033",
    # Page 1 §A line 3 — Ordinary dividends (federal 1040 line 3b)
    "sch_ca_line_part_i_a_3_col_a":               "540ca_form - 1035",
    "sch_ca_line_part_i_a_3_subtractions":        "540ca_form - 1036",
    "sch_ca_line_part_i_a_3_additions":           "540ca_form - 1037",
    # Page 1 §A line 4 — IRA distributions (federal 1040 line 4b)
    "sch_ca_line_part_i_a_4_col_a":               "540ca_form - 1039",
    "sch_ca_line_part_i_a_4_subtractions":        "540ca_form - 1040",
    "sch_ca_line_part_i_a_4_additions":           "540ca_form - 1041",
    # Page 1 §A line 5b — Pensions/annuities (incl. RRB Tier 1/2)
    "sch_ca_line_part_i_a_5b_col_a":              "540ca_form - 1043",
    "sch_ca_line_part_i_a_5b_subtractions":       "540ca_form - 1044",
    "sch_ca_line_part_i_a_5b_additions":          "540ca_form - 1045",
    # Page 1 §A line 6 — Social Security benefits (no Col C — CA never
    # taxes more than federal taxes; addition impossible)
    "sch_ca_line_part_i_a_6_col_a":               "540ca_form - 1047",
    "sch_ca_line_part_i_a_6_subtractions":        "540ca_form - 1048",
    # Page 1 §A line 7a — Capital gain or (loss)
    "sch_ca_line_part_i_a_7_col_a":               "540ca_form - 1049",
    "sch_ca_line_part_i_a_7_subtractions":        "540ca_form - 1050",
    "sch_ca_line_part_i_a_7_additions":           "540ca_form - 1051",
    # Page 1 §B line 1 — Taxable refunds (no Col C — CA never taxes
    # state refunds; addition impossible)
    "sch_ca_line_part_i_b_1_col_a":               "540ca_form - 1052",
    "sch_ca_line_part_i_b_1_subtractions":        "540ca_form - 1053",
    # Page 1 §B line 3 — Business income or (loss)
    "sch_ca_line_part_i_b_3_col_a":               "540ca_form - 1056",
    "sch_ca_line_part_i_b_3_subtractions":        "540ca_form - 1057",
    "sch_ca_line_part_i_b_3_additions":           "540ca_form - 1058",
    # Page 1 §B line 4 — Other gains
    "sch_ca_line_part_i_b_4_col_a":               "540ca_form - 1059",
    "sch_ca_line_part_i_b_4_subtractions":        "540ca_form - 1060",
    "sch_ca_line_part_i_b_4_additions":           "540ca_form - 1061",
    # Page 1 §B line 5 — Rental/royalties/partnership/S-corp
    "sch_ca_line_part_i_b_5_col_a":               "540ca_form - 1062",
    "sch_ca_line_part_i_b_5_subtractions":        "540ca_form - 1063",
    "sch_ca_line_part_i_b_5_additions":           "540ca_form - 1064",
    # Page 1 §B line 6 — Farm income
    "sch_ca_line_part_i_b_6_col_a":               "540ca_form - 1065",
    "sch_ca_line_part_i_b_6_subtractions":        "540ca_form - 1066",
    "sch_ca_line_part_i_b_6_additions":           "540ca_form - 1067",
    # Page 1 §B line 7 — Unemployment compensation (no Col C — UI
    # excluded by CA; addition impossible)
    "sch_ca_line_part_i_b_7_col_a":               "540ca_form - 1068",
    "sch_ca_line_part_i_b_7_subtractions":        "540ca_form - 1069",
    # Page 2 §B line 8z — Other income (write-in catch-all)
    "sch_ca_line_part_i_b_8z_col_a":              "540ca_form - 2038",
    "sch_ca_line_part_i_b_8z_subtractions":       "540ca_form - 2039",
    "sch_ca_line_part_i_b_8z_additions":          "540ca_form - 2040",
    # Page 3 §C line 11 — Educator expenses (no Col C — CA conforms
    # fully; addition impossible)
    "sch_ca_line_part_i_c_11_col_a":              "540ca_form - 3010",
    "sch_ca_line_part_i_c_11_subtractions":       "540ca_form - 3011",
    # Page 3 §C line 13 — HSA deduction (no Col C — CA disallows HSA;
    # subtractions only, addition impossible)
    "sch_ca_line_part_i_c_13_col_a":              "540ca_form - 3015",
    "sch_ca_line_part_i_c_13_subtractions":       "540ca_form - 3016",
    # Page 3 §C line 15 — Deductible part of self-employment tax (no
    # Col C — federal/CA conform; addition impossible)
    "sch_ca_line_part_i_c_15_col_a":              "540ca_form - 3019",
    "sch_ca_line_part_i_c_15_subtractions":       "540ca_form - 3020",
    # Page 3 §C line 17 — Self-employed health insurance (no Col C —
    # CA conforms; addition impossible)
    "sch_ca_line_part_i_c_17_col_a":              "540ca_form - 3022",
    "sch_ca_line_part_i_c_17_subtractions":       "540ca_form - 3023",
    # Page 3 §C line 20 — IRA deduction
    "sch_ca_line_part_i_c_20_col_a":              "540ca_form - 3029",
    "sch_ca_line_part_i_c_20_subtractions":       "540ca_form - 3030",
    "sch_ca_line_part_i_c_20_additions":          "540ca_form - 3031",
    # Page 3 §C line 21 — Student loan interest deduction (no Col B —
    # CA permits MORE than federal; subtraction impossible)
    "sch_ca_line_part_i_c_21_col_a":              "540ca_form - 3032",
    "sch_ca_line_part_i_c_21_additions":          "540ca_form - 3033",
    # Page 4 line 27 — Part I Total: Col A federal AGI passthrough
    # + Col B total subtractions + Col C total additions
    "sch_ca_federal_agi":                         "540ca_form - 4032",
    "sch_ca_total_subtractions":                  "540ca_form - 4033",
    "sch_ca_total_additions":                     "540ca_form - 4034",
}


# Per-line and total sums are kernel-emitted; no PDF cell receives a
# sum of multiple compute keys at fill time.
_AGGREGATIONS_2024: dict[str, tuple[str, ...]] = {}


# No within-form derivations in v1.
_DERIVATIONS_2024: dict[str, Callable[[Mapping[str, object]], object]] = {}


# Compute keys with no direct PDF cell on the 2024 form.
# Tooltip-verified: column structure identical to 2025 — same lines
# lack Col C (subtraction-only conformance) and same line (§C 21) lacks
# Col B (addition-only conformance).
_SUPPRESSED_2024: frozenset[str] = frozenset({
    # Transit value — flows to f540 line 13 via f540_ca_agi mapping.
    "sch_ca_ca_agi",
    # Form column-omissions: lines for which the 2024 PDF lacks the
    # corresponding column widget (tooltip-verified).
    "sch_ca_line_part_i_a_6_additions",
    "sch_ca_line_part_i_b_1_additions",
    "sch_ca_line_part_i_b_7_additions",
    "sch_ca_line_part_i_c_11_additions",
    "sch_ca_line_part_i_c_13_additions",
    "sch_ca_line_part_i_c_15_additions",
    "sch_ca_line_part_i_c_17_additions",
    "sch_ca_line_part_i_c_21_subtractions",
})


# All v1 checkboxes are out-of-scope. The single /Btn widget on the
# 2024 form (page 5 Col B section header) has no compute key wired.
_CHECKBOX_STATES_2024: dict[str, str] = {}


PdfSchCa._MAPPINGS[2024] = _MAPPING_2024


# ---------------------------------------------------------------------------
# 2023 registries — tooltip-read from pdfs/california/2023/sch_ca.pdf,
# filled-emit-verified.
#
# THIRD FTB naming scheme: bare zero-padded numbers ('1027', '2035') — the
# '540ca_form - ' prefix of 2024/2025 is GONE (matching the 2023 Sch D (540)
# and Form 540). Each field's /TU tooltip was compared against the 2025 field
# of the same line+column: 54 of 57 fields keep the identical sequence number
# (the prefix is merely stripped). The exception is line 8z's three cells,
# which SHIFTED 2038/2039/2040 -> 2035/2036/2037 because the 2023 form
# enumerates its 8a-8u other-income sub-lines with different field numbers
# ahead of 8z — an invisible-shift trap caught by the tooltip read, NOT by
# assuming the prefix-strip carried every number. (The §A line-7 tooltip reads
# "Line 7" in 2023 vs "Line 7a" in 2025 — same capital-gain cell/column,
# benign wording.) Column structure (which lines lack Col B/C) is identical to
# 2024/2025 per the Step-1 conformity review.
# ---------------------------------------------------------------------------

_MAPPING_2023: dict[str, str] = {
    # Page 1 — Taxpayer header ([PLANNED]: orchestrator-supplied)
    "sch_ca_taxpayer_name":                       "1000",
    "sch_ca_taxpayer_ssn":                        "1001",
    # Page 1 §A line 1z — Sum of wages 1a–1i (federal 1040 line 1z)
    "sch_ca_line_part_i_a_1z_col_a":              "1027",
    "sch_ca_line_part_i_a_1z_subtractions":       "1028",
    "sch_ca_line_part_i_a_1z_additions":          "1029",
    # Page 1 §A line 2 — Taxable interest (federal 1040 line 2b)
    "sch_ca_line_part_i_a_2_col_a":               "1031",
    "sch_ca_line_part_i_a_2_subtractions":        "1032",
    "sch_ca_line_part_i_a_2_additions":           "1033",
    # Page 1 §A line 3 — Ordinary dividends (federal 1040 line 3b)
    "sch_ca_line_part_i_a_3_col_a":               "1035",
    "sch_ca_line_part_i_a_3_subtractions":        "1036",
    "sch_ca_line_part_i_a_3_additions":           "1037",
    # Page 1 §A line 4 — IRA distributions (federal 1040 line 4b)
    "sch_ca_line_part_i_a_4_col_a":               "1039",
    "sch_ca_line_part_i_a_4_subtractions":        "1040",
    "sch_ca_line_part_i_a_4_additions":           "1041",
    # Page 1 §A line 5b — Pensions/annuities (incl. RRB Tier 1/2)
    "sch_ca_line_part_i_a_5b_col_a":              "1043",
    "sch_ca_line_part_i_a_5b_subtractions":       "1044",
    "sch_ca_line_part_i_a_5b_additions":          "1045",
    # Page 1 §A line 6 — Social Security benefits (no Col C — CA never
    # taxes more than federal taxes; addition impossible)
    "sch_ca_line_part_i_a_6_col_a":               "1047",
    "sch_ca_line_part_i_a_6_subtractions":        "1048",
    # Page 1 §A line 7a — Capital gain or (loss) (2023 tooltip: "Line 7")
    "sch_ca_line_part_i_a_7_col_a":               "1049",
    "sch_ca_line_part_i_a_7_subtractions":        "1050",
    "sch_ca_line_part_i_a_7_additions":           "1051",
    # Page 1 §B line 1 — Taxable refunds (no Col C — CA never taxes
    # state refunds; addition impossible)
    "sch_ca_line_part_i_b_1_col_a":               "1052",
    "sch_ca_line_part_i_b_1_subtractions":        "1053",
    # Page 1 §B line 3 — Business income or (loss)
    "sch_ca_line_part_i_b_3_col_a":               "1056",
    "sch_ca_line_part_i_b_3_subtractions":        "1057",
    "sch_ca_line_part_i_b_3_additions":           "1058",
    # Page 1 §B line 4 — Other gains
    "sch_ca_line_part_i_b_4_col_a":               "1059",
    "sch_ca_line_part_i_b_4_subtractions":        "1060",
    "sch_ca_line_part_i_b_4_additions":           "1061",
    # Page 1 §B line 5 — Rental/royalties/partnership/S-corp
    "sch_ca_line_part_i_b_5_col_a":               "1062",
    "sch_ca_line_part_i_b_5_subtractions":        "1063",
    "sch_ca_line_part_i_b_5_additions":           "1064",
    # Page 1 §B line 6 — Farm income
    "sch_ca_line_part_i_b_6_col_a":               "1065",
    "sch_ca_line_part_i_b_6_subtractions":        "1066",
    "sch_ca_line_part_i_b_6_additions":           "1067",
    # Page 1 §B line 7 — Unemployment compensation (no Col C — UI
    # excluded by CA; addition impossible)
    "sch_ca_line_part_i_b_7_col_a":               "1068",
    "sch_ca_line_part_i_b_7_subtractions":        "1069",
    # Page 2 §B line 8z — Other income (write-in catch-all). SHIFTED to
    # 2035/2036/2037 in 2023 (2024/2025 use 2038/2039/2040).
    "sch_ca_line_part_i_b_8z_col_a":              "2035",
    "sch_ca_line_part_i_b_8z_subtractions":       "2036",
    "sch_ca_line_part_i_b_8z_additions":          "2037",
    # Page 3 §C line 11 — Educator expenses (no Col C — CA conforms
    # fully; addition impossible)
    "sch_ca_line_part_i_c_11_col_a":              "3010",
    "sch_ca_line_part_i_c_11_subtractions":       "3011",
    # Page 3 §C line 13 — HSA deduction (no Col C — CA disallows HSA;
    # subtractions only, addition impossible)
    "sch_ca_line_part_i_c_13_col_a":              "3015",
    "sch_ca_line_part_i_c_13_subtractions":       "3016",
    # Page 3 §C line 15 — Deductible part of self-employment tax (no
    # Col C — federal/CA conform; addition impossible)
    "sch_ca_line_part_i_c_15_col_a":              "3019",
    "sch_ca_line_part_i_c_15_subtractions":       "3020",
    # Page 3 §C line 17 — Self-employed health insurance (no Col C —
    # CA conforms; addition impossible)
    "sch_ca_line_part_i_c_17_col_a":              "3022",
    "sch_ca_line_part_i_c_17_subtractions":       "3023",
    # Page 3 §C line 20 — IRA deduction
    "sch_ca_line_part_i_c_20_col_a":              "3029",
    "sch_ca_line_part_i_c_20_subtractions":       "3030",
    "sch_ca_line_part_i_c_20_additions":          "3031",
    # Page 3 §C line 21 — Student loan interest deduction (no Col B —
    # CA permits MORE than federal; subtraction impossible)
    "sch_ca_line_part_i_c_21_col_a":              "3032",
    "sch_ca_line_part_i_c_21_additions":          "3033",
    # Page 4 line 27 — Part I Total: Col A federal AGI passthrough
    # + Col B total subtractions + Col C total additions
    "sch_ca_federal_agi":                         "4032",
    "sch_ca_total_subtractions":                  "4033",
    "sch_ca_total_additions":                     "4034",
}


_AGGREGATIONS_2023: dict[str, tuple[str, ...]] = {}


_DERIVATIONS_2023: dict[str, Callable[[Mapping[str, object]], object]] = {}


# Column structure identical to 2024/2025 (Step-1 conformity review):
# same subtraction-only §A/§B lines lack Col C, and §C line 21 lacks Col B.
_SUPPRESSED_2023: frozenset[str] = frozenset({
    # Transit value — flows to f540 line 13 via f540_ca_agi mapping.
    "sch_ca_ca_agi",
    # Form column-omissions (2023 PDF lacks the corresponding widget).
    "sch_ca_line_part_i_a_6_additions",
    "sch_ca_line_part_i_b_1_additions",
    "sch_ca_line_part_i_b_7_additions",
    "sch_ca_line_part_i_c_11_additions",
    "sch_ca_line_part_i_c_13_additions",
    "sch_ca_line_part_i_c_15_additions",
    "sch_ca_line_part_i_c_17_additions",
    "sch_ca_line_part_i_c_21_subtractions",
})


_CHECKBOX_STATES_2023: dict[str, str] = {}


PdfSchCa._MAPPINGS[2023] = _MAPPING_2023

# Year-keyed dispatch tables for the four registries above — replaces
# `if year == <literal>` branching with membership-gated dict lookup.
_AGGREGATIONS_BY_YEAR: dict[int, dict[str, tuple[str, ...]]] = {
    2023: _AGGREGATIONS_2023, 2024: _AGGREGATIONS_2024, 2025: _AGGREGATIONS_2025,
}
_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2023: _DERIVATIONS_2023, 2024: _DERIVATIONS_2024, 2025: _DERIVATIONS_2025,
}
_SUPPRESSED_BY_YEAR: dict[int, frozenset[str]] = {
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2023: _CHECKBOX_STATES_2023, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}
