"""PDF field mapping for IRS Form 4868.

Maps computed result/config keys to the PDF form field names in the IRS's
fillable f4868.pdf. Field names are opaque (f1_4, c1_1, etc.) — this
mapping was built by filling each field with a probe marker and visually
identifying which 4868 line it corresponds to.

Field names use the full path format:
    topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_4[0]

Probe methodology: each text field was filled with its short name (e.g.
"f1_4"), the PDF was rendered to PNG via pdftoppm, and the marker's
position on the rendered page was matched to the printed label.
"""

from tenforty.mappings.registry import PdfFormMapping


class Pdf4868(PdfFormMapping[dict[str, str]]):
    """PDF field mapping for IRS Form 4868 (Automatic Extension)."""

    _FORM_NAME = "Form 4868"

    # Note on checkboxes: c1_1 and c1_2 are /Btn (checkbox) fields.
    # PdfFiller currently writes text values only; checkbox /Btn fields
    # require an On/Off value rather than a string. They are declared here
    # for completeness — the mapping documents the correct field names, but
    # PdfFiller will need future work to handle /Btn fields.  The default
    # state (unchecked) is correct for the typical extension filing.

    _MAPPINGS: dict[int, dict[str, str]] = {
        2024: {
            # === VoucherHeader — fiscal-year date fields ===
            "fiscal_year_begin": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_1[0]",
            "fiscal_year_end_month": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_2[0]",
            "fiscal_year_end_year": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_3[0]",

            # === Part I — Identification ===
            # 2024 uses Part1_ReadOrder (not PartI_ReadOrder as in 2025).
            "full_name": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_4[0]",
            "address": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_5[0]",
            "address_city": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_6[0]",
            "address_state": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_7[0]",
            "address_zip": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_8[0]",
            "ssn": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_9[0]",
            "spouse_ssn": "topmostSubform[0].Page1[0].Part1_ReadOrder[0].f1_10[0]",

            # === Part II — Individual Income Tax ===
            "estimated_total_tax": "topmostSubform[0].Page1[0].f1_11[0]",
            "total_payments": "topmostSubform[0].Page1[0].f1_12[0]",
            "balance_due": "topmostSubform[0].Page1[0].f1_13[0]",
            "amount_paying_with_extension": "topmostSubform[0].Page1[0].f1_14[0]",
            "out_of_country": "topmostSubform[0].Page1[0].c1_1[0]",
            "nonresident_alien": "topmostSubform[0].Page1[0].c1_2[0]",

            # === Form 4868-V payment voucher ===
            # 2024 uses Col3 (not Col4 as in 2025).
            "voucher_amount": "topmostSubform[0].Page3[0].Col3[0].f3_1[0]",
        },
        2025: {
            # === VoucherHeader — fiscal-year date fields ===
            # These appear in the header line: "For calendar year 2025, or
            # other tax year beginning ____, 2025, and ending ____, 20__."
            # Calendar-year filers leave these blank.
            "fiscal_year_begin": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_1[0]",
            "fiscal_year_end_month": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_2[0]",
            "fiscal_year_end_year": "topmostSubform[0].Page1[0].VoucherHeader[0].f1_3[0]",

            # === Part I — Identification ===
            # Line 1: Your name(s) — one combined field for the full name
            "full_name": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_4[0]",
            # Address line
            "address": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_5[0]",
            # City, town, or post office
            "address_city": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_6[0]",
            # State (MaxLen=2)
            "address_state": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_7[0]",
            # ZIP code
            "address_zip": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_8[0]",
            # Line 2: Your social security number
            "ssn": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_9[0]",
            # Line 3: Spouse's social security number (MFJ)
            "spouse_ssn": "topmostSubform[0].Page1[0].PartI_ReadOrder[0].f1_10[0]",

            # === Part II — Individual Income Tax ===
            # Line 4: Estimate of total tax liability for 2025
            "estimated_total_tax": "topmostSubform[0].Page1[0].f1_11[0]",
            # Line 5: Total 2025 payments
            "total_payments": "topmostSubform[0].Page1[0].f1_12[0]",
            # Line 6: Balance due (line 4 − line 5, not less than 0)
            "balance_due": "topmostSubform[0].Page1[0].f1_13[0]",
            # Line 7: Amount you're paying with this extension
            "amount_paying_with_extension": "topmostSubform[0].Page1[0].f1_14[0]",
            # Line 8: "Out of the country" checkbox (/Btn — see class note)
            "out_of_country": "topmostSubform[0].Page1[0].c1_1[0]",
            # Line 9: Nonresident alien filing 1040-NR checkbox (/Btn — see class note)
            "nonresident_alien": "topmostSubform[0].Page1[0].c1_2[0]",

            # === Form 4868-V payment voucher (Page3 in XFA structure) ===
            # Dollar amount on the detachable payment voucher
            "voucher_amount": "topmostSubform[0].Page3[0].Col4[0].f3_1[0]",
        },
    }


# 2023's Form 4868 field tree is byte-identical to 2024's (verified: identical
# AcroForm field-path sets), so 2023 reuses the 2024 payload unchanged. The
# fields-on-template gate re-verifies existence; the 2023 emit + parity gates
# verify positions.
Pdf4868._MAPPINGS[2023] = Pdf4868._MAPPINGS[2024]
