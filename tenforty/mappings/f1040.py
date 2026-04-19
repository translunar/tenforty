from tenforty.mappings.registry import FormMapping


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
            # and box type — Task 3 will add that aggregation.
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
        },
    }

    INPUTS: dict[int, dict[str, str]] = {
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
        },
    }

    OUTPUTS: dict[int, dict[str, str]] = {
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
        },
    }
