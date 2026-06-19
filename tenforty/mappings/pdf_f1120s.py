"""PDF field mappings for IRS Form 1120-S (2024 and 2025).

Direct entries (`_MAPPING_<year>`) map a compute output key to one PDF
field path. Aggregations (`_AGGREGATIONS_<year>`) describe PDF cells that
receive a sum of multiple compute keys. Derivations (`_DERIVATIONS_<year>`)
describe PDF cells whose value is computed from compute outputs (e.g.,
overpayment minus credited-to-next-year). Suppressions
(`_SUPPRESSED_<year>`) declare compute keys that have no fillable cell on
the year's form (write-in only). Checkbox states (`_CHECKBOX_STATES_<year>`)
map a compute key to the PDF "on" appearance state name (e.g. `"/1"`,
`"/2"`, `"/3"`) for IRS XFA forms whose checkbox cells use non-conventional
state names.

All field paths come from probing the actual PDF AcroForms via pypdf.
See docs/plans/t14-f1120s-probe.md for the 2025 per-line rationale.
"""

from collections.abc import Callable, Mapping
from tenforty.mappings.registry import PdfFormMapping


# ── 2025 registries ──────────────────────────────────────────────────────────
#
# Direct 1:1 mappings — most compute keys go here.
# Authoritative field paths come from docs/plans/t14-f1120s-probe.md.
_MAPPING_2025: dict[str, str] = {
    # Income — Lines 1a-6
    "f1120s_gross_receipts":            "topmostSubform[0].Page1[0].f1_17[0]",
    "f1120s_returns_and_allowances":    "topmostSubform[0].Page1[0].f1_18[0]",
    "f1120s_net_receipts":              "topmostSubform[0].Page1[0].f1_19[0]",
    "f1120s_cost_of_goods_sold":        "topmostSubform[0].Page1[0].f1_20[0]",
    "f1120s_gross_profit":              "topmostSubform[0].Page1[0].f1_21[0]",
    "f1120s_net_gain_loss_4797":        "topmostSubform[0].Page1[0].f1_22[0]",
    "f1120s_other_income":              "topmostSubform[0].Page1[0].f1_23[0]",
    "f1120s_total_income":              "topmostSubform[0].Page1[0].f1_24[0]",
    # Deductions — Lines 7-22 (2025 numbering)
    "f1120s_compensation_of_officers":  "topmostSubform[0].Page1[0].f1_25[0]",
    "f1120s_salaries_wages":            "topmostSubform[0].Page1[0].f1_26[0]",
    "f1120s_repairs_maintenance":       "topmostSubform[0].Page1[0].f1_27[0]",
    "f1120s_bad_debts":                 "topmostSubform[0].Page1[0].f1_28[0]",
    "f1120s_rents":                     "topmostSubform[0].Page1[0].f1_29[0]",
    "f1120s_taxes_licenses":            "topmostSubform[0].Page1[0].f1_30[0]",
    "f1120s_interest":                  "topmostSubform[0].Page1[0].f1_31[0]",
    "f1120s_depreciation":              "topmostSubform[0].Page1[0].f1_32[0]",
    "f1120s_depletion":                 "topmostSubform[0].Page1[0].f1_33[0]",
    "f1120s_advertising":               "topmostSubform[0].Page1[0].f1_34[0]",
    "f1120s_pension_profit_sharing":    "topmostSubform[0].Page1[0].f1_35[0]",
    "f1120s_employee_benefits":         "topmostSubform[0].Page1[0].f1_36[0]",
    # Why skip `f1_37`: the 2025 form added a new Line 19 ("Energy
    # efficient commercial buildings deduction", Form 7205) with no
    # corresponding compute key in the v1 1120-S model. The next compute
    # key (`f1120s_other_deductions`) maps to Line 20 (`f1_38`).
    "f1120s_other_deductions":          "topmostSubform[0].Page1[0].f1_38[0]",
    "f1120s_total_deductions":          "topmostSubform[0].Page1[0].f1_39[0]",
    "f1120s_ordinary_business_income":  "topmostSubform[0].Page1[0].f1_40[0]",
    # Tax — Line 23a only (2025 numbering); §1374 BIG and §453 deferred
    # interest live in aggregations/suppressed registries.
    "f1120s_net_passive_income_tax":    "topmostSubform[0].Page1[0].f1_41[0]",
    # Payments — Lines 24b-24z, 25-27, 28a (2025 numbering)
    "f1120s_tax_deposited_with_7004":   "topmostSubform[0].Page1[0].f1_45[0]",
    "f1120s_credit_for_federal_excise_tax": "topmostSubform[0].Page1[0].f1_46[0]",
    "f1120s_refundable_credits":        "topmostSubform[0].Page1[0].f1_47[0]",
    "f1120s_total_payments":            "topmostSubform[0].Page1[0].f1_48[0]",
    "f1120s_estimated_tax_penalty":     "topmostSubform[0].Page1[0].f1_49[0]",
    "f1120s_amount_owed":               "topmostSubform[0].Page1[0].f1_50[0]",
    "f1120s_overpayment":               "topmostSubform[0].Page1[0].f1_51[0]",
    "f1120s_credited_to_next_year":     "topmostSubform[0].Page1[0].f1_52[0]",
    # Schedule B — accounting method (checkboxes: [0]=Cash, [1]=Accrual, [2]=Other)
    "f1120s_sch_b_accounting_method_cash":    "topmostSubform[0].Page2[0].c2_1[0]",
    "f1120s_sch_b_accounting_method_accrual": "topmostSubform[0].Page2[0].c2_1[1]",
    "f1120s_sch_b_accounting_method_other":   "topmostSubform[0].Page2[0].c2_1[2]",
    # Schedule B — entity info (business activity code lives in page-1 header item B)
    "f1120s_sch_b_business_activity_code":        "topmostSubform[0].Page1[0].ABC[0].f1_12[0]",
    "f1120s_sch_b_business_activity_description": "topmostSubform[0].Page2[0].f2_2[0]",
    "f1120s_sch_b_product_or_service":            "topmostSubform[0].Page2[0].f2_3[0]",
    # Schedule B — yes/no questions. Only Yes-side checkbox paths are mapped.
    "f1120s_sch_b_has_any_foreign_shareholders": "topmostSubform[0].Page2[0].c2_2[0]",
    "f1120s_sch_b_any_c_corp_subsidiaries":      "topmostSubform[0].Page2[0].c2_3[0]",
    "f1120s_sch_b_owns_foreign_entity":          "topmostSubform[0].Page2[0].c2_4[0]",
    # Schedule K — income/loss items
    "f1120s_sch_k_ordinary_business_income":    "topmostSubform[0].Page3[0].f3_3[0]",
    "f1120s_sch_k_net_rental_real_estate":      "topmostSubform[0].Page3[0].f3_4[0]",
    "f1120s_sch_k_other_net_rental_income":     "topmostSubform[0].Page3[0].f3_7[0]",
    "f1120s_sch_k_interest_income":             "topmostSubform[0].Page3[0].f3_8[0]",
    "f1120s_sch_k_ordinary_dividends":          "topmostSubform[0].Page3[0].f3_9[0]",
    "f1120s_sch_k_royalties":                   "topmostSubform[0].Page3[0].f3_11[0]",
    "f1120s_sch_k_net_short_term_capital_gain": "topmostSubform[0].Page3[0].f3_12[0]",
    "f1120s_sch_k_net_long_term_capital_gain":  "topmostSubform[0].Page3[0].f3_13[0]",
    "f1120s_sch_k_net_section_1231_gain":       "topmostSubform[0].Page3[0].f3_16[0]",
    "f1120s_sch_k_other_income":                "topmostSubform[0].Page3[0].f3_18[0]",
    # Schedule K — deductions/credits
    "f1120s_sch_k_section_179_deduction":       "topmostSubform[0].Page3[0].f3_19[0]",
    "f1120s_sch_k_charitable_contributions":    "topmostSubform[0].Page3[0].f3_20[0]",
    "f1120s_sch_k_low_income_housing_credit":   "topmostSubform[0].Page3[0].f3_27[0]",
    # Schedule K — other items
    "f1120s_sch_k_tax_exempt_interest":         "topmostSubform[0].Page3[0].f3_43[0]",
    "f1120s_sch_k_investment_income":           "topmostSubform[0].Page4[0].f4_1[0]",
    "f1120s_sch_k_income_loss_reconciliation":  "topmostSubform[0].Page4[0].f4_4[0]",
}


# ── 2024 registries ──────────────────────────────────────────────────────────
#
# The 2024 form has 441 AcroForm fields vs 454 for 2025. The 2024 form uses
# the same line structure (including Line 19 Energy efficient commercial
# buildings deduction), but Page1 AcroForm field numbering is offset by -4
# vs 2025 throughout (e.g. 2025's f1_17[0] = 2024's f1_13[0]).
# The ABC subform follows the same -4 offset (f1_12 → f1_8 for business
# activity code). Schedule B (Page2), Schedule K (Page3/Page4), and the
# derivation cell structure are identical between years.
#
# Structural differences resolved from the probe of
# pdfs/federal/2024/f1120s.pdf:
#
# 1. f1120s_built_in_gains_tax: The 2024 form has a fillable cell for
#    Line 23b "Tax from Schedule D" at f1_38[0] (2025 suppressed it).
#    → goes in _MAPPING_2024 (not _SUPPRESSED_2024).
#
# 2. f1120s_estimated_tax_payments and f1120s_prior_year_overpayment_credited:
#    Line 24a "Current year's estimated tax payments and preceding year's
#    overpayment credited to the current year" is a single combined cell in
#    the 2024 form at f1_40[0] — same aggregation pattern as 2025's f1_44[0].
#    → both keys go in _AGGREGATIONS_2024.
#
# 3. f1120s_interest_on_453_deferred and f1120s_total_tax: aggregated into
#    Line 23c "Add lines 23a and 23b" cell at f1_39[0], same as 2025
#    aggregates them into f1_43[0].
#    → both keys go in _AGGREGATIONS_2024.
#
# All field paths below were confirmed present in the probe output of
# pdfs/federal/2024/f1120s.pdf (441 fields total).

_MAPPING_2024: dict[str, str] = {
    # Income — Lines 1a-6
    "f1120s_gross_receipts":            "topmostSubform[0].Page1[0].f1_13[0]",
    "f1120s_returns_and_allowances":    "topmostSubform[0].Page1[0].f1_14[0]",
    "f1120s_net_receipts":              "topmostSubform[0].Page1[0].f1_15[0]",
    "f1120s_cost_of_goods_sold":        "topmostSubform[0].Page1[0].f1_16[0]",
    "f1120s_gross_profit":              "topmostSubform[0].Page1[0].f1_17[0]",
    "f1120s_net_gain_loss_4797":        "topmostSubform[0].Page1[0].f1_18[0]",
    "f1120s_other_income":              "topmostSubform[0].Page1[0].f1_19[0]",
    "f1120s_total_income":              "topmostSubform[0].Page1[0].f1_20[0]",
    # Deductions — Lines 7-22 (same numbering as 2025; Line 19 Energy exists
    # in 2024 too but has no compute key — skipped at f1_33[0])
    "f1120s_compensation_of_officers":  "topmostSubform[0].Page1[0].f1_21[0]",
    "f1120s_salaries_wages":            "topmostSubform[0].Page1[0].f1_22[0]",
    "f1120s_repairs_maintenance":       "topmostSubform[0].Page1[0].f1_23[0]",
    "f1120s_bad_debts":                 "topmostSubform[0].Page1[0].f1_24[0]",
    "f1120s_rents":                     "topmostSubform[0].Page1[0].f1_25[0]",
    "f1120s_taxes_licenses":            "topmostSubform[0].Page1[0].f1_26[0]",
    "f1120s_interest":                  "topmostSubform[0].Page1[0].f1_27[0]",
    "f1120s_depreciation":              "topmostSubform[0].Page1[0].f1_28[0]",
    "f1120s_depletion":                 "topmostSubform[0].Page1[0].f1_29[0]",
    "f1120s_advertising":               "topmostSubform[0].Page1[0].f1_30[0]",
    "f1120s_pension_profit_sharing":    "topmostSubform[0].Page1[0].f1_31[0]",
    "f1120s_employee_benefits":         "topmostSubform[0].Page1[0].f1_32[0]",
    # Skip f1_33[0] — Line 19 Energy efficient commercial buildings (no compute key)
    "f1120s_other_deductions":          "topmostSubform[0].Page1[0].f1_34[0]",
    "f1120s_total_deductions":          "topmostSubform[0].Page1[0].f1_35[0]",
    "f1120s_ordinary_business_income":  "topmostSubform[0].Page1[0].f1_36[0]",
    # Tax — Line 23a and Line 23b (built_in_gains_tax has its own cell in 2024)
    "f1120s_net_passive_income_tax":    "topmostSubform[0].Page1[0].f1_37[0]",
    "f1120s_built_in_gains_tax":        "topmostSubform[0].Page1[0].f1_38[0]",
    # Line 23c (total_tax + interest_on_453_deferred) → _AGGREGATIONS_2024
    # Payments — Lines 24b-24z, 25-28a
    # Line 24a (estimated + prior year) → _AGGREGATIONS_2024
    "f1120s_tax_deposited_with_7004":       "topmostSubform[0].Page1[0].f1_41[0]",
    "f1120s_credit_for_federal_excise_tax": "topmostSubform[0].Page1[0].f1_42[0]",
    "f1120s_refundable_credits":            "topmostSubform[0].Page1[0].f1_43[0]",
    "f1120s_total_payments":                "topmostSubform[0].Page1[0].f1_44[0]",
    "f1120s_estimated_tax_penalty":         "topmostSubform[0].Page1[0].f1_45[0]",
    "f1120s_amount_owed":                   "topmostSubform[0].Page1[0].f1_46[0]",
    "f1120s_overpayment":                   "topmostSubform[0].Page1[0].f1_47[0]",
    "f1120s_credited_to_next_year":         "topmostSubform[0].Page1[0].f1_48[0]",
    # Schedule B — accounting method radio group (same paths as 2025)
    "f1120s_sch_b_accounting_method_cash":    "topmostSubform[0].Page2[0].c2_1[0]",
    "f1120s_sch_b_accounting_method_accrual": "topmostSubform[0].Page2[0].c2_1[1]",
    "f1120s_sch_b_accounting_method_other":   "topmostSubform[0].Page2[0].c2_1[2]",
    # Schedule B — entity info
    # business_activity_code lives in the Page1 ABC subform; in 2024 the
    # ABC subform uses f1_8[0] (2025 uses f1_12[0]; same -4 offset applies)
    "f1120s_sch_b_business_activity_code":        "topmostSubform[0].Page1[0].ABC[0].f1_8[0]",
    "f1120s_sch_b_business_activity_description": "topmostSubform[0].Page2[0].f2_2[0]",
    "f1120s_sch_b_product_or_service":            "topmostSubform[0].Page2[0].f2_3[0]",
    # Schedule B — yes/no questions (Yes-side only; same paths as 2025)
    "f1120s_sch_b_has_any_foreign_shareholders": "topmostSubform[0].Page2[0].c2_2[0]",
    "f1120s_sch_b_any_c_corp_subsidiaries":      "topmostSubform[0].Page2[0].c2_3[0]",
    "f1120s_sch_b_owns_foreign_entity":          "topmostSubform[0].Page2[0].c2_4[0]",
    # Schedule K — income/loss items (identical paths to 2025)
    "f1120s_sch_k_ordinary_business_income":    "topmostSubform[0].Page3[0].f3_3[0]",
    "f1120s_sch_k_net_rental_real_estate":      "topmostSubform[0].Page3[0].f3_4[0]",
    "f1120s_sch_k_other_net_rental_income":     "topmostSubform[0].Page3[0].f3_7[0]",
    "f1120s_sch_k_interest_income":             "topmostSubform[0].Page3[0].f3_8[0]",
    "f1120s_sch_k_ordinary_dividends":          "topmostSubform[0].Page3[0].f3_9[0]",
    "f1120s_sch_k_royalties":                   "topmostSubform[0].Page3[0].f3_11[0]",
    "f1120s_sch_k_net_short_term_capital_gain": "topmostSubform[0].Page3[0].f3_12[0]",
    "f1120s_sch_k_net_long_term_capital_gain":  "topmostSubform[0].Page3[0].f3_13[0]",
    "f1120s_sch_k_net_section_1231_gain":       "topmostSubform[0].Page3[0].f3_16[0]",
    "f1120s_sch_k_other_income":                "topmostSubform[0].Page3[0].f3_18[0]",
    # Schedule K — deductions/credits (identical paths to 2025)
    "f1120s_sch_k_section_179_deduction":       "topmostSubform[0].Page3[0].f3_19[0]",
    "f1120s_sch_k_charitable_contributions":    "topmostSubform[0].Page3[0].f3_20[0]",
    "f1120s_sch_k_low_income_housing_credit":   "topmostSubform[0].Page3[0].f3_27[0]",
    # Schedule K — other items (identical paths to 2025)
    "f1120s_sch_k_tax_exempt_interest":         "topmostSubform[0].Page3[0].f3_43[0]",
    "f1120s_sch_k_investment_income":           "topmostSubform[0].Page4[0].f4_1[0]",
    "f1120s_sch_k_income_loss_reconciliation":  "topmostSubform[0].Page4[0].f4_4[0]",
}


class PdfF1120S(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for IRS Form 1120-S.

    Unlike `Pdf1040`, which uses a single flat compute-key → PDF-field
    dict, this class exposes a five-registry design because the 2025
    Form 1120-S has structural patterns that a flat map cannot express:

    - `_MAPPING_<year>` — direct 1:1 compute-key → PDF-field-path. Most
      keys live here. This is the same shape as `Pdf1040._MAPPINGS`.
    - `_AGGREGATIONS_<year>` — PDF cells that receive the *sum* of
      multiple compute keys. The 2025 form combined former lines 23a +
      23b into a single line-24a cell, and the §453 deferred-interest
      amount must be folded into the line-23c "Total tax" write-in
      because no separate fillable cell exists.
    - `_DERIVATIONS_<year>` — PDF cells whose value is *computed* from
      compute outputs (e.g., line 28b refund = overpayment − credited).
      These never receive a single compute key directly.
    - `_SUPPRESSED_<year>` — compute keys that have *no* fillable cell
      on the year's form. v1 declares them out-of-scope-for-PDF and
      relies on attestations to ensure the user reports them externally.
    - `_CHECKBOX_STATES_<year>` — for boolean compute keys whose target
      PDF cell is an IRS XFA checkbox, this maps the compute key to the
      per-field "on" appearance state name (e.g. `"/1"`, `"/2"`, `"/3"`)
      because IRS XFA forms use non-conventional state names rather than
      the usual `"/Yes"`.

    These extensions did not exist for F1040 because the 1040's PDF
    fields line up 1:1 with compute outputs at the keys we expose. They
    are necessary for 1120-S because the IRS reorganized the Tax and
    Payments section on the 2025 revision (consolidating cells, dropping
    the built-in-gains-tax line, and converting some former cells into
    write-in adjustments).

    The partition invariant (enforced by the mapping test) is that every
    expected compute key is OWNED by exactly one of `_MAPPING_<year>`,
    `_AGGREGATIONS_<year>`, or `_SUPPRESSED_<year>`. Derivations consume
    compute keys but do not own them; see the comment block above
    `_DERIVATIONS_2025` for the convention.
    """

    _FORM_NAME = "Form 1120-S"
    _MAPPINGS: dict[int, dict[str, str]] = {2024: _MAPPING_2024, 2025: _MAPPING_2025}

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        if year == 2024:
            return _AGGREGATIONS_2024
        if year == 2025:
            return _AGGREGATIONS_2025
        raise ValueError(f"No Form 1120-S aggregations for year {year}")

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year == 2024:
            return _DERIVATIONS_2024
        if year == 2025:
            return _DERIVATIONS_2025
        raise ValueError(f"No Form 1120-S derivations for year {year}")

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year == 2024:
            return _SUPPRESSED_2024
        if year == 2025:
            return _SUPPRESSED_2025
        raise ValueError(f"No Form 1120-S suppressions for year {year}")

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        """Return compute key → PDF "on" state for IRS XFA checkbox fields.

        IRS XFA forms use per-field state names ("/1", "/2", "/3") rather than
        the conventional "/Yes". These overrides are passed to PdfFiller.fill()
        so that bool compute keys toggle the correct appearance state.
        """
        if year == 2024:
            return _CHECKBOX_STATES_2024
        if year == 2025:
            return _CHECKBOX_STATES_2025
        raise ValueError(f"No Form 1120-S checkbox states for year {year}")


# PDF cells that receive a sum of multiple compute keys (2025).
_AGGREGATIONS_2025: dict[str, tuple[str, ...]] = {
    # Line 24a — combined cell on 2025 for current-year estimated +
    # prior-year overpayment credited (was lines 23a + 23b on 2024).
    "topmostSubform[0].Page1[0].f1_44[0]": (
        "f1120s_estimated_tax_payments",
        "f1120s_prior_year_overpayment_credited",
    ),
    # Line 23c — IRS instructions tell filers to add §453(l)(3) /
    # §453A(c) interest into "Total tax" via a write-in; no separate
    # fillable cell exists for `interest_on_453_deferred`.
    "topmostSubform[0].Page1[0].f1_43[0]": (
        "f1120s_total_tax",
        "f1120s_interest_on_453_deferred",
    ),
}


# PDF cells whose value is derived from compute outputs (2025).
#
# Convention: derivation lambdas consume compute keys but do not own
# them. Every key referenced inside a lambda body must already appear in
# `_MAPPING_2025`, `_AGGREGATIONS_2025`, or `_SUPPRESSED_2025`. The
# partition test enforces ownership; lambda consumption is intentionally
# excluded from the partition.
_DERIVATIONS_2025: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 28b "Refunded" — refund = overpayment − credited to next year.
    "topmostSubform[0].Page1[0].f1_53[0]": lambda c: (
        c["f1120s_overpayment"] - c["f1120s_credited_to_next_year"]
    ),
}


# Checkbox "on" state names for IRS XFA checkbox fields (2025).
#
# IRS XFA forms use per-field state names ("/1", "/2", "/3") rather than the
# conventional "/Yes" that simpler PDF forms use. pypdf's
# update_page_form_field_values looks up the written value in the field's
# /AP/N appearance dict; only an exact match sets the field; anything else
# silently falls back to "/Off". These are the exact AP/N keys verified from
# the 2025 form template.
#
# Accounting method is a radio group: [0]=Cash(/1), [1]=Accrual(/2),
# [2]=Other(/3). The yes/no questions each have a single checkbox whose on
# state is always "/1".
_CHECKBOX_STATES_2025: dict[str, str] = {
    "f1120s_sch_b_accounting_method_cash":    "/1",
    "f1120s_sch_b_accounting_method_accrual": "/2",
    "f1120s_sch_b_accounting_method_other":   "/3",
    "f1120s_sch_b_has_any_foreign_shareholders": "/1",
    "f1120s_sch_b_any_c_corp_subsidiaries":      "/1",
    "f1120s_sch_b_owns_foreign_entity":          "/1",
}


# Compute keys with no fillable cell on the 2025 form.
_SUPPRESSED_2025: frozenset[str] = frozenset({
    # Why: 2025 1120-S removed the separate "Built-in Gains Tax" cell.
    # When nonzero (per the §1374 scope-out), this amount is reported via
    # attached statement / write-in. v1 declares it suppressed; the
    # scope-out attestation guarantees the user is aware they must
    # report it externally.
    "f1120s_built_in_gains_tax",
})


# PDF cells that receive a sum of multiple compute keys (2024).
_AGGREGATIONS_2024: dict[str, tuple[str, ...]] = {
    # Line 23c — same pattern as 2025: total_tax + interest_on_453_deferred
    # aggregated into the "Add lines 23a and 23b" cell.
    "topmostSubform[0].Page1[0].f1_39[0]": (
        "f1120s_total_tax",
        "f1120s_interest_on_453_deferred",
    ),
    # Line 24a — combined cell for current-year estimated tax payments and
    # preceding year's overpayment credited (same single-cell design as 2025).
    "topmostSubform[0].Page1[0].f1_40[0]": (
        "f1120s_estimated_tax_payments",
        "f1120s_prior_year_overpayment_credited",
    ),
}


# PDF cells whose value is derived from compute outputs (2024).
#
# Convention: derivation lambdas consume compute keys but do not own them.
_DERIVATIONS_2024: dict[str, Callable[[Mapping[str, object]], object]] = {
    # Line 28 "Refunded" — same derivation as 2025 but at 2024's f1_49[0].
    "topmostSubform[0].Page1[0].f1_49[0]": lambda c: (
        c["f1120s_overpayment"] - c["f1120s_credited_to_next_year"]
    ),
}


# Checkbox "on" state names for IRS XFA checkbox fields (2024).
#
# The 2024 form uses the same XFA state names as 2025: the accounting method
# radio group uses "/1" (cash), "/2" (accrual), "/3" (other), and each
# yes/no question uses "/1" for the Yes checkbox. Verified against the
# "/_States_" lists from pypdf.get_fields() on pdfs/federal/2024/f1120s.pdf:
#   c2_1[0]: ['/1', '/Off']  c2_1[1]: ['/2', '/Off']  c2_1[2]: ['/3', '/Off']
#   c2_2[0]: ['/1', '/Off']  c2_3[0]: ['/1', '/Off']  c2_4[0]: ['/1', '/Off']
_CHECKBOX_STATES_2024: dict[str, str] = {
    "f1120s_sch_b_accounting_method_cash":    "/1",
    "f1120s_sch_b_accounting_method_accrual": "/2",
    "f1120s_sch_b_accounting_method_other":   "/3",
    "f1120s_sch_b_has_any_foreign_shareholders": "/1",
    "f1120s_sch_b_any_c_corp_subsidiaries":      "/1",
    "f1120s_sch_b_owns_foreign_entity":          "/1",
}


# Compute keys with no fillable cell on the 2024 form.
# In 2024, f1120s_built_in_gains_tax has its own cell (Line 23b, f1_38[0]),
# so nothing needs suppression.
_SUPPRESSED_2024: frozenset[str] = frozenset()
