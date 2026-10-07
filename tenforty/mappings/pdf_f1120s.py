"""PDF field mappings for IRS Form 1120-S.

Declared years are whatever ``_MAPPINGS`` below carries, which tracks
``tenforty.years.SCORP_FEDERAL_YEARS`` (the manifest is the single source of
truth for year support — this docstring intentionally names no year list so it
cannot go stale).

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


# ── Schedule B answer cells (shared by every year) ───────────────────────────
# One Yes box ([0], on-state "/1") and one No box ([1], on-state "/2") per
# question. The cell GROUP names are the only per-year difference: 2021 and 2022
# zero-pad the page-2 groups for lines 5a-9 (c2_05 ... c2_09); 2023-2025 do not.
# Page-3 groups (c3_1 ... c3_6) are spelled the same every year; line 16
# (digital assets, c3_6) exists on the 2023-2025 forms only. Every group name and
# its row was certified against each year's own template (widget Rect matched to
# the printed question), never inferred from numbering.
# (answer field, page, group name for 2021/2022, group name for 2023-2025)
_SCH_B_PAIR_CELLS: tuple[tuple[str, int, str, str], ...] = (
    ("shareholder_disregarded_entity_trust_estate_or_nominee", 2, "c2_2", "c2_2"),
    ("owns_20pct_stock_of_any_corporation", 2, "c2_3", "c2_3"),
    ("owns_20pct_interest_in_partnership_or_trust", 2, "c2_4", "c2_4"),
    ("restricted_stock_outstanding", 2, "c2_05", "c2_5"),
    ("stock_options_or_warrants_outstanding", 2, "c2_06", "c2_6"),
    ("filed_form_8918", 2, "c2_07", "c2_7"),
    ("section_163j_election", 2, "c2_09", "c2_9"),
    ("form_8990_conditions_met", 2, "c2_10", "c2_10"),
    ("receipts_and_assets_under_250k", 2, "c2_11", "c2_11"),
    ("nonshareholder_debt_canceled", 3, "c3_1", "c3_1"),
    ("qsub_election_terminated", 3, "c3_2", "c3_2"),
    ("payments_requiring_1099s", 3, "c3_3", "c3_3"),
    ("filed_required_1099s", 3, "c3_4", "c3_4"),
    ("qualified_opportunity_fund", 3, "c3_5", "c3_5"),
)
_SCH_B_Q16_FIELD = "digital_asset_transactions"  # page 3, c3_6, 2023+ only
_SCH_B_Q7_FIELD = "issued_oid_debt_instruments"  # single box, no No cell
_SCH_B_Q7_GROUP = ("c2_08", "c2_8")              # (2021/2022, 2023-2025)
_SCH_B_Q8_AMOUNT_FIELD = "net_unrealized_built_in_gain"  # line 8 dollar cell
_SCH_B_Q8_CELL = "topmostSubform[0].Page2[0].f2_48[0]"


def _sch_b_answer_cells(
    padded_groups: bool, has_q16: bool,
) -> tuple[dict[str, str], dict[str, str]]:
    """(compute-key -> PDF path, compute-key -> on-state) for the Schedule B
    answer cells of one year. ``padded_groups`` selects the 2021/2022 spelling;
    ``has_q16`` adds line 16 (2023+). Yes keys are ``f1120s_sch_b_<field>``
    (on-state "/1"); No keys append ``_no`` (on-state "/2")."""
    mapping: dict[str, str] = {}
    states: dict[str, str] = {}

    def add(field, page, group, with_no=True):
        base = f"topmostSubform[0].Page{page}[0].{group}"
        mapping[f"f1120s_sch_b_{field}"] = f"{base}[0]"
        states[f"f1120s_sch_b_{field}"] = "/1"
        if with_no:
            mapping[f"f1120s_sch_b_{field}_no"] = f"{base}[1]"
            states[f"f1120s_sch_b_{field}_no"] = "/2"

    for field, page, padded, plain in _SCH_B_PAIR_CELLS:
        add(field, page, padded if padded_groups else plain)
    add(_SCH_B_Q7_FIELD, 2, _SCH_B_Q7_GROUP[0 if padded_groups else 1],
        with_no=False)
    if has_q16:
        add(_SCH_B_Q16_FIELD, 3, "c3_6")
    mapping[f"f1120s_sch_b_{_SCH_B_Q8_AMOUNT_FIELD}"] = _SCH_B_Q8_CELL
    return mapping, states


_SCH_B_MAPPING_2021_2022, _SCH_B_STATES_2021_2022 = _sch_b_answer_cells(True, False)
_SCH_B_MAPPING_2023_ON, _SCH_B_STATES_2023_ON = _sch_b_answer_cells(False, True)
# Compute keys with no cell on the 2021/2022 forms (line 16 does not exist).
_SCH_B_Q16_KEYS = frozenset({
    f"f1120s_sch_b_{_SCH_B_Q16_FIELD}", f"f1120s_sch_b_{_SCH_B_Q16_FIELD}_no"})


# ── Schedule K pro-rata amount cells, sections 12-17 (every year) ────────────
# ONE table drives the whole block so the compute placeholders and the printed
# cells cannot drift apart. Each row: compute key, then the Page-3 field NUMBER
# on the 2021-2023 forms and on the 2024-2025 forms (None = the line has no cell
# on that vintage). The numbers SHIFT between vintages and were certified per
# year by matching each widget's row to the printed line label on that year's
# own template (tests/test_f1120s_sch_k_zero_fill.py repeats that check
# independently): line 12e exists on 2024+ only; 12c/12d are f3_23/f3_25 on the
# older forms but f3_22/f3_24 later; 13a-13g and 15a-16f sit one field lower on
# 2021-2023 (13a is f3_26 there, f3_27 from 2024). Type-text sub-cells and 17d
# have no amount cell and stay blank. 17b/17c (Page 4) are identical every year.
_SCH_K_P3_ROWS: tuple[tuple[str, int | None, int | None], ...] = (
    ("f1120s_sch_k_noncash_charitable_contributions", 21, 21),     # 12b
    ("f1120s_sch_k_investment_interest_expense", 23, 22),          # 12c
    ("f1120s_sch_k_section_59e2_expenditures", 25, 24),            # 12d
    ("f1120s_sch_k_other_deductions", None, 26),                   # 12e
    ("f1120s_sch_k_low_income_housing_credit", 26, 27),            # 13a
    ("f1120s_sch_k_low_income_housing_credit_other", 27, 28),      # 13b
    ("f1120s_sch_k_qualified_rehab_expenditures", 28, 29),         # 13c
    ("f1120s_sch_k_other_rental_real_estate_credits", 30, 31),     # 13d
    ("f1120s_sch_k_other_rental_credits", 32, 33),                 # 13e
    ("f1120s_sch_k_biofuel_producer_credit", 33, 34),              # 13f
    ("f1120s_sch_k_other_credits", 35, 36),                        # 13g
    ("f1120s_sch_k_amt_depreciation_adjustment", 36, 37),          # 15a
    ("f1120s_sch_k_amt_adjusted_gain_loss", 37, 38),               # 15b
    ("f1120s_sch_k_amt_depletion", 38, 39),                        # 15c
    ("f1120s_sch_k_amt_oil_gas_gross_income", 39, 40),             # 15d
    ("f1120s_sch_k_amt_oil_gas_deductions", 40, 41),               # 15e
    ("f1120s_sch_k_amt_other_items", 41, 42),                      # 15f
    ("f1120s_sch_k_tax_exempt_interest", 42, 43),                  # 16a
    ("f1120s_sch_k_other_tax_exempt_income", 43, 44),              # 16b
    ("f1120s_sch_k_nondeductible_expenses", 44, 45),               # 16c
    ("f1120s_sch_k_distributions", 45, 46),                        # 16d
    ("f1120s_sch_k_repayment_of_shareholder_loans", 46, 47),       # 16e
    ("f1120s_sch_k_foreign_taxes_paid", 47, 48),                   # 16f
)
_SCH_K_P4_ROWS: tuple[tuple[str, int], ...] = (
    ("f1120s_sch_k_investment_expenses", 2),                       # 17b
    ("f1120s_sch_k_dividend_distributions", 3),                    # 17c
)


def _sch_k_cells(newer: bool) -> dict[str, str]:
    """Schedule K section 12-17 cells for one vintage (``newer`` = 2024-2025).
    Lines with no cell on the vintage are simply absent (see
    ``_SCH_K_NO_CELL_2021_2023``)."""
    out = {
        key: f"topmostSubform[0].Page3[0].f3_{n}[0]"
        for key, old, new in _SCH_K_P3_ROWS
        if (n := new if newer else old) is not None
    }
    out.update({key: f"topmostSubform[0].Page4[0].f4_{n}[0]"
                for key, n in _SCH_K_P4_ROWS})
    return out


_SCH_K_CELLS_2021_2023: dict[str, str] = _sch_k_cells(False)
_SCH_K_CELLS_2024_2025: dict[str, str] = _sch_k_cells(True)
# Compute keys the 2021-2023 forms have no cell for (suppressed there).
_SCH_K_NO_CELL_2021_2023: frozenset[str] = frozenset(
    key for key, old, _ in _SCH_K_P3_ROWS if old is None)


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
    # Line 19 "Energy efficient commercial buildings deduction" (Form 7205) is
    # f1_37 on the 2025 form; the compute value is always 0 (nonzero refused).
    # Other deductions follows at Line 20 (`f1_38`).
    "f1120s_energy_efficient_buildings_deduction":
        "topmostSubform[0].Page1[0].f1_37[0]",
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
    # Schedule B — every question's Yes ([0]) and No ([1]) cells, line 7's box and
    # line 8's amount (see _sch_b_answer_cells).
    **_SCH_B_MAPPING_2023_ON,
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
    **_SCH_K_CELLS_2024_2025,
    # Schedule K — other items
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
    # Line 19 Energy efficient commercial buildings (Form 7205): f1_33[0] on the
    # 2023 and 2024 forms; value always 0 (nonzero refused at compute).
    "f1120s_energy_efficient_buildings_deduction":
        "topmostSubform[0].Page1[0].f1_33[0]",
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
    # Schedule B — every question's Yes/No cells (same cells as 2025)
    **_SCH_B_MAPPING_2023_ON,
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
    **_SCH_K_CELLS_2024_2025,
    # Schedule K — other items (identical paths to 2025)
    "f1120s_sch_k_investment_income":           "topmostSubform[0].Page4[0].f4_1[0]",
    "f1120s_sch_k_income_loss_reconciliation":  "topmostSubform[0].Page4[0].f4_4[0]",
}


# ── 2023 registries ──────────────────────────────────────────────────────────
#
# The 2023 Form 1120-S shares 2024's AcroForm field-NAME set (a field-tree
# diff shows a single difference — 2024 carries one extra field, Page3 f3_48),
# so Page 1 (income/deductions/tax/payments, Item B code f1_8), Schedule B
# (Page 2), and the Schedule K lines on Pages 3–4 inherit the 2024 registries.
#
# EXCEPT one cell, because identical field NAMES do NOT guarantee identical
# field-to-LINE assignments — the IRS shifted the Schedule K AMT/other-items
# block by one field between 2023 and 2024. Verified by filled-emit on each
# year's real template (probe render committed as f1120s.probe.pdf):
#
#   Line 16a "Tax-exempt interest income":  2023 → f3_42,  2024/2025 → f3_43
#   Line 15f "Other AMT items":             2023 → f3_41,  2024/2025 → f3_42
#
# So f1120s_sch_k_tax_exempt_interest is f3_42 for 2023 but f3_43 for
# 2024/2025 — BOTH correct for their own year. This is the renumbering trap:
# a path-existence check passes either way (both fields exist on every
# template); only the rendered position distinguishes the right cell.
_MAPPING_2023: dict[str, str] = {
    **{k: v for k, v in _MAPPING_2024.items()
       if k not in _SCH_K_CELLS_2024_2025},
    # Every 2023 Schedule K section 12-17 cell comes from the 2021-2023 table
    # (13a is f3_26 here, not 2024's f3_27; 16a f3_42; no line 12e).
    **_SCH_K_CELLS_2021_2023,
}


# 2022 Form 1120-S. Built by side-by-side marker-probe renders of the 2022 and
# 2023 templates (both committed: f1120s.probe.pdf for 2022). The /Rect-based
# triage tools were actively MISLEADING here — they reported a uniform -2 page-1
# shift, but the rendered markers show the 2022 fields simply sit two rows lower
# on the page with the SAME names (the renumbering trap in reverse: same
# position != same field). Reading the printed line labels is the only
# authority. What the renders actually show:
#   * Page 1 lines 1a-18 keep their 2023 field names (f1_13-f1_32).
#   * 2023 has a line-19 "Energy efficient commercial buildings (Form 7205)"
#     field (f1_33) that 2022 LACKS, so every field from line 19 "Other
#     deductions" onward is 2023's name MINUS ONE (f1_34->f1_33 … f1_48->f1_47).
#   * 2023 has a line-24d "Elective payment election from Form 3800" field
#     (f1_43, the compute key `f1120s_refundable_credits`) that 2022 LACKS
#     entirely — so refundable_credits is SUPPRESSED for 2022, not mapped.
#   * Pages 2 (Sch B), 3 (Sch K), and 4 are byte-identical to 2023 — including
#     f1120s_sch_k_tax_exempt_interest at f3_42 (the 2023 line-16a cell; the
#     2024/2025 f3_43 shift does NOT apply to 2022).
# Every full path resolved against the 2022 template's own AcroForm inventory.
_MAPPING_2022: dict[str, str] = {
    "f1120s_gross_receipts": "topmostSubform[0].Page1[0].f1_13[0]",
    "f1120s_returns_and_allowances": "topmostSubform[0].Page1[0].f1_14[0]",
    "f1120s_net_receipts": "topmostSubform[0].Page1[0].f1_15[0]",
    "f1120s_cost_of_goods_sold": "topmostSubform[0].Page1[0].f1_16[0]",
    "f1120s_gross_profit": "topmostSubform[0].Page1[0].f1_17[0]",
    "f1120s_net_gain_loss_4797": "topmostSubform[0].Page1[0].f1_18[0]",
    "f1120s_other_income": "topmostSubform[0].Page1[0].f1_19[0]",
    "f1120s_total_income": "topmostSubform[0].Page1[0].f1_20[0]",
    "f1120s_compensation_of_officers": "topmostSubform[0].Page1[0].f1_21[0]",
    "f1120s_salaries_wages": "topmostSubform[0].Page1[0].f1_22[0]",
    "f1120s_repairs_maintenance": "topmostSubform[0].Page1[0].f1_23[0]",
    "f1120s_bad_debts": "topmostSubform[0].Page1[0].f1_24[0]",
    "f1120s_rents": "topmostSubform[0].Page1[0].f1_25[0]",
    "f1120s_taxes_licenses": "topmostSubform[0].Page1[0].f1_26[0]",
    "f1120s_interest": "topmostSubform[0].Page1[0].f1_27[0]",
    "f1120s_depreciation": "topmostSubform[0].Page1[0].f1_28[0]",
    "f1120s_depletion": "topmostSubform[0].Page1[0].f1_29[0]",
    "f1120s_advertising": "topmostSubform[0].Page1[0].f1_30[0]",
    "f1120s_pension_profit_sharing": "topmostSubform[0].Page1[0].f1_31[0]",
    "f1120s_employee_benefits": "topmostSubform[0].Page1[0].f1_32[0]",
    # Line 19 onward: 2022 lacks 2023's Form-7205 line, so names are -1.
    "f1120s_other_deductions": "topmostSubform[0].Page1[0].f1_33[0]",
    "f1120s_total_deductions": "topmostSubform[0].Page1[0].f1_34[0]",
    "f1120s_ordinary_business_income": "topmostSubform[0].Page1[0].f1_35[0]",
    "f1120s_net_passive_income_tax": "topmostSubform[0].Page1[0].f1_36[0]",
    "f1120s_built_in_gains_tax": "topmostSubform[0].Page1[0].f1_37[0]",
    "f1120s_tax_deposited_with_7004": "topmostSubform[0].Page1[0].f1_40[0]",
    "f1120s_credit_for_federal_excise_tax": "topmostSubform[0].Page1[0].f1_41[0]",
    "f1120s_total_payments": "topmostSubform[0].Page1[0].f1_43[0]",
    "f1120s_estimated_tax_penalty": "topmostSubform[0].Page1[0].f1_44[0]",
    "f1120s_amount_owed": "topmostSubform[0].Page1[0].f1_45[0]",
    "f1120s_overpayment": "topmostSubform[0].Page1[0].f1_46[0]",
    "f1120s_credited_to_next_year": "topmostSubform[0].Page1[0].f1_47[0]",
    # Schedule B (page 2 + business activity code on page 1) — identical to 2023.
    "f1120s_sch_b_accounting_method_cash": "topmostSubform[0].Page2[0].c2_1[0]",
    "f1120s_sch_b_accounting_method_accrual": "topmostSubform[0].Page2[0].c2_1[1]",
    "f1120s_sch_b_accounting_method_other": "topmostSubform[0].Page2[0].c2_1[2]",
    "f1120s_sch_b_business_activity_code": "topmostSubform[0].Page1[0].ABC[0].f1_8[0]",
    "f1120s_sch_b_business_activity_description": "topmostSubform[0].Page2[0].f2_2[0]",
    "f1120s_sch_b_product_or_service": "topmostSubform[0].Page2[0].f2_3[0]",
    **_SCH_B_MAPPING_2021_2022,
    # Schedule K (pages 3-4) — byte-identical to 2023.
    "f1120s_sch_k_ordinary_business_income": "topmostSubform[0].Page3[0].f3_3[0]",
    "f1120s_sch_k_net_rental_real_estate": "topmostSubform[0].Page3[0].f3_4[0]",
    "f1120s_sch_k_other_net_rental_income": "topmostSubform[0].Page3[0].f3_7[0]",
    "f1120s_sch_k_interest_income": "topmostSubform[0].Page3[0].f3_8[0]",
    "f1120s_sch_k_ordinary_dividends": "topmostSubform[0].Page3[0].f3_9[0]",
    "f1120s_sch_k_royalties": "topmostSubform[0].Page3[0].f3_11[0]",
    "f1120s_sch_k_net_short_term_capital_gain": "topmostSubform[0].Page3[0].f3_12[0]",
    "f1120s_sch_k_net_long_term_capital_gain": "topmostSubform[0].Page3[0].f3_13[0]",
    "f1120s_sch_k_net_section_1231_gain": "topmostSubform[0].Page3[0].f3_16[0]",
    "f1120s_sch_k_other_income": "topmostSubform[0].Page3[0].f3_18[0]",
    "f1120s_sch_k_section_179_deduction": "topmostSubform[0].Page3[0].f3_19[0]",
    "f1120s_sch_k_charitable_contributions": "topmostSubform[0].Page3[0].f3_20[0]",
    **_SCH_K_CELLS_2021_2023,
    "f1120s_sch_k_investment_income": "topmostSubform[0].Page4[0].f4_1[0]",
    "f1120s_sch_k_income_loss_reconciliation": "topmostSubform[0].Page4[0].f4_4[0]",
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
    _MAPPINGS: dict[int, dict[str, str]] = {
        # 2021 field-to-line assignment verified IDENTICAL to 2022 by
        # side-by-side marker-probe (pdfs/federal/2021/f1120s.probe.pdf);
        # both are the pre-2023 layout. Inherits the 2022 mapping verbatim.
        2021: _MAPPING_2022,
        2022: _MAPPING_2022,
        2023: _MAPPING_2023, 2024: _MAPPING_2024, 2025: _MAPPING_2025,
    }

    @classmethod
    def get_aggregations(cls, year: int) -> dict[str, tuple[str, ...]]:
        if year not in _AGGREGATIONS_BY_YEAR:
            raise ValueError(f"No Form 1120-S aggregations for year {year}")
        return _AGGREGATIONS_BY_YEAR[year]

    @classmethod
    def get_derivations(
        cls,
        year: int,
    ) -> dict[str, Callable[[Mapping[str, object]], object]]:
        if year not in _DERIVATIONS_BY_YEAR:
            raise ValueError(f"No Form 1120-S derivations for year {year}")
        return _DERIVATIONS_BY_YEAR[year]

    @classmethod
    def get_suppressed(cls, year: int) -> frozenset[str]:
        if year not in _SUPPRESSED_BY_YEAR:
            raise ValueError(f"No Form 1120-S suppressions for year {year}")
        return _SUPPRESSED_BY_YEAR[year]

    @classmethod
    def get_checkbox_states(cls, year: int) -> dict[str, str]:
        """Return compute key → PDF "on" state for IRS XFA checkbox fields.

        IRS XFA forms use per-field state names ("/1", "/2", "/3") rather than
        the conventional "/Yes". These overrides are passed to PdfFiller.fill()
        so that bool compute keys toggle the correct appearance state.
        """
        if year not in _CHECKBOX_STATES_BY_YEAR:
            raise ValueError(f"No Form 1120-S checkbox states for year {year}")
        return _CHECKBOX_STATES_BY_YEAR[year]

    @classmethod
    def get_entity_header_fields(cls, year: int) -> dict[str, str]:
        """Entity-identity key -> page-1 header text cell (name/address block and
        items A, D, E, F, I).

        ADDITIVE and independent of the compute-key registries above: these
        keys are NOT ``f1120s.compute`` outputs. Like the CA 100S entity
        identity, their values are injected at emit time from ``SCorpReturn``
        (see ``_entity_header_values`` in the orchestrator), so they live
        outside the compute-key partition (``_MAPPING_<year>`` /
        ``_AGGREGATIONS_<year>`` / ``_SUPPRESSED_<year>``). Every path was
        certified per year by a marker-probe render of that year's own template
        (each cell filled with its own label, page rendered, label read against
        the printed item caption), not inferred from field numbering."""
        if year not in _ENTITY_HEADER_BY_YEAR:
            raise ValueError(f"No Form 1120-S entity header cells for year {year}")
        return _ENTITY_HEADER_BY_YEAR[year]

    @classmethod
    def get_item_g_cells(cls, year: int) -> dict[bool, tuple[str, str]]:
        """{answer: (field_path, ON-state)} for page 1 item G (Yes / No).
        Additive: the orchestrator writes only the chosen answer's box."""
        if year not in _ITEM_G_BY_YEAR:
            raise ValueError(f"No Form 1120-S item G cells for year {year}")
        return _ITEM_G_BY_YEAR[year]

    @classmethod
    def get_item_h_cells(cls, year: int) -> dict[str, tuple[str, str]]:
        """{item: (field_path, ON-state)} for the item H check-if boxes other
        than H(4) Amended (see ``get_amended_mark``). Additive: only a True
        item is written."""
        if year not in _ITEM_H_BY_YEAR:
            raise ValueError(f"No Form 1120-S item H cells for year {year}")
        return _ITEM_H_BY_YEAR[year]

    @classmethod
    def get_amended_mark(cls, year: int) -> tuple[str, str]:
        """(field_path, ON-state) for box H(4) "Amended return" (§4a).

        ADDITIVE and independent of the value/aggregation/derivation/checkbox
        registries above: nothing here changes an existing mapped field. The
        orchestrator merges this single entry into the fill only when the
        S-corp return is flagged amended, writing the ON-state; an unflagged
        return sets nothing (the box stays /Off). Certified from each
        template's own get_fields()/_States_ (probe-tables "Entity amended
        checkboxes").
        """
        if year not in _AMENDED_MARK_BY_YEAR:
            raise ValueError(f"No Form 1120-S amended mark for year {year}")
        return _AMENDED_MARK_BY_YEAR[year]


# Page 1 item G (electing S this year, Yes / No) and item H "Check if:" boxes
# (1) Final return, (2) Name change, (3) Address change, (5) S election
# termination. Identical on every template 2021-2025 (each verified separately,
# the 2021 template included): widget Rects against the printed captions. Item G
# is one two-widget group c1_2 (Yes [0] export /1 left, No [1] export /2 right);
# each H box is its own checkbox c1_3 / c1_4 / c1_5 / (c1_6 = H(4) Amended,
# wired via get_amended_mark) / c1_7, export /1.
_P1_ = "topmostSubform[0].Page1[0]."
_ITEM_G: dict[bool, tuple[str, str]] = {
    True: (_P1_ + "c1_2[0]", "/1"), False: (_P1_ + "c1_2[1]", "/2")}
_ITEM_H: dict[str, tuple[str, str]] = {
    "final_return": (_P1_ + "c1_3[0]", "/1"),
    "name_change": (_P1_ + "c1_4[0]", "/1"),
    "address_change": (_P1_ + "c1_5[0]", "/1"),
    "s_election_terminated": (_P1_ + "c1_7[0]", "/1"),
}
_ITEM_G_BY_YEAR = {y: _ITEM_G for y in (2021, 2022, 2023, 2024, 2025)}
_ITEM_H_BY_YEAR = {y: _ITEM_H for y in (2021, 2022, 2023, 2024, 2025)}

# §4a amended-return mark — box H(4) "Amended return".
# Field PATH + ON-state read off each template's own get_fields()/_States_:
# path topmostSubform[0].Page1[0].c1_6[0], /_States_ ['/1','/Off'], ON '/1',
# IDENTICAL across all supported years 2021-2025 (bare topmostSubform
# namespace, no year prefix). See amended-returns-probe-tables.md §(a).
_AMENDED_MARK_1120S: tuple[str, str] = (
    "topmostSubform[0].Page1[0].c1_6[0]", "/1")
_AMENDED_MARK_BY_YEAR: dict[int, tuple[str, str]] = {
    2021: _AMENDED_MARK_1120S, 2022: _AMENDED_MARK_1120S,
    2023: _AMENDED_MARK_1120S, 2024: _AMENDED_MARK_1120S,
    2025: _AMENDED_MARK_1120S,
}


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
# [2]=Other(/3). Each Schedule B yes/no question is a separate Yes box ([0], on
# state "/1") and No box ([1], on state "/2"); see _sch_b_answer_cells.
_CHECKBOX_STATES_2025: dict[str, str] = {
    "f1120s_sch_b_accounting_method_cash":    "/1",
    "f1120s_sch_b_accounting_method_accrual": "/2",
    "f1120s_sch_b_accounting_method_other":   "/3",
    **_SCH_B_STATES_2023_ON,
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
# yes/no question uses "/1" for its Yes box and "/2" for its No box (see
# _sch_b_answer_cells). Verified against the
# "/_States_" lists from pypdf.get_fields() on pdfs/federal/2024/f1120s.pdf:
#   c2_1[0]: ['/1', '/Off']  c2_1[1]: ['/2', '/Off']  c2_1[2]: ['/3', '/Off']
#   c2_2[0]: ['/1', '/Off']  c2_2[1]: ['/2', '/Off']  (and every pair likewise)
_CHECKBOX_STATES_2024: dict[str, str] = {
    "f1120s_sch_b_accounting_method_cash":    "/1",
    "f1120s_sch_b_accounting_method_accrual": "/2",
    "f1120s_sch_b_accounting_method_other":   "/3",
    **_SCH_B_STATES_2023_ON,
}


# Compute keys with no fillable cell on the 2024 form.
# In 2024, f1120s_built_in_gains_tax has its own cell (Line 23b, f1_38[0]),
# so nothing needs suppression.
_SUPPRESSED_2024: frozenset[str] = frozenset()


# Year-keyed dispatch tables for the four registries above — replaces
# `if year == <literal>` branching with membership-gated dict lookup.
# 2023 reuses the 2024 objects for these four registries: the two aggregation
# cells (Page1 f1_39, f1_40), the refund derivation (Page1 f1_49), the empty
# suppression set (built-in-gains tax has its own Line 23b cell f1_38 in 2023,
# as in 2024), and the XFA checkbox on-states (Page 2 tree identical to 2024)
# are all byte-identical between the two years.
# 2022 tax-and-payments registries. The Tax and Payments block sits one line
# earlier than 2023 (2022 has no line-24d elective-payment field), so the
# aggregation/derivation cells are 2023's minus one — render-confirmed on
# f1120s.probe.pdf page 1:
#   Line 22c "Add 22a and 22b" (total tax write-in):  2023 f1_39 -> 2022 f1_38
#   Line 23a estimated + prior overpayment:           2023 f1_40 -> 2022 f1_39
#   Line 27 "Refunded" (overpayment - credited):      2023 f1_49 -> 2022 f1_48
# refundable_credits has no 2022 cell (2022 lacks the elective-payment line), so
# it is SUPPRESSED. Built-in gains tax has its own Line 22b cell (f1_37), so it
# is NOT suppressed (as in 2023/2024). Page-2 XFA checkbox on-states are
# byte-identical to 2024 (verified: c2_1[0..2]=/1,/2,/3; c2_2..4[0]=/1).
_AGGREGATIONS_2022: dict[str, tuple[str, ...]] = {
    "topmostSubform[0].Page1[0].f1_38[0]": (
        "f1120s_total_tax",
        "f1120s_interest_on_453_deferred",
    ),
    "topmostSubform[0].Page1[0].f1_39[0]": (
        "f1120s_estimated_tax_payments",
        "f1120s_prior_year_overpayment_credited",
    ),
}
_DERIVATIONS_2022: dict[str, Callable[[Mapping[str, object]], object]] = {
    "topmostSubform[0].Page1[0].f1_48[0]": lambda c: (
        c["f1120s_overpayment"] - c["f1120s_credited_to_next_year"]
    ),
}
_SUPPRESSED_2022: frozenset[str] = frozenset(
    _SCH_K_NO_CELL_2021_2023 | {"f1120s_refundable_credits",
     # No line 19 energy deduction on the 2021-2022 forms.
     "f1120s_energy_efficient_buildings_deduction"} | _SCH_B_Q16_KEYS)


# 2021 inherits every 2022 tax-and-payments registry verbatim: the 2021 and
# 2022 templates are the identical pre-2023 layout (marker-probe confirmed), so
# the two aggregation cells (f1_38, f1_39), the refund derivation (f1_48), the
# refundable_credits suppression, and the Page-2 XFA checkbox on-states all
# carry over unchanged.
_AGGREGATIONS_BY_YEAR: dict[int, dict[str, tuple[str, ...]]] = {
    2021: _AGGREGATIONS_2022,
    2022: _AGGREGATIONS_2022,
    2023: _AGGREGATIONS_2024, 2024: _AGGREGATIONS_2024, 2025: _AGGREGATIONS_2025,
}
_DERIVATIONS_BY_YEAR: dict[int, dict[str, Callable[[Mapping[str, object]], object]]] = {
    2021: _DERIVATIONS_2022,
    2022: _DERIVATIONS_2022,
    2023: _DERIVATIONS_2024, 2024: _DERIVATIONS_2024, 2025: _DERIVATIONS_2025,
}
_SUPPRESSED_2023: frozenset[str] = _SUPPRESSED_2024 | _SCH_K_NO_CELL_2021_2023
_SUPPRESSED_BY_YEAR: dict[int, frozenset[str]] = {
    2021: _SUPPRESSED_2022,
    2022: _SUPPRESSED_2022,
    2023: _SUPPRESSED_2023, 2024: _SUPPRESSED_2024, 2025: _SUPPRESSED_2025,
}
# 2021/2022: same accounting-method states, but the Schedule B answer cells use
# the zero-padded group names and have no line 16 (so no line 16 on-state).
_CHECKBOX_STATES_2022: dict[str, str] = {
    "f1120s_sch_b_accounting_method_cash":    "/1",
    "f1120s_sch_b_accounting_method_accrual": "/2",
    "f1120s_sch_b_accounting_method_other":   "/3",
    **_SCH_B_STATES_2021_2022,
}
_CHECKBOX_STATES_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _CHECKBOX_STATES_2022,
    2022: _CHECKBOX_STATES_2022,
    2023: _CHECKBOX_STATES_2024, 2024: _CHECKBOX_STATES_2024, 2025: _CHECKBOX_STATES_2025,
}


# ── Page-1 entity header identity cells ──────────────────────────────────────
# 2021-2024 share one layout: the address block is name / street / ONE combined
# "City or town, state or province, country, and ZIP" cell, item A sits in the
# ABC subform (f1_7), and items D/E/F/I are f1_9..f1_12. 2025 splits the address
# into city / state / country / ZIP cells (the country cell is left blank: a
# domestic return) and shifts items A and D/E/F/I to f1_11 and f1_13..f1_16.
_P1 = "topmostSubform[0].Page1[0]."
_ENTITY_HEADER_2021_2024: dict[str, str] = {
    "f1120s_entity_s_election_date":
        _P1 + "ABC[0].f1_7[0]",
    "f1120s_entity_name":
        _P1 + "CalendarYear-TypePrint_ReadOrder[0].f1_4[0]",
    "f1120s_entity_street":
        _P1 + "CalendarYear-TypePrint_ReadOrder[0].f1_5[0]",
    "f1120s_entity_city_state_zip":
        _P1 + "CalendarYear-TypePrint_ReadOrder[0].f1_6[0]",
    "f1120s_entity_ein":               _P1 + "f1_9[0]",
    "f1120s_entity_date_incorporated": _P1 + "f1_10[0]",
    "f1120s_entity_total_assets":      _P1 + "f1_11[0]",
    "f1120s_entity_shareholder_count": _P1 + "f1_12[0]",
}
_ENTITY_HEADER_2025: dict[str, str] = {
    "f1120s_entity_s_election_date":
        _P1 + "ABC[0].f1_11[0]",
    "f1120s_entity_name":
        _P1 + "Date_Name_ReadOrder[0].f1_4[0]",
    "f1120s_entity_street":
        _P1 + "Date_Name_ReadOrder[0].f1_5[0]",
    "f1120s_entity_city":
        _P1 + "Date_Name_ReadOrder[0].f1_7[0]",
    "f1120s_entity_state":
        _P1 + "Date_Name_ReadOrder[0].f1_8[0]",
    "f1120s_entity_zip":
        _P1 + "Date_Name_ReadOrder[0].f1_10[0]",
    "f1120s_entity_ein":               _P1 + "f1_13[0]",
    "f1120s_entity_date_incorporated": _P1 + "f1_14[0]",
    "f1120s_entity_total_assets":      _P1 + "f1_15[0]",
    "f1120s_entity_shareholder_count": _P1 + "f1_16[0]",
}
_ENTITY_HEADER_BY_YEAR: dict[int, dict[str, str]] = {
    2021: _ENTITY_HEADER_2021_2024, 2022: _ENTITY_HEADER_2021_2024,
    2023: _ENTITY_HEADER_2021_2024, 2024: _ENTITY_HEADER_2021_2024,
    2025: _ENTITY_HEADER_2025,
}
