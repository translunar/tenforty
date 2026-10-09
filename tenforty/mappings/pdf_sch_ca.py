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

import re
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


# Section-total and Part II line-30 derivations are installed below
# (_install_sch_ca_totals, _install_sch_ca_part_ii).
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


# ---------------------------------------------------------------------------
# 2022 registries — INHERITED from 2023 by field-tree identity.
# 2022 field tree is IDENTICAL to 2023 (diff_pdf_fields, controller-verified);
# fields-on-template gate re-verifies every path against the 2022 template,
# emit round-trip verifies values land.
# ---------------------------------------------------------------------------
_MAPPING_2022 = _MAPPING_2023
_AGGREGATIONS_2022 = _AGGREGATIONS_2023
_DERIVATIONS_2022 = _DERIVATIONS_2023
_SUPPRESSED_2022 = _SUPPRESSED_2023
_CHECKBOX_STATES_2022 = _CHECKBOX_STATES_2023


PdfSchCa._MAPPINGS[2022] = _MAPPING_2022


# ---------------------------------------------------------------------------
# 2021 registries — FRESH air-gapped probe from pdfs/california/2021/sch_ca.pdf,
# controller-reconciled (all 57 paths on the 2021 template, 57 unique, no
# collisions).
#
# FOURTH FTB naming shape: bare zero-padded numbers ('1003', '2026', '3065')
# like 2023 — but the 2021 form does NOT align field-name-for-field-name with
# 2022/2023. The 2021 AcroForm renumbers its widgets end-to-end (e.g. name/ssn
# are 1001/1002 vs 2023's 1000/1001; line 1z Col A is 1003 vs 2023's 1027; the
# §C deductions land in the 2xxx/3xxx bands at entirely different sequence
# numbers). That namespace drift is exactly why 2021 is a fresh 57-key DIRECT
# map, NOT an inherit from 2023 the way 2022 was (commit 595aefd). Column
# structure (which lines lack Col B/C) is identical to 2022/2023: same
# subtraction-only §A/§B lines lack Col C, §C line 21 lacks Col B.
# ---------------------------------------------------------------------------

_MAPPING_2021: dict[str, str] = {
    # Page 1 — Taxpayer header ([PLANNED]: orchestrator-supplied)
    "sch_ca_taxpayer_name":                       "1001",
    "sch_ca_taxpayer_ssn":                        "1002",
    # Page 1 §A line 1z — Sum of wages 1a–1i (federal 1040 line 1z)
    "sch_ca_line_part_i_a_1z_col_a":              "1003",
    "sch_ca_line_part_i_a_1z_subtractions":       "1004",
    "sch_ca_line_part_i_a_1z_additions":          "1005",
    # Page 1 §A line 2 — Taxable interest (federal 1040 line 2b)
    "sch_ca_line_part_i_a_2_col_a":               "1007",
    "sch_ca_line_part_i_a_2_subtractions":        "1008",
    "sch_ca_line_part_i_a_2_additions":           "1009",
    # Page 1 §A line 3 — Ordinary dividends (federal 1040 line 3b)
    "sch_ca_line_part_i_a_3_col_a":               "1011",
    "sch_ca_line_part_i_a_3_subtractions":        "1012",
    "sch_ca_line_part_i_a_3_additions":           "1013",
    # Page 1 §A line 4 — IRA distributions (federal 1040 line 4b)
    "sch_ca_line_part_i_a_4_col_a":               "1015",
    "sch_ca_line_part_i_a_4_subtractions":        "1016",
    "sch_ca_line_part_i_a_4_additions":           "1017",
    # Page 1 §A line 5b — Pensions/annuities (incl. RRB Tier 1/2)
    "sch_ca_line_part_i_a_5b_col_a":              "1019",
    "sch_ca_line_part_i_a_5b_subtractions":       "1020",
    "sch_ca_line_part_i_a_5b_additions":          "1021",
    # Page 1 §A line 6 — Social Security benefits (no Col C — CA never
    # taxes more than federal taxes; addition impossible)
    "sch_ca_line_part_i_a_6_col_a":               "1023",
    "sch_ca_line_part_i_a_6_subtractions":        "1024",
    # Page 1 §A line 7 — Capital gain or (loss)
    "sch_ca_line_part_i_a_7_col_a":               "1026",
    "sch_ca_line_part_i_a_7_subtractions":        "1027",
    "sch_ca_line_part_i_a_7_additions":           "1028",
    # Page 1 §B line 1 — Taxable refunds (no Col C — CA never taxes
    # state refunds; addition impossible)
    "sch_ca_line_part_i_b_1_col_a":               "1029",
    "sch_ca_line_part_i_b_1_subtractions":        "1030",
    # Page 1 §B line 3 — Business income or (loss)
    "sch_ca_line_part_i_b_3_col_a":               "1035",
    "sch_ca_line_part_i_b_3_subtractions":        "1036",
    "sch_ca_line_part_i_b_3_additions":           "1037",
    # Page 1 §B line 4 — Other gains
    "sch_ca_line_part_i_b_4_col_a":               "1038",
    "sch_ca_line_part_i_b_4_subtractions":        "1039",
    "sch_ca_line_part_i_b_4_additions":           "1040",
    # Page 1 §B line 5 — Rental/royalties/partnership/S-corp
    "sch_ca_line_part_i_b_5_col_a":               "1041",
    "sch_ca_line_part_i_b_5_subtractions":        "1042",
    "sch_ca_line_part_i_b_5_additions":           "1043",
    # Page 1 §B line 6 — Farm income
    "sch_ca_line_part_i_b_6_col_a":               "1044",
    "sch_ca_line_part_i_b_6_subtractions":        "1045",
    "sch_ca_line_part_i_b_6_additions":           "1046",
    # Page 1 §B line 7 — Unemployment compensation (no Col C — UI
    # excluded by CA; addition impossible)
    "sch_ca_line_part_i_b_7_col_a":               "1047",
    "sch_ca_line_part_i_b_7_subtractions":        "1048",
    # Page 2 §B line 8z — Other income (write-in catch-all)
    "sch_ca_line_part_i_b_8z_col_a":              "2026",
    "sch_ca_line_part_i_b_8z_subtractions":       "2027",
    "sch_ca_line_part_i_b_8z_additions":          "2028",
    # Page 2 §C line 11 — Educator expenses (no Col C — CA conforms
    # fully; addition impossible)
    "sch_ca_line_part_i_c_11_col_a":              "2047",
    "sch_ca_line_part_i_c_11_subtractions":       "2048",
    # Page 2 §C line 13 — HSA deduction (no Col C — CA disallows HSA;
    # subtractions only, addition impossible)
    "sch_ca_line_part_i_c_13_col_a":              "2053",
    "sch_ca_line_part_i_c_13_subtractions":       "2054",
    # Page 2 §C line 15 — Deductible part of self-employment tax (no
    # Col C — federal/CA conform; addition impossible)
    "sch_ca_line_part_i_c_15_col_a":              "2059",
    "sch_ca_line_part_i_c_15_subtractions":       "2060",
    # Page 2 §C line 17 — Self-employed health insurance (no Col C —
    # CA conforms; addition impossible)
    "sch_ca_line_part_i_c_17_col_a":              "2065",
    "sch_ca_line_part_i_c_17_subtractions":       "2066",
    # Page 3 §C line 20 — IRA deduction
    "sch_ca_line_part_i_c_20_col_a":              "3015",
    "sch_ca_line_part_i_c_20_subtractions":       "3016",
    "sch_ca_line_part_i_c_20_additions":          "3017",
    # Page 3 §C line 21 — Student loan interest deduction (no Col B —
    # CA permits MORE than federal; subtraction impossible)
    "sch_ca_line_part_i_c_21_col_a":              "3018",
    "sch_ca_line_part_i_c_21_additions":          "3019",
    # Page 3 line 27 — Part I Total: Col A federal AGI passthrough
    # + Col B total subtractions + Col C total additions
    "sch_ca_federal_agi":                         "3065",
    "sch_ca_total_subtractions":                  "3066",
    "sch_ca_total_additions":                     "3067",
}


_AGGREGATIONS_2021: dict[str, tuple[str, ...]] = {}


# Section-total derivations are installed below (_install_sch_ca_totals).
_DERIVATIONS_2021: dict[str, Callable[[Mapping[str, object]], object]] = {}


# Column structure identical to 2022/2023 (same subtraction-only §A/§B lines
# lack Col C, and §C line 21 lacks Col B).
_SUPPRESSED_2021: frozenset[str] = frozenset({
    # Transit value — flows to f540 line 13 via f540_ca_agi mapping.
    "sch_ca_ca_agi",
    # Form column-omissions (2021 PDF lacks the corresponding widget).
    "sch_ca_line_part_i_a_6_additions",
    "sch_ca_line_part_i_b_1_additions",
    "sch_ca_line_part_i_b_7_additions",
    "sch_ca_line_part_i_c_11_additions",
    "sch_ca_line_part_i_c_13_additions",
    "sch_ca_line_part_i_c_15_additions",
    "sch_ca_line_part_i_c_17_additions",
    "sch_ca_line_part_i_c_21_subtractions",
})


_CHECKBOX_STATES_2021: dict[str, str] = {}


PdfSchCa._MAPPINGS[2021] = _MAPPING_2021

# Year-keyed dispatch tables for the four registries above — replaces
# `if year == <literal>` branching with membership-gated dict lookup.
# ── Catalog-routed Col B / Col C cells and the section-total cells ──────────
#
# Every Part I line the divergence catalog can post to has a Col B (subtractions)
# and/or Col C (additions) compute key. Until now only the lines with a federal
# Col A source were placed on the form, so a divergence on (say) line 1a, 8c or
# 24j was added into line 27 yet printed NOWHERE — the page did not foot against
# its visible addends. These tables place every catalog-reachable Part I cell, and
# the section totals (1z, 9a, 10, 25, 26) are DERIVED from the same keys so line
# 10 - line 26 = line 27 holds on the page by construction.
#
# Field numbers were generated from each template's /TU tooltips
# (tests/_schca_tooltips.py) restricted to Part I, and are re-verified against
# those tooltips by tests/test_ca_sch_ca_completeness.py.
#
# Catalog (line, column) pairs whose column has NO widget on the template (the
# catalog allows a direction the form does not print) are owned in SUPPRESSED:
# 2021 Part I §B 8e additions (+ the pre-existing column omissions such as §C 13
# additions). Their amounts still reach line 27 via the kernel totals.

_CATALOG_CELLS_2021: dict[str, str] = {'sch_ca_line_part_i_b_2a_additions': '1034',
     'sch_ca_line_part_i_b_8a_additions': '1051',
     'sch_ca_line_part_i_b_8b_subtractions': '1053',
     'sch_ca_line_part_i_b_8c_additions': '1057',
     'sch_ca_line_part_i_b_8d_additions': '1059',
     'sch_ca_line_part_i_b_8e_subtractions': '1061',
     'sch_ca_line_part_i_b_8m_subtractions': '2014',
     'sch_ca_line_part_i_b_8n_subtractions': '2017',
     'sch_ca_line_part_i_b_8o_additions': '2021',
     'sch_ca_line_part_i_b_9b1_subtractions': '2033',
     'sch_ca_line_part_i_b_9b2_subtractions': '2036',
     'sch_ca_line_part_i_b_9b3_subtractions': '2039',
     'sch_ca_line_part_i_b_9b4_subtractions': '2042',
     'sch_ca_line_part_i_c_12_additions': '2052',
     'sch_ca_line_part_i_c_12_subtractions': '2051',
     'sch_ca_line_part_i_c_14_additions': '2058',
     'sch_ca_line_part_i_c_19a_additions': '3006',
     'sch_ca_line_part_i_c_24b_additions': '3028',
     'sch_ca_line_part_i_c_24b_subtractions': '3027',
     'sch_ca_line_part_i_c_24c_subtractions': '3030',
     'sch_ca_line_part_i_c_24d_subtractions': '3033',
     'sch_ca_line_part_i_c_24f_additions': '3040',
     'sch_ca_line_part_i_c_24f_subtractions': '3039',
     'sch_ca_line_part_i_c_24g_additions': '3043',
     'sch_ca_line_part_i_c_24g_subtractions': '3042',
     'sch_ca_line_part_i_c_24i_subtractions': '3048',
     'sch_ca_line_part_i_c_24j_subtractions': '3051'}

_TOTAL_CELLS_2021: dict[str, str] = {'1zA': '1003',
     '1zB': '1004',
     '1zC': '1005',
     '9aA': '2029',
     '9aB': '2030',
     '9aC': '2031',
     '10A': '2044',
     '10B': '2045',
     '10C': '2046',
     '25A': '3059',
     '25B': '3060',
     '25C': '3061',
     '26A': '3062',
     '26B': '3063',
     '26C': '3064'}

_CATALOG_CELLS_2023: dict[str, str] = {'sch_ca_line_part_i_a_1a_additions': '1004',
     'sch_ca_line_part_i_a_1a_subtractions': '1003',
     'sch_ca_line_part_i_a_1d_subtractions': '1012',
     'sch_ca_line_part_i_a_1h_additions': '1025',
     'sch_ca_line_part_i_a_1h_subtractions': '1024',
     'sch_ca_line_part_i_a_1i_additions': '1026',
     'sch_ca_line_part_i_b_2a_additions': '1055',
     'sch_ca_line_part_i_b_8a_additions': '2002',
     'sch_ca_line_part_i_b_8b_subtractions': '2004',
     'sch_ca_line_part_i_b_8c_additions': '2007',
     'sch_ca_line_part_i_b_8c_subtractions': '2006',
     'sch_ca_line_part_i_b_8d_additions': '2009',
     'sch_ca_line_part_i_b_8e_additions': '2011',
     'sch_ca_line_part_i_b_8f_subtractions': '2013',
     'sch_ca_line_part_i_b_8k_additions': '2019',
     'sch_ca_line_part_i_b_8n_subtractions': '2023',
     'sch_ca_line_part_i_b_8o_subtractions': '2025',
     'sch_ca_line_part_i_b_8p_additions': '2028',
     'sch_ca_line_part_i_b_8p_subtractions': '2027',
     'sch_ca_line_part_i_b_9b1_subtractions': '3004',
     'sch_ca_line_part_i_b_9b2_subtractions': '3005',
     'sch_ca_line_part_i_b_9b3_subtractions': '3006',
     'sch_ca_line_part_i_c_12_additions': '3014',
     'sch_ca_line_part_i_c_12_subtractions': '3013',
     'sch_ca_line_part_i_c_14_additions': '3018',
     'sch_ca_line_part_i_c_19a_additions': '3026',
     'sch_ca_line_part_i_c_24b_additions': '4004',
     'sch_ca_line_part_i_c_24b_subtractions': '4003',
     'sch_ca_line_part_i_c_24c_subtractions': '4006',
     'sch_ca_line_part_i_c_24d_subtractions': '4008',
     'sch_ca_line_part_i_c_24f_additions': '4012',
     'sch_ca_line_part_i_c_24f_subtractions': '4011',
     'sch_ca_line_part_i_c_24g_additions': '4015',
     'sch_ca_line_part_i_c_24g_subtractions': '4014',
     'sch_ca_line_part_i_c_24i_subtractions': '4018',
     'sch_ca_line_part_i_c_24j_subtractions': '4020'}

_TOTAL_CELLS_2023: dict[str, str] = {'1aA': '1002',
     '1aB': '1003',
     '1aC': '1004',
     '1zA': '1027',
     '1zB': '1028',
     '1zC': '1029',
     '9aA': '3001',
     '9aB': '3002',
     '9aC': '3003',
     '10A': '3007',
     '10B': '3008',
     '10C': '3009',
     '25A': '4026',
     '25B': '4027',
     '25C': '4028',
     '26A': '4029',
     '26B': '4030',
     '26C': '4031'}

_CATALOG_CELLS_2024: dict[str, str] = {'sch_ca_line_part_i_a_1a_additions': '540ca_form - 1004',
     'sch_ca_line_part_i_a_1a_subtractions': '540ca_form - 1003',
     'sch_ca_line_part_i_a_1d_subtractions': '540ca_form - 1012',
     'sch_ca_line_part_i_a_1h_additions': '540ca_form - 1025',
     'sch_ca_line_part_i_a_1h_subtractions': '540ca_form - 1024',
     'sch_ca_line_part_i_a_1i_additions': '540ca_form - 1026',
     'sch_ca_line_part_i_b_2a_additions': '540ca_form - 1055',
     'sch_ca_line_part_i_b_8a_additions': '540ca_form - 2002',
     'sch_ca_line_part_i_b_8b_subtractions': '540ca_form - 2004',
     'sch_ca_line_part_i_b_8c_additions': '540ca_form - 2007',
     'sch_ca_line_part_i_b_8d_additions': '540ca_form - 2009',
     'sch_ca_line_part_i_b_8e_additions': '540ca_form - 2011',
     'sch_ca_line_part_i_b_8f_subtractions': '540ca_form - 2013',
     'sch_ca_line_part_i_b_8k_additions': '540ca_form - 2019',
     'sch_ca_line_part_i_b_8n_subtractions': '540ca_form - 2023',
     'sch_ca_line_part_i_b_8o_subtractions': '540ca_form - 2025',
     'sch_ca_line_part_i_b_8p_additions': '540ca_form - 2028',
     'sch_ca_line_part_i_b_8p_subtractions': '540ca_form - 2027',
     'sch_ca_line_part_i_b_9b1_subtractions': '540ca_form - 3004',
     'sch_ca_line_part_i_b_9b2_subtractions': '540ca_form - 3005',
     'sch_ca_line_part_i_b_9b3_subtractions': '540ca_form - 3006',
     'sch_ca_line_part_i_c_12_additions': '540ca_form - 3014',
     'sch_ca_line_part_i_c_12_subtractions': '540ca_form - 3013',
     'sch_ca_line_part_i_c_14_additions': '540ca_form - 3018',
     'sch_ca_line_part_i_c_19a_additions': '540ca_form - 3026',
     'sch_ca_line_part_i_c_24b_additions': '540ca_form - 4004',
     'sch_ca_line_part_i_c_24b_subtractions': '540ca_form - 4003',
     'sch_ca_line_part_i_c_24c_subtractions': '540ca_form - 4006',
     'sch_ca_line_part_i_c_24d_subtractions': '540ca_form - 4008',
     'sch_ca_line_part_i_c_24f_additions': '540ca_form - 4012',
     'sch_ca_line_part_i_c_24f_subtractions': '540ca_form - 4011',
     'sch_ca_line_part_i_c_24g_additions': '540ca_form - 4015',
     'sch_ca_line_part_i_c_24g_subtractions': '540ca_form - 4014',
     'sch_ca_line_part_i_c_24i_subtractions': '540ca_form - 4018',
     'sch_ca_line_part_i_c_24j_subtractions': '540ca_form - 4020'}

_TOTAL_CELLS_2024: dict[str, str] = {'1aA': '540ca_form - 1002',
     '1aB': '540ca_form - 1003',
     '1aC': '540ca_form - 1004',
     '1zA': '540ca_form - 1027',
     '1zB': '540ca_form - 1028',
     '1zC': '540ca_form - 1029',
     '9aA': '540ca_form - 3001',
     '9aB': '540ca_form - 3002',
     '9aC': '540ca_form - 3003',
     '10A': '540ca_form - 3007',
     '10B': '540ca_form - 3008',
     '10C': '540ca_form - 3009',
     '25A': '540ca_form - 4026',
     '25B': '540ca_form - 4027',
     '25C': '540ca_form - 4028',
     '26A': '540ca_form - 4029',
     '26B': '540ca_form - 4030',
     '26C': '540ca_form - 4031'}

_CATALOG_CELLS_2025: dict[str, str] = {'sch_ca_line_part_i_a_1a_additions': '540ca_form - 1004',
     'sch_ca_line_part_i_a_1a_subtractions': '540ca_form - 1003',
     'sch_ca_line_part_i_a_1d_subtractions': '540ca_form - 1012',
     'sch_ca_line_part_i_a_1h_additions': '540ca_form - 1025',
     'sch_ca_line_part_i_a_1h_subtractions': '540ca_form - 1024',
     'sch_ca_line_part_i_a_1i_additions': '540ca_form - 1026',
     'sch_ca_line_part_i_b_2a_additions': '540ca_form - 1055',
     'sch_ca_line_part_i_b_8a_additions': '540ca_form - 2002',
     'sch_ca_line_part_i_b_8c_additions': '540ca_form - 2007',
     'sch_ca_line_part_i_b_8d_additions': '540ca_form - 2009',
     'sch_ca_line_part_i_b_8e_additions': '540ca_form - 2011',
     'sch_ca_line_part_i_b_8f_subtractions': '540ca_form - 2013',
     'sch_ca_line_part_i_b_8k_additions': '540ca_form - 2019',
     'sch_ca_line_part_i_b_8n_subtractions': '540ca_form - 2023',
     'sch_ca_line_part_i_b_8o_subtractions': '540ca_form - 2025',
     'sch_ca_line_part_i_b_8p_additions': '540ca_form - 2028',
     'sch_ca_line_part_i_b_8p_subtractions': '540ca_form - 2027',
     'sch_ca_line_part_i_b_9b1_subtractions': '540ca_form - 3004B',
     'sch_ca_line_part_i_b_9b2_subtractions': '540ca_form - 3005B',
     'sch_ca_line_part_i_b_9b3_subtractions': '540ca_form - 3006B',
     'sch_ca_line_part_i_c_12_subtractions': '540ca_form - 3013',
     'sch_ca_line_part_i_c_19a_additions': '540ca_form - 3026',
     'sch_ca_line_part_i_c_24b_additions': '540ca_form - 4004',
     'sch_ca_line_part_i_c_24b_subtractions': '540ca_form - 4003',
     'sch_ca_line_part_i_c_24d_subtractions': '540ca_form - 4008',
     'sch_ca_line_part_i_c_24f_additions': '540ca_form - 4012',
     'sch_ca_line_part_i_c_24f_subtractions': '540ca_form - 4011',
     'sch_ca_line_part_i_c_24g_additions': '540ca_form - 4015',
     'sch_ca_line_part_i_c_24g_subtractions': '540ca_form - 4014',
     'sch_ca_line_part_i_c_24i_subtractions': '540ca_form - 4018',
     'sch_ca_line_part_i_c_24j_subtractions': '540ca_form - 4020',
    'sch_ca_line_part_i_b_8b_subtractions': '540ca_form - 2004',
    'sch_ca_line_part_i_c_12_additions': '540ca_form - 3014',
    'sch_ca_line_part_i_c_14_additions': '540ca_form - 3018'}

_TOTAL_CELLS_2025: dict[str, str] = {'1aA': '540ca_form - 1002',
     '1aB': '540ca_form - 1003',
     '1aC': '540ca_form - 1004',
     '1zA': '540ca_form - 1027',
     '1zB': '540ca_form - 1028',
     '1zC': '540ca_form - 1029',
     '9aA': '540ca_form - 3001',
     '9aB': '540ca_form - 3002',
     '9aC': '540ca_form - 3003',
     '10A': '540ca_form - 3007',
     '10B': '540ca_form - 3008',
     '10C': '540ca_form - 3009',
     '25A': '540ca_form - 4026',
     '25B': '540ca_form - 4027',
     '25C': '540ca_form - 4028',
     '26A': '540ca_form - 4029',
     '26B': '540ca_form - 4030',
     '26C': '540ca_form - 4031'}


_SUFFIX = {"A": "col_a", "B": "subtractions", "C": "additions"}

# Section membership by compute-key pattern (key = sch_ca_line_<pattern>_<suffix>).
# Line 1 block: 2022+ lines 1a-1i and the 1z subtotal; 2021's single un-lettered line 1.
_LINE_1_BLOCK = r"part_i_(a_1[a-z]|line_1)"
_SECTION_A_REST = r"part_i_a_(2|3|4|5b|6|7)"
_SECTION_B_MAIN = r"part_i_b_(1|2a|3|4|5|6|7)"
_LINE_8_BLOCK = r"part_i_b_8[a-z]"           # -> line 9a
_LINE_9B_BLOCK = r"part_i_b_9b\d"            # Col B only, joins line 10 Col B
_SECTION_C_MAIN = r"part_i_c_(1[1-8]|19a|2[0-3])"
_LINE_24_BLOCK = r"part_i_c_24[a-z]"         # -> line 25
_LINE_26_OWN = r"part_i_line_26"             # the §179A row posts at line 26 itself


def _install_sch_ca_totals(year, mapping, derivations, suppressed,
                           catalog_cells, total_cells):
    """Place every catalog-routed Part I cell and derive the section totals from
    the same compute keys, so line 10 - line 26 = line 27 on the printed page."""
    mapping.update(catalog_cells)
    universe = set(mapping) | set(suppressed)

    def keys(pattern, col):
        rx = re.compile(rf"sch_ca_line_({pattern})_{_SUFFIX[col]}")
        return sorted(k for k in universe if rx.fullmatch(k))

    def total(c, groups, col):
        return sum(c.get(k, 0) for g in groups for k in keys(g, col))

    def any_present(c, groups, col):
        return any(k in c for g in groups for k in keys(g, col))

    def put(token, col, groups, *, always):
        field = total_cells.get(token + col)
        if field is None:
            return
        if always:
            derivations[field] = lambda c, g=groups, col=col: total(c, g, col)
        else:
            derivations[field] = (
                lambda c, g=groups, col=col:
                total(c, g, col) if any_present(c, g, col) else None)

    for col in "ABC":
        if col != "A":   # 1z Col A is the 1:1 federal passthrough (wages)
            put("1z", col, (_LINE_1_BLOCK,), always=False)
        put("9a", col, (_LINE_8_BLOCK,), always=False)
        put("25", col, (_LINE_24_BLOCK,), always=False)
        line10 = (_LINE_1_BLOCK, _SECTION_A_REST, _SECTION_B_MAIN, _LINE_8_BLOCK)
        if col == "B":
            line10 += (_LINE_9B_BLOCK,)
        put("10", col, line10, always=True)
        put("26", col, (_SECTION_C_MAIN, _LINE_24_BLOCK, _LINE_26_OWN), always=True)

    # Line 1a Col A mirrors its federal counterpart (Form 1040 line 1a = W-2 wages,
    # which is also what feeds the 1z subtotal; 1b-1i have no federal source and
    # stay blank, as on the federal 1040).
    if "1aA" in total_cells:
        derivations[total_cells["1aA"]] = (
            lambda c: c.get("sch_ca_line_part_i_a_1z_col_a"))



# Section A memo cells (federal 1040 lines 2a/3a/4a/5a/6a). Tooltip-verified:
# each tooltip ends "Line N a." (see tests/test_ca_sch_ca_completeness.py).
_MEMO_KEYS = ("sch_ca_memo_line_2a_tax_exempt_interest",
              "sch_ca_memo_line_3a_qualified_dividends",
              "sch_ca_memo_line_4a_ira_distributions",
              "sch_ca_memo_line_5a_pensions",
              "sch_ca_memo_line_6a_social_security")
_MEMO_FIELDS = {
    2021: ("1006", "1010", "1014", "1018", "1022"),
    2023: ("1030", "1034", "1038", "1042", "1046"),
    2024: tuple(f"540ca_form - {n}" for n in (1030, 1034, 1038, 1042, 1046)),
    2025: tuple(f"540ca_form - {n}" for n in (1030, 1034, 1038, 1042, 1046)),
}
for _y, _m in ((2021, _MAPPING_2021), (2023, _MAPPING_2023),
               (2024, _MAPPING_2024), (2025, _MAPPING_2025)):
    _m.update(dict(zip(_MEMO_KEYS, _MEMO_FIELDS[_y])))

# Keys the catalog can post that have no cell of their own: (a) the §179A row posts
# AT line 26 (its amount is folded into the derived line-26 cell), (b) catalog
# directions the template prints no column for (see the note above).
_LINE_26_KEYS = frozenset({
    "sch_ca_line_part_i_line_26_subtractions",
    "sch_ca_line_part_i_line_26_additions",
})
_SUPPRESSED_2021 = _SUPPRESSED_2021 | _LINE_26_KEYS | {
    "sch_ca_line_part_i_b_8e_additions",
    # 2021 prints one un-lettered line 1; the catalog's "Part I line 1" rows share
    # its Col B / Col C cells with the "1z" keys, so they are folded into the one
    # derived cell (a second 1:1 mapping onto the same field would be a duplicate path).
    "sch_ca_line_part_i_line_1_subtractions",
    "sch_ca_line_part_i_line_1_additions"}
_SUPPRESSED_2023 = _SUPPRESSED_2023 | _LINE_26_KEYS
_SUPPRESSED_2022 = _SUPPRESSED_2023
_SUPPRESSED_2024 = _SUPPRESSED_2024 | _LINE_26_KEYS
_SUPPRESSED_2025 = _SUPPRESSED_2025 | _LINE_26_KEYS

_install_sch_ca_totals(2021, _MAPPING_2021, _DERIVATIONS_2021, _SUPPRESSED_2021,
                       _CATALOG_CELLS_2021, _TOTAL_CELLS_2021)
# 2022 shares 2023's mapping / derivation / suppression objects (identical field tree).
_install_sch_ca_totals(2023, _MAPPING_2023, _DERIVATIONS_2023, _SUPPRESSED_2023,
                       _CATALOG_CELLS_2023, _TOTAL_CELLS_2023)
_install_sch_ca_totals(2024, _MAPPING_2024, _DERIVATIONS_2024, _SUPPRESSED_2024,
                       _CATALOG_CELLS_2024, _TOTAL_CELLS_2024)
_install_sch_ca_totals(2025, _MAPPING_2025, _DERIVATIONS_2025, _SUPPRESSED_2025,
                       _CATALOG_CELLS_2025, _TOTAL_CELLS_2025)


# ── Part II (adjustments to federal itemized deductions) ────────────────────
#
# forms.sch_ca.compute_part_ii_itemized emits one key per printed cell —
# sch_ca_line_part_ii_<line>[_col_a|_subtractions|_additions] — only on a
# return that itemizes, so on a standard-deduction return every cell below
# stays blank. Tokens are the line plus its column (A federal amounts,
# B subtractions, C additions); lines 1-3, 18, 26, 28 and 29 are single cells.
#
# Field numbers were read from each template's /TU tooltips and are
# re-verified against them by tests/test_ca_sch_ca_part_ii_print.py. 2021
# numbers Part II in its own 4xxx/5xxx bands (it starts a page earlier);
# 2022-2025 share one numbering, with the '540ca_form - ' prefix from 2024.
_PART_II_TOKENS = (
    "1", "2", "3", "4A",
    "5aA", "5aB", "5bA", "5cA", "5dA", "5eA", "5eB", "5eC",
    "7A", "7B", "7C",
    "8aA", "8eA", "10A",
    "11A", "12A", "14A",
    "17A", "17B", "17C",
    "18", "26", "28", "29",
)
_PART_II_FIELDS_2021 = (
    "4001", "4005", "4009", "4013",
    "4016", "4017", "4019", "4022", "4025", "4028", "4029", "4030",
    "4035", "4036", "4037",
    "4038", "4050", "4056",
    "5001", "5004", "5010",
    "5019", "5020", "5021",
    "5022", "5031", "5034", "5035",
)
_PART_II_FIELDS_2023 = (
    "5001", "5002", "5003", "5004",
    "5006", "5007", "5008", "5009", "5010", "5011", "5012", "5013",
    "5018", "5019", "5020",
    "5021", "5027", "5033",
    "6001", "6004", "6010",
    "6019", "6020", "6021",
    "6022", "6031", "6034", "6035",
)
_PART_II_FIELDS_2024 = tuple(f"540ca_form - {n}" for n in _PART_II_FIELDS_2023)
# Line 30 ("the larger of line 29 or your standard deduction ... Transfer the
# amount on line 30 to Form 540, line 18").
_PART_II_LINE_30_FIELD = {
    2021: "5036", 2023: "6036",
    2024: "540ca_form - 6036", 2025: "540ca_form - 6036",
}
# The section sums and the total are what Form 540 line 18 is computed from;
# the page prints the per-line cells above, not these.
_PART_II_TRANSIT_KEYS = frozenset({
    "sch_ca_part_ii_medical",
    "sch_ca_part_ii_taxes",
    "sch_ca_part_ii_mortgage",
    "sch_ca_part_ii_charity",
    "ca_itemized_total",
})


def _part_ii_key(token: str) -> str:
    if token[-1] in _SUFFIX:
        return f"sch_ca_line_part_ii_{token[:-1]}_{_SUFFIX[token[-1]]}"
    return f"sch_ca_line_part_ii_{token}"


def _install_sch_ca_part_ii(mapping, derivations, fields, line_30_field):
    mapping.update(
        {_part_ii_key(token): field
         for token, field in zip(_PART_II_TOKENS, fields, strict=True)})
    # Line 30 is by definition the Form 540 line 18 deduction, so it prints
    # that figure itself rather than a second computation of it — and only
    # when Part II is on the page at all (line 28 present).
    derivations[line_30_field] = (
        lambda c: c.get("f540_deduction")
        if c.get("sch_ca_line_part_ii_28") is not None else None)


# 2022 shares 2023's mapping / derivation objects (identical field tree).
for _y, _m, _d, _fields in (
        (2021, _MAPPING_2021, _DERIVATIONS_2021, _PART_II_FIELDS_2021),
        (2023, _MAPPING_2023, _DERIVATIONS_2023, _PART_II_FIELDS_2023),
        (2024, _MAPPING_2024, _DERIVATIONS_2024, _PART_II_FIELDS_2024),
        (2025, _MAPPING_2025, _DERIVATIONS_2025, _PART_II_FIELDS_2024)):
    _install_sch_ca_part_ii(_m, _d, _fields, _PART_II_LINE_30_FIELD[_y])

_SUPPRESSED_2021 = _SUPPRESSED_2021 | _PART_II_TRANSIT_KEYS
_SUPPRESSED_2023 = _SUPPRESSED_2023 | _PART_II_TRANSIT_KEYS
_SUPPRESSED_2022 = _SUPPRESSED_2023
_SUPPRESSED_2024 = _SUPPRESSED_2024 | _PART_II_TRANSIT_KEYS
_SUPPRESSED_2025 = _SUPPRESSED_2025 | _PART_II_TRANSIT_KEYS


_AGGREGATIONS_BY_YEAR: dict[int, dict[str, tuple[str, ...]]] = {
    2021: _AGGREGATIONS_2021, 2022: _AGGREGATIONS_2022,
    2023: _AGGREGATIONS_2023, 2024: _AGGREGATIONS_2024, 2025: _AGGREGATIONS_2025,
}
_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2021: _DERIVATIONS_2021, 2022: _DERIVATIONS_2022,
    2023: _DERIVATIONS_2023, 2024: _DERIVATIONS_2024, 2025: _DERIVATIONS_2025,
}
_SUPPRESSED_BY_YEAR: dict[int, frozenset[str]] = {
    2021: _SUPPRESSED_2021, 2022: _SUPPRESSED_2022,
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _CHECKBOX_STATES_2021, 2022: _CHECKBOX_STATES_2022,
    2023: _CHECKBOX_STATES_2023, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}
