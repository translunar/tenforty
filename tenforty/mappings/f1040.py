from typing import NamedTuple

from tenforty.mappings.registry import FormMapping


# Form 8949 XLS row slots: each subsection box gets 11 lot rows on its sheet.
# The input columns (AJ=description, AK=date_acquired, etc.) are the same in
# both years; only the row_base and checkbox_cell differ by year.
#
# 2025 layout: ST lot rows start at 41, LT lot rows start at 91.
# 2024 layout: ST lot rows start at 35, LT lot rows start at 88.
#   (The 2024 workbook has more physical lot rows — 20 ST, 28 LT — but we
#   only need 11 rows for the parity battery, which uses at most 1 lot.)
#
# Boxes C/F ("no 1099-B received") are out of scope — Form1099B implies a
# 1099-B was received.
_F8949_LOT_ROWS = 11
_F8949_LOT_COLS = {
    "description":       "AJ",
    "date_acquired":     "AK",
    "date_sold":         "AL",
    "proceeds":          "AM",
    "basis":             "AN",
    "adjustment_code":   "AO",
    "adjustment_amount": "AP",
}


class _F8949BoxSlot(NamedTuple):
    letter: str
    sheet: str
    row_base: int        # first lot data row for this box's section
    checkbox_cell: str   # per-box "X" gate read by Sch. D rollup formulas


# 2025: ST Part I lot rows start at 41, LT Part II lot rows start at 91.
# LT checkboxes (Box D/E) are at C75/C77.
_F8949_BOX_SLOTS_2025: tuple[_F8949BoxSlot, ...] = (
    _F8949BoxSlot("a", "8949A", 41, "C25"),  # short-term, basis reported
    _F8949BoxSlot("b", "8949B", 41, "C27"),  # short-term, basis not reported
    _F8949BoxSlot("d", "8949A", 91, "C75"),  # long-term,  basis reported
    _F8949BoxSlot("e", "8949B", 91, "C77"),  # long-term,  basis not reported
)

# 2024: ST Part I lot rows start at 35, LT Part II lot rows start at 88.
# LT checkboxes (Box D/E) are at C78/C80 in the 2024 workbook layout.
_F8949_BOX_SLOTS_2024: tuple[_F8949BoxSlot, ...] = (
    _F8949BoxSlot("a", "8949A", 35, "C25"),  # short-term, basis reported
    _F8949BoxSlot("b", "8949B", 35, "C27"),  # short-term, basis not reported
    _F8949BoxSlot("d", "8949A", 88, "C78"),  # long-term,  basis reported
    _F8949BoxSlot("e", "8949B", 88, "C80"),  # long-term,  basis not reported
)

# Backward-compatible alias (used by existing callers that don't pass a year).
_F8949_BOX_SLOTS = _F8949_BOX_SLOTS_2025


def _f8949_box_inputs(slot: _F8949BoxSlot) -> dict[str, str]:
    out: dict[str, str] = {}
    out[f"f8949_box_{slot.letter}_checkbox"] = slot.checkbox_cell
    for i in range(_F8949_LOT_ROWS):
        idx = i + 1
        row = slot.row_base + i
        for field, col in _F8949_LOT_COLS.items():
            out[f"f8949_box_{slot.letter}_lot_{idx}_{field}"] = f"{col}{row}"
    return out


def _f8949_box_sheet_map(slot: _F8949BoxSlot) -> dict[str, str]:
    out: dict[str, str] = {}
    out[f"f8949_box_{slot.letter}_checkbox"] = slot.sheet
    for i in range(_F8949_LOT_ROWS):
        idx = i + 1
        for field in _F8949_LOT_COLS:
            out[f"f8949_box_{slot.letter}_lot_{idx}_{field}"] = slot.sheet
    return out


def _f8949_all_inputs(slots: tuple = _F8949_BOX_SLOTS_2025) -> dict[str, str]:
    out: dict[str, str] = {}
    for slot in slots:
        out |= _f8949_box_inputs(slot)
    return out


def _f8949_all_sheet_map(slots: tuple = _F8949_BOX_SLOTS_2025) -> dict[str, str]:
    out: dict[str, str] = {}
    for slot in slots:
        out |= _f8949_box_sheet_map(slot)
    return out


class F1040(FormMapping):
    """Mapping for the entire federal 1040 workbook (all sheets).

    Input keys use the convention: {form}_{field}_{index}.
    - W-2 fields: w2_{field}_{employer_number} (1-6 supported by XLS)
    - 1099 fields: {form_type}_{field}_{payer_number}
    - Schedule E: sche_{field}_{property_letter}

    Values are either named ranges (e.g., "File_Single") or direct cell
    references on a specific sheet (e.g., "C3" on the W-2s sheet). Named
    ranges are resolved by openpyxl automatically. Direct cell references
    require the sheet name prefix in the engine (stored in SHEET_MAP).
    """

    SHEET_MAP: dict[int, dict[str, str]] = {
        2024: {
            "w2_wages_1": "W-2s",
            "w2_fed_withheld_1": "W-2s",
            "w2_ss_wages_1": "W-2s",
            "w2_ss_withheld_1": "W-2s",
            "w2_medicare_wages_1": "W-2s",
            "w2_medicare_withheld_1": "W-2s",
            "w2_state_wages_1": "W-2s",
            "w2_state_withheld_1": "W-2s",
            "interest_1": "1099-INT",
            "ordinary_dividends_1": "1099-DIV",
            "qualified_dividends_1": "1099-DIV",
            "capital_gain_distributions_1": "1099-DIV",
            "sche_rents_a": "Sch. E",
            "sche_property_type_a": "Sch. E",
            "sche_fair_rental_days_a": "Sch. E",
            "sche_personal_use_days_a": "Sch. E",
            "sche_advertising_a": "Sch. E",
            "sche_auto_and_travel_a": "Sch. E",
            "sche_cleaning_and_maintenance_a": "Sch. E",
            "sche_commissions_a": "Sch. E",
            "sche_insurance_a": "Sch. E",
            "sche_legal_and_professional_fees_a": "Sch. E",
            "sche_management_fees_a": "Sch. E",
            "sche_mortgage_interest_a": "Sch. E",
            "sche_other_interest_a": "Sch. E",
            "sche_repairs_a": "Sch. E",
            "sche_supplies_a": "Sch. E",
            "sche_taxes_a": "Sch. E",
            "sche_utilities_a": "Sch. E",
            "sche_depreciation_a": "Sch. E",
            "sche_other_expenses_a": "Sch. E",
            "mortgage_interest": "Sch. A",
            "property_tax": "Sch. A",
            "k1_a_entity_name": "Sch. E",
            "k1_a_entity_type_s_corp": "Sch. E",
            "k1_a_entity_type_partnership": "Sch. E",
            "k1_a_entity_ein": "Sch. E",
            "k1_b_entity_name": "Sch. E",
            "k1_b_entity_type_s_corp": "Sch. E",
            "k1_b_entity_type_partnership": "Sch. E",
            "k1_b_entity_ein": "Sch. E",
            "k1_c_entity_name": "Sch. E",
            "k1_c_entity_type_s_corp": "Sch. E",
            "k1_c_entity_type_partnership": "Sch. E",
            "k1_c_entity_ein": "Sch. E",
            "k1_d_entity_name": "Sch. E",
            "k1_d_entity_type_s_corp": "Sch. E",
            "k1_d_entity_type_partnership": "Sch. E",
            "k1_d_entity_ein": "Sch. E",
            "k1_a_passive_loss": "Sch. E",
            "k1_a_passive_income": "Sch. E",
            "k1_a_nonpassive_loss": "Sch. E",
            "k1_a_nonpassive_income": "Sch. E",
            "k1_b_passive_loss": "Sch. E",
            "k1_b_passive_income": "Sch. E",
            "k1_b_nonpassive_loss": "Sch. E",
            "k1_b_nonpassive_income": "Sch. E",
            "k1_c_passive_loss": "Sch. E",
            "k1_c_passive_income": "Sch. E",
            "k1_c_nonpassive_loss": "Sch. E",
            "k1_c_nonpassive_income": "Sch. E",
            "k1_d_passive_loss": "Sch. E",
            "k1_d_passive_income": "Sch. E",
            "k1_d_nonpassive_loss": "Sch. E",
            "k1_d_nonpassive_income": "Sch. E",
            "k1_a_qbi_amount": "8995",
            "k1_b_qbi_amount": "8995",
            "k1_c_qbi_amount": "8995",
            "k1_d_qbi_amount": "8995",
            # SALT refund tax-benefit-rule worksheet (same sheet name in 2024).
            "prior_year_itemized_deduction": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_single": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfj": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfs": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_hoh": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_qw": "Sch 1, Line 1 (SALT)",
            # Form 1099-G
            "g_unemployment_1": "1099-G",
            "g_state_refund_1": "1099-G",
            "g_fed_withheld_1": "1099-G",
            "g_rtaa_1": "1099-G",
            "g_taxable_grants_1": "1099-G",
            "g_ag_1": "1099-G",
            "g_market_gain_1": "1099-G",
            "g_unemployment_2": "1099-G",
            "g_state_refund_2": "1099-G",
            "g_fed_withheld_2": "1099-G",
            "g_rtaa_2": "1099-G",
            "g_taxable_grants_2": "1099-G",
            "g_ag_2": "1099-G",
            "g_market_gain_2": "1099-G",
            "g_unemployment_3": "1099-G",
            "g_state_refund_3": "1099-G",
            "g_fed_withheld_3": "1099-G",
            "g_rtaa_3": "1099-G",
            "g_taxable_grants_3": "1099-G",
            "g_ag_3": "1099-G",
            "g_market_gain_3": "1099-G",
            "g_unemployment_4": "1099-G",
            "g_state_refund_4": "1099-G",
            "g_fed_withheld_4": "1099-G",
            "g_rtaa_4": "1099-G",
            "g_taxable_grants_4": "1099-G",
            "g_ag_4": "1099-G",
            "g_market_gain_4": "1099-G",
            "g_unemployment_5": "1099-G",
            "g_state_refund_5": "1099-G",
            "g_fed_withheld_5": "1099-G",
            "g_rtaa_5": "1099-G",
            "g_taxable_grants_5": "1099-G",
            "g_ag_5": "1099-G",
            "g_market_gain_5": "1099-G",
            "g_unemployment_6": "1099-G",
            "g_state_refund_6": "1099-G",
            "g_fed_withheld_6": "1099-G",
            "g_rtaa_6": "1099-G",
            "g_taxable_grants_6": "1099-G",
            "g_ag_6": "1099-G",
            "g_market_gain_6": "1099-G",
            # Schedule 1 line 4 (other gains/losses): 2024 uses the named
            # range OtherGainsLosses = 'Sch. 1'!AL20, so no SHEET_MAP entry
            # needed (named range resolves the sheet automatically).
            # Schedule A line 5e SALT capped: direct cell ref N29 on Sch. A.
            "sch_a_line_5e_salt_capped": "Sch. A",
            # Form 8582 line 11: direct cell ref AE43 on 8582.
            "f8582_line_11_oracle": "8582",
            # Schedule 1 line 26: direct cell ref AC98 on Sch. 1.
            "sch_1_line_26": "Sch. 1",
            # Form 8582 Part IV input cells: no named ranges in 2024; all are
            # direct cell refs on the '8582' sheet.
            "sche_8582_net_income": "8582",
            "sche_8582_net_loss": "8582",
            "k1_a_8582_net_income": "8582",
            "k1_a_8582_net_loss": "8582",
            "k1_a_8582_prior_year_loss": "8582",
            "k1_b_8582_net_income": "8582",
            "k1_b_8582_net_loss": "8582",
            "k1_b_8582_prior_year_loss": "8582",
            "k1_c_8582_net_income": "8582",
            "k1_c_8582_net_loss": "8582",
            "k1_c_8582_prior_year_loss": "8582",
            "k1_d_8582_net_income": "8582",
            "k1_d_8582_net_loss": "8582",
            "k1_d_8582_prior_year_loss": "8582",
            **_f8949_all_sheet_map(_F8949_BOX_SLOTS_2024),
        },
        2025: {
            "w2_wages_1": "W-2s",
            "w2_fed_withheld_1": "W-2s",
            "w2_ss_wages_1": "W-2s",
            "w2_ss_withheld_1": "W-2s",
            "w2_medicare_wages_1": "W-2s",
            "w2_medicare_withheld_1": "W-2s",
            "w2_state_wages_1": "W-2s",
            "w2_state_withheld_1": "W-2s",
            "interest_1": "1099-INT",
            "ordinary_dividends_1": "1099-DIV",
            "qualified_dividends_1": "1099-DIV",
            "capital_gain_distributions_1": "1099-DIV",
            "sche_rents_a": "Sch. E",
            "sche_property_type_a": "Sch. E",
            "sche_fair_rental_days_a": "Sch. E",
            "sche_personal_use_days_a": "Sch. E",
            "sche_advertising_a": "Sch. E",
            "sche_auto_and_travel_a": "Sch. E",
            "sche_cleaning_and_maintenance_a": "Sch. E",
            "sche_commissions_a": "Sch. E",
            "sche_insurance_a": "Sch. E",
            "sche_legal_and_professional_fees_a": "Sch. E",
            "sche_management_fees_a": "Sch. E",
            "sche_mortgage_interest_a": "Sch. E",
            "sche_other_interest_a": "Sch. E",
            "sche_repairs_a": "Sch. E",
            "sche_supplies_a": "Sch. E",
            "sche_taxes_a": "Sch. E",
            "sche_utilities_a": "Sch. E",
            "sche_depreciation_a": "Sch. E",
            "sche_other_expenses_a": "Sch. E",
            "mortgage_interest": "Sch. A",
            "property_tax": "Sch. A",
            # Sch. E Part II (K-1 pass-through entities). Per-row cells for
            # name (col C), P/S entity-type box (col O), and EIN (col Y) at
            # rows 80..83 for K-1 letters A..D. Income/loss column mappings
            # are intentionally deferred: the form's Part II table aggregates
            # K-1 income into four columns (passive/nonpassive * income/loss)
            # that require per-K-1 routing based on material_participation
            # and box type; aggregation is deferred until that routing is implemented.
            "k1_a_entity_name": "Sch. E",
            "k1_a_entity_type_s_corp": "Sch. E",
            "k1_a_entity_type_partnership": "Sch. E",
            "k1_a_entity_ein": "Sch. E",
            "k1_b_entity_name": "Sch. E",
            "k1_b_entity_type_s_corp": "Sch. E",
            "k1_b_entity_type_partnership": "Sch. E",
            "k1_b_entity_ein": "Sch. E",
            "k1_c_entity_name": "Sch. E",
            "k1_c_entity_type_s_corp": "Sch. E",
            "k1_c_entity_type_partnership": "Sch. E",
            "k1_c_entity_ein": "Sch. E",
            "k1_d_entity_name": "Sch. E",
            "k1_d_entity_type_s_corp": "Sch. E",
            "k1_d_entity_type_partnership": "Sch. E",
            "k1_d_entity_ein": "Sch. E",
            # Sch. E Part II K-1 income/loss per-row cells (rows 88..91 = A..D).
            # Passive loss (g) = col C, passive income (h) = col K,
            # nonpassive loss (i) = col S, nonpassive income (k) = col AH.
            "k1_a_passive_loss": "Sch. E",
            "k1_a_passive_income": "Sch. E",
            "k1_a_nonpassive_loss": "Sch. E",
            "k1_a_nonpassive_income": "Sch. E",
            "k1_b_passive_loss": "Sch. E",
            "k1_b_passive_income": "Sch. E",
            "k1_b_nonpassive_loss": "Sch. E",
            "k1_b_nonpassive_income": "Sch. E",
            "k1_c_passive_loss": "Sch. E",
            "k1_c_passive_income": "Sch. E",
            "k1_c_nonpassive_loss": "Sch. E",
            "k1_c_nonpassive_income": "Sch. E",
            "k1_d_passive_loss": "Sch. E",
            "k1_d_passive_income": "Sch. E",
            "k1_d_nonpassive_loss": "Sch. E",
            "k1_d_nonpassive_income": "Sch. E",
            # Form 8995 K-1 QBI input cells. Each K-1's QBI amount is entered
            # in column AB at rows 14/16/18/20 (lines i–iv). These have no
            # named range; the sheet name is in SHEET_MAP.
            "k1_a_qbi_amount": "8995",
            "k1_b_qbi_amount": "8995",
            "k1_c_qbi_amount": "8995",
            "k1_d_qbi_amount": "8995",
            # SALT refund tax-benefit-rule worksheet: prior-year itemized
            # deduction amount goes in cell J45 on the SALT worksheet.
            # The SALT worksheet has its own filing-status checkboxes
            # (P6/P8/P10/P12/P14) independent of the main 1040 sheet.
            "prior_year_itemized_deduction": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_single": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfj": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_mfs": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_hoh": "Sch 1, Line 1 (SALT)",
            "salt_filing_status_qw": "Sch 1, Line 1 (SALT)",
            # Form 1099-G (filer's copy — 6 payers supported in cols D..I).
            "g_unemployment_1": "1099-G",
            "g_state_refund_1": "1099-G",
            "g_fed_withheld_1": "1099-G",
            "g_rtaa_1": "1099-G",
            "g_taxable_grants_1": "1099-G",
            "g_ag_1": "1099-G",
            "g_market_gain_1": "1099-G",
            "g_unemployment_2": "1099-G",
            "g_state_refund_2": "1099-G",
            "g_fed_withheld_2": "1099-G",
            "g_rtaa_2": "1099-G",
            "g_taxable_grants_2": "1099-G",
            "g_ag_2": "1099-G",
            "g_market_gain_2": "1099-G",
            "g_unemployment_3": "1099-G",
            "g_state_refund_3": "1099-G",
            "g_fed_withheld_3": "1099-G",
            "g_rtaa_3": "1099-G",
            "g_taxable_grants_3": "1099-G",
            "g_ag_3": "1099-G",
            "g_market_gain_3": "1099-G",
            "g_unemployment_4": "1099-G",
            "g_state_refund_4": "1099-G",
            "g_fed_withheld_4": "1099-G",
            "g_rtaa_4": "1099-G",
            "g_taxable_grants_4": "1099-G",
            "g_ag_4": "1099-G",
            "g_market_gain_4": "1099-G",
            "g_unemployment_5": "1099-G",
            "g_state_refund_5": "1099-G",
            "g_fed_withheld_5": "1099-G",
            "g_rtaa_5": "1099-G",
            "g_taxable_grants_5": "1099-G",
            "g_ag_5": "1099-G",
            "g_market_gain_5": "1099-G",
            "g_unemployment_6": "1099-G",
            "g_state_refund_6": "1099-G",
            "g_fed_withheld_6": "1099-G",
            "g_rtaa_6": "1099-G",
            "g_taxable_grants_6": "1099-G",
            "g_ag_6": "1099-G",
            "g_market_gain_6": "1099-G",
            # Schedule 1 line 4 (other gains/losses): direct cell ref
            # because the value isn't named in the workbook. Cell AJ19
            # holds ROUND(AC19,0); line 10's SUM references the same
            # rounded expression inline.
            "sch_1_line_4_other_gains": "Sch. 1",
            **_f8949_all_sheet_map(),
        },
    }

    INPUTS: dict[int, dict[str, str]] = {
        2024: {
            "filing_status_single": "File_Single",
            "filing_status_married_jointly": "File_Marr_Joint",
            "filing_status_married_separately": "File_Marr_Sep",
            "filing_status_head_of_household": "File_Head",
            "filing_status_qualifying_widow": "File_Qual_Widow",
            "birthdate_month": "YourBirthMonth",
            "birthdate_day": "YourBirthDay",
            "birthdate_year": "YourBirthYear",
            "w2_wages_1": "C3",
            "w2_fed_withheld_1": "C4",
            "w2_ss_wages_1": "C5",
            "w2_ss_withheld_1": "C6",
            "w2_medicare_wages_1": "C7",
            "w2_medicare_withheld_1": "C8",
            # In 2024 the W-2s sheet has 6 fewer rows before state fields;
            # state wages (box 16) = row 22, state income tax (box 17) = row 23.
            "w2_state_wages_1": "C22",
            "w2_state_withheld_1": "C23",
            "interest_1": "D6",
            "ordinary_dividends_1": "D6",
            "qualified_dividends_1": "D7",
            "capital_gain_distributions_1": "D8",
            "mortgage_interest": "T37",
            "property_tax": "N25",
            "sche_property_type_a": "D21",
            "sche_fair_rental_days_a": "AA21",
            "sche_personal_use_days_a": "AF21",
            "sche_rents_a": "V30",
            "sche_advertising_a": "V33",
            "sche_auto_and_travel_a": "V34",
            "sche_cleaning_and_maintenance_a": "V35",
            "sche_commissions_a": "V36",
            "sche_insurance_a": "V37",
            "sche_legal_and_professional_fees_a": "V38",
            "sche_management_fees_a": "V39",
            "sche_mortgage_interest_a": "V40",
            "sche_other_interest_a": "V41",
            "sche_repairs_a": "V42",
            "sche_supplies_a": "V43",
            "sche_taxes_a": "V44",
            "sche_utilities_a": "V45",
            "sche_depreciation_a": "V46",
            "sche_other_expenses_a": "V47",
            # Sch. E Part II K-1 per-row cells (rows 80..83 = A..D).
            "k1_a_entity_name": "C80",
            "k1_a_entity_type_s_corp": "O80",
            "k1_a_entity_type_partnership": "O80",
            "k1_a_entity_ein": "Y80",
            "k1_b_entity_name": "C81",
            "k1_b_entity_type_s_corp": "O81",
            "k1_b_entity_type_partnership": "O81",
            "k1_b_entity_ein": "Y81",
            "k1_c_entity_name": "C82",
            "k1_c_entity_type_s_corp": "O82",
            "k1_c_entity_type_partnership": "O82",
            "k1_c_entity_ein": "Y82",
            "k1_d_entity_name": "C83",
            "k1_d_entity_type_s_corp": "O83",
            "k1_d_entity_type_partnership": "O83",
            "k1_d_entity_ein": "Y83",
            # Sch. E Part II K-1 income/loss cells (rows 88..91 = A..D).
            "k1_a_passive_loss": "C88",
            "k1_a_passive_income": "K88",
            "k1_a_nonpassive_loss": "S88",
            "k1_a_nonpassive_income": "AH88",
            "k1_b_passive_loss": "C89",
            "k1_b_passive_income": "K89",
            "k1_b_nonpassive_loss": "S89",
            "k1_b_nonpassive_income": "AH89",
            "k1_c_passive_loss": "C90",
            "k1_c_passive_income": "K90",
            "k1_c_nonpassive_loss": "S90",
            "k1_c_nonpassive_income": "AH90",
            "k1_d_passive_loss": "C91",
            "k1_d_passive_income": "K91",
            "k1_d_nonpassive_loss": "S91",
            "k1_d_nonpassive_income": "AH91",
            # Form 8995 K-1 QBI input cells (column AB, lines i–iv at rows
            # 14/16/18/20). Same layout as 2025.
            "k1_a_qbi_amount": "AB14",
            "k1_b_qbi_amount": "AB16",
            "k1_c_qbi_amount": "AB18",
            "k1_d_qbi_amount": "AB20",
            # SALT refund tax-benefit-rule worksheet. In 2024 the prior-year
            # itemized deduction input is at J51 (2025 moved it to J45 when
            # the worksheet gained new lines 5–7 above it).
            "prior_year_itemized_deduction": "J51",
            "salt_filing_status_single": "P6",
            "salt_filing_status_mfj": "P8",
            "salt_filing_status_mfs": "P10",
            "salt_filing_status_hoh": "P12",
            "salt_filing_status_qw": "P14",
            # Form 8582 Part IV input cells. The 2024 workbook uses the same
            # cell addresses (N49/R49/V49..V53) as 2025 but lacks named ranges
            # for them; direct cell refs are used here.
            "sche_8582_net_income": "N49",
            "sche_8582_net_loss": "R49",
            "k1_a_8582_net_income": "N50",
            "k1_a_8582_net_loss": "R50",
            "k1_a_8582_prior_year_loss": "V50",
            "k1_b_8582_net_income": "N51",
            "k1_b_8582_net_loss": "R51",
            "k1_b_8582_prior_year_loss": "V51",
            "k1_c_8582_net_income": "N52",
            "k1_c_8582_net_loss": "R52",
            "k1_c_8582_prior_year_loss": "V52",
            "k1_d_8582_net_income": "N53",
            "k1_d_8582_net_loss": "R53",
            "k1_d_8582_prior_year_loss": "V53",
            # Form 1099-G filer cells (same layout as 2025).
            "g_unemployment_1": "D6",
            "g_state_refund_1": "D7",
            "g_fed_withheld_1": "D9",
            "g_rtaa_1": "D10",
            "g_taxable_grants_1": "D11",
            "g_ag_1": "D12",
            "g_market_gain_1": "D15",
            "g_unemployment_2": "E6",
            "g_state_refund_2": "E7",
            "g_fed_withheld_2": "E9",
            "g_rtaa_2": "E10",
            "g_taxable_grants_2": "E11",
            "g_ag_2": "E12",
            "g_market_gain_2": "E15",
            "g_unemployment_3": "F6",
            "g_state_refund_3": "F7",
            "g_fed_withheld_3": "F9",
            "g_rtaa_3": "F10",
            "g_taxable_grants_3": "F11",
            "g_ag_3": "F12",
            "g_market_gain_3": "F15",
            "g_unemployment_4": "G6",
            "g_state_refund_4": "G7",
            "g_fed_withheld_4": "G9",
            "g_rtaa_4": "G10",
            "g_taxable_grants_4": "G11",
            "g_ag_4": "G12",
            "g_market_gain_4": "G15",
            "g_unemployment_5": "H6",
            "g_state_refund_5": "H7",
            "g_fed_withheld_5": "H9",
            "g_rtaa_5": "H10",
            "g_taxable_grants_5": "H11",
            "g_ag_5": "H12",
            "g_market_gain_5": "H15",
            "g_unemployment_6": "I6",
            "g_state_refund_6": "I7",
            "g_fed_withheld_6": "I9",
            "g_rtaa_6": "I10",
            "g_taxable_grants_6": "I11",
            "g_ag_6": "I12",
            "g_market_gain_6": "I15",
            **_f8949_all_inputs(_F8949_BOX_SLOTS_2024),
        },
        2025: {
            "filing_status_single": "File_Single",
            "filing_status_married_jointly": "File_Marr_Joint",
            "filing_status_married_separately": "File_Marr_Sep",
            "filing_status_head_of_household": "File_Head",
            "filing_status_qualifying_widow": "File_Qual_Widow",
            "birthdate_month": "YourBirthMonth",
            "birthdate_day": "YourBirthDay",
            "birthdate_year": "YourBirthYear",
            "w2_wages_1": "C3",
            "w2_fed_withheld_1": "C4",
            "w2_ss_wages_1": "C5",
            "w2_ss_withheld_1": "C6",
            "w2_medicare_wages_1": "C7",
            "w2_medicare_withheld_1": "C8",
            "w2_state_wages_1": "C28",
            "w2_state_withheld_1": "C29",
            "interest_1": "D6",
            "ordinary_dividends_1": "D6",
            "qualified_dividends_1": "D7",
            "capital_gain_distributions_1": "D8",
            "mortgage_interest": "T37",
            "property_tax": "N25",
            "sche_property_type_a": "D21",
            "sche_fair_rental_days_a": "AA21",
            "sche_personal_use_days_a": "AF21",
            "sche_rents_a": "V30",
            "sche_advertising_a": "V33",
            "sche_auto_and_travel_a": "V34",
            "sche_cleaning_and_maintenance_a": "V35",
            "sche_commissions_a": "V36",
            "sche_insurance_a": "V37",
            "sche_legal_and_professional_fees_a": "V38",
            "sche_management_fees_a": "V39",
            "sche_mortgage_interest_a": "V40",
            "sche_other_interest_a": "V41",
            "sche_repairs_a": "V42",
            "sche_supplies_a": "V43",
            "sche_taxes_a": "V44",
            "sche_utilities_a": "V45",
            "sche_depreciation_a": "V46",
            "sche_other_expenses_a": "V47",
            # Sch. E Part II K-1 per-row cells (rows 80..83 = A..D).
            "k1_a_entity_name": "C80",
            "k1_a_entity_type_s_corp": "O80",
            "k1_a_entity_type_partnership": "O80",
            "k1_a_entity_ein": "Y80",
            "k1_b_entity_name": "C81",
            "k1_b_entity_type_s_corp": "O81",
            "k1_b_entity_type_partnership": "O81",
            "k1_b_entity_ein": "Y81",
            "k1_c_entity_name": "C82",
            "k1_c_entity_type_s_corp": "O82",
            "k1_c_entity_type_partnership": "O82",
            "k1_c_entity_ein": "Y82",
            "k1_d_entity_name": "C83",
            "k1_d_entity_type_s_corp": "O83",
            "k1_d_entity_type_partnership": "O83",
            "k1_d_entity_ein": "Y83",
            # Sch. E Part II K-1 income/loss cells (rows 88..91 = A..D).
            # (g) passive loss = col C, (h) passive income = col K,
            # (i) nonpassive loss = col S, (k) nonpassive income = col AH.
            "k1_a_passive_loss": "C88",
            "k1_a_passive_income": "K88",
            "k1_a_nonpassive_loss": "S88",
            "k1_a_nonpassive_income": "AH88",
            "k1_b_passive_loss": "C89",
            "k1_b_passive_income": "K89",
            "k1_b_nonpassive_loss": "S89",
            "k1_b_nonpassive_income": "AH89",
            "k1_c_passive_loss": "C90",
            "k1_c_passive_income": "K90",
            "k1_c_nonpassive_loss": "S90",
            "k1_c_nonpassive_income": "AH90",
            "k1_d_passive_loss": "C91",
            "k1_d_passive_income": "K91",
            "k1_d_nonpassive_loss": "S91",
            "k1_d_nonpassive_income": "AH91",
            # Form 8995 K-1 QBI input cells (column AB, lines i–iv at rows
            # 14/16/18/20). No named range; resolved via SHEET_MAP → "8995".
            "k1_a_qbi_amount": "AB14",
            "k1_b_qbi_amount": "AB16",
            "k1_c_qbi_amount": "AB18",
            "k1_d_qbi_amount": "AB20",
            # SALT refund tax-benefit-rule (Sch 1, Line 1 worksheet).
            # J45 = prior year total itemized deductions (line 4).
            # P6/P8/P10/P12/P14 = filing status checkboxes (independent
            # of the main 1040 named ranges).
            "prior_year_itemized_deduction": "J45",
            "salt_filing_status_single": "P6",
            "salt_filing_status_mfj": "P8",
            "salt_filing_status_mfs": "P10",
            "salt_filing_status_hoh": "P12",
            "salt_filing_status_qw": "P14",
            # Form 8582 Part IV input cells (rental real estate activities).
            # Slot A = Sch E Part I rental (row 49); slots B-E = K-1 a-d
            # rental RE (rows 50-53). Income (col N) and loss (col R) are
            # separate positive-amount entries; prior-year carryforward is
            # col V. Named ranges resolve to '8582' sheet without SHEET_MAP.
            "sche_8582_net_income": "F8582_P4A_NetIncome",
            "sche_8582_net_loss": "F8582_P4A_NetLoss",
            "k1_a_8582_net_income": "F8582_P4B_NetIncome",
            "k1_a_8582_net_loss": "F8582_P4B_NetLoss",
            "k1_a_8582_prior_year_loss": "F8582_P4B_PriorLoss",
            "k1_b_8582_net_income": "F8582_P4C_NetIncome",
            "k1_b_8582_net_loss": "F8582_P4C_NetLoss",
            "k1_b_8582_prior_year_loss": "F8582_P4C_PriorLoss",
            "k1_c_8582_net_income": "F8582_P4D_NetIncome",
            "k1_c_8582_net_loss": "F8582_P4D_NetLoss",
            "k1_c_8582_prior_year_loss": "F8582_P4D_PriorLoss",
            "k1_d_8582_net_income": "F8582_P4E_NetIncome",
            "k1_d_8582_net_loss": "F8582_P4E_NetLoss",
            "k1_d_8582_prior_year_loss": "F8582_P4E_PriorLoss",
            # Form 1099-G filer cells (payer N in column {D,E,F,G,H,I}[N-1]).
            # Row 6: unemployment compensation (box 1)
            # Row 7: state or local income tax refund (box 2)
            # Row 9: federal income tax withheld (box 4)
            # Row 10: RTAA payments (box 5)
            # Row 11: taxable grants (box 6)
            # Row 12: agriculture payments (box 7a, disaster)
            # Row 15: market gain (box 9)
            "g_unemployment_1": "D6",
            "g_state_refund_1": "D7",
            "g_fed_withheld_1": "D9",
            "g_rtaa_1": "D10",
            "g_taxable_grants_1": "D11",
            "g_ag_1": "D12",
            "g_market_gain_1": "D15",
            "g_unemployment_2": "E6",
            "g_state_refund_2": "E7",
            "g_fed_withheld_2": "E9",
            "g_rtaa_2": "E10",
            "g_taxable_grants_2": "E11",
            "g_ag_2": "E12",
            "g_market_gain_2": "E15",
            "g_unemployment_3": "F6",
            "g_state_refund_3": "F7",
            "g_fed_withheld_3": "F9",
            "g_rtaa_3": "F10",
            "g_taxable_grants_3": "F11",
            "g_ag_3": "F12",
            "g_market_gain_3": "F15",
            "g_unemployment_4": "G6",
            "g_state_refund_4": "G7",
            "g_fed_withheld_4": "G9",
            "g_rtaa_4": "G10",
            "g_taxable_grants_4": "G11",
            "g_ag_4": "G12",
            "g_market_gain_4": "G15",
            "g_unemployment_5": "H6",
            "g_state_refund_5": "H7",
            "g_fed_withheld_5": "H9",
            "g_rtaa_5": "H10",
            "g_taxable_grants_5": "H11",
            "g_ag_5": "H12",
            "g_market_gain_5": "H15",
            "g_unemployment_6": "I6",
            "g_state_refund_6": "I7",
            "g_fed_withheld_6": "I9",
            "g_rtaa_6": "I10",
            "g_taxable_grants_6": "I11",
            "g_ag_6": "I12",
            "g_market_gain_6": "I15",
            **_f8949_all_inputs(),
        },
    }

    OUTPUTS: dict[int, dict[str, str]] = {
        2024: {
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "Standard",
            "taxable_income": "Taxable_Inc",
            "total_tax": "Tax",
            "federal_withheld": "W2_FedTaxWH",
            "additional_medicare_withheld": "F8959_WH",
            "f8959_tax_total": "F8959_Tax",
            "f8959_required": "F8959_Reqd",
            "overpaid": "Overpaid",
            "sche_line26": "SchE1_Line26",
            "sch_1_line_10": "Additional_Income",
            # Schedule 1 line 26 (Total Adjustments): 2024 uses the named
            # range AdjustToIncome = 'Sch. 1'!AC98. SHEET_MAP routes the
            # engine to 'Sch. 1' for the fallback read path.
            "sch_1_line_26": "AC98",
            "sch_1_line_1_taxable_refunds": "Sch1_Line1",
            "sch_1_line_3_business_income": "BusinessIncomeLoss",
            # Line 4 (other gains/losses): 2024 has the named range
            # OtherGainsLosses = 'Sch. 1'!AL20 — the rounded display value,
            # equivalent to 2025's direct ref AJ19.
            "sch_1_line_4_other_gains": "OtherGainsLosses",
            "sch_1_line_5_rental_re_royalty": "SchE_IncomeLoss",
            "sch_1_line_6_farm_income": "FarmIncomeLoss",
            "sch_1_line_7_unemployment": "UnEmploymentComp",
            "sch_1_line_11_educator": "EducatorExpenses",
            "sch_1_line_13_hsa": "HSA_Deduct",
            "sch_1_line_15_se_tax": "SE_Deduct",
            "sch_1_line_17_se_health": "SEHealthInsDeduct",
            "sch_1_line_20_ira": "IRADeduct",
            "sch_1_line_21_student_loan_interest": "StudentLoanIntDeduct",
            "sche_line41": "SchE1_Line41",
            "schd_line16": "SchDLine16",
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
            "schedule_a_total": "Tot_Item_Deduct",
            # Schedule A line 5e (SALT capped): 2024 has no SALT_Limited named
            # range. Cell N29 on 'Sch. A' holds MIN(total SALT, $10k cap).
            # SHEET_MAP routes the engine to 'Sch. A'.
            "sch_a_line_5e_salt_capped": "N29",
            "magi": "ModAdjGrossInc",
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
            "f8995_line_15_oracle": "QBID",
            "net_capital_gain": "NetCapitalGain",
            "_qbi_deduction_1040": "QBID_1040",
            # Form 8582 line 11: 2024 has no F8582_Line11 named range. Cell
            # AE43 on '8582' holds the line 11 total (same formula as 2025,
            # same row — the named range was added in the 2025 workbook only).
            # SHEET_MAP routes the engine to '8582'.
            "f8582_line_11_oracle": "AE43",
            "f8949_box_a_total_proceeds":   "F8949ASTD",
            "f8949_box_a_total_basis":      "F8949ASTE",
            "f8949_box_a_total_adjustment": "F8949ASTG",
            "f8949_box_a_total_gain":       "F8949ASTH",
            "f8949_box_b_total_proceeds":   "F8949BSTD",
            "f8949_box_b_total_basis":      "F8949BSTE",
            "f8949_box_b_total_adjustment": "F8949BSTG",
            "f8949_box_b_total_gain":       "F8949BSTH",
            "f8949_box_d_total_proceeds":   "F8949ALTD",
            "f8949_box_d_total_basis":      "F8949ALTE",
            "f8949_box_d_total_adjustment": "F8949ALTG",
            "f8949_box_d_total_gain":       "F8949ALTH",
            "f8949_box_e_total_proceeds":   "F8949BLTD",
            "f8949_box_e_total_basis":      "F8949BLTE",
            "f8949_box_e_total_adjustment": "F8949BLTG",
            "f8949_box_e_total_gain":       "F8949BLTH",
        },
        2025: {
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "Standard",
            "taxable_income": "Taxable_Inc",
            "total_tax": "Tax",
            "federal_withheld": "W2_FedTaxWH",
            # Form 8959 Part III: Additional Medicare Tax withheld by employers
            # on wages exceeding the $200k/$250k threshold (IRC §3101(b)(2)).
            # Flows to 1040 line 25c via Form 8959.
            "additional_medicare_withheld": "F8959_WH",
            # Form 8959 line 18: total Additional Medicare Tax. Used as the
            # oracle cross-check target for forms.f8959.compute's native math.
            "f8959_tax_total": "F8959_Tax",
            # Oracle-authoritative gate for whether Form 8959 must be filed.
            # Preferred over the wage-threshold heuristic in the orchestrator
            # predicate so we don't emit a zero-valued form.
            "f8959_required": "F8959_Reqd",
            "overpaid": "Overpaid",
            "sche_line26": "SchE1_Line26",
            # Schedule 1 line 10 (Total Additional Income). Oracle cross-check
            # target for forms.sch_1.compute's native math.
            "sch_1_line_10": "Additional_Income",
            # Schedule 1 line 26 (Total Adjustments to Income). Oracle
            # cross-check target for forms.sch_1.compute's native math.
            "sch_1_line_26": "Sch1A_Deductions",
            # Schedule 1 Part I per-line breakdowns (XLS-sourced; named
            # ranges in the Sch. 1 sheet). These keys feed downstream
            # Sch CA kernel auto-derive and other state-return
            # consumers that need per-line granularity.
            "sch_1_line_1_taxable_refunds": "Sch1_Line1",
            "sch_1_line_3_business_income": "BusinessIncomeLoss",
            # Line 4 has no named range; direct cell ref to AJ19
            # (rounded display of AC19). SHEET_MAP routes to "Sch. 1".
            "sch_1_line_4_other_gains": "AJ19",
            "sch_1_line_5_rental_re_royalty": "SchE_IncomeLoss",
            "sch_1_line_6_farm_income": "FarmIncomeLoss",
            "sch_1_line_7_unemployment": "UnEmploymentComp",
            # Schedule 1 Part II per-line breakdowns (XLS-sourced;
            # named ranges in the Sch. 1 sheet).
            "sch_1_line_11_educator": "EducatorExpenses",
            "sch_1_line_13_hsa": "HSA_Deduct",
            "sch_1_line_15_se_tax": "SE_Deduct",
            "sch_1_line_17_se_health": "SEHealthInsDeduct",
            "sch_1_line_20_ira": "IRADeduct",
            "sch_1_line_21_student_loan_interest": "StudentLoanIntDeduct",
            "sche_line41": "SchE1_Line41",
            "schd_line16": "SchDLine16",
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
            "schedule_a_total": "Tot_Item_Deduct",
            # Schedule A line 5e (SALT capped). Oracle cross-check target for
            # forms.sch_a.compute's native OBBBA cap.
            "sch_a_line_5e_salt_capped": "SALT_Limited",
            # MAGI for phaseout math (IRC §164(b)(6) phaseout threshold).
            "magi": "ModAdjGrossInc",
            # --- Totals ---
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
            # --- Form 8995 oracle cross-check ---
            # Form 8995 line 15: Qualified Business Income Deduction.
            # Oracle authoritative output for cross-checking forms.f8995.compute.
            "f8995_line_15_oracle": "QBID",
            # Form 8995 line 12: net capital gain (qualified dividends +
            # net LTCG) as computed on the worksheet.
            "net_capital_gain": "NetCapitalGain",
            # QBI deduction as entered on 1040 line 13 (= QBID). Used in
            # f1040.compute to derive taxable_income_before_qbi_deduction
            # (no single named range exists for the pre-QBI figure).
            "_qbi_deduction_1040": "QBID_1040",
            # Form 8582 line 11: total losses allowed from all passive
            # activities. Oracle cross-check target for forms.f8582.compute.
            "f8582_line_11_oracle": "F8582_Line11",
            # Form 8949 per-subsection totals. Each physical sheet (8949A,
            # 8949B) carries one ST box (top-of-sheet checkbox = A or B) and
            # one LT box (mid-sheet checkbox = D or E) — ST sums Part I row 52,
            # LT sums Part II row 102. Suffixes: D=proceeds, E=basis,
            # G=adjustment, H=gain. Used as oracle cross-check targets for
            # forms.f8949.compute native math.
            "f8949_box_a_total_proceeds":   "F8949ASTD",
            "f8949_box_a_total_basis":      "F8949ASTE",
            "f8949_box_a_total_adjustment": "F8949ASTG",
            "f8949_box_a_total_gain":       "F8949ASTH",
            "f8949_box_b_total_proceeds":   "F8949BSTD",
            "f8949_box_b_total_basis":      "F8949BSTE",
            "f8949_box_b_total_adjustment": "F8949BSTG",
            "f8949_box_b_total_gain":       "F8949BSTH",
            "f8949_box_d_total_proceeds":   "F8949ALTD",
            "f8949_box_d_total_basis":      "F8949ALTE",
            "f8949_box_d_total_adjustment": "F8949ALTG",
            "f8949_box_d_total_gain":       "F8949ALTH",
            "f8949_box_e_total_proceeds":   "F8949BLTD",
            "f8949_box_e_total_basis":      "F8949BLTE",
            "f8949_box_e_total_adjustment": "F8949BLTG",
            "f8949_box_e_total_gain":       "F8949BLTH",
        },
    }


# --- Federal 2023 workbook wiring -------------------------------------------
# 2023 inherits the 2024 XLS cell/named-range mapping: the 2024 workbook carries
# the pre-2025 layout (the W-2 sheet's 6-fewer-rows-before-state-fields shift and
# the F8949 box slots at rows 35/88), which the TY2023 workbook from the same
# vendor lineage shares. Two families of per-year drift were found empirically
# (native-vs-oracle smoke + the full parity sweep) and are handled here:
#
# 1. Stray vendor data: the distributed workbook shipped with a hardcoded
#    -2,800 "amount of adjustment" at 8949A!AP115 (the last, otherwise-empty
#    row of the box-D long-term sum range Q88:Q115), which understated capital
#    gain by $2,800. Cleared in the committed workbook (surgical XML edit; no
#    formula/structure touched).
#
# 2. The 'Sch. A' sheet is shifted ONE COLUMN LEFT vs 2024 (verified: 2023 M29
#    holds 2024 N29's formula with every column -1 — R->Q, N->M, P->O; the
#    mortgage debt-limit cells and "Home mortgage interest" label move T->S;
#    property-tax reader O26='=ROUND(M25,0)' mirrors 2024 P26='=ROUND(N25,0)').
#    The named-range outputs (Standard/TotalDeductions/QBID) resolve by NAME so
#    they need no override, but the three Schedule A cell-ADDRESS references do:
#    mortgage_interest T37->S37 and property_tax N25->M25 (inputs), and the
#    sch_a_line_5e_salt_capped output N29->M29. The 'Sch 1, Line 1 (SALT)'
#    worksheet did NOT shift (O6/O8 still read P6/P8), so its filing-status
#    inputs are unchanged. With these three overrides the itemizer scenario
#    itemizes to 30,000 (line 5e capped at 10,000) and every scenario's line-5e
#    output reads 0 instead of None — native==oracle across the battery.
F1040.INPUTS[2023] = F1040.inherit(2024, {
    "mortgage_interest": "S37",   # 'Sch. A' col -1 (2024 T37)
    "property_tax": "M25",        # 'Sch. A' col -1 (2024 N25)
}, source="inputs")
F1040.OUTPUTS[2023] = F1040.inherit(2024, {
    "sch_a_line_5e_salt_capped": "M29",   # 'Sch. A' col -1 (2024 N29)
}, source="outputs")
F1040.SHEET_MAP[2023] = dict(F1040.SHEET_MAP[2024])

# 2022's workbook matches 2023's layout EXCEPT the 'Sch. A' sheet, which the
# vendor reorganized vs 2023. Only the three 'Sch. A' cell-ADDRESS references
# need overrides (the named-range outputs Standard/TotalDeductions/QBID resolve
# by name); each verified per-cell against spreadsheets/federal/{2022,2023}/1040.xlsx:
#  - property_tax input +1 row (2023 M25 -> 2022 M26): 2022 reader
#    O27='=ROUND(M26,0)' mirrors 2023 O26='=ROUND(M25,0)'.
#  - sch_a_line_5e_salt_capped output +1 row (2023 M29 -> 2022 M30): 2022
#    M30='=IF(Q30<>"",ROUND(Q30,0),MIN(M28,O22))' mirrors 2023 M29's MIN(M27,O21).
#  - mortgage_interest input: the mortgage debt-limit block shifted -2 rows, so
#    2023 S37 -> 2022 S35. The 2022 deduction reader M38='=MIN(S43,ROUND(S35,0))'
#    consumes S35 exactly as 2023 M37='=MIN(S42,ROUND(S37,0))' consumes S37; the
#    debt limits (2023 S35/S36=1M/500k) sit at 2022 S33/S34.
# The 'Sch 1, Line 1 (SALT)' worksheet and all other input sheets align with
# 2023 (spot-checked). The cell-drift smoke over the itemizer scenario confirms.
# The 2022 '8582' sheet's passive-activity property table is shifted +1 ROW vs
# 2023 (proven: the column-sum consumer moved from 2023 N54='=SUM(N49..N53)' to
# 2022 N55='=SUM(N50..N54)', so the five property rows N49-N53 became N50-N54).
# Two consequences: (a) the Schedule-E row's net-income/net-loss cells (2023
# N49/R49) are absorbed into the 2022 header merge N48:Q49 / R48:U49, so they are
# read-only MergedCells and writing them raises AttributeError; (b) the K-1 rows
# (2023 N50-N53) stay writable but at 2022 would land one property row too high.
# Every 8582 cell-address reference therefore needs +1 row (all targets verified
# writable). Line-11 output likewise: 2023 AE43='=IF(AO21,"",SUM(AE39,AE41))' ->
# 2022 AE44='=IF(AO21,"",SUM(AE40,AE42))'.
_SCHE_8582_2022 = {
    "sche_8582_net_income": "N50", "sche_8582_net_loss": "R50",
    "k1_a_8582_net_income": "N51", "k1_a_8582_net_loss": "R51",
    "k1_a_8582_prior_year_loss": "V51",
    "k1_b_8582_net_income": "N52", "k1_b_8582_net_loss": "R52",
    "k1_b_8582_prior_year_loss": "V52",
    "k1_c_8582_net_income": "N53", "k1_c_8582_net_loss": "R53",
    "k1_c_8582_prior_year_loss": "V53",
    "k1_d_8582_net_income": "N54", "k1_d_8582_net_loss": "R54",
    "k1_d_8582_prior_year_loss": "V54",
}
F1040.INPUTS[2022] = F1040.inherit(2023, {
    "mortgage_interest": "S35",   # 'Sch. A' mortgage block -2 rows (2023 S37)
    "property_tax": "M26",        # 'Sch. A' +1 row (2023 M25)
    **_SCHE_8582_2022,            # '8582' property table +1 row (see note above)
}, source="inputs")
F1040.OUTPUTS[2022] = F1040.inherit(2023, {
    "sch_a_line_5e_salt_capped": "M30",   # 'Sch. A' +1 row (2023 M29)
    "f8582_line_11_oracle": "AE44",       # '8582' +1 row (2023 AE43)
}, source="outputs")
F1040.SHEET_MAP[2022] = dict(F1040.SHEET_MAP[2023])


# --- Federal 2021 workbook wiring (BOUNDED PARTIAL WIRE) --------------------
# The TY2021 vendor workbook STRUCTURALLY OMITS the Form 8582 tab (passive-
# activity loss limitation): proven by named-range absence — F8582_Line9 /
# F8582_MAGI exist in the 2022 workbook and are gone in 2021, with no renamed
# equivalent. The passive-activity key group therefore has NO oracle target in
# 2021 no matter how it is wired. Rather than an ad-hoc drop, those keys are
# declared in the explicit WORKBOOK_KEY_EXCLUSIONS registry below, which:
#   (1) the parity harness READS and surfaces as explicit skips-with-reason
#       (never silently absent),
#   (2) is typo-guarded — a test asserts every excluded key exists in another
#       workbook year's map, and
#   (3) is governed by the restated invariant: a workbook year yields full
#       penny-parity over its DECLARED surface; exclusions are explicit,
#       reasoned, and gated.
# Every OTHER surface is wired off 2022 with full drift discipline — each moved
# cell is proven by a CONSUMER formula in the 2021 workbook, never by value-
# equality on a blank data-entry cell. Two sheets drifted vs 2022; the rest are
# identical (named-range outputs resolve by name and were verified present):
#
#  - 'W-2s': the state-tax rows shifted UP 1 (fewer intermediate rows in 2021).
#    Proven by the box-label column: box 16 label A22->A21, box 17 label
#    A23->A22 (boxes 1-6 labels at rows 3-8 are unchanged, so C3..C8 are
#    stable). So w2_state_wages_1 C22->C21 and w2_state_withheld_1 C23->C22.
#
#  - 'Sch. E': TWO different shifts in one sheet (a value-equality inference
#    would have gotten this wrong). The property-header row moved UP 1 while
#    the income+expense block moved UP 3. Both proven by the same consumer
#    formula: 2022 AZ24 '=IF(D21<>6,V30,0)' -> 2021 AZ23 '=IF(D20<>6,V27,0)'
#    (property_type D21->D20 is -1; rents V30->V27 is -3 in the SAME formula),
#    corroborated by the expense subtotal 2022 V48 '...SUM(V33:AC47)...' ->
#    2021 V45 '...SUM(V30:AC44)...' (the 15-row expense block -3) and the
#    depreciation rollups 2022 SUM(V40..)/SUM(V46..) -> 2021 SUM(V37..)/
#    SUM(V43..). So property cells (D/AA/AF)21 -> (…)20, and the income+
#    expense cells V30/V33..V47 -> V27/V30..V44.
#
#  - 'Sch. A': IDENTICAL to 2022 — mortgage reader MIN(S..,ROUND(S35,0)),
#    property reader O27='=ROUND(M26,0)', line-5e M30='=…MIN(M28,O22)' all
#    match, so the three 2022 cell-address overrides (S35/M26/M30) carry
#    unchanged.
#  - '8949A'/'8949B': IDENTICAL — F8949 box/total named ranges resolve to the
#    same cells (C25/C27/C78/C80 checkboxes; Q55/Q116 totals) and the section
#    headers sit at the same rows, so the 2022 F8949 box slots apply as-is.
#  - '1099-INT'/'1099-DIV': IDENTICAL — labels at the same rows (D6; 1a/1b/2a
#    at rows 6/7/8).
#
# The 33 named ranges present in 2022 but absent in 2021 (F2555 foreign-income
# family, IRA-distribution split, the F8582_* set) are scope-documented in the
# followups ledger; only the 8582 set is referenced by our maps and needs the
# exclusion. The Sch. E Part II K-1 cells ALSO drifted -3 (same as the income/
# expense block) and are overridden below — the battery populates no K-1s, but
# the merged-cell guard requires every input cell be writable, so they are
# re-homed onto their 2021 anchor cells. 1099-G cells are inherited unchanged
# (the battery populates no 1099-G, so they are never written); the soffice
# parity gate is the backstop for any cell we moved.

# (year, key) -> human reason. A workbook year yields full penny-parity over
# its DECLARED surface; where a vendor workbook structurally omits a form, that
# form's keys are excluded here — explicitly, with a reason, and gated. NOT an
# ad-hoc skip. Consumed by tests/test_f1040_spine_oracle.py.
WORKBOOK_KEY_EXCLUSIONS: dict[tuple[int, str], str] = {}
_F8582_KEYS_2022 = tuple(
    k for k, v in F1040.SHEET_MAP[2022].items() if v == "8582")
for _key in _F8582_KEYS_2022:
    WORKBOOK_KEY_EXCLUSIONS[(2021, _key)] = (
        "TY2021 vendor workbook omits the Form 8582 tab (passive-activity "
        "loss limitation) — no oracle target exists for this key")

_SCHE_2021 = {
    # property-header region: -1 row (proven by AZ23 IF(D20<>6,...) + row-21->20
    # property-column consumers).
    "sche_property_type_a": "D20",
    "sche_fair_rental_days_a": "AA20",
    "sche_personal_use_days_a": "AF20",
    # income + expense region: -3 rows (rents V30->V27 from the same AZ23
    # formula; the 15-row expense block V33..V47 -> V30..V44 from SUM range).
    "sche_rents_a": "V27",
    "sche_advertising_a": "V30",
    "sche_auto_and_travel_a": "V31",
    "sche_cleaning_and_maintenance_a": "V32",
    "sche_commissions_a": "V33",
    "sche_insurance_a": "V34",
    "sche_legal_and_professional_fees_a": "V35",
    "sche_management_fees_a": "V36",
    "sche_mortgage_interest_a": "V37",
    "sche_other_interest_a": "V38",
    "sche_repairs_a": "V39",
    "sche_supplies_a": "V40",
    "sche_taxes_a": "V41",
    "sche_utilities_a": "V42",
    "sche_depreciation_a": "V43",
    "sche_other_expenses_a": "V44",
    # Sch. E Part II (K-1 pass-through) is the SAME -3 shift as the income/
    # expense block. Proven by the printed entity-letter row markers (col B:
    # 'A' at 2022 row 80 -> 2021 row 77; income 'A' at 2022 row 88 -> 2021
    # row 85) and merge-geometry alignment (the entity-name merge C{r}:N{r}
    # and income merges C{r}:J{r}/K{r}:R{r} each shift -3 onto their writable
    # anchor cell). Without this override the inherited 2022 rows land on 2021
    # NON-anchor MergedCells (writes raise) — caught by the merged-cell guard.
    # The battery exercises no K-1s, so these are wired for map-writability +
    # completeness, not for parity coverage (K-1 income is not in PARITY_KEYS).
    "k1_a_entity_name": "C77",
    "k1_a_entity_type_s_corp": "O77",
    "k1_a_entity_type_partnership": "O77",
    "k1_a_entity_ein": "Y77",
    "k1_b_entity_name": "C78",
    "k1_b_entity_type_s_corp": "O78",
    "k1_b_entity_type_partnership": "O78",
    "k1_b_entity_ein": "Y78",
    "k1_c_entity_name": "C79",
    "k1_c_entity_type_s_corp": "O79",
    "k1_c_entity_type_partnership": "O79",
    "k1_c_entity_ein": "Y79",
    "k1_d_entity_name": "C80",
    "k1_d_entity_type_s_corp": "O80",
    "k1_d_entity_type_partnership": "O80",
    "k1_d_entity_ein": "Y80",
    "k1_a_passive_loss": "C85",
    "k1_a_passive_income": "K85",
    "k1_a_nonpassive_loss": "S85",
    "k1_a_nonpassive_income": "AH85",
    "k1_b_passive_loss": "C86",
    "k1_b_passive_income": "K86",
    "k1_b_nonpassive_loss": "S86",
    "k1_b_nonpassive_income": "AH86",
    "k1_c_passive_loss": "C87",
    "k1_c_passive_income": "K87",
    "k1_c_nonpassive_loss": "S87",
    "k1_c_nonpassive_income": "AH87",
    "k1_d_passive_loss": "C88",
    "k1_d_passive_income": "K88",
    "k1_d_nonpassive_loss": "S88",
    "k1_d_nonpassive_income": "AH88",
}


def _wire_2021() -> None:
    """Build 2021 maps off 2022 with the proven drift overrides, then drop the
    exclusion-registry keys from every map (inherit() merges but cannot remove,
    so the removal is explicit here and single-sourced from the registry)."""
    excluded = {k for (yr, k) in WORKBOOK_KEY_EXCLUSIONS if yr == 2021}
    inputs = F1040.inherit(2022, {
        "w2_state_wages_1": "C21",     # 'W-2s' box-16 row -1 (2022 C22)
        "w2_state_withheld_1": "C22",  # 'W-2s' box-17 row -1 (2022 C23)
        **_SCHE_2021,
    }, source="inputs")
    outputs = F1040.inherit(2022, {}, source="outputs")  # Sch.A M30 unchanged
    F1040.INPUTS[2021] = {k: v for k, v in inputs.items() if k not in excluded}
    F1040.OUTPUTS[2021] = {k: v for k, v in outputs.items()
                           if k not in excluded}
    F1040.SHEET_MAP[2021] = {k: v for k, v in F1040.SHEET_MAP[2022].items()
                             if k not in excluded}


_wire_2021()
