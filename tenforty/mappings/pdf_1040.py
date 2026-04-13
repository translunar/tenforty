"""PDF field mapping for IRS Form 1040.

Maps computed result keys to the PDF form field names in the IRS's
fillable f1040.pdf. Field names are opaque (f1_47, f2_07, etc.) so this
mapping was built by filling each field with its name and visually
identifying which 1040 line it corresponds to.

Field names use the full path format:
    topmostSubform[0].Page1[0].f1_47[0]
"""


class Pdf1040:
    """PDF field mapping for IRS Form 1040."""

    _MAPPINGS: dict[int, dict[str, str]] = {
        2025: {
            # === Page 1: Header ===
            "first_name": "topmostSubform[0].Page1[0].f1_01[0]",
            "last_name": "topmostSubform[0].Page1[0].f1_02[0]",
            "ssn": "topmostSubform[0].Page1[0].f1_03[0]",
            "spouse_first_name": "topmostSubform[0].Page1[0].f1_04[0]",
            "spouse_last_name": "topmostSubform[0].Page1[0].f1_05[0]",
            "spouse_ssn": "topmostSubform[0].Page1[0].f1_06[0]",
            "address": "topmostSubform[0].Page1[0].f1_07[0]",
            "apt_no": "topmostSubform[0].Page1[0].f1_08[0]",
            "city": "topmostSubform[0].Page1[0].f1_09[0]",
            "state": "topmostSubform[0].Page1[0].f1_10[0]",
            "zip_code": "topmostSubform[0].Page1[0].f1_11[0]",

            # === Page 1: Income (Lines 1-11) ===
            # Line 1a: Wages, salaries, tips (W-2 box 1)
            "wages": "topmostSubform[0].Page1[0].f1_47[0]",
            # Line 1b: Household employee income
            "household_employee_income": "topmostSubform[0].Page1[0].f1_48[0]",
            # Line 1c: Tip income
            "tip_income": "topmostSubform[0].Page1[0].f1_49[0]",
            # Line 1d: Medicaid waiver payments
            "medicaid_waiver": "topmostSubform[0].Page1[0].f1_50[0]",
            # Line 1e: Taxable dependent care benefits
            "dependent_care_benefits": "topmostSubform[0].Page1[0].f1_51[0]",
            # Line 1f: Employer-provided adoption benefits
            "adoption_benefits": "topmostSubform[0].Page1[0].f1_52[0]",
            # Line 1g: Form 8919 wages
            "form_8919_wages": "topmostSubform[0].Page1[0].f1_53[0]",
            # Line 1h: Other earned income — type (f1_54) and amount (f1_55)
            "other_earned_income_type": "topmostSubform[0].Page1[0].f1_54[0]",
            "other_earned_income": "topmostSubform[0].Page1[0].f1_55[0]",
            # Line 1i: Nontaxable combat pay election
            "combat_pay_election": "topmostSubform[0].Page1[0].f1_56[0]",
            # Line 1z: Total of 1a through 1h
            "total_w2_income": "topmostSubform[0].Page1[0].f1_57[0]",
            # Line 2a: Tax-exempt interest
            "tax_exempt_interest": "topmostSubform[0].Page1[0].f1_58[0]",
            # Line 2b: Taxable interest
            "taxable_interest": "topmostSubform[0].Page1[0].f1_59[0]",
            # Line 3a: Qualified dividends
            "qualified_dividends": "topmostSubform[0].Page1[0].f1_60[0]",
            # Line 3b: Ordinary dividends
            "ordinary_dividends": "topmostSubform[0].Page1[0].f1_61[0]",
            # Line 4a: IRA distributions
            "ira_distributions": "topmostSubform[0].Page1[0].f1_62[0]",
            # Line 4b: IRA taxable amount
            "ira_taxable": "topmostSubform[0].Page1[0].f1_63[0]",
            # Line 5a: Pensions and annuities
            "pensions": "topmostSubform[0].Page1[0].f1_65[0]",
            # Line 5b: Pensions taxable amount
            "pensions_taxable": "topmostSubform[0].Page1[0].f1_66[0]",
            # Line 6a: Social security benefits
            "social_security": "topmostSubform[0].Page1[0].f1_68[0]",
            # Line 6b: Social security taxable amount
            "social_security_taxable": "topmostSubform[0].Page1[0].f1_69[0]",
            # Line 7a: Capital gain or (loss)
            "capital_gain_loss": "topmostSubform[0].Page1[0].f1_70[0]",
            # Line 7b: (new on 2025 form — unmapped, reserved for future use)
            # Line 8: Other income from Schedule 1, line 10
            "other_income": "topmostSubform[0].Page1[0].f1_72[0]",
            # Line 9: Total income
            "total_income": "topmostSubform[0].Page1[0].f1_73[0]",
            # Line 10: Adjustments to income from Schedule 1, line 26
            "adjustments": "topmostSubform[0].Page1[0].f1_74[0]",
            # Line 11a: Adjusted gross income
            "agi": "topmostSubform[0].Page1[0].f1_75[0]",

            # === Page 2: Tax and Credits (Lines 11b-24) ===
            # Line 11b (AGI repeated at top of page 2)
            "agi_page2": "topmostSubform[0].Page2[0].f2_01[0]",
            # Line 12e: Standard deduction or itemized deductions
            "standard_deduction": "topmostSubform[0].Page2[0].f2_02[0]",
            # Line 13a: Qualified business income deduction
            "qbi_deduction": "topmostSubform[0].Page2[0].f2_03[0]",
            # Line 13b: Additional deductions from Schedule 1-A
            "additional_deductions": "topmostSubform[0].Page2[0].f2_04[0]",
            # Line 14: Add lines 12, 13a, and 13b
            "total_deductions": "topmostSubform[0].Page2[0].f2_05[0]",
            # Line 15: Taxable income (line 11b minus line 14)
            "taxable_income": "topmostSubform[0].Page2[0].f2_06[0]",
            # Line 16: Tax (f2_07 is the 8814/4972 checkbox value on this line)
            "total_tax": "topmostSubform[0].Page2[0].f2_08[0]",
            # Line 17: Amount from Schedule 2, line 3
            "schedule2_tax": "topmostSubform[0].Page2[0].f2_09[0]",
            # Line 18: Add lines 16 and 17
            "tax_plus_schedule2": "topmostSubform[0].Page2[0].f2_10[0]",
            # Line 19: Child tax credit / credit for other dependents
            "child_tax_credit": "topmostSubform[0].Page2[0].f2_11[0]",
            # Line 20: Amount from Schedule 3, line 8
            "schedule3_credits": "topmostSubform[0].Page2[0].f2_12[0]",
            # Line 21: Add lines 19 and 20
            "total_credits": "topmostSubform[0].Page2[0].f2_13[0]",
            # Line 22: Subtract line 21 from line 18
            "tax_after_credits": "topmostSubform[0].Page2[0].f2_14[0]",
            # Line 23: Other taxes from Schedule 2, line 21
            "other_taxes": "topmostSubform[0].Page2[0].f2_15[0]",
            # Line 24: Total tax (add lines 22 and 23)
            "total_tax_liability": "topmostSubform[0].Page2[0].f2_16[0]",

            # === Page 2: Payments (Lines 25-33) ===
            # Line 25a: Federal income tax withheld from W-2
            "federal_withheld_w2": "topmostSubform[0].Page2[0].f2_17[0]",
            # Line 25b: Federal income tax withheld from 1099
            "federal_withheld_1099": "topmostSubform[0].Page2[0].f2_18[0]",
            # Line 25c: Other forms (see instructions)
            "federal_withheld_other": "topmostSubform[0].Page2[0].f2_19[0]",
            # Line 25d: Total (add 25a through 25c)
            "federal_withheld": "topmostSubform[0].Page2[0].f2_20[0]",
            # Line 26: Estimated tax payments
            "estimated_payments": "topmostSubform[0].Page2[0].f2_21[0]",
            # f2_22 is the EIC-spouse-SSN field
            # Line 27a: Earned income credit (EIC)
            "eic": "topmostSubform[0].Page2[0].f2_23[0]",
            # Line 28: Additional child tax credit from Schedule 8812
            "additional_child_tax_credit": "topmostSubform[0].Page2[0].f2_24[0]",
            # Line 29: American opportunity credit from Form 8863
            "american_opportunity_credit": "topmostSubform[0].Page2[0].f2_25[0]",
            # Line 30: Refundable adoption credit from Form 8839
            "adoption_credit_8839": "topmostSubform[0].Page2[0].f2_26[0]",
            # Line 31: Amount from Schedule 3, line 15
            "schedule3_payments": "topmostSubform[0].Page2[0].f2_27[0]",
            # Line 32: Total other payments and refundable credits
            "total_other_payments": "topmostSubform[0].Page2[0].f2_28[0]",
            # Line 33: Total payments (add lines 25d, 26, and 32)
            "total_payments": "topmostSubform[0].Page2[0].f2_29[0]",

            # === Page 2: Refund / Amount You Owe (Lines 34-38) ===
            # Line 34: Overpaid (if line 33 > line 24)
            "overpaid": "topmostSubform[0].Page2[0].f2_30[0]",
            # Line 35a: Amount of line 34 you want refunded to you
            "refund": "topmostSubform[0].Page2[0].f2_31[0]",
            # f2_31 is "If Form 8888 is attached, check here"
            # f2_32 is routing number, f2_33 is account number
            # Line 36: Applied to next year estimated tax
            "applied_to_next_year": "topmostSubform[0].Page2[0].f2_34[0]",
            # Line 37: Amount you owe (if line 24 > line 33)
            "amount_owed": "topmostSubform[0].Page2[0].f2_35[0]",
            # Line 38: Estimated tax penalty
            "estimated_tax_penalty": "topmostSubform[0].Page2[0].f2_36[0]",
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict[str, str]:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No PDF mapping for year {year}")
        return cls._MAPPINGS[year]
