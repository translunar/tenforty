"""PDF field mapping for IRS Schedule 2 (Form 1040), Additional Taxes.

Flat scalars. Years 2022-2025 only (tenforty.years.SCHEDULE_C_FAMILY_YEARS).
Field names were derived by marker-probe (scripts/probe_pdf_fields.py) and
are pinned line-by-line in tests/fixtures/golden_field_lines.py.

Part I was renumbered in 2024: the excess advance premium tax credit
repayment moved from line 2 to line 1a and a line 1z subtotal was added (see
tenforty/forms/sch_2.py). The alternative minimum tax box is deliberately
unmapped in every year -- it is unmodeled and stays blank.

2025 added an exemption-number box (f1_14) ahead of the line 4 amount, which
shifted lines 4 and 11 by one field and dropped one field from page 2.
"""
from tenforty.mappings.registry import PdfFormMapping

_P1 = "form1[0].Page1[0]"
_P2 = "form1[0].Page2[0]"

_FIELDS_2022_2023: dict[str, str] = {
    "taxpayer_name": f"{_P1}.f1_01[0]",
    "taxpayer_ssn": f"{_P1}.f1_02[0]",
    "sch_2_line_2_excess_aptc_repayment": f"{_P1}.f1_04[0]",
    "sch_2_line_3_part_i_total": f"{_P1}.f1_05[0]",
    "sch_2_line_4_se_tax": f"{_P1}.f1_06[0]",
    "sch_2_line_11_additional_medicare_tax": f"{_P1}.f1_13[0]",
    "sch_2_line_21_total_other_taxes": f"{_P2}.f2_25[0]",
}

_FIELDS_2024: dict[str, str] = {
    "taxpayer_name": f"{_P1}.f1_01[0]",
    "taxpayer_ssn": f"{_P1}.f1_02[0]",
    "sch_2_line_1a_excess_aptc_repayment":
        f"{_P1}.Line1a_ReadOrder[0].f1_03[0]",
    "sch_2_line_1z_total_additions": f"{_P1}.f1_11[0]",
    "sch_2_line_3_part_i_total": f"{_P1}.f1_13[0]",
    "sch_2_line_4_se_tax": f"{_P1}.f1_14[0]",
    "sch_2_line_11_additional_medicare_tax": f"{_P1}.f1_21[0]",
    "sch_2_line_21_total_other_taxes": f"{_P2}.f2_25[0]",
}

_FIELDS_2025: dict[str, str] = {
    **_FIELDS_2024,
    "sch_2_line_4_se_tax": f"{_P1}.f1_15[0]",
    "sch_2_line_11_additional_medicare_tax": f"{_P1}.f1_22[0]",
    "sch_2_line_21_total_other_taxes": f"{_P2}.f2_24[0]",
}


class PdfSch2(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule 2"

    _MAPPINGS: dict[int, dict] = {
        2022: _FIELDS_2022_2023,
        2023: _FIELDS_2022_2023,
        2024: _FIELDS_2024,
        2025: _FIELDS_2025,
    }
