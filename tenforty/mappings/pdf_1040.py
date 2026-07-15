"""PDF field mapping for IRS Form 1040.

Maps computed result keys to the PDF form field names in the IRS's
fillable f1040.pdf. Field names are opaque (f1_47, f2_07, etc.) so this
mapping was built by filling each field with its name and visually
identifying which 1040 line it corresponds to.

Field names use the full path format:
    topmostSubform[0].Page1[0].f1_47[0]
"""

from tenforty.mappings.registry import PdfFormMapping


class Pdf1040(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for IRS Form 1040."""

    _FORM_NAME = "Form 1040"

    _MAPPINGS: dict[int, dict[str, str]] = {
        2022: {
            # Built by marker-probe: every field on the 2022 template was
            # stamped with its own name (scripts/probe_pdf_fields.py), rendered
            # (pdfs/federal/2022/f1040.probe.pdf), and each marker read against
            # the printed 2022 line labels on BOTH pages. 2022 shares 2023's
            # structural layout (lines 11-15 on page 1; page 2 starts at line
            # 16), but the field NAMES renumber in two uniform blocks relative
            # to 2023 — the renumbering trap: a diff/inherit would silently
            # mis-map, so every path below was read from the render, then its
            # full container path resolved against the 2022 template inventory.
            #   * Header block: 2023 f1_04..f1_14 -> 2022 f1_02..f1_12 (-2).
            #     Also different containers: SSNs nest in YourSocial[0] /
            #     SpousesSocial[0], and the address block is Address[0] (2023
            #     used a flat SSN and Address_ReadOrder[0]).
            #   * Income block: 2023 f1_31..f1_59 -> 2022 f1_28..f1_56 (-3).
            #     Lines 4a-11 nest in Lines4a-11_ReadOrder[0] (note the plural,
            #     vs 2023's Line4a-11_ReadOrder[0]); line 12 nests in
            #     StandardDeductionBubble[0]; lines 13-15 are flat on Page1.
            #   * Page 2 (lines 16-38) is byte-identical to 2023 (same field
            #     names, same positions — render-confirmed line by line).

            # === Page 1: Header ===
            "first_name": "topmostSubform[0].Page1[0].f1_02[0]",
            "last_name": "topmostSubform[0].Page1[0].f1_03[0]",
            "ssn": "topmostSubform[0].Page1[0].YourSocial[0].f1_04[0]",
            "spouse_first_name": "topmostSubform[0].Page1[0].f1_05[0]",
            "spouse_last_name": "topmostSubform[0].Page1[0].f1_06[0]",
            "spouse_ssn": "topmostSubform[0].Page1[0].SpousesSocial[0].f1_07[0]",
            # Address fields live inside Address[0] in 2022.
            "address": "topmostSubform[0].Page1[0].Address[0].f1_08[0]",
            "apt_no": "topmostSubform[0].Page1[0].Address[0].f1_09[0]",
            "city": "topmostSubform[0].Page1[0].Address[0].f1_10[0]",
            "state": "topmostSubform[0].Page1[0].Address[0].f1_11[0]",
            "zip_code": "topmostSubform[0].Page1[0].Address[0].f1_12[0]",

            # === Page 1: Income (Lines 1-11) ===
            # Lines 1a-3b sit directly on Page1 at f1_28-f1_41.
            # Line 1a: Wages, salaries, tips (W-2 box 1)
            "wages": "topmostSubform[0].Page1[0].f1_28[0]",
            # Line 1b: Household employee income
            "household_employee_income": "topmostSubform[0].Page1[0].f1_29[0]",
            # Line 1c: Tip income
            "tip_income": "topmostSubform[0].Page1[0].f1_30[0]",
            # Line 1d: Medicaid waiver payments
            "medicaid_waiver": "topmostSubform[0].Page1[0].f1_31[0]",
            # Line 1e: Taxable dependent care benefits
            "dependent_care_benefits": "topmostSubform[0].Page1[0].f1_32[0]",
            # Line 1f: Employer-provided adoption benefits
            "adoption_benefits": "topmostSubform[0].Page1[0].f1_33[0]",
            # Line 1g: Form 8919 wages
            "form_8919_wages": "topmostSubform[0].Page1[0].f1_34[0]",
            # Line 1h: Other earned income (amount only — no "type" field in 2022)
            "other_earned_income": "topmostSubform[0].Page1[0].f1_35[0]",
            # Line 1i: Nontaxable combat pay election
            "combat_pay_election": "topmostSubform[0].Page1[0].f1_36[0]",
            # Line 1z: Total of 1a through 1h
            "total_w2_income": "topmostSubform[0].Page1[0].f1_37[0]",
            # Line 2a: Tax-exempt interest
            "tax_exempt_interest": "topmostSubform[0].Page1[0].f1_38[0]",
            # Line 2b: Taxable interest
            "taxable_interest": "topmostSubform[0].Page1[0].f1_39[0]",
            # Line 3a: Qualified dividends
            "qualified_dividends": "topmostSubform[0].Page1[0].f1_40[0]",
            # Line 3b: Ordinary dividends
            "ordinary_dividends": "topmostSubform[0].Page1[0].f1_41[0]",

            # Lines 4a-11 live inside Lines4a-11_ReadOrder[0] (plural in 2022).
            # Line 4a: IRA distributions
            "ira_distributions": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_42[0]",
            # Line 4b: IRA taxable amount
            "ira_taxable": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_43[0]",
            # Line 5a: Pensions and annuities
            "pensions": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_44[0]",
            # Line 5b: Pensions taxable amount
            "pensions_taxable": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_45[0]",
            # Line 6a: Social security benefits
            "social_security": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_46[0]",
            # Line 6b: Social security taxable amount
            "social_security_taxable": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_47[0]",
            # Line 7: Capital gain or (loss)
            "capital_gain_loss": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_48[0]",
            # Line 8: Additional income from Schedule 1, line 10 (full Sch 1
            # line-10 total — see the 2023 note below on the footing fix).
            "sch_1_line_10": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_49[0]",
            # Line 9: Total income
            "total_income": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_50[0]",
            # Line 10: Adjustments to income from Schedule 1, line 26
            "adjustments": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_51[0]",
            # Line 11: Adjusted gross income
            "agi": "topmostSubform[0].Page1[0].Lines4a-11_ReadOrder[0].f1_52[0]",

            # === Page 1: Deduction & taxable income (Lines 12-15) ===
            # Line 12: deduction actually applied — nests in StandardDeductionBubble.
            "applied_deduction": "topmostSubform[0].Page1[0].StandardDeductionBubble[0].f1_53[0]",
            # Line 13: Qualified business income deduction (single line, 2022)
            "qbi_deduction": "topmostSubform[0].Page1[0].f1_54[0]",
            # Line 14: Add lines 12 and 13
            "total_deductions": "topmostSubform[0].Page1[0].f1_55[0]",
            # Line 15: Taxable income (line 11 minus line 14)
            "taxable_income": "topmostSubform[0].Page1[0].f1_56[0]",

            # === Page 2: Tax and Credits (Lines 16-24) — identical to 2023 ===
            # f2_01 is the line-16 "from Form 8814/4972/…" checkbox amount.
            # Line 16: Tax
            "total_tax": "topmostSubform[0].Page2[0].f2_02[0]",
            # Line 17: Amount from Schedule 2, line 3
            "schedule2_tax": "topmostSubform[0].Page2[0].f2_03[0]",
            # Line 18: Add lines 16 and 17
            "tax_plus_schedule2": "topmostSubform[0].Page2[0].f2_04[0]",
            # Line 19: Child tax credit / credit for other dependents
            "child_tax_credit": "topmostSubform[0].Page2[0].f2_05[0]",
            # Line 20: Amount from Schedule 3, line 8
            "schedule3_credits": "topmostSubform[0].Page2[0].f2_06[0]",
            # Line 21: Add lines 19 and 20
            "total_credits": "topmostSubform[0].Page2[0].f2_07[0]",
            # Line 22: Subtract line 21 from line 18
            "tax_after_credits": "topmostSubform[0].Page2[0].f2_08[0]",
            # Line 23: Other taxes from Schedule 2, line 21
            "other_taxes": "topmostSubform[0].Page2[0].f2_09[0]",
            # Line 24: Total tax (add lines 22 and 23)
            "total_tax_liability": "topmostSubform[0].Page2[0].f2_10[0]",

            # === Page 2: Payments (Lines 25-33) ===
            # Line 25a: Federal income tax withheld from W-2
            "federal_withheld_w2": "topmostSubform[0].Page2[0].f2_11[0]",
            # Line 25b: Federal income tax withheld from 1099
            "federal_withheld_1099": "topmostSubform[0].Page2[0].f2_12[0]",
            # Line 25c: Other forms (see instructions)
            "federal_withheld_other": "topmostSubform[0].Page2[0].f2_13[0]",
            # Line 25d: Total (add 25a through 25c)
            "federal_withheld": "topmostSubform[0].Page2[0].f2_14[0]",
            # Line 26: Estimated tax payments (2022 est. + 2021 applied)
            "estimated_tax_payments": "topmostSubform[0].Page2[0].f2_15[0]",
            # Line 27: Earned income credit (EIC)
            "eic": "topmostSubform[0].Page2[0].f2_16[0]",
            # Line 28: Additional child tax credit from Schedule 8812
            "additional_child_tax_credit": "topmostSubform[0].Page2[0].f2_17[0]",
            # Line 29: American opportunity credit from Form 8863
            "american_opportunity_credit": "topmostSubform[0].Page2[0].f2_18[0]",
            # Line 30: Reserved for future use (f2_19, not mapped)
            # Line 31: Amount from Schedule 3, line 15
            "schedule3_payments": "topmostSubform[0].Page2[0].f2_20[0]",
            # Line 32: Total other payments and refundable credits
            "total_other_payments": "topmostSubform[0].Page2[0].f2_21[0]",
            # Line 33: Total payments (add lines 25d, 26, and 32)
            "total_payments": "topmostSubform[0].Page2[0].f2_22[0]",

            # === Page 2: Refund / Amount You Owe (Lines 34-38) ===
            # Line 34: Overpaid (if line 33 > line 24)
            "overpaid": "topmostSubform[0].Page2[0].f2_23[0]",
            # Line 35a: Amount of line 34 you want refunded to you
            "refund": "topmostSubform[0].Page2[0].f2_24[0]",
            # f2_25/f2_26 are RoutingNo/AccountNo (lines 35b/35d).
            # Line 36: Applied to next year (2023) estimated tax
            "applied_to_next_year": "topmostSubform[0].Page2[0].f2_27[0]",
            # Line 37: Amount you owe (if line 24 > line 33)
            "amount_owed": "topmostSubform[0].Page2[0].f2_28[0]",
            # Line 38: Estimated tax penalty
            "estimated_tax_penalty": "topmostSubform[0].Page2[0].f2_29[0]",
        },
        2023: {
            # Built by marker-probe: every field on the 2023 template was
            # stamped with its own field name (scripts/probe_pdf_fields.py),
            # rendered (pdfs/federal/2023/f1040.probe.pdf), and each marker
            # read against the printed 2023 line labels. The 2023 layout
            # differs structurally from 2024 — NOT a field-name renumbering
            # you can inherit:
            #   * Lines 11–15 (AGI, deduction, QBI, total ded., taxable
            #     income) sit on PAGE 1 (f1_55–f1_59); 2024 moved 11b–15 to
            #     page 2. So there is no `agi_page2` on 2023, and page 2
            #     starts at line 16.
            #   * The 1a–1z block has one fewer field (no line-1h "type"
            #     text field), so income f-numbers run f1_31–f1_44 flat.
            #   * Line 13 is a single QBI line (no 13a/13b Schedule 1-A
            #     split → no `additional_deductions`).
            #   * Line 7 has no 7b "child's capital gain" amount field, and
            #     line 5c is a checkbox (no `pensions_other_explanation`
            #     text field). These 2024-only keys are omitted; the filler
            #     simply skips result keys with no field on this year's form.
            #   * State/ZIP are Address_ReadOrder f1_13/f1_14 (2024 used
            #     f1_16/f1_17 — the foreign-address fields reorder).

            # === Page 1: Header ===
            "first_name": "topmostSubform[0].Page1[0].f1_04[0]",
            "last_name": "topmostSubform[0].Page1[0].f1_05[0]",
            "ssn": "topmostSubform[0].Page1[0].f1_06[0]",
            "spouse_first_name": "topmostSubform[0].Page1[0].f1_07[0]",
            "spouse_last_name": "topmostSubform[0].Page1[0].f1_08[0]",
            "spouse_ssn": "topmostSubform[0].Page1[0].f1_09[0]",
            # Address fields live inside Address_ReadOrder in 2023.
            "address": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_10[0]",
            "apt_no": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_11[0]",
            "city": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_12[0]",
            "state": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_13[0]",
            "zip_code": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_14[0]",

            # === Page 1: Income (Lines 1-11) ===
            # Lines 1a–3b sit directly on Page1 at f1_31–f1_44.
            # Line 1a: Wages, salaries, tips (W-2 box 1)
            "wages": "topmostSubform[0].Page1[0].f1_31[0]",
            # Line 1b: Household employee income
            "household_employee_income": "topmostSubform[0].Page1[0].f1_32[0]",
            # Line 1c: Tip income
            "tip_income": "topmostSubform[0].Page1[0].f1_33[0]",
            # Line 1d: Medicaid waiver payments
            "medicaid_waiver": "topmostSubform[0].Page1[0].f1_34[0]",
            # Line 1e: Taxable dependent care benefits
            "dependent_care_benefits": "topmostSubform[0].Page1[0].f1_35[0]",
            # Line 1f: Employer-provided adoption benefits
            "adoption_benefits": "topmostSubform[0].Page1[0].f1_36[0]",
            # Line 1g: Form 8919 wages
            "form_8919_wages": "topmostSubform[0].Page1[0].f1_37[0]",
            # Line 1h: Other earned income (amount only — no "type" field in 2023)
            "other_earned_income": "topmostSubform[0].Page1[0].f1_38[0]",
            # Line 1i: Nontaxable combat pay election
            "combat_pay_election": "topmostSubform[0].Page1[0].f1_39[0]",
            # Line 1z: Total of 1a through 1h
            "total_w2_income": "topmostSubform[0].Page1[0].f1_40[0]",
            # Line 2a: Tax-exempt interest
            "tax_exempt_interest": "topmostSubform[0].Page1[0].f1_41[0]",
            # Line 2b: Taxable interest
            "taxable_interest": "topmostSubform[0].Page1[0].f1_42[0]",
            # Line 3a: Qualified dividends
            "qualified_dividends": "topmostSubform[0].Page1[0].f1_43[0]",
            # Line 3b: Ordinary dividends
            "ordinary_dividends": "topmostSubform[0].Page1[0].f1_44[0]",

            # Lines 4a-11 live inside Line4a-11_ReadOrder[0].
            # Line 4a: IRA distributions
            "ira_distributions": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_45[0]",
            # Line 4b: IRA taxable amount
            "ira_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_46[0]",
            # Line 5a: Pensions and annuities
            "pensions": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_47[0]",
            # Line 5b: Pensions taxable amount
            "pensions_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_48[0]",
            # Line 6a: Social security benefits
            "social_security": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_49[0]",
            # Line 6b: Social security taxable amount
            "social_security_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_50[0]",
            # Line 7: Capital gain or (loss)
            "capital_gain_loss": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_51[0]",
            # Line 8: Additional income from Schedule 1, line 10. Sources the
            # FULL Schedule 1 line-10 total (`sch_1_line_10`), not the
            # rental-only `other_income` key — otherwise line 8 understates
            # additional income (e.g. omits 1099-G unemployment) and the return
            # fails to foot against line 9 / the attached Schedule 1.
            "sch_1_line_10": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_52[0]",
            # Line 9: Total income
            "total_income": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_53[0]",
            # Line 10: Adjustments to income from Schedule 1, line 26
            "adjustments": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_54[0]",
            # Line 11: Adjusted gross income
            "agi": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_55[0]",

            # === Page 1: Deduction & taxable income (Lines 12-15) ===
            # These are on PAGE 1 in 2023 (f1_56–f1_59), directly on Page1.
            # Line 12: Standard deduction OR itemized deductions — the
            # deduction actually applied (reads `applied_deduction`).
            "applied_deduction": "topmostSubform[0].Page1[0].f1_56[0]",
            # Line 13: Qualified business income deduction (single line, 2023)
            "qbi_deduction": "topmostSubform[0].Page1[0].f1_57[0]",
            # Line 14: Add lines 12 and 13
            "total_deductions": "topmostSubform[0].Page1[0].f1_58[0]",
            # Line 15: Taxable income (line 11 minus line 14)
            "taxable_income": "topmostSubform[0].Page1[0].f1_59[0]",

            # === Page 2: Tax and Credits (Lines 16-24) ===
            # Page 2 starts at line 16 in 2023 (no line 11b-15 repeat).
            # f2_01 is the line-16 "from Form 8814/4972/…" checkbox amount.
            # Line 16: Tax
            "total_tax": "topmostSubform[0].Page2[0].f2_02[0]",
            # Line 17: Amount from Schedule 2, line 3
            "schedule2_tax": "topmostSubform[0].Page2[0].f2_03[0]",
            # Line 18: Add lines 16 and 17
            "tax_plus_schedule2": "topmostSubform[0].Page2[0].f2_04[0]",
            # Line 19: Child tax credit / credit for other dependents
            "child_tax_credit": "topmostSubform[0].Page2[0].f2_05[0]",
            # Line 20: Amount from Schedule 3, line 8
            "schedule3_credits": "topmostSubform[0].Page2[0].f2_06[0]",
            # Line 21: Add lines 19 and 20
            "total_credits": "topmostSubform[0].Page2[0].f2_07[0]",
            # Line 22: Subtract line 21 from line 18
            "tax_after_credits": "topmostSubform[0].Page2[0].f2_08[0]",
            # Line 23: Other taxes from Schedule 2, line 21
            "other_taxes": "topmostSubform[0].Page2[0].f2_09[0]",
            # Line 24: Total tax (add lines 22 and 23)
            "total_tax_liability": "topmostSubform[0].Page2[0].f2_10[0]",

            # === Page 2: Payments (Lines 25-33) ===
            # Line 25a: Federal income tax withheld from W-2
            "federal_withheld_w2": "topmostSubform[0].Page2[0].f2_11[0]",
            # Line 25b: Federal income tax withheld from 1099
            "federal_withheld_1099": "topmostSubform[0].Page2[0].f2_12[0]",
            # Line 25c: Other forms (see instructions)
            "federal_withheld_other": "topmostSubform[0].Page2[0].f2_13[0]",
            # Line 25d: Total (add 25a through 25c)
            "federal_withheld": "topmostSubform[0].Page2[0].f2_14[0]",
            # Line 26: Estimated tax payments (2023 est. + 2022 applied)
            "estimated_tax_payments": "topmostSubform[0].Page2[0].f2_15[0]",
            # Line 27: Earned income credit (EIC)
            "eic": "topmostSubform[0].Page2[0].f2_16[0]",
            # Line 28: Additional child tax credit from Schedule 8812
            "additional_child_tax_credit": "topmostSubform[0].Page2[0].f2_17[0]",
            # Line 29: American opportunity credit from Form 8863
            "american_opportunity_credit": "topmostSubform[0].Page2[0].f2_18[0]",
            # Line 30: Reserved for future use (f2_19, not mapped)
            # Line 31: Amount from Schedule 3, line 15
            "schedule3_payments": "topmostSubform[0].Page2[0].f2_20[0]",
            # Line 32: Total other payments and refundable credits
            "total_other_payments": "topmostSubform[0].Page2[0].f2_21[0]",
            # Line 33: Total payments (add lines 25d, 26, and 32)
            "total_payments": "topmostSubform[0].Page2[0].f2_22[0]",

            # === Page 2: Refund / Amount You Owe (Lines 34-38) ===
            # Line 34: Overpaid (if line 33 > line 24)
            "overpaid": "topmostSubform[0].Page2[0].f2_23[0]",
            # Line 35a: Amount of line 34 you want refunded to you
            "refund": "topmostSubform[0].Page2[0].f2_24[0]",
            # f2_25/f2_26 are RoutingNo/AccountNo (lines 35b/35d).
            # Line 36: Applied to next year (2024) estimated tax
            "applied_to_next_year": "topmostSubform[0].Page2[0].f2_27[0]",
            # Line 37: Amount you owe (if line 24 > line 33)
            "amount_owed": "topmostSubform[0].Page2[0].f2_28[0]",
            # Line 38: Estimated tax penalty
            "estimated_tax_penalty": "topmostSubform[0].Page2[0].f2_29[0]",
        },
        2024: {
            # === Page 1: Header ===
            # Names and SSNs are on Page1 directly (same field numbers as 2025).
            "first_name": "topmostSubform[0].Page1[0].f1_01[0]",
            "last_name": "topmostSubform[0].Page1[0].f1_02[0]",
            "ssn": "topmostSubform[0].Page1[0].f1_03[0]",
            "spouse_first_name": "topmostSubform[0].Page1[0].f1_04[0]",
            "spouse_last_name": "topmostSubform[0].Page1[0].f1_05[0]",
            "spouse_ssn": "topmostSubform[0].Page1[0].f1_06[0]",
            # Address fields live inside Address_ReadOrder in 2024.
            "address": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_10[0]",
            "apt_no": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_11[0]",
            "city": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_12[0]",
            "state": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_16[0]",
            "zip_code": "topmostSubform[0].Page1[0].Address_ReadOrder[0].f1_17[0]",

            # === Page 1: Income (Lines 1-11) ===
            # Lines 1a–1z (wages/salaries section) and 2a/2b/3a sit directly on
            # Page1 at f1_32–f1_45.
            # Line 1a: Wages, salaries, tips (W-2 box 1)
            "wages": "topmostSubform[0].Page1[0].f1_32[0]",
            # Line 1b: Household employee income
            "household_employee_income": "topmostSubform[0].Page1[0].f1_33[0]",
            # Line 1c: Tip income
            "tip_income": "topmostSubform[0].Page1[0].f1_34[0]",
            # Line 1d: Medicaid waiver payments
            "medicaid_waiver": "topmostSubform[0].Page1[0].f1_35[0]",
            # Line 1e: Taxable dependent care benefits
            "dependent_care_benefits": "topmostSubform[0].Page1[0].f1_36[0]",
            # Line 1f: Employer-provided adoption benefits
            "adoption_benefits": "topmostSubform[0].Page1[0].f1_37[0]",
            # Line 1g: Form 8919 wages
            "form_8919_wages": "topmostSubform[0].Page1[0].f1_38[0]",
            # Line 1h: Other earned income — type (f1_39) and amount (f1_40)
            "other_earned_income_type": "topmostSubform[0].Page1[0].f1_39[0]",
            "other_earned_income": "topmostSubform[0].Page1[0].f1_40[0]",
            # Line 1i: Nontaxable combat pay election
            "combat_pay_election": "topmostSubform[0].Page1[0].f1_41[0]",
            # Line 1z: Total of 1a through 1h
            "total_w2_income": "topmostSubform[0].Page1[0].f1_42[0]",
            # Line 2a: Tax-exempt interest
            "tax_exempt_interest": "topmostSubform[0].Page1[0].f1_43[0]",
            # Line 2b: Taxable interest
            "taxable_interest": "topmostSubform[0].Page1[0].f1_44[0]",
            # Line 3a: Qualified dividends
            "qualified_dividends": "topmostSubform[0].Page1[0].f1_45[0]",
            # Line 3b: Ordinary dividends (outside the Line4a-11 subform)
            "ordinary_dividends": "topmostSubform[0].Page1[0].f1_57[0]",

            # Lines 4a-9 live inside Line4a-11_ReadOrder[0].
            # Line 4a: IRA distributions
            "ira_distributions": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_46[0]",
            # Line 4b: IRA taxable amount
            "ira_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_47[0]",
            # Line 5a: Pensions and annuities
            "pensions": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_48[0]",
            # Line 5b: Pensions taxable amount
            "pensions_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_49[0]",
            # Line 5c: "Other" explanation (text field)
            "pensions_other_explanation": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_50[0]",
            # Line 6a: Social security benefits
            "social_security": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_51[0]",
            # Line 6b: Social security taxable amount
            "social_security_taxable": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_52[0]",
            # Line 7a: Capital gain or (loss)
            "capital_gain_loss": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_53[0]",
            # Line 7b: Amount for the "includes child's capital gain or (loss)" checkbox
            "child_capital_gain": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_54[0]",
            # Line 8: Additional income from Schedule 1, line 10 — the full Sch 1
            # line-10 total (`sch_1_line_10`), not the rental-only `other_income`
            # key (see the 2023 note above; footing fix, all years).
            "sch_1_line_10": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_55[0]",
            # Line 9: Total income
            "total_income": "topmostSubform[0].Page1[0].Line4a-11_ReadOrder[0].f1_56[0]",
            # Line 10: Adjustments to income from Schedule 1, line 26
            "adjustments": "topmostSubform[0].Page1[0].f1_58[0]",
            # Line 11a: Adjusted gross income
            "agi": "topmostSubform[0].Page1[0].f1_59[0]",

            # === Page 2: Tax and Credits (Lines 11b-24) ===
            # Page 2 field numbers are identical to 2025.
            # Line 11b (AGI repeated at top of page 2)
            "agi_page2": "topmostSubform[0].Page2[0].f2_01[0]",
            # Line 12: Standard deduction OR itemized deductions — the
            # deduction actually applied. Reads `applied_deduction` (not
            # `standard_deduction`, which is 0 when itemizing → would render
            # line 12 = 0 for itemizers).
            "applied_deduction": "topmostSubform[0].Page2[0].f2_02[0]",
            # Line 13a: Qualified business income deduction
            "qbi_deduction": "topmostSubform[0].Page2[0].f2_03[0]",
            # Line 13b: Additional deductions from Schedule 1-A
            "additional_deductions": "topmostSubform[0].Page2[0].f2_04[0]",
            # Line 14: Add lines 12, 13a, and 13b
            "total_deductions": "topmostSubform[0].Page2[0].f2_05[0]",
            # Line 15: Taxable income (line 11b minus line 14)
            "taxable_income": "topmostSubform[0].Page2[0].f2_06[0]",
            # Line 16: Tax
            "total_tax": "topmostSubform[0].Page2[0].f2_07[0]",
            # Line 17: Amount from Schedule 2, line 3
            "schedule2_tax": "topmostSubform[0].Page2[0].f2_08[0]",
            # Line 18: Add lines 16 and 17
            "tax_plus_schedule2": "topmostSubform[0].Page2[0].f2_09[0]",
            # Line 19: Child tax credit / credit for other dependents
            "child_tax_credit": "topmostSubform[0].Page2[0].f2_10[0]",
            # Line 20: Amount from Schedule 3, line 8
            "schedule3_credits": "topmostSubform[0].Page2[0].f2_11[0]",
            # Line 21: Add lines 19 and 20
            "total_credits": "topmostSubform[0].Page2[0].f2_12[0]",
            # Line 22: Subtract line 21 from line 18
            "tax_after_credits": "topmostSubform[0].Page2[0].f2_13[0]",
            # Line 23: Other taxes from Schedule 2, line 21
            "other_taxes": "topmostSubform[0].Page2[0].f2_14[0]",
            # Line 24: Total tax (add lines 22 and 23)
            "total_tax_liability": "topmostSubform[0].Page2[0].f2_15[0]",

            # === Page 2: Payments (Lines 25-33) ===
            # Line 25a: Federal income tax withheld from W-2
            "federal_withheld_w2": "topmostSubform[0].Page2[0].f2_16[0]",
            # Line 25b: Federal income tax withheld from 1099
            "federal_withheld_1099": "topmostSubform[0].Page2[0].f2_17[0]",
            # Line 25c: Other forms (see instructions)
            "federal_withheld_other": "topmostSubform[0].Page2[0].f2_18[0]",
            # Line 25d: Total (add 25a through 25c)
            "federal_withheld": "topmostSubform[0].Page2[0].f2_19[0]",
            # Line 26: Estimated tax payments
            "estimated_tax_payments": "topmostSubform[0].Page2[0].f2_20[0]",
            # Line 27a: Earned income credit (EIC)
            "eic": "topmostSubform[0].Page2[0].f2_21[0]",
            # Line 28: Additional child tax credit from Schedule 8812
            "additional_child_tax_credit": "topmostSubform[0].Page2[0].f2_22[0]",
            # Line 29: American opportunity credit from Form 8863
            "american_opportunity_credit": "topmostSubform[0].Page2[0].f2_23[0]",
            # Line 30: Refundable adoption credit from Form 8839
            "adoption_credit_8839": "topmostSubform[0].Page2[0].f2_27[0]",
            # Line 31: Amount from Schedule 3, line 15
            "schedule3_payments": "topmostSubform[0].Page2[0].f2_28[0]",
            # Line 32: Total other payments and refundable credits
            "total_other_payments": "topmostSubform[0].Page2[0].f2_29[0]",
            # Line 33: Total payments (add lines 25d, 26, and 32)
            "total_payments": "topmostSubform[0].Page2[0].f2_30[0]",

            # === Page 2: Refund / Amount You Owe (Lines 34-38) ===
            # Line 34: Overpaid (if line 33 > line 24)
            "overpaid": "topmostSubform[0].Page2[0].f2_31[0]",
            # Line 35a: Amount of line 34 you want refunded to you
            "refund": "topmostSubform[0].Page2[0].f2_32[0]",
            # Line 36: Applied to next year estimated tax
            "applied_to_next_year": "topmostSubform[0].Page2[0].f2_33[0]",
            # Line 37: Amount you owe (if line 24 > line 33)
            "amount_owed": "topmostSubform[0].Page2[0].f2_34[0]",
            # Line 38: Estimated tax penalty
            "estimated_tax_penalty": "topmostSubform[0].Page2[0].f2_35[0]",
        },
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
            # Line 5c: "Other" explanation (for the 3rd checkbox; 1=rollover, 2=PSO, 3=other)
            "pensions_other_explanation": "topmostSubform[0].Page1[0].f1_67[0]",
            # Line 6a: Social security benefits
            "social_security": "topmostSubform[0].Page1[0].f1_68[0]",
            # Line 6b: Social security taxable amount
            "social_security_taxable": "topmostSubform[0].Page1[0].f1_69[0]",
            # Line 7a: Capital gain or (loss)
            "capital_gain_loss": "topmostSubform[0].Page1[0].f1_70[0]",
            # Line 7b: Amount for the "includes child's capital gain or (loss)" checkbox
            "child_capital_gain": "topmostSubform[0].Page1[0].f1_71[0]",
            # Line 8: Additional income from Schedule 1, line 10 — the full Sch 1
            # line-10 total (`sch_1_line_10`), not the rental-only `other_income`
            # key (see the 2023 note above; footing fix, all years).
            "sch_1_line_10": "topmostSubform[0].Page1[0].f1_72[0]",
            # Line 9: Total income
            "total_income": "topmostSubform[0].Page1[0].f1_73[0]",
            # Line 10: Adjustments to income from Schedule 1, line 26
            "adjustments": "topmostSubform[0].Page1[0].f1_74[0]",
            # Line 11a: Adjusted gross income
            "agi": "topmostSubform[0].Page1[0].f1_75[0]",

            # === Page 2: Tax and Credits (Lines 11b-24) ===
            # Line 11b (AGI repeated at top of page 2)
            "agi_page2": "topmostSubform[0].Page2[0].f2_01[0]",
            # Line 12: Standard deduction OR itemized deductions — the
            # deduction actually applied. Reads `applied_deduction` (not
            # `standard_deduction`, which is 0 when itemizing → would render
            # line 12 = 0 for itemizers).
            "applied_deduction": "topmostSubform[0].Page2[0].f2_02[0]",
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
            "estimated_tax_payments": "topmostSubform[0].Page2[0].f2_21[0]",
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

