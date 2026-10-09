# tests/fixtures/golden_field_lines.py
"""Golden field->line expectations for Form 1040 and Schedule 1 money lines.

PROVENANCE: derived by MARKER-PROBE — every text field on each year's blank
IRS template was stamped with its own field name (scripts/probe_pdf_fields.py),
rendered, and read via `pdftotext -layout` against the printed line labels. The
IRS templates in this repo carry NO /TU tooltips, so the marker-probe (the same
method the mappings were built with) is the authoritative line-identity source.

Each entry maps a semantic result key -> (leaf field name, IRS line number the
field prints on). tests/test_mapping_line_identity.py pins the live mapping to
these leaves (catching the shifted-but-existing failure class that the
fields-on-template existence gate cannot) and, when pdftotext is available,
re-derives the probe to prove the leaf really lands on the stated line.

REGENERATE: re-run the marker-probe per year and re-read the money-line rows;
see the audit harness in the f1040-2024-layout-fix branch history. Line 10 and
line 26 of Schedule 1 (whose printed descriptions reference OTHER line numbers,
e.g. "Combine lines 1 through 7 and 9") were confirmed by reading the raw probe
row, since a naive leftmost/nearest-label parser mis-associates those rows."""

GOLDEN_FIELD_LINES: dict = {
    ("federal", "1040", 2021): {
        "adjustments": ("f1_42", "10"),
        "agi": ("f1_43", "11"),
        "taxable_income": ("f1_49", "15"),
        "total_tax": ("f2_02", "16"),
        "tax_liability_line24": ("f2_10", "24"),
        "total_payments": ("f2_24", "33"),
        "overpaid": ("f2_25", "34"),
        "refund": ("f2_26", "35a"),
        "amount_owed": ("f2_30", "37"),
    },
    ("federal", "1040", 2022): {
        "adjustments": ("f1_51", "10"),
        "agi": ("f1_52", "11"),
        "taxable_income": ("f1_56", "15"),
        "total_tax": ("f2_02", "16"),
        "tax_liability_line24": ("f2_10", "24"),
        "total_payments": ("f2_22", "33"),
        "overpaid": ("f2_23", "34"),
        "refund": ("f2_24", "35a"),
        "amount_owed": ("f2_28", "37"),
    },
    ("federal", "1040", 2023): {
        "adjustments": ("f1_54", "10"),
        "agi": ("f1_55", "11"),
        "taxable_income": ("f1_59", "15"),
        "total_tax": ("f2_02", "16"),
        "tax_liability_line24": ("f2_10", "24"),
        "total_payments": ("f2_22", "33"),
        "overpaid": ("f2_23", "34"),
        "refund": ("f2_24", "35a"),
        "amount_owed": ("f2_28", "37"),
    },
    ("federal", "1040", 2024): {
        "adjustments": ("f1_55", "10"),
        "agi": ("f1_56", "11"),
        "taxable_income": ("f1_60", "15"),
        "total_tax": ("f2_02", "16"),
        "tax_liability_line24": ("f2_10", "24"),
        "total_payments": ("f2_22", "33"),
        "overpaid": ("f2_23", "34"),
        "refund": ("f2_24", "35a"),
        "amount_owed": ("f2_28", "37"),
    },
    ("federal", "1040", 2025): {
        "adjustments": ("f1_74", "10"),
        "agi": ("f1_75", "11a"),
        "taxable_income": ("f2_06", "15"),
        "total_tax": ("f2_08", "16"),
        "tax_liability_line24": ("f2_16", "24"),
        "total_payments": ("f2_29", "33"),
        "overpaid": ("f2_30", "34"),
        "refund": ("f2_31", "35a"),
        "amount_owed": ("f2_35", "37"),
    },
    ("federal", "sch_1", 2021): {
        "sch_1_line_1_taxable_refunds": ("f1_03", "1"),
        "sch_1_line_7_unemployment": ("f1_10", "7"),
        "sch_1_line_10_total_additional_income": ("f1_31", "10"),
        "sch_1_line_26_total_adjustments": ("f2_31", "26"),
    },
    ("federal", "sch_1", 2022): {
        "sch_1_line_1_taxable_refunds": ("f1_03", "1"),
        "sch_1_line_7_unemployment": ("f1_10", "7"),
        "sch_1_line_10_total_additional_income": ("f1_36", "10"),
        "sch_1_line_26_total_adjustments": ("f2_31", "26"),
    },
    ("federal", "sch_1", 2023): {
        "sch_1_line_1_taxable_refunds": ("f1_03", "1"),
        "sch_1_line_7_unemployment": ("f1_10", "7"),
        "sch_1_line_10_total_additional_income": ("f1_36", "10"),
        "sch_1_line_26_total_adjustments": ("f2_31", "26"),
    },
    ("federal", "sch_1", 2024): {
        "sch_1_line_1_taxable_refunds": ("f1_04", "1"),
        "sch_1_line_7_unemployment": ("f1_11", "7"),
        "sch_1_line_10_total_additional_income": ("f1_38", "10"),
        "sch_1_line_26_total_adjustments": ("f2_31", "26"),
    },
    ("federal", "sch_1", 2025): {
        "sch_1_line_1_taxable_refunds": ("f1_04", "1"),
        "sch_1_line_7_unemployment": ("f1_12", "7"),
        "sch_1_line_10_total_additional_income": ("f1_38", "10"),
        "sch_1_line_26_total_adjustments": ("f2_30", "26"),
    },
    # Schedule A money lines. 2021-2024 share one field numbering; the 2025
    # re-issue dropped four write-in fields ahead of the amount boxes (line 6
    # lost one, line 8b one, line 16 two), so every leaf from line 6 down
    # differs. Lines 6 and 16 each have a description field on the same row as
    # the amount box, which the row-token probe cannot tell apart -- the
    # amount-column geometry test in tests/test_pdf_sch_a_mapping.py does.
    **{
        ("federal", "sch_a", year): {
            "sch_a_line_1_medical_gross": ("f1_3", "1"),
            "sch_a_line_2_agi": ("f1_4", "2"),
            "sch_a_line_3_medical_floor": ("f1_5", "3"),
            "sch_a_line_4_medical_deductible": ("f1_6", "4"),
            "sch_a_line_5a_state_income_tax": ("f1_7", "5a"),
            "sch_a_line_5b_property_tax": ("f1_8", "5b"),
            "sch_a_line_5c_personal_property_tax": ("f1_9", "5c"),
            "sch_a_line_5d_salt_sum": ("f1_10", "5d"),
            "sch_a_line_5e_salt_capped": ("f1_11", "5e"),
            "sch_a_line_6_other_taxes": (line_6, "6"),
            "sch_a_line_7_taxes_total": (line_7, "7"),
            "sch_a_line_8a_mortgage_interest": (line_8a, "8a"),
            "sch_a_line_10_interest_total": (line_10, "10"),
            "sch_a_line_11_charity_cash": (line_11, "11"),
            "sch_a_line_12_charity_noncash": (line_12, "12"),
            "sch_a_line_14_charity_total": (line_14, "14"),
            "sch_a_line_15_casualty": (line_15, "15"),
            "sch_a_line_16_other": (line_16, "16"),
            "sch_a_line_17_total": (line_17, "17"),
        }
        for year, (line_6, line_7, line_8a, line_10, line_11, line_12,
                   line_14, line_15, line_16, line_17) in (
            *((y, ("f1_14", "f1_15", "f1_16", "f1_24", "f1_25", "f1_26",
                   "f1_28", "f1_29", "f1_33", "f1_34"))
              for y in (2021, 2022, 2023, 2024)),
            (2025, ("f1_13", "f1_14", "f1_15", "f1_22", "f1_23", "f1_24",
                    "f1_26", "f1_27", "f1_29", "f1_30")),
        )
    },
    # Schedule E page-2 Part II/III totals. Line 41 is the form-true grand
    # total (line 26 + line 32) bound to the line-41 box; the prior mapping
    # bound the pte-only subtotal to line 39's field (2022-2025) and line 37
    # to line 35's field. 2021 uses its own field numbering (f2_61/f2_69).
    ("federal", "sch_e", 2021): {
        "sch_e_line_26_total": ("f1_84", "26"),
        "sch_e_line_32_total_partnership_scorp": ("f2_42", "32"),
        "sch_e_line_37_total_estate_trust": ("f2_61", "37"),
        "sch_e_line_41_total_income": ("f2_69", "41"),
    },
    ("federal", "sch_e", 2022): {
        "sch_e_line_26_total": ("f1_84", "26"),
        "sch_e_line_32_total_partnership_scorp": ("f2_47", "32"),
        "sch_e_line_37_total_estate_trust": ("f2_70", "37"),
        "sch_e_line_41_total_income": ("f2_78", "41"),
    },
    ("federal", "sch_e", 2023): {
        "sch_e_line_26_total": ("f1_84", "26"),
        "sch_e_line_32_total_partnership_scorp": ("f2_47", "32"),
        "sch_e_line_37_total_estate_trust": ("f2_70", "37"),
        "sch_e_line_41_total_income": ("f2_78", "41"),
    },
    ("federal", "sch_e", 2024): {
        "sch_e_line_26_total": ("f1_84", "26"),
        "sch_e_line_32_total_partnership_scorp": ("f2_47", "32"),
        "sch_e_line_37_total_estate_trust": ("f2_70", "37"),
        "sch_e_line_41_total_income": ("f2_78", "41"),
    },
    ("federal", "sch_e", 2025): {
        "sch_e_line_26_total": ("f1_84", "26"),
        "sch_e_line_32_total_partnership_scorp": ("f2_47", "32"),
        "sch_e_line_37_total_estate_trust": ("f2_70", "37"),
        "sch_e_line_41_total_income": ("f2_78", "41"),
    },
    # Schedule 2. Part I was renumbered in 2024: the excess-APTC repayment
    # moved from line 2 to line 1a (with a new 1z subtotal).
    ("federal", "sch_2", 2021): {
        "sch_2_line_2_excess_aptc_repayment": ("f1_04", "2"),
        "sch_2_line_3_part_i_total": ("f1_05", "3"),
        "sch_2_line_4_se_tax": ("f1_06", "4"),
        "sch_2_line_11_additional_medicare_tax": ("f1_13", "11"),
        "sch_2_line_21_total_other_taxes": ("f2_25", "21"),
    },
    ("federal", "sch_2", 2022): {
        "sch_2_line_2_excess_aptc_repayment": ("f1_04", "2"),
        "sch_2_line_3_part_i_total": ("f1_05", "3"),
        "sch_2_line_4_se_tax": ("f1_06", "4"),
        "sch_2_line_11_additional_medicare_tax": ("f1_13", "11"),
        "sch_2_line_21_total_other_taxes": ("f2_25", "21"),
    },
    ("federal", "sch_2", 2023): {
        "sch_2_line_2_excess_aptc_repayment": ("f1_04", "2"),
        "sch_2_line_3_part_i_total": ("f1_05", "3"),
        "sch_2_line_4_se_tax": ("f1_06", "4"),
        "sch_2_line_11_additional_medicare_tax": ("f1_13", "11"),
        "sch_2_line_21_total_other_taxes": ("f2_25", "21"),
    },
    ("federal", "sch_2", 2024): {
        "sch_2_line_1a_excess_aptc_repayment": ("f1_03", "1a"),
        "sch_2_line_1z_total_additions": ("f1_11", "1z"),
        "sch_2_line_3_part_i_total": ("f1_13", "3"),
        "sch_2_line_4_se_tax": ("f1_14", "4"),
        "sch_2_line_11_additional_medicare_tax": ("f1_21", "11"),
        "sch_2_line_21_total_other_taxes": ("f2_25", "21"),
    },
    ("federal", "sch_2", 2025): {
        "sch_2_line_1a_excess_aptc_repayment": ("f1_03", "1a"),
        "sch_2_line_1z_total_additions": ("f1_11", "1z"),
        "sch_2_line_3_part_i_total": ("f1_13", "3"),
        "sch_2_line_4_se_tax": ("f1_15", "4"),
        "sch_2_line_11_additional_medicare_tax": ("f1_22", "11"),
        "sch_2_line_21_total_other_taxes": ("f2_24", "21"),
    },
    # Schedule SE. 2021-2022 zero-pad the first nine leaves (f1_06); 2023+ do
    # not (f1_6). Line 7 is a read-only pre-printed field and is not mapped.
    **{
        ("federal", "sch_se", year): {
            "sch_se_line_2_net_profit": ("f1_05", "2"),
            "sch_se_line_3_net_profit": ("f1_06", "3"),
            "sch_se_line_4a_net_earnings": ("f1_07", "4a"),
            "sch_se_line_4c_net_earnings": ("f1_09", "4c"),
            "sch_se_line_6_total_net_earnings": ("f1_12", "6"),
            "sch_se_line_8a_ss_wages_and_tips": ("f1_14", "8a"),
            "sch_se_line_8d_wages_subject_to_ss": ("f1_17", "8d"),
            "sch_se_line_9_ss_earnings_remaining": ("f1_18", "9"),
            "sch_se_line_10_ss_portion": ("f1_19", "10"),
            "sch_se_line_11_medicare_portion": ("f1_20", "11"),
            "sch_se_line_12_se_tax": ("f1_21", "12"),
            "sch_se_line_13_half_deduction": ("f1_22", "13"),
        }
        for year in (2021, 2022)
    },
    **{
        ("federal", "sch_se", year): {
            "sch_se_line_2_net_profit": ("f1_5", "2"),
            "sch_se_line_3_net_profit": ("f1_6", "3"),
            "sch_se_line_4a_net_earnings": ("f1_7", "4a"),
            "sch_se_line_4c_net_earnings": ("f1_9", "4c"),
            "sch_se_line_6_total_net_earnings": ("f1_12", "6"),
            "sch_se_line_8a_ss_wages_and_tips": ("f1_14", "8a"),
            "sch_se_line_8d_wages_subject_to_ss": ("f1_17", "8d"),
            "sch_se_line_9_ss_earnings_remaining": ("f1_18", "9"),
            "sch_se_line_10_ss_portion": ("f1_19", "10"),
            "sch_se_line_11_medicare_portion": ("f1_20", "11"),
            "sch_se_line_12_se_tax": ("f1_21", "12"),
            "sch_se_line_13_half_deduction": ("f1_22", "13"),
        }
        for year in (2023, 2024, 2025)
    },
    # Schedule C money lines. "Other expenses (from line 48)" is line 27a
    # through 2024 and line 27b in 2025 -- same field, relabelled.
    **{
        ("federal", "sch_c", year): {
            "sch_c_line_1_gross_receipts": ("f1_10", "1"),
            "sch_c_line_3_net_receipts": ("f1_12", "3"),
            "sch_c_line_5_gross_profit": ("f1_14", "5"),
            "sch_c_line_7_gross_income": ("f1_16", "7"),
            "sch_c_expense_advertising": ("f1_17", "8"),
            "sch_c_expense_insurance": ("f1_24", "15"),
            "sch_c_expense_legal_professional": ("f1_27", "17"),
            "sch_c_expense_office_expense": ("f1_28", "18"),
            "sch_c_expense_rent_lease": ("f1_31", "20b"),
            "sch_c_expense_supplies": ("f1_33", "22"),
            "sch_c_expense_taxes_licenses": ("f1_34", "23"),
            "sch_c_expense_travel": ("f1_35", "24a"),
            "sch_c_expense_deductible_meals": ("f1_36", "24b"),
            "sch_c_expense_utilities": ("f1_37", "25"),
            "sch_c_expense_wages": ("f1_38", "26"),
            "sch_c_expense_other_expenses": ("f1_39", other_expenses_line),
            "sch_c_line_28_total_expenses": ("f1_41", "28"),
            "sch_c_line_29_tentative_profit": ("f1_42", "29"),
            "sch_c_line_31_net_profit": ("f1_46", "31"),
            "sch_c_line_48_total_other_expenses": ("f2_33", "48"),
        }
        for year, other_expenses_line in (
            (2021, "27a"), (2022, "27a"), (2023, "27a"), (2024, "27a"),
            (2025, "27b"),
        )
    },
}
