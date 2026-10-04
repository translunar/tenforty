"""PDF field mapping for FTB 2025 Form 540 (California Resident).

Mirrors the five-registry design from `pdf_f1120s.py`:

- `_MAPPING_2025` — direct compute_key → PDF-field-path. The 11 compute
  output keys with a direct cell + 14 [PLANNED] orchestrator-supplied
  keys (taxpayer/spouse/address/email/phone/county) reserved for
  future wiring.
- `_AGGREGATIONS_2025` — empty for f540. All within-form sums on Form
  540 are encoded as DERIVATIONS (max(0, ...) clamps, sign-split flow)
  rather than pure +/- of compute keys.
- `_DERIVATIONS_2025` — PDF cells whose value is computed from compute
  outputs at fill time. Includes (a) form-internal arithmetic per the
  probe artifact, (b) lines 111 / 114 / 115 (amount you owe, total amount
  due, refund — installed for every year by `_install_amount_due`), (c) the verbose
  filing-status radio group (`540_form_1036 RB`), and (d) the two
  tax-source checkboxes on line 31 (Tax Table vs Rate Schedule).
- `_SUPPRESSED_2025` — extended semantics from SP2: compute keys with
  no direct PDF cell, EITHER because they are out-of-scope for v1 OR
  because they are consumed only by derivations (sign-split,
  enum-typed). The partition test treats SUPPRESSED as ownership for
  consumed-by-derivation keys; the derivation lambdas may then read
  them.
- `_CHECKBOX_STATES_2025` — empty for f540. All checkbox cells in v1
  are either out-of-scope or wired through DERIVATIONS that emit the
  `/Yes`/`/Off` state string directly.

Field paths come from the probe artifact at
`docs/plans/sp3-t12-f540-probe.md` (gitignored). pypdf reports flat
field names (`540_form_<page><seq>`), simpler than the IRS XFA
`topmostSubform[0].PageN[0]....` convention used in SP2.

The verbose FTB filing-status radio appearance states (`/1 . Single.`,
etc.) live byte-for-byte in `_FILING_STATUS_RB_STATES` to isolate this
known-brittle FTB encoding anomaly from caller code.
"""

from collections.abc import Callable, Mapping

from tenforty.mappings.registry import PdfFormMapping
from tenforty.models import FilingStatus


_FILING_STATUS_RB_STATES: dict[FilingStatus, str] = {
    FilingStatus.SINGLE: "/1 . Single.",
    FilingStatus.MARRIED_JOINTLY: (
        "/2 . Married/R D P filing jointly "
        "(even if only one spouse / R D P had income). See instructions."
    ),
    FilingStatus.MARRIED_SEPARATELY: "/3 . Married or R D P filing separately.",
    FilingStatus.HEAD_OF_HOUSEHOLD: (
        "/4 . Head of household (with qualifying person). See instructions."
    ),
    FilingStatus.QUALIFYING_WIDOW: "/5 . Qualifying surviving spouse or R D P .",
}


class PdfF540(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for FTB Form 540 (California Resident).

    Five-registry design (see module docstring). The partition invariant
    enforced by the mapping test is that every expected compute key from
    `f540.compute()` is OWNED by exactly one of `_MAPPING_<year>`,
    `_AGGREGATIONS_<year>`, or `_SUPPRESSED_<year>`. Derivations consume
    compute keys but do not own them — every key referenced inside a
    lambda body must already be owned elsewhere or supplied by the
    orchestrator at fill time (e.g., `[PLANNED]` taxpayer keys).
    """

    _FORM_NAME = "Form 540"
    _MAPPINGS: dict[int, dict[str, str]] = {}  # populated below after _MAPPING_2025

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        if year not in _AGGREGATIONS_BY_YEAR:
            raise ValueError(f"No Form 540 aggregations for year {year}")
        return _AGGREGATIONS_BY_YEAR[year]

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in _DERIVATIONS_BY_YEAR:
            raise ValueError(f"No Form 540 derivations for year {year}")
        return _DERIVATIONS_BY_YEAR[year]

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year not in _SUPPRESSED_BY_YEAR:
            raise ValueError(f"No Form 540 suppressions for year {year}")
        return _SUPPRESSED_BY_YEAR[year]

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        if year not in _CHECKBOX_STATES_BY_YEAR:
            raise ValueError(f"No Form 540 checkbox states for year {year}")
        return _CHECKBOX_STATES_BY_YEAR[year]


# Direct 1:1 mappings — compute keys with a direct PDF cell + [PLANNED]
# orchestrator-supplied keys reserved for future wiring.
_MAPPING_2025: dict[str, str] = {
    # Page 1 — Taxpayer / spouse / address ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_first_name":      "540_form_1003",
    "f540_taxpayer_middle_initial":  "540_form_1004",
    "f540_taxpayer_last_name":       "540_form_1005",
    "f540_taxpayer_suffix":          "540_form_1006",
    "f540_taxpayer_ssn":             "540_form_1007",
    "f540_spouse_first_name":        "540_form_1008",
    "f540_spouse_last_name":         "540_form_1010",
    "f540_spouse_ssn":               "540_form_1012",
    "f540_address_street":           "540_form_1015",
    "f540_address_city":             "540_form_1018",
    "f540_address_state":            "540_form_1019",
    "f540_address_zip":              "540_form_1020",
    "f540_residence_county":         "540_form_1028",
    # Page 2 — Taxable income + tax
    "f540_federal_agi":              "540_form_2019",  # line 13 (federal AGI)
    "f540_ca_agi":                   "540_form_2023",  # line 17
    "f540_deduction":                "540_form_2024",  # line 18
    "f540_taxable_income":           "540_form_2025",  # line 19
    "f540_ca_tax":                   "540_form_2030",  # line 31
    "f540_exemption_credit":         "540_form_2031",  # line 32
    # Page 3 — Credits + payments + use tax
    "f540_renter_credit":            "540_form_3004",  # line 46
    "f540_estimated_payments":       "540_form_3012",  # line 72
    "f540_use_tax":                  "540_form_3019",  # line 91
    # Page 4 — Voluntary contributions
    "f540_voluntary_contributions":  "540_form_4024",  # line 110
    # Page 5 — Estimated tax penalty
    "f540_estimated_tax_penalty":    "540_form_5005",  # line 113
    # Page 6 — Sign block ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_email":           "540_form_6002",
    "f540_taxpayer_phone":           "540_form_6003",
}


# All within-form sums on Form 540 are clamped (max(0, ...)) or
# sign-split — encoded as DERIVATIONS rather than pure aggregations.
_AGGREGATIONS_2025: dict[str, tuple[str, ...]] = {}


# PDF cells whose value is derived from compute outputs at fill time.
#
# Convention: derivation lambdas consume compute keys but do not own
# them. Keys referenced via `c[...]` must already appear in
# `_MAPPING_2025`, `_AGGREGATIONS_2025`, or `_SUPPRESSED_2025`. Keys
# referenced via `c.get(..., default)` are orchestrator-supplied or
# v1-default ([PLANNED] / [OUT_OF_V1_SCOPE]) and the partition test
# does not enforce ownership for them. PdfFiller catches KeyError and
# skips the cell when a required key is absent; lambdas returning
# `None` are also skipped (no value written).
#
# Named helpers below extract sub-expressions that recur across multiple
# derivation lambdas. Each helper is called from at least 2 places — see
# call counts in inline comments.


def _line_33(c: Mapping[str, object]) -> float:
    """Line 33 = max(0, line 31 − line 32). Called from 540_form_2032,
    540_form_2036, _line_47-consumers (3006/3010/3027/4004/4005)."""
    return max(0, c["f540_ca_tax"] - c["f540_exemption_credit"])


def _line_47(c: Mapping[str, object]) -> float:
    """Line 47 = total credits (renter + ptet + [PLANNED] line40/43-45).
    Called from 540_form_3005, 540_form_3006, 540_form_3010, 540_form_3027,
    540_form_4004, 540_form_4005."""
    return (
        c["f540_renter_credit"]
        + c.get("f540_ptet_credit", 0)
        + c.get("f540_line40_child_dep_care", 0)
        + c.get("f540_line43_credit_amount", 0)
        + c.get("f540_line44_credit_amount", 0)
        + c.get("f540_line45_sch_p_credits", 0)
    )


def _line_48(c: Mapping[str, object]) -> float:
    """Line 48 = max(0, line 35 − line 47). In v1 line 35 == line 33
    (line 34 OUT_OF_V1_SCOPE defaults 0). Called from 540_form_3006,
    540_form_3010, 540_form_3027, 540_form_4004, 540_form_4005."""
    return max(0, _line_33(c) - _line_47(c))


def _line_64(c: Mapping[str, object]) -> float:
    """Line 64 = line 48 + 61 + 62 + 63. Lines 61-63 ([PLANNED] AMT,
    behavioral health, other taxes/recapture) default 0. Called from
    540_form_3010, 540_form_3027, 540_form_4004, 540_form_4005."""
    return (
        _line_48(c)
        + c.get("f540_line61_amt", 0)
        + c.get("f540_line62_behavioral_health", 0)
        + c.get("f540_line63_other_taxes", 0)
    )


def _line_78(c: Mapping[str, object]) -> float:
    """Line 78 = total payments = sum of lines 71-77 (CA withholding, estimated
    payments, 592-B/593 withholding, Program 4.0, EITC, YCTC, FYTC). Only
    line 72 (estimated payments) and line 71 (CA withholding) are modeled in
    v1; the rest default 0. This is the SINGLE line-78 total; the per-year
    line-78 boxes and the settlement chain (line 93) both read it, so they
    cannot disagree."""
    return (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    )


def _line_93(c: Mapping[str, object]) -> float:
    """Line 93 = max(0, line 78 − line 91). Line 91 is use tax
    (``f540_use_tax``). Line 78 is the TOTAL payments (``_line_78``), NOT the
    estimated-payments component alone — sourcing only estimated payments
    understated line 93 whenever payments arrived via CA withholding, which
    collapsed line 95 toward 0 and made line 100 (tax due) print the full tax
    ignoring payments while line 97/99 (overpaid) went unfilled. Called from
    the line-93/95/97/99/100 derivations in every year surface."""
    return max(0, _line_78(c) - c["f540_use_tax"])


def _line_95(c: Mapping[str, object]) -> float:
    """Line 95 = max(0, line 93 − line 92). Line 92 = ISR penalty
    ([PLANNED]; defaults 0). Called from 540_form_3025, 540_form_3027,
    540_form_4004, 540_form_4005."""
    return max(0, _line_93(c) - c.get("f540_line92_isr_penalty", 0))


_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Filing-status radio group (page 1, line 1-5). Verbose state
    # strings per the FTB convention (FTB encoding anomaly).
    "540_form_1036 RB": lambda c: _FILING_STATUS_RB_STATES[c["f540_filing_status"]],
    # Line 31 tax-source checkboxes. f540_taxable_income ≤ 100,000 →
    # Tax Table; > 100,000 → Rate Schedule. The lambda returns the
    # appearance state string directly so PdfFiller's _render_scalar
    # passes it through (bool would be rejected).
    "540_form_2026 CB": lambda c: "/Yes" if c["f540_taxable_income"] <= 100_000 else "/Off",
    "540_form_2027 CB": lambda c: "/Yes" if c["f540_taxable_income"] > 100_000 else "/Off",
    # Line 33 = max(0, line 31 − line 32). Line 31 = ca_tax, line 32 = exemption.
    "540_form_2032": lambda c: _line_33(c),
    # Line 35 = line 33 + line 34. Line 34 (Sch G-1 / FTB 5870A) is
    # OUT_OF_V1_SCOPE, defaults 0 — so v1 line 35 == line 33.
    "540_form_2036": lambda c: _line_33(c),
    # Line 47 = total credits (renters + ptet + [PLANNED] line40/43-45,
    # all default 0 in v1). Note: this is NOT compute()'s
    # f540_total_credits, which includes exemption credit (already
    # subtracted at line 32). See module-level note on line-47 vs
    # compute() total-credits semantic divergence.
    "540_form_3005": lambda c: _line_47(c),
    # Line 48 = max(0, line 35 − line 47).
    "540_form_3006": lambda c: _line_48(c),
    # Line 64 = line 48 + 61 + 62 + 63. Lines 61-63 ([PLANNED] AMT,
    # behavioral health, other taxes/recapture) default 0.
    "540_form_3010": lambda c: _line_64(c),
    # Line 78 = sum lines 71-77. Only line 72 = estimated_payments is
    # in v1; lines 71/73-77 ([PLANNED] CA withholding, 592-B/593,
    # Program 4.0, EITC, YCTC, FYTC) default 0.
    "540_form_3018": lambda c: (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    ),
    # Line 93 = max(0, line 78 − line 91). Line 78 is the TOTAL payments
    # (_line_78: lines 71-77, incl. CA withholding), not just estimated.
    "540_form_3023": lambda c: _line_93(c),
    # Line 94 = max(0, line 91 − line 78).
    "540_form_3024": lambda c: max(
        0, c["f540_use_tax"] - _line_78(c)
    ),
    # Line 95 = max(0, line 93 − line 92). Line 92 = ISR penalty
    # ([PLANNED]; defaults 0).
    "540_form_3025": lambda c: _line_95(c),
    # Line 96 = max(0, line 92 − line 93). With line 92 defaulting 0,
    # this is 0 in v1.
    "540_form_3026": lambda c: max(
        0,
        c.get("f540_line92_isr_penalty", 0) - _line_93(c),
    ),
    # Line 97 = max(0, line 95 − line 64). The "overpaid tax" branch.
    "540_form_3027": lambda c: max(0, _line_95(c) - _line_64(c)),
    # Line 99 = line 97 − line 98 (line 98 carryover-to-2026 is
    # [OUT_OF_V1_SCOPE]; defaults 0). Equals line 97 in v1.
    "540_form_4004": lambda c: (
        max(0, _line_95(c) - _line_64(c))
        - c.get("f540_line98_applied_to_2026_estimated", 0)
    ),
    # Line 100 = max(0, line 64 − line 95). The "tax due" branch.
    "540_form_4005": lambda c: max(0, _line_64(c) - _line_95(c)),
}


# Compute keys with no direct PDF cell on the 2025 form.
#
# Extended SUPPRESSED semantics (SP3 calibration): includes BOTH
# (a) keys with no fillable cell (out-of-scope; user reports externally
# via attestation) AND (b) keys consumed only by derivations (sign-split
# flow, enum-typed dispatch). The partition test treats both subsets as
# ownership; derivation lambdas may read them.
_SUPPRESSED_2025: frozenset[str] = frozenset({
    # No PDF cell: the net tax position (Schedule X reads it). Lines 111 /
    # 114 / 115 are derived from the form's own lines — see _AMOUNT_DUE_CELLS.
    "f540_total_liability",
    # Consumed-by-derivation only (filing-status RB lookup via
    # _FILING_STATUS_RB_STATES).
    "f540_filing_status",
    # PTET credit — claimed via line 43/44 with credit code; concrete
    # cell allocation deferred to Sub-plan 4. The line 47 derivation
    # consumes it via c.get(..., 0).
    "f540_ptet_credit",
    # Compute()'s f540_total_credits includes exemption_credit
    # (subtracted at line 32 on the form). The form's line 47
    # "total credits" excludes exemption — different semantic. v1
    # derives line 47 directly from renter + ptet + [PLANNED] credits;
    # the compute() key is internal-only for the final-liability calc.
    # Surfaced as a follow-up (line-47 vs compute() total-credits
    # semantic divergence).
    "f540_total_credits",
})


# All v1 checkboxes are either out-of-scope (no compute key) or wired
# through DERIVATIONS that emit "/Yes" / "/Off" strings directly. No
# bool compute keys are mapped to checkbox cells in v1.
_CHECKBOX_STATES_2025: dict[str, str] = {}


# ── 2024 registries ─────────────────────────────────────────────────────────
#
# Field names use hyphen prefix `540-NNNN` (vs 2025's `540_form_NNNN`).
# Sequence numbers and semantic line assignments are identical between
# years — verified against `/TU` tooltips from the 2024 PDF probe.

_FILING_STATUS_RB_STATES_2024: dict[FilingStatus, str] = {
    FilingStatus.SINGLE: "/Box 1 . Single.",
    FilingStatus.MARRIED_JOINTLY: (
        "/Box 2 . Married/Registered Domestic Partner filing jointly "
        "(even if only one spouse/Registered Domestic Partner had income). See instructions."
    ),
    FilingStatus.MARRIED_SEPARATELY: (
        "/Box 3 . Married or Registered Domestic Partner filing separately."
    ),
    FilingStatus.HEAD_OF_HOUSEHOLD: (
        "/Box 4 . Head of household (with qualifying person). See instructions."
    ),
    FilingStatus.QUALIFYING_WIDOW: (
        "/Box 5 . Qualifying surviving spouse or Registered Domestic Partner."
    ),
}


_MAPPING_2024: dict[str, str] = {
    # Page 1 — Taxpayer / spouse / address ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_first_name":      "540-1003",
    "f540_taxpayer_middle_initial":  "540-1004",
    "f540_taxpayer_last_name":       "540-1005",
    "f540_taxpayer_suffix":          "540-1006",
    "f540_taxpayer_ssn":             "540-1007",
    "f540_spouse_first_name":        "540-1008",
    "f540_spouse_last_name":         "540-1010",
    "f540_spouse_ssn":               "540-1012",
    "f540_address_street":           "540-1015",
    "f540_address_city":             "540-1018",
    "f540_address_state":            "540-1019",
    "f540_address_zip":              "540-1020",
    "f540_residence_county":         "540-1028",
    # Page 2 — Taxable income + tax
    "f540_federal_agi":              "540-2019",  # line 13 (federal AGI)
    "f540_ca_agi":                   "540-2023",  # line 17
    "f540_deduction":                "540-2024",  # line 18
    "f540_taxable_income":           "540-2025",  # line 19
    "f540_ca_tax":                   "540-2030",  # line 31
    "f540_exemption_credit":         "540-2031",  # line 32
    # Page 3 — Credits + payments + use tax
    "f540_renter_credit":            "540-3004",  # line 46
    "f540_estimated_payments":       "540-3012",  # line 72
    "f540_use_tax":                  "540-3019",  # line 91
    # Page 4 — Voluntary contributions
    "f540_voluntary_contributions":  "540-4024",  # line 110
    # Page 5 — Estimated tax penalty
    "f540_estimated_tax_penalty":    "540-5005",  # line 113
    # Page 6 — Sign block ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_email":           "540-6002",
    "f540_taxpayer_phone":           "540-6003",
}


_AGGREGATIONS_2024: dict[str, tuple[str, ...]] = {}


_DERIVATIONS_2024: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Filing-status radio group (page 1, line 1-5). Verbose state strings
    # per the 2024 FTB PDF probe (different from 2025 strings).
    "540-1036 RB": lambda c: _FILING_STATUS_RB_STATES_2024[c["f540_filing_status"]],
    # Line 31 tax-source checkboxes. f540_taxable_income ≤ 100,000 →
    # Tax Table; > 100,000 → Rate Schedule. On-states `/Yes`/`/Off` per probe.
    "540-2026 CB": lambda c: "/Yes" if c["f540_taxable_income"] <= 100_000 else "/Off",
    "540-2027 CB": lambda c: "/Yes" if c["f540_taxable_income"] > 100_000 else "/Off",
    # Line 33 = max(0, line 31 − line 32).
    "540-2032": lambda c: _line_33(c),
    # Line 35 = line 33 + line 34. Line 34 OUT_OF_V1_SCOPE, defaults 0.
    "540-2036": lambda c: _line_33(c),
    # Line 47 = total credits (renters + ptet + [PLANNED] line40/43-45).
    "540-3005": lambda c: _line_47(c),
    # Line 48 = max(0, line 35 − line 47).
    "540-3006": lambda c: _line_48(c),
    # Line 64 = line 48 + 61 + 62 + 63.
    "540-3010": lambda c: _line_64(c),
    # Line 78 = sum lines 71-77.
    "540-3018": lambda c: (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    ),
    # Line 93 = max(0, line 78 − line 91).
    "540-3023": lambda c: _line_93(c),
    # Line 94 = max(0, line 91 − line 78).
    "540-3024": lambda c: max(
        0, c["f540_use_tax"] - _line_78(c)
    ),
    # Line 95 = max(0, line 93 − line 92).
    "540-3025": lambda c: _line_95(c),
    # Line 96 = max(0, line 92 − line 93).
    "540-3026": lambda c: max(
        0,
        c.get("f540_line92_isr_penalty", 0) - _line_93(c),
    ),
    # Line 97 = max(0, line 95 − line 64).
    "540-3027": lambda c: max(0, _line_95(c) - _line_64(c)),
    # Line 99 = line 97 − line 98.
    "540-4004": lambda c: (
        max(0, _line_95(c) - _line_64(c))
        - c.get("f540_line98_applied_to_2026_estimated", 0)
    ),
    # Line 100 = max(0, line 64 − line 95).
    "540-4005": lambda c: max(0, _line_64(c) - _line_95(c)),
}


_SUPPRESSED_2024: frozenset[str] = frozenset({
    # No PDF cell: the net tax position (see _AMOUNT_DUE_CELLS for 111-115).
    "f540_total_liability",
    # Consumed-by-derivation only (filing-status RB lookup via
    # _FILING_STATUS_RB_STATES_2024).
    "f540_filing_status",
    # PTET credit — claimed via line 43/44 with credit code; concrete
    # cell allocation deferred to Sub-plan 4.
    "f540_ptet_credit",
    # Compute()'s f540_total_credits includes exemption_credit
    # (subtracted at line 32 on the form); different semantic from line 47.
    "f540_total_credits",
})


_CHECKBOX_STATES_2024: dict[str, str] = {}


# ── 2023 registries ─────────────────────────────────────────────────────────
#
# THIRD FTB field-naming scheme: bare zero-padded numbers (`2023`, `3004`,
# `1036 CB`) with NO `540_form_`/`540-` prefix — matching the 2023 Sch D (540)
# and Sch CA schemes. Each widget carries a descriptive `/TU` tooltip naming
# its line, so the mapping was read from those tooltips and filled-emit-verified
# on the real 2023 template.
#
# TWO structural divergences from 2024/2025 — both invisible-shift traps caught
# only by reading tooltips + the /Btn probe, NOT by assuming the sequence
# numbers carried over:
#   1. Filing status is FIVE separate line-1..5 checkboxes (1036/1037/1038/
#      1040/1041 CB), not the single verbose-export radio group `NNNN RB`.
#   2. Several back-page cells shifted their sequence number vs 2024/2025:
#      line 110 -> 4026 (not 4024), line 113 -> 5006 (not 5005),
#      line 111 owe -> 4027 (not 5002), line 115 refund -> 5008 (not 5007).

_MAPPING_2023: dict[str, str] = {
    # Page 1 — Taxpayer / spouse / address ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_first_name":      "1003",
    "f540_taxpayer_middle_initial":  "1004",
    "f540_taxpayer_last_name":       "1005",
    "f540_taxpayer_suffix":          "1006",
    "f540_taxpayer_ssn":             "1007",
    "f540_spouse_first_name":        "1008",
    "f540_spouse_last_name":         "1010",
    "f540_spouse_ssn":               "1012",
    "f540_address_street":           "1015",
    "f540_address_city":             "1018",
    "f540_address_state":            "1019",
    "f540_address_zip":              "1020",
    "f540_residence_county":         "1028",
    # Page 2 — Taxable income + tax
    "f540_federal_agi":              "2019",  # line 13 (federal AGI)
    "f540_ca_agi":                   "2023",  # line 17
    "f540_deduction":                "2024",  # line 18
    "f540_taxable_income":           "2025",  # line 19
    "f540_ca_tax":                   "2030",  # line 31
    "f540_exemption_credit":         "2031",  # line 32
    # Page 3 — Credits + payments + use tax
    "f540_renter_credit":            "3004",  # line 46
    "f540_estimated_payments":       "3012",  # line 72
    "f540_use_tax":                  "3019",  # line 91
    # Page 4 — Voluntary contributions (line 110 -> 4026, SHIFTED from 4024)
    "f540_voluntary_contributions":  "4026",  # line 110
    # Page 5 — Estimated tax penalty (line 113 -> 5006, SHIFTED from 5005)
    "f540_estimated_tax_penalty":    "5006",  # line 113
    # Page 6 — Sign block ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_email":           "6002",
    "f540_taxpayer_phone":           "6003",
}


_AGGREGATIONS_2023: dict[str, tuple[str, ...]] = {}


# 2023 filing status: FIVE line-1..5 checkboxes (structural divergence #1).
# Source of truth for both the derivations below and the coverage test.
_FILING_STATUS_CB_2023: dict[FilingStatus, str] = {
    FilingStatus.SINGLE:             "1036 CB",  # Line 1. Single
    FilingStatus.MARRIED_JOINTLY:    "1037 CB",  # Line 2. MFJ / RDP jointly
    FilingStatus.MARRIED_SEPARATELY: "1038 CB",  # Line 3. MFS / RDP separately
    FilingStatus.HEAD_OF_HOUSEHOLD:  "1040 CB",  # Line 4. Head of household
    FilingStatus.QUALIFYING_WIDOW:   "1041 CB",  # Line 5. Qualifying surviving spouse / RDP
}


_DERIVATIONS_2023: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 31 tax-source checkboxes (checkbox A = tax table, B = rate
    # schedule). On-states `/Yes`/`/Off` per the 2023 /Btn probe.
    "2026 CB": lambda c: "/Yes" if c["f540_taxable_income"] <= 100_000 else "/Off",
    "2027 CB": lambda c: "/Yes" if c["f540_taxable_income"] > 100_000 else "/Off",
    # Line 33 = max(0, line 31 − line 32).
    "2032": lambda c: _line_33(c),
    # Line 35 = line 33 + line 34. Line 34 OUT_OF_V1_SCOPE, defaults 0.
    "2036": lambda c: _line_33(c),
    # Line 47 = total credits (renters + ptet + [PLANNED] line40/43-45).
    "3005": lambda c: _line_47(c),
    # Line 48 = max(0, line 35 − line 47).
    "3006": lambda c: _line_48(c),
    # Line 64 = line 48 + 61 + 62 + 63.
    "3010": lambda c: _line_64(c),
    # Line 78 = sum lines 71-77 (only line 72 = estimated_payments in v1).
    "3018": lambda c: (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    ),
    # Line 93 = max(0, line 78 − line 91).
    "3023": lambda c: _line_93(c),
    # Line 94 = max(0, line 91 − line 78).
    "3024": lambda c: max(0, c["f540_use_tax"] - _line_78(c)),
    # Line 95 = max(0, line 93 − line 92).
    "3025": lambda c: _line_95(c),
    # Line 96 = max(0, line 92 − line 93).
    "3026": lambda c: max(0, c.get("f540_line92_isr_penalty", 0) - _line_93(c)),
    # Line 97 = max(0, line 95 − line 64).
    "3027": lambda c: max(0, _line_95(c) - _line_64(c)),
    # Line 99 = line 97 − line 98.
    "4004": lambda c: (
        max(0, _line_95(c) - _line_64(c))
        - c.get("f540_line98_applied_to_2026_estimated", 0)
    ),
    # Line 100 = max(0, line 64 − line 95).
    "4005": lambda c: max(0, _line_64(c) - _line_95(c)),
}

# Filing-status checkboxes, generated from _FILING_STATUS_CB_2023 so the
# coverage test can assert every FilingStatus has a cell. Default-arg binding
# (`_s=status`) captures each status in its own lambda closure.
for _status, _cb in _FILING_STATUS_CB_2023.items():
    _DERIVATIONS_2023[_cb] = (
        lambda c, _s=_status: "/Yes" if c["f540_filing_status"] == _s else "/Off"
    )
del _status, _cb


_SUPPRESSED_2023: frozenset[str] = frozenset({
    # No PDF cell: the net tax position (see _AMOUNT_DUE_CELLS for 111-115).
    "f540_total_liability",
    # Consumed-by-derivation only (filing-status checkboxes via
    # _FILING_STATUS_CB_2023).
    "f540_filing_status",
    # PTET credit — line 43/44 with credit code; cell allocation deferred.
    "f540_ptet_credit",
    # compute()'s f540_total_credits includes exemption_credit (subtracted
    # at line 32); different semantic from line 47.
    "f540_total_credits",
})


_CHECKBOX_STATES_2023: dict[str, str] = {}


# ── 2021 registries ─────────────────────────────────────────────────────────
#
# FOURTH FTB field-naming scheme: MIXED AcroForm names — mostly bare numeric
# ("2009"/"2017"/"3008") plus a few "Text Field N" widgets (residence county =
# "Text Field 439"). That is the CA 2021 namespace; the sequence numbers do NOT
# line up with 2023's (e.g. 2021's exemption credit is box 2017 and its renter
# credit is box 2031, whereas box 2031 is the exemption credit on 2023).
#
# The direct result_key → cell placements below come from the air-gapped fresh
# probe. The get_derivations surface (_DERIVATIONS_2021) is ADDITIVELY ported
# from _DERIVATIONS_2023: 22 form-internal computed cells (line totals, the two
# line-31 tax-source checkboxes, the five filing-status checkboxes, and the
# sign-split refund/owe cells). Each target box was RE-PLACED from the 2021
# template's OWN /TU tooltips and confirmed on the probe render — the 2021
# namespace differs from 2023, so NO sequence number was assumed to carry over.
# Formulas were carried from 2023 but each composition was re-verified against
# the 2021 printed form; the ONE structural divergence is the total-tax line:
# 2021 inserts a new line 64 (Excess APAS repayment), pushing "total tax" to
# line 65 (box 3006) with an extra addend — see _total_tax_2021. The four
# compute keys consumed by these derivations (f540_total_liability,
# f540_filing_status, f540_ptet_credit, f540_total_credits) are owned in
# _SUPPRESSED_2021 for the partition invariant.

_MAPPING_2021: dict[str, str] = {
    # 2021 fresh air-gapped probe, controller-reconciled against the 2021 template (CA namespace differs from 2023).
    # Page 1 — Taxpayer / spouse / address ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_first_name":      "1003",
    "f540_taxpayer_middle_initial":  "1004",
    "f540_taxpayer_last_name":       "1005",
    "f540_taxpayer_suffix":          "1006",
    "f540_taxpayer_ssn":             "1007",
    "f540_spouse_first_name":        "1008",
    "f540_spouse_last_name":         "1010",
    "f540_spouse_ssn":               "1012",
    "f540_address_street":           "1015",
    "f540_address_city":             "1018",
    "f540_address_state":            "1019",
    "f540_address_zip":              "1020",
    "f540_residence_county":         "Text Field 439",
    # Page 2 — Taxable income + tax
    "f540_federal_agi":              "2005",  # line 13 (federal AGI)
    "f540_ca_agi":                   "2009",
    "f540_deduction":                "2010",
    "f540_taxable_income":           "2011",
    "f540_ca_tax":                   "2016",
    # Line 32 "Exemption credits" (the APPLIED credit). The compute emits the applied exemption credit and REFUSES above the AGI phaseout threshold (phaseout not implemented), so below that threshold line 11 == line 32 by construction. Line 11 "Exemption amount" (box 2003) is intentionally UNMAPPED — no compute key feeds it; populating both boxes from one key is a ledgered cross-year CA follow-up (federal-1z-family form-completeness hygiene), not this pack.
    "f540_exemption_credit":         "2017",
    # Page 3 — Credits + payments + use tax
    "f540_renter_credit":            "2031",
    "f540_estimated_payments":       "3008",
    "f540_use_tax":                  "3014",
    # Page 4 — Voluntary contributions
    "f540_voluntary_contributions":  "4024",
    # Page 5 — Estimated tax penalty
    "f540_estimated_tax_penalty":    "5007",
    # Page 6 — Sign block ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_email":           "5019",
    "f540_taxpayer_phone":           "5020",
}


_AGGREGATIONS_2021: dict[str, tuple[str, ...]] = {}


# 2021 filing status: FIVE line-1..5 checkboxes (as on 2023 — box numbers
# differ). Source of truth for the derivations below and the coverage test.
# ON-state is /Yes per each box's OWN /_States_ (['/Yes', '/Off']).
_FILING_STATUS_CB_2021: dict[FilingStatus, str] = {
    FilingStatus.SINGLE:             "1029 CB",  # Line 1. Single
    FilingStatus.MARRIED_JOINTLY:    "1030 CB",  # Line 2. MFJ / RDP jointly
    FilingStatus.MARRIED_SEPARATELY: "1031 CB",  # Line 3. MFS / RDP separately
    FilingStatus.HEAD_OF_HOUSEHOLD:  "1033 CB",  # Line 4. Head of household
    FilingStatus.QUALIFYING_WIDOW:   "1034 CB",  # Line 5. Qualifying widow(er)
}


def _total_tax_2021(c: Mapping[str, object]) -> float:
    """2021 Line 65 total tax = line 48 + 61 + 62 + 63 + 64.

    STRUCTURAL DIVERGENCE from 2023: on 2023 the total-tax line is line 64
    (box 3010, helper `_line_64` = line 48 + 61 + 62 + 63). The 2021 form
    inserts a NEW line 64 (Excess APAS repayment) between the other-taxes
    lines and the total, so "total tax" is line 65 (box 3006) with an EXTRA
    addend. Reuses `_line_64` for the shared 48+61+62+63 sub-sum (year-agnostic
    pure arithmetic) and adds the 2021-only line-64 APAS term
    ([PLANNED]/OUT_OF_V1_SCOPE; defaults 0 → in v1 line 65 numerically equals
    the 2023 `_line_64` value, but the composition matches the 2021 form).
    Feeds 2021 lines 65/97/100 (boxes 3006/3018/3021)."""
    return _line_64(c) + c.get("f540_line64_apas_repayment", 0)


# get_derivations surface for 2021 — 22 form-internal computed cells ADDITIVELY
# ported from _DERIVATIONS_2023. Target boxes re-placed from the 2021 template's
# own /TU tooltips + probe render; formulas carried from 2023, each composition
# re-verified against the 2021 printed form. The 2023 box that carried each
# derivation is noted in parentheses (the sequence numbers do NOT carry over).
_DERIVATIONS_2021: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 31 tax-source checkboxes (A = tax table, B = rate schedule). 2021
    # boxes 2012/2013 CB (2023: 2026/2027 CB). ON-state /Yes per each box's
    # OWN /_States_ (['/Yes', '/Off']).
    "2012 CB": lambda c: "/Yes" if c["f540_taxable_income"] <= 100_000 else "/Off",
    "2013 CB": lambda c: "/Yes" if c["f540_taxable_income"] > 100_000 else "/Off",
    # Line 33 (box 2018) /TU "Subtract line 32 from line 31. If less than zero,
    # enter 0." = max(0, line 31 − line 32). Composition verified. (2023: 2032.)
    "2018": lambda c: _line_33(c),
    # Line 35 (box 2022) /TU "Add line 33 and line 34." Line 34 OUT_OF_V1_SCOPE
    # (defaults 0) → line 35 == line 33. (2023: 2036.)
    "2022": lambda c: _line_33(c),
    # Line 47 (box 2032) /TU "Add line 40 through line 46. These are your total
    # credits." = renter + ptet + [PLANNED] line40/43-45. Composition verified:
    # same line-40..46 span as 2023. (2023: 3005.)
    "2032": lambda c: _line_47(c),
    # Line 48 (box 2033) /TU "Subtract line 47 from line 35. If less than zero,
    # enter 0." = max(0, line 35 − line 47). (2023: 3006.)
    "2033": lambda c: _line_48(c),
    # Line 65 (box 3006) /TU "Add line 48, line 61, line 62, line 63, and line
    # 64. This is your total tax." 2021's total-tax line — line 65, NOT line 64
    # as on 2023 (box 3010). See _total_tax_2021 for the divergence.
    "3006": lambda c: _total_tax_2021(c),
    # Line 78 (box 3013) /TU "Add line 71 through line 77. These are your total
    # payments." Only line 72 (est_payments) nonzero in v1. NOTE 2021 line 74 =
    # Excess SDI and line 77 = Net PAS (2023: Program-4.0 / FYTC) — differing
    # [PLANNED] labels, all 0 in v1; the 71-77 span composition holds. (2023: 3018.)
    "3013": lambda c: (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    ),
    # Line 93 (box 3016) /TU "If line 78 is more than line 91, subtract line 91
    # from line 78." = max(0, line 78 − line 91); line 78 is the TOTAL payments
    # (_line_78: lines 71-77, incl. CA withholding). (2023: 3023.)
    "3016": lambda c: _line_93(c),
    # Line 94 (box 3023) /TU "If line 91 is more than line 78, subtract line 78
    # from line 91." = max(0, line 91 − line 78). (2023: 3024.)
    "3023": lambda c: max(0, c["f540_use_tax"] - _line_78(c)),
    # Line 95 (box 3017) /TU "Payments after ISR Penalty. If line 93 is more
    # than line 92, subtract line 92 from line 93." = max(0, line 93 − line 92).
    # (2023: 3025.)
    "3017": lambda c: _line_95(c),
    # Line 96 (box 3024) /TU "ISR Penalty Balance. If line 92 is more than line
    # 93, subtract line 93 from line 92." = max(0, line 92 − line 93). (2023: 3026.)
    "3024": lambda c: max(0, c.get("f540_line92_isr_penalty", 0) - _line_93(c)),
    # Line 97 (box 3018) /TU "Overpaid tax. If line 95 is more than line 65,
    # subtract line 65 from line 95." = max(0, line 95 − line 65). References
    # 2021's line-65 total tax (2023 referenced line 64). (2023: 3027.)
    "3018": lambda c: max(0, _line_95(c) - _total_tax_2021(c)),
    # Line 99 (box 3020) /TU "Overpaid tax available this year. Subtract line 98
    # from line 97." = line 97 − line 98. Line 98 (applied to 2022 est. tax)
    # OUT_OF_V1_SCOPE, defaults 0. (2023: 4004.)
    "3020": lambda c: (
        max(0, _line_95(c) - _total_tax_2021(c))
        - c.get("f540_line98_applied_to_2022_estimated", 0)
    ),
    # Line 100 (box 3021) /TU "Tax due. If line 95 is less than line 65,
    # subtract line 95 from line 65." = max(0, line 65 − line 95). (2023: 4005.)
    "3021": lambda c: max(0, _total_tax_2021(c) - _line_95(c)),
}

# Filing-status checkboxes, generated from _FILING_STATUS_CB_2021 so the
# coverage test can assert every FilingStatus has a cell. Default-arg binding
# (`_s=status`) captures each status in its own lambda closure. ON-state /Yes
# per each box's own /_States_. (2021 boxes 1029/1030/1031/1033/1034 CB;
# 2023: 1036/1037/1038/1040/1041 CB.)
for _status, _cb in _FILING_STATUS_CB_2021.items():
    _DERIVATIONS_2021[_cb] = (
        lambda c, _s=_status: "/Yes" if c["f540_filing_status"] == _s else "/Off"
    )
del _status, _cb


# Compute keys with no direct PDF cell on the 2021 pack — consumed by the
# ported derivations above (filing-status checkboxes, line-47 vs compute()
# total-credits divergence, PTET) or, for f540_total_liability, printed
# nowhere (lines 111-115: see _AMOUNT_DUE_CELLS). Owned here for the
# partition invariant, exactly as on 2023-2025.
_SUPPRESSED_2021: frozenset[str] = frozenset({
    "f540_total_liability",
    "f540_filing_status",
    "f540_ptet_credit",
    "f540_total_credits",
})


_CHECKBOX_STATES_2021: dict[str, str] = {}


# ── 2022 registries ─────────────────────────────────────────────────────────
#
# Same bare-numeric FTB field-naming scheme as 2023 ('2023'/'3004'/'1036 CB').
# The 2022 field tree is near-identical to 2023: the direct-map cells match 2023
# box-for-box EXCEPT the sign-block email/phone (2022 boxes 5019/5020 vs 2023's
# 6002/6003 — re-placed from the 2022 template's OWN /TU tooltips). The 25 direct
# placements below come from the controller-reconciled air-gapped 2022 probe.
#
# The get_derivations surface (_DERIVATIONS_2022) is ADDITIVELY ported from
# _DERIVATIONS_2023: 22 form-internal computed cells (15 line-total / refund-owe
# text cells + 2 line-31 tax-source checkboxes + 5 filing-status checkboxes).
# Each target box was RE-PLACED from the 2022 template's OWN /TU tooltips + probe
# render, and each composition RE-VERIFIED against the 2022 printed form. Result:
# every 2022 derivation box carries the SAME sequence number as 2023 and every
# formula matches the 2023 composition. IMPORTANTLY, 2022 does NOT have the
# 2021-only structural divergence: box 3010's /TU reads "Line 64. Add line 48,
# line 61, line 62, and line 63. This is your total tax." — so 2022 total tax is
# line 64 == `_line_64` (NO Excess-APAS line-64 insertion / line-65 shift, and
# NO `_total_tax_2021` helper). Lines 97 (3027) and 100 (4005) reference line 64,
# matching 2023. All seven checkbox ON-states are /Yes per each box's own
# /_States_ (['/Yes', '/Off']). The four compute keys consumed by these
# derivations are owned in _SUPPRESSED_2022 for the partition invariant.

_MAPPING_2022: dict[str, str] = {
    # 2022 controller-reconciled air-gapped probe (CA bare-numeric namespace,
    # matches 2023 except sign-block email/phone).
    # Page 1 — Taxpayer / spouse / address ([PLANNED]: orchestrator-supplied)
    "f540_taxpayer_first_name":      "1003",
    "f540_taxpayer_middle_initial":  "1004",
    "f540_taxpayer_last_name":       "1005",
    "f540_taxpayer_suffix":          "1006",
    "f540_taxpayer_ssn":             "1007",
    "f540_spouse_first_name":        "1008",
    "f540_spouse_last_name":         "1010",
    "f540_spouse_ssn":               "1012",
    "f540_address_street":           "1015",
    "f540_address_city":             "1018",
    "f540_address_state":            "1019",
    "f540_address_zip":              "1020",
    "f540_residence_county":         "1028",
    # Page 2 — Taxable income + tax
    "f540_federal_agi":              "2019",  # line 13 (federal AGI)
    "f540_ca_agi":                   "2023",  # line 17
    "f540_deduction":                "2024",  # line 18
    "f540_taxable_income":           "2025",  # line 19
    "f540_ca_tax":                   "2030",  # line 31
    # Line 32 "Exemption credits" (box 2031, the APPLIED credit): compute emits
    # the applied exemption credit and refuses above the AGI phaseout threshold,
    # so below it line 11 == line 32 by construction. Line 11 "Exemption amount"
    # (box 2017) is intentionally UNMAPPED — no compute key feeds it; populating
    # both boxes from one key is a ledgered cross-year CA follow-up, not this pack.
    "f540_exemption_credit":         "2031",  # line 32 (applied credit)
    # Page 3 — Credits + payments + use tax
    "f540_renter_credit":            "3004",  # line 46
    "f540_estimated_payments":       "3012",  # line 72
    "f540_use_tax":                  "3019",  # line 91
    # Page 4 — Voluntary contributions (line 110 total)
    "f540_voluntary_contributions":  "4026",  # line 110
    # Page 5 — Estimated tax penalty
    "f540_estimated_tax_penalty":    "5006",  # line 113
    # Page 5 — Sign block ([PLANNED]: orchestrator-supplied). 2022 boxes 5019/5020
    # (2023: 6002/6003), re-placed from the 2022 /TU tooltips.
    "f540_taxpayer_email":           "5019",
    "f540_taxpayer_phone":           "5020",
}


_AGGREGATIONS_2022: dict[str, tuple[str, ...]] = {}


# 2022 filing status: FIVE line-1..5 checkboxes (as on 2023 — SAME box numbers).
# Source of truth for the derivations below and the coverage test. ON-state /Yes
# per each box's OWN /_States_ (['/Yes', '/Off']).
_FILING_STATUS_CB_2022: dict[FilingStatus, str] = {
    FilingStatus.SINGLE:             "1036 CB",  # Line 1. Single
    FilingStatus.MARRIED_JOINTLY:    "1037 CB",  # Line 2. MFJ / RDP jointly
    FilingStatus.MARRIED_SEPARATELY: "1038 CB",  # Line 3. MFS / RDP separately
    FilingStatus.HEAD_OF_HOUSEHOLD:  "1040 CB",  # Line 4. Head of household
    FilingStatus.QUALIFYING_WIDOW:   "1041 CB",  # Line 5. Qualifying surviving spouse / RDP
}


# get_derivations surface for 2022 — 22 form-internal computed cells ADDITIVELY
# ported from _DERIVATIONS_2023. Target boxes re-placed from the 2022 template's
# own /TU tooltips + probe render; each composition re-verified against the 2022
# printed form. The 2022 boxes carry the SAME sequence numbers as 2023 and the
# formulas match the 2023 composition (line 64 total tax — see block comment;
# NO 2021-style APAS line-64 insertion, so `_line_64` is used directly).
_DERIVATIONS_2022: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 31 tax-source checkboxes (A = tax table, B = rate schedule). Boxes
    # 2026/2027 CB. /TU: "Line 31. Tax. Checkbox A/B...". ON-state /Yes per each
    # box's OWN /_States_ (['/Yes', '/Off']).
    "2026 CB": lambda c: "/Yes" if c["f540_taxable_income"] <= 100_000 else "/Off",
    "2027 CB": lambda c: "/Yes" if c["f540_taxable_income"] > 100_000 else "/Off",
    # Line 33 (box 2032) /TU "Subtract line 32 from line 31. If less than zero,
    # enter 0." = max(0, line 31 − line 32).
    "2032": lambda c: _line_33(c),
    # Line 35 (box 2036) /TU "Add line 33 and line 34." Line 34 OUT_OF_V1_SCOPE
    # (defaults 0) → line 35 == line 33.
    "2036": lambda c: _line_33(c),
    # Line 47 (box 3005) /TU "Add line 40 through line 46. These are your total
    # credits." = renter + ptet + [PLANNED] line40/43-45.
    "3005": lambda c: _line_47(c),
    # Line 48 (box 3006) /TU "Subtract line 47 from line 35. If less than zero,
    # enter 0." = max(0, line 35 − line 47).
    "3006": lambda c: _line_48(c),
    # Line 64 (box 3010) /TU "Add line 48, line 61, line 62, and line 63. This is
    # your total tax." 2022 total tax IS line 64 (like 2023, NOT the 2021 line 65)
    # — use `_line_64` directly; no APAS addend.
    "3010": lambda c: _line_64(c),
    # Line 78 (box 3018) /TU "Add line 71 through line 77. These are your total
    # payments." Only line 72 (est_payments) nonzero in v1.
    "3018": lambda c: (
        c.get("f540_line71_ca_withholding", 0)
        + c["f540_estimated_payments"]
        + c.get("f540_line73_592b_593_withholding", 0)
        + c.get("f540_line74_program_40_motion_picture", 0)
        + c.get("f540_line75_eitc", 0)
        + c.get("f540_line76_yctc", 0)
        + c.get("f540_line77_fytc", 0)
    ),
    # Line 93 (box 3023) /TU "If line 78 is more than line 91, subtract line 91
    # from line 78." = max(0, line 78 − line 91).
    "3023": lambda c: _line_93(c),
    # Line 94 (box 3024) /TU "If line 91 is more than line 78, subtract line 78
    # from line 91." = max(0, line 91 − line 78).
    "3024": lambda c: max(0, c["f540_use_tax"] - _line_78(c)),
    # Line 95 (box 3025) /TU "If line 93 is more than line 92, subtract line 92
    # from line 93." = max(0, line 93 − line 92).
    "3025": lambda c: _line_95(c),
    # Line 96 (box 3026) /TU "If line 92 is more than line 93, subtract line 93
    # from line 92." = max(0, line 92 − line 93).
    "3026": lambda c: max(0, c.get("f540_line92_isr_penalty", 0) - _line_93(c)),
    # Line 97 (box 3027) /TU "Overpaid tax. If line 95 is more than line 64,
    # subtract line 64 from line 95." = max(0, line 95 − line 64). References
    # line 64 (2022 total tax), matching 2023.
    "3027": lambda c: max(0, _line_95(c) - _line_64(c)),
    # Line 99 (box 4004) /TU "Overpaid tax available this year. Subtract line 98
    # from line 97." = line 97 − line 98. Line 98 OUT_OF_V1_SCOPE (defaults 0).
    "4004": lambda c: (
        max(0, _line_95(c) - _line_64(c))
        - c.get("f540_line98_applied_to_2023_estimated", 0)
    ),
    # Line 100 (box 4005) /TU "Tax due. If line 95 is less than line 64, subtract
    # line 95 from line 64." = max(0, line 64 − line 95). References line 64.
    "4005": lambda c: max(0, _line_64(c) - _line_95(c)),
}

# Filing-status checkboxes, generated from _FILING_STATUS_CB_2022 so the coverage
# test can assert every FilingStatus has a cell. Default-arg binding (`_s=status`)
# captures each status in its own lambda closure. ON-state /Yes per each box's own
# /_States_. (2022 boxes 1036/1037/1038/1040/1041 CB — same as 2023.)
for _status, _cb in _FILING_STATUS_CB_2022.items():
    _DERIVATIONS_2022[_cb] = (
        lambda c, _s=_status: "/Yes" if c["f540_filing_status"] == _s else "/Off"
    )
del _status, _cb


# Compute keys with no direct PDF cell on the 2022 pack — consumed by the ported
# derivations above (filing-status checkboxes, line-47 vs compute()
# total-credits divergence, PTET) or, for f540_total_liability, printed nowhere
# (lines 111-115: see _AMOUNT_DUE_CELLS). Owned here for the partition
# invariant, exactly as on 2021/2023-2025.
_SUPPRESSED_2022: frozenset[str] = frozenset({
    "f540_total_liability",
    "f540_filing_status",
    "f540_ptet_credit",
    "f540_total_credits",
})


_CHECKBOX_STATES_2022: dict[str, str] = {}


# ── Presentation layer (all years): header identity, DOB, exemptions, state ──
# ── wages, use-tax and third-party-designee boxes, per-page name/SSN ────────
#
# Field numbers below were read from each year's template /TU tooltips and
# confirmed by rendering the filled page (tests/test_ca_540_presentation.py).
# Values come from ``forms.f540.presentation_keys`` (scenario-derived) and the
# compute results; nothing here is computed.
#
# EXPLICIT ZERO / "NO" BOXES (per the 540 instructions):
#  * Line 91 "Use Tax. Do not leave blank" / "If the amount due is zero, you
#    must check the applicable box to indicate that you either owe no use tax,
#    or you paid your use tax obligation directly to [CDTFA]" (2025 Form 540
#    booklet, line 91). Line 91 therefore always prints (an explicit 0 via the
#    f540_use_tax mapping) and, when it is zero, the "No use tax is owed" box
#    is checked. The "paid directly to CDTFA" alternative has no input field in
#    the model, so it is never selected.
#  * Third-party designee: the model has no designee, so "No" is checked.
#
# Radio on-state tokens differ per year (the 2021-2023 and 2025 templates use
# opaque "/0" and "/1"; 2024 uses the literal labels). Which token is which was
# established by widget GEOMETRY and render (the "No use tax" box is the LEFT
# box; designee "No" is the RIGHT box) and is pinned by a geometry test.

_YEAR_PRESENTATION = {
    # year: (text-field prefix, line7 box/amt, line10 box/amt, line11, line12,
    #        per-page name fields, per-page SSN fields, use-tax radio + "no use
    #        tax" token, designee radio + "No" token)
    2021: ("", ("1038", "1039"), ("1056", "1057"), "2003", "2004",
           ("2001", "3001", "4001", "5001"), ("2002", "3002", "4002", "5002"),
           ("3015 RB", "/0"), ("5025 RB", "/1")),
    2022: ("", ("1045", "1046"), ("2015", "2016"), "2017", "2018",
           ("2001",), ("2002",), ("3020 RB", "/0"), ("5025 RB", "/1")),
    2023: ("", ("1045", "1046"), ("2015", "2016"), "2017", "2018",
           ("2001",), ("2002",), ("3020 RB", "/0"), ("6008 RB", "/1")),
    2024: ("540-", ("1041", "1042"), ("2015", "2016"), "2017", "2018",
           ("2001",), ("2002",),
           ("540-3020 RB", "/No use tax is owed."), ("540-6008 RB", "/No")),
    2025: ("540_form_", ("1041", "1042"), ("2015", "2016"), "2017", "2018",
           ("2001",), ("2002",),
           ("540_form_3020 RB", "/0"), ("540_form_6008 RB", "/1")),
}

# Header fields are numbered identically (1003/1005/1015/1018-1020/1024) in every
# year; only the prefix differs. (Same for the SSN already mapped at 1007.)
# Lines 14 / 15 / 16 (Sch CA line 27 col B / "13 - 14" / col C) and line 71
# (CA withholding) sit at the same numbers in 2022-2025; 2021 is renumbered.
# Line 78 and line 17 already print the downstream figures, so leaving these
# blank made page 2 / page 3 not foot on the page.
_ADJUSTMENT_LINES = {
    2021: ("2006", "2007", "2008", "3007"),
    2022: ("2020", "2021", "2022", "3011"),
    2023: ("2020", "2021", "2022", "3011"),
    2024: ("2020", "2021", "2022", "3011"),
    2025: ("2020", "2021", "2022", "3011"),
}


def _line_15(c: Mapping[str, object]) -> str:
    """Line 15 = line 13 - line 14; the form says a negative result is entered
    in parentheses."""
    v = c["f540_federal_agi"] - c["sch_ca_total_subtractions"]
    return f"({abs(v)})" if v < 0 else str(v)


_HEADER_NUMBERS = {
    "f540_taxpayer_first_name": "1003",
    "f540_taxpayer_last_name": "1005",
    "f540_taxpayer_dob": "1024",
    "f540_address_street": "1015",
    "f540_address_city": "1018",
    "f540_address_state": "1019",
    "f540_address_zip": "1020",
}


# Side 1 "If your address above is the same as your principal/physical
# residence address at the time of filing, check this box." Full field names
# (2021's is unnumbered). ON-state /Yes per each box's OWN /_States_
# (['/Yes', '/Off']) in every year; ``forms.f540.presentation_keys`` supplies
# that state string, and only when the scenario states it.
_RESIDENCE_SAME_BOX = {
    2021: "Text Field 439 CB 1",
    2022: "1029 CB",
    2023: "1029 CB",
    2024: "540-1029 CB",
    2025: "540_form_1029 CB",
}


# Line 92 "If you and your household had full-year health care coverage, check
# the box." Full field names (2021's box is numbered differently). ON-state
# /Yes per each box's OWN /_States_ (['/Yes', '/Off']) in every year;
# ``forms.f540.presentation_keys`` supplies that state string.
_FULL_YEAR_COVERAGE_BOX = {
    2021: "3016 CB",
    2022: "3021 CB",
    2023: "3021 CB",
    2024: "540-3021 CB",
    2025: "540_form_3021 CB",
}


def _install_presentation(year, mapping, derivations):
    (prefix, l7, l10, l11, l12, name_fields, ssn_fields,
     (use_tax_radio, no_use_tax), (designee_radio, designee_no)) = _YEAR_PRESENTATION[year]
    mapping.update({key: prefix + num for key, num in _HEADER_NUMBERS.items()})
    mapping["f540_address_is_residence_checkbox"] = _RESIDENCE_SAME_BOX[year]
    mapping["f540_full_year_coverage_checkbox"] = _FULL_YEAR_COVERAGE_BOX[year]
    mapping.update({
        "f540_line7_count": prefix + l7[0],
        "f540_line7_amount": prefix + l7[1],
        "f540_line10_count": prefix + l10[0],
        "f540_line10_amount": prefix + l10[1],
        "f540_line11_exemption_amount": prefix + l11,
        "f540_line12_state_wages": prefix + l12,
    })
    l14, l15, l16, l71 = _ADJUSTMENT_LINES[year]
    mapping["f540_line71_ca_withholding"] = prefix + l71
    derivations[prefix + l14] = lambda c: c["sch_ca_total_subtractions"]
    derivations[prefix + l15] = _line_15
    derivations[prefix + l16] = lambda c: c["sch_ca_total_additions"]
    for field in name_fields:
        derivations[prefix + field] = lambda c: c.get("f540_taxpayer_name")
    for field in ssn_fields:
        derivations[prefix + field] = lambda c: c.get("f540_taxpayer_ssn")
    derivations[use_tax_radio] = (
        lambda c, tok=no_use_tax: tok if c["f540_use_tax"] == 0 else None)
    derivations[designee_radio] = lambda c, tok=designee_no: tok


# AMOUNT YOU OWE / TOTAL AMOUNT DUE / REFUND (lines 111-115).
#
# The FTB booklet text for lines 111, 114 and 115 is identical 2021-2025, so
# one set of helpers serves every year; only the cells differ:
#  * Line 111 "Amount You Owe": "If you do not have an amount on line 99, add
#    the amount on line 94, line 96, line 100, and line 110, if any ... If you
#    have an amount on line 99 and the amount on line 110 is more than line 99,
#    subtract line 99 from line 110". Line 113 is NOT part of line 111.
#  * Line 112 "Interest and Penalties": a stated input
#    (``f540_interest_and_penalties``); blank when unstated.
#  * Line 113: the stated FTB 5805 result (``f540_estimated_tax_penalty``),
#    mapped directly per year. LIMITATION: the "FTB 5805 / 5805F is attached"
#    boxes beside it are not mapped and are never checked.
#  * Line 114 "Total Amount Due": "Is there an amount on line 111? Yes: Add
#    line 111, line 112, and line 113." Otherwise, from the line 115
#    instruction: when line 110 + 112 + 113 is "more than line 99, subtract
#    line 99 from the sum ... and enter the result on line 114".
#  * Line 115 "Refund or No Amount Due": line 99 when nothing is reported on
#    lines 110/112/113; else line 99 minus their sum when the sum is not more.
#
# Lines 94, 96, 99 and 100 are read through the year's OWN printed-cell
# derivations, so these lines cannot disagree with the cells above them.
# ``f540_total_liability`` is no longer printed anywhere: it nets line 113 into
# the tax position, which is why it overstated line 111 by the penalty.
_AMOUNT_DUE_CELLS = {
    # year: (line 94, line 96, line 99, line 100, line 111, line 112, line 114, line 115)
    2021: ("3023", "3024", "3020", "3021", "5003", "5004", "5008", "5009"),
    2022: ("3024", "3026", "4004", "4005", "4027", "5003", "5007", "5008"),
    2023: ("3024", "3026", "4004", "4005", "4027", "5003", "5007", "5008"),
    2024: ("540-3024", "540-3026", "540-4004", "540-4005",
           "540-5002", "540-5003", "540-5006", "540-5007"),
    2025: ("540_form_3024", "540_form_3026", "540_form_4004", "540_form_4005",
           "540_form_5002", "540_form_5003", "540_form_5006", "540_form_5007"),
}


def _lines_110_112_113(c: Mapping[str, object]) -> tuple[float, float, float]:
    """(line 110, line 112, line 113). An unstated line 112 counts as 0 here;
    whether it MAY be unstated is ``interest_and_penalties_must_be_stated``."""
    return (
        c["f540_voluntary_contributions"],
        c.get("f540_interest_and_penalties") or 0,
        c["f540_estimated_tax_penalty"],
    )


def _line_111(year: int, c: Mapping[str, object]) -> float | None:
    """Line 111, or None when the line is blank."""
    l94, l96, l99, l100 = (_DERIVATIONS_BY_YEAR[year][cell](c)
                           for cell in _AMOUNT_DUE_CELLS[year][:4])
    l110 = c["f540_voluntary_contributions"]
    if l99 > 0:
        return l110 - l99 if l110 > l99 else None
    owed = l94 + l96 + l100 + l110
    return owed if owed > 0 else None


def _line_114(year: int, c: Mapping[str, object]) -> float | None:
    """Line 114, or None when the line is blank."""
    l110, l112, l113 = _lines_110_112_113(c)
    l111 = _line_111(year, c)
    if l111 is not None:
        return l111 + l112 + l113
    l99 = _DERIVATIONS_BY_YEAR[year][_AMOUNT_DUE_CELLS[year][2]](c)
    excess = l110 + l112 + l113 - l99
    return excess if excess > 0 else None


def _line_115(year: int, c: Mapping[str, object]) -> float | None:
    """Line 115, or None when the line is blank (an amount is due instead, or
    there is no overpayment to refund)."""
    if _line_114(year, c) is not None:
        return None
    l99 = _DERIVATIONS_BY_YEAR[year][_AMOUNT_DUE_CELLS[year][2]](c)
    if l99 <= 0:
        return None
    return l99 - sum(_lines_110_112_113(c))


def interest_and_penalties_must_be_stated(year: int, c: Mapping[str, object]) -> bool:
    """Whether line 112 may NOT be left unstated on this return.

    A pure refund return (nothing on lines 110, 112 or 113, no amount on line
    111) takes the line 115 "No" branch and never reads line 112. Any other
    return carries line 112 into line 114 or line 115, so an unstated value
    there would silently count as zero.
    """
    l110, _, l113 = _lines_110_112_113(c)
    return _line_111(year, c) is not None or l110 != 0 or l113 != 0


def _install_amount_due(year, mapping, derivations):
    _, _, _, _, l111, l112, l114, l115 = _AMOUNT_DUE_CELLS[year]
    mapping["f540_interest_and_penalties"] = l112
    derivations[l111] = lambda c, y=year: _line_111(y, c)
    derivations[l114] = lambda c, y=year: _line_114(y, c)
    derivations[l115] = lambda c, y=year: _line_115(y, c)


for _y, _m, _d in (
    (2021, _MAPPING_2021, _DERIVATIONS_2021),
    (2022, _MAPPING_2022, _DERIVATIONS_2022),
    (2023, _MAPPING_2023, _DERIVATIONS_2023),
    (2024, _MAPPING_2024, _DERIVATIONS_2024),
    (2025, _MAPPING_2025, _DERIVATIONS_2025),
):
    _install_presentation(_y, _m, _d)
    _install_amount_due(_y, _m, _d)


PdfF540._MAPPINGS = {
    2021: _MAPPING_2021,
    2022: _MAPPING_2022,
    2023: _MAPPING_2023,
    2024: _MAPPING_2024,
    2025: _MAPPING_2025,
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
    2021: _SUPPRESSED_2021, 2022: _SUPPRESSED_2022,
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _CHECKBOX_STATES_2021, 2022: _CHECKBOX_STATES_2022,
    2023: _CHECKBOX_STATES_2023, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}
