# 2025 Field Coverage

Fields verified through round-trip PDF tests: engine → translate → fill PDF → read back.

15 of 69 f1040 PDF fields are currently exercised by round-trip tests.

## f1040 (Form 1040)

### Page 1 — Header

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| first_name | 1040 header | — |
| last_name | 1040 header | — |
| ssn | 1040 header | — |
| spouse_first_name | 1040 header | — |
| spouse_last_name | 1040 header | — |
| spouse_ssn | 1040 header | — |
| address | 1040 header | — |
| apt_no | 1040 header | — |
| city | 1040 header | — |
| state | 1040 header | — |
| zip_code | 1040 header | — |

### Page 1 — Income

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| wages | 1040 L1a | simple_w2, w2_investments, itemized, max_income, max_deductions |
| household_employee_income | 1040 L1b | — |
| tip_income | 1040 L1c | — |
| medicaid_waiver | 1040 L1d | — |
| dependent_care_benefits | 1040 L1e | — |
| adoption_benefits | 1040 L1f | — |
| form_8919_wages | 1040 L1g | — |
| strike_benefits | 1040 L1h | — |
| stock_option_income | 1040 L1i | — |
| total_w2_income | 1040 L1z | — |
| tax_exempt_interest | 1040 L2a | — |
| taxable_interest | 1040 L2b | simple_w2, w2_investments, max_income, max_deductions |
| qualified_dividends | 1040 L3a | w2_investments, max_income, max_deductions |
| ordinary_dividends | 1040 L3b | w2_investments, max_income, max_deductions |
| ira_distributions | 1040 L4a | — |
| ira_taxable | 1040 L4b | — |
| pensions | 1040 L5a | — |
| pensions_taxable | 1040 L5b | — |
| social_security | 1040 L6a | — |
| social_security_taxable | 1040 L6b | — |
| lump_sum_election | 1040 L6c | — |
| capital_gain_loss | 1040 L7 | — |
| other_income | 1040 L8 | — |
| total_income | 1040 L9 | simple_w2, w2_investments, itemized, max_income, max_deductions |
| adjustments | 1040 L10 | — |
| agi | 1040 L11 | simple_w2, w2_investments, itemized, max_income, max_deductions |

### Page 2 — Tax and Credits

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| agi_page2 | 1040 L11b | simple_w2, w2_investments, itemized, max_income, max_deductions |
| standard_deduction | 1040 L12e | simple_w2, w2_investments, max_income |
| qbi_deduction | 1040 L13a | — |
| additional_deductions | 1040 L13b | — |
| total_deductions | 1040 L14 | simple_w2, w2_investments, itemized, max_income, max_deductions |
| taxable_income | 1040 L15 | simple_w2, w2_investments, itemized, max_income, max_deductions |
| total_tax | 1040 L16 | simple_w2, w2_investments, itemized, max_income, max_deductions |
| schedule2_tax | 1040 L17 | — |
| tax_plus_schedule2 | 1040 L18 | — |
| child_tax_credit | 1040 L19 | — |
| schedule3_credits | 1040 L20 | — |
| total_credits | 1040 L21 | — |
| tax_after_credits | 1040 L22 | — |
| other_taxes | 1040 L23 | — |
| total_tax_liability | 1040 L24 | — |

### Page 2 — Payments

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| federal_withheld_w2 | 1040 L25a | simple_w2, w2_investments, itemized, max_income, max_deductions |
| federal_withheld_1099 | 1040 L25b | — |
| federal_withheld_other | 1040 L25c | — |
| federal_withheld | 1040 L25d | simple_w2, w2_investments, itemized, max_income, max_deductions |
| estimated_payments | 1040 L26 | — |
| eic | 1040 L27a | — |
| additional_child_tax_credit | 1040 L28 | — |
| american_opportunity_credit | 1040 L29 | — |
| adoption_credit_8839 | 1040 L30 | — |
| schedule3_payments | 1040 L31 | — |
| total_other_payments | 1040 L32 | — |
| total_payments | 1040 L33 | simple_w2, w2_investments, itemized, max_income, max_deductions |

### Page 2 — Refund / Amount Owed

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| overpaid | 1040 L34 | simple_w2, w2_investments, itemized, max_income, max_deductions |
| refund | 1040 L35a | — |
| applied_to_next_year | 1040 L36 | — |
| amount_owed | 1040 L37 | — |
| estimated_tax_penalty | 1040 L38 | — |

## Schedule A (Itemized Deductions)

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| mortgage_interest | Sch A L8a | itemized, max_deductions |
| property_tax | Sch A L5b | itemized, max_deductions |

*Note: Schedule A PDF mapping not yet created. These fields are written to the XLS
and verified via engine output (`total_deductions`), but not yet round-trip verified
through a Schedule A PDF.*

## Schedule D (Capital Gains)

| Key | Form/Line | Exercised By |
|-----|-----------|--------------|
| schd_line16 | Sch D L16 | max_income (via cap gain distributions) |

*Note: Schedule D PDF mapping not yet created.*
