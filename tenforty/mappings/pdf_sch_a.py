"""PDF field mapping for IRS Schedule A (Itemized Deductions).

Field names enumerated from ``pdfs/federal/2025/f1040sa.pdf``. Positions
resolved via rect y-coordinates (higher y = top of page) — the right-
column amount cells (x≈504) are the line-totals (4, 7, 10, 14, 17);
the left-column x≈410 cells carry individual subparts.
"""

from tenforty.mappings.registry import PdfFormMapping, inherit_pdf_fields

_PAGE1 = "form1[0].Page1[0]"

_SCALARS_2025: dict[str, str] = {
    "taxpayer_name": f"{_PAGE1}.f1_1[0]",
    "taxpayer_ssn": f"{_PAGE1}.f1_2[0]",
    # Medical
    "sch_a_line_1_medical_gross": f"{_PAGE1}.f1_3[0]",
    "sch_a_line_2_agi": f"{_PAGE1}.Line2_ReadOrder[0].f1_4[0]",
    "sch_a_line_3_medical_floor": f"{_PAGE1}.f1_5[0]",
    "sch_a_line_4_medical_deductible": f"{_PAGE1}.f1_6[0]",
    # Taxes (SALT)
    "sch_a_line_5a_sales_tax_checkbox": f"{_PAGE1}.c1_1[0]",
    "sch_a_line_5a_state_income_tax": f"{_PAGE1}.f1_7[0]",
    "sch_a_line_5b_property_tax": f"{_PAGE1}.f1_8[0]",
    "sch_a_line_5c_personal_property_tax": f"{_PAGE1}.f1_9[0]",
    "sch_a_line_5d_salt_sum": f"{_PAGE1}.f1_10[0]",
    "sch_a_line_5e_salt_capped": f"{_PAGE1}.f1_11[0]",
    "sch_a_line_6_other_taxes": f"{_PAGE1}.f1_13[0]",
    "sch_a_line_7_taxes_total": f"{_PAGE1}.f1_14[0]",
    # Interest
    "sch_a_line_8a_mortgage_interest": f"{_PAGE1}.f1_15[0]",
    "sch_a_line_10_interest_total": f"{_PAGE1}.f1_22[0]",
    # Charity
    "sch_a_line_11_charity_cash": f"{_PAGE1}.f1_23[0]",
    "sch_a_line_12_charity_noncash": f"{_PAGE1}.f1_24[0]",
    "sch_a_line_14_charity_total": f"{_PAGE1}.f1_26[0]",
    # Casualty / other
    "sch_a_line_15_casualty": f"{_PAGE1}.f1_27[0]",
    "sch_a_line_16_other": f"{_PAGE1}.f1_29[0]",
    "sch_a_line_17_total": f"{_PAGE1}.f1_30[0]",
}


class PdfSchA(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule A"

    _MAPPINGS: dict[int, dict] = {
        2025: {"scalars": _SCALARS_2025, "repeaters": {}},
        # 2024 re-issue renamed the root container (form1[0] ->
        # topmostSubform[0]) and un-nested line 2's AGI cell out of
        # Line2_ReadOrder; everything else is unchanged (pinned by
        # tests/test_mapping_year_identity.py).
        2024: {
            "scalars": inherit_pdf_fields(
                _SCALARS_2025,
                root_swap=("form1[0]", "topmostSubform[0]"),
                overrides={
                    "sch_a_line_2_agi": "topmostSubform[0].Page1[0].f1_4[0]",
                },
            ),
            "repeaters": {},
        },
    }


# 2023's Schedule A field tree is byte-identical to 2024's (verified: identical
# AcroForm field-path sets), so 2023 reuses the 2024 payload unchanged. The
# fields-on-template gate re-verifies existence; the 2023 emit + parity gates
# verify positions.
PdfSchA._MAPPINGS[2023] = PdfSchA._MAPPINGS[2024]


# 2022's Schedule A field tree is byte-identical to 2023's (verified widget-level:
# same fully-qualified names, pages, and /Rects), so 2022 reuses the 2023 payload.
PdfSchA._MAPPINGS[2022] = PdfSchA._MAPPINGS[2023]
