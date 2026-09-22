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
}
