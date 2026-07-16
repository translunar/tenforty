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
  probe artifact, (b) the sign-split flow for `f540_total_liability`
  → owe (`540_form_5002`) / refund (`540_form_5007`), (c) the verbose
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


def _line_93(c: Mapping[str, object]) -> float:
    """Line 93 = max(0, line 78 − line 91). Line 78 ≈ estimated_payments
    in v1 (other [PLANNED] payment lines default 0). Called from
    540_form_3023, 540_form_3025, 540_form_3026, 540_form_3027,
    540_form_4004, 540_form_4005."""
    return max(0, c["f540_estimated_payments"] - c["f540_use_tax"])


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
    # Line 93 = max(0, line 78 − line 91). Line 78 ≈ estimated_payments
    # in v1 (other [PLANNED] payment lines default 0).
    "540_form_3023": lambda c: _line_93(c),
    # Line 94 = max(0, line 91 − line 78).
    "540_form_3024": lambda c: max(
        0, c["f540_use_tax"] - c["f540_estimated_payments"]
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
    # Line 111 (owe) — sign-split branch of f540_total_liability.
    # Returns the value when positive (owed); None otherwise (skipped).
    "540_form_5002": lambda c: (
        c["f540_total_liability"] if c["f540_total_liability"] > 0 else None
    ),
    # Line 115 (refund) — sign-split branch of f540_total_liability.
    # Returns the absolute value when negative (refund due); None otherwise.
    "540_form_5007": lambda c: (
        -c["f540_total_liability"] if c["f540_total_liability"] < 0 else None
    ),
}


# Compute keys with no direct PDF cell on the 2025 form.
#
# Extended SUPPRESSED semantics (SP3 calibration): includes BOTH
# (a) keys with no fillable cell (out-of-scope; user reports externally
# via attestation) AND (b) keys consumed only by derivations (sign-split
# flow, enum-typed dispatch). The partition test treats both subsets as
# ownership; derivation lambdas may read them.
_SUPPRESSED_2025: frozenset[str] = frozenset({
    # Consumed-by-derivation only (sign-split: 540_form_5002 owe /
    # 540_form_5007 refund).
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
        0, c["f540_use_tax"] - c["f540_estimated_payments"]
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
    # Line 111 (owe) — sign-split branch of f540_total_liability.
    "540-5002": lambda c: (
        c["f540_total_liability"] if c["f540_total_liability"] > 0 else None
    ),
    # Line 115 (refund) — sign-split branch of f540_total_liability.
    "540-5007": lambda c: (
        -c["f540_total_liability"] if c["f540_total_liability"] < 0 else None
    ),
}


_SUPPRESSED_2024: frozenset[str] = frozenset({
    # Consumed-by-derivation only (sign-split: 540-5002 owe / 540-5007 refund).
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
    "3024": lambda c: max(0, c["f540_use_tax"] - c["f540_estimated_payments"]),
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
    # Line 111 (owe) — sign-split branch of f540_total_liability
    # (cell 4027, SHIFTED from 2024/2025's 5002).
    "4027": lambda c: (
        c["f540_total_liability"] if c["f540_total_liability"] > 0 else None
    ),
    # Line 115 (refund) — sign-split branch of f540_total_liability
    # (cell 5008, SHIFTED from 2024/2025's 5007).
    "5008": lambda c: (
        -c["f540_total_liability"] if c["f540_total_liability"] < 0 else None
    ),
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
    # Consumed-by-derivation only (sign-split: 4027 owe / 5008 refund).
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
    # credits." = renter + [PLANNED] line40/43-45. Composition verified: same
    # line-40..46 span as 2023. (2023: 3005.)
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
    # from line 78." = max(0, line 78 − line 91); line78 ≈ est_payments in v1.
    # (2023: 3023.)
    "3016": lambda c: _line_93(c),
    # Line 94 (box 3023) /TU "If line 91 is more than line 78, subtract line 78
    # from line 91." = max(0, line 91 − line 78). (2023: 3024.)
    "3023": lambda c: max(0, c["f540_use_tax"] - c["f540_estimated_payments"]),
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
    # Line 111 (box 5003, "Amount You Owe") — sign-split owe branch of
    # f540_total_liability; value when positive, else None (skipped). (2023: 4027.)
    "5003": lambda c: (
        c["f540_total_liability"] if c["f540_total_liability"] > 0 else None
    ),
    # Line 115 (box 5009, "Refund or no amount due") — sign-split refund branch
    # of f540_total_liability; abs value when negative, else None. (2023: 5008.)
    "5009": lambda c: (
        -c["f540_total_liability"] if c["f540_total_liability"] < 0 else None
    ),
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
# ported derivations above (sign-split refund/owe, filing-status checkboxes,
# line-47 vs compute() total-credits divergence, PTET). Owned here for the
# partition invariant, exactly as on 2023-2025.
_SUPPRESSED_2021: frozenset[str] = frozenset({
    "f540_total_liability",
    "f540_filing_status",
    "f540_ptet_credit",
    "f540_total_credits",
})


_CHECKBOX_STATES_2021: dict[str, str] = {}


PdfF540._MAPPINGS = {
    2021: _MAPPING_2021,
    2023: _MAPPING_2023,
    2024: _MAPPING_2024,
    2025: _MAPPING_2025,
}

# Year-keyed dispatch tables for the four registries above — replaces
# `if year == <literal>` branching with membership-gated dict lookup.
_AGGREGATIONS_BY_YEAR: dict[int, dict[str, tuple[str, ...]]] = {
    2021: _AGGREGATIONS_2021,
    2023: _AGGREGATIONS_2023, 2024: _AGGREGATIONS_2024, 2025: _AGGREGATIONS_2025,
}
_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2021: _DERIVATIONS_2021,
    2023: _DERIVATIONS_2023, 2024: _DERIVATIONS_2024, 2025: _DERIVATIONS_2025,
}
_SUPPRESSED_BY_YEAR: dict[int, frozenset[str]] = {
    2021: _SUPPRESSED_2021,
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _CHECKBOX_STATES_2021,
    2023: _CHECKBOX_STATES_2023, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}
