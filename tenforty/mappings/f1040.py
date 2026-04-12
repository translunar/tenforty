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
        },
    }

    OUTPUTS: dict[int, dict[str, str]] = {
        2025: {
            "wages": "Wages",
            "agi": "Adj_Gross_Inc",
            "standard_deduction": "SD_Single",
            "taxable_income": "Taxable_Inc",
            "total_tax": "Tax",
            "federal_withheld": "W2_FedTaxWH",
            "overpaid": "Overpaid",
            "sche_line26": "SchE1_Line26",
            "sche_line41": "SchE1_Line41",
            "schd_line16": "SchDLine16",
            "interest_income": "Interest_Inc",
            "dividend_income": "Dividend_Inc",
            "schedule_a_total": "Tot_Item_Deduct",
            # --- Totals ---
            "total_income": "Total_Income",
            "total_payments": "Tot_Payments",
            "total_deductions": "TotalDeductions",
        },
    }
