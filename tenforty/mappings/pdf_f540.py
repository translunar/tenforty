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
        if year == 2025:
            return _AGGREGATIONS_2025
        raise ValueError(f"No Form 540 aggregations for year {year}")

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year == 2025:
            return _DERIVATIONS_2025
        raise ValueError(f"No Form 540 derivations for year {year}")

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year == 2025:
            return _SUPPRESSED_2025
        raise ValueError(f"No Form 540 suppressions for year {year}")

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        if year == 2025:
            return _CHECKBOX_STATES_2025
        raise ValueError(f"No Form 540 checkbox states for year {year}")


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


PdfF540._MAPPINGS = {2025: _MAPPING_2025}
