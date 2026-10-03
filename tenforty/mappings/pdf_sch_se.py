"""PDF field mapping for IRS Schedule SE (Form 1040), Self-Employment Tax.

Flat scalars, Part I only. Years 2022-2025
(tenforty.years.SCHEDULE_C_FAMILY_YEARS). Field names were derived by
marker-probe and are pinned in tests/fixtures/golden_field_lines.py.

Every key tenforty/forms/sch_se.py emits maps directly -- including the
chain lines 2 and 4a, which the compute emits so the printed form's own
arithmetic is complete -- EXCEPT line 7
(sch_se_line_7_ss_wage_base): on all four templates the line-7 field is
READ-ONLY with the year's wage base pre-printed, so there is nothing to fill.

2022 zero-pads the first nine field leaves (f1_01..f1_09); 2023-2025 do not
(f1_1..f1_9). Leaves f1_10 and above are identical in all four years.
"""
from tenforty.mappings.registry import PdfFormMapping, inherit_pdf_fields

_P1 = "topmostSubform[0].Page1[0]"

_FIELDS_2023_2025: dict[str, str] = {
    "taxpayer_name": f"{_P1}.f1_1[0]",
    "taxpayer_ssn": f"{_P1}.f1_2[0]",
    "sch_se_line_2_net_profit": f"{_P1}.f1_5[0]",
    "sch_se_line_3_net_profit": f"{_P1}.f1_6[0]",
    "sch_se_line_4a_net_earnings": f"{_P1}.f1_7[0]",
    "sch_se_line_4c_net_earnings": f"{_P1}.f1_9[0]",
    "sch_se_line_6_total_net_earnings": f"{_P1}.f1_12[0]",
    "sch_se_line_8d_wages_subject_to_ss": f"{_P1}.f1_17[0]",
    "sch_se_line_9_ss_earnings_remaining": f"{_P1}.f1_18[0]",
    "sch_se_line_10_ss_portion": f"{_P1}.f1_19[0]",
    "sch_se_line_11_medicare_portion": f"{_P1}.f1_20[0]",
    "sch_se_line_12_se_tax": f"{_P1}.f1_21[0]",
    "sch_se_line_13_half_deduction": f"{_P1}.f1_22[0]",
}

_FIELDS_2022: dict[str, str] = inherit_pdf_fields(
    _FIELDS_2023_2025,
    overrides={
        "taxpayer_name": f"{_P1}.f1_01[0]",
        "taxpayer_ssn": f"{_P1}.f1_02[0]",
        "sch_se_line_2_net_profit": f"{_P1}.f1_05[0]",
        "sch_se_line_3_net_profit": f"{_P1}.f1_06[0]",
        "sch_se_line_4a_net_earnings": f"{_P1}.f1_07[0]",
        "sch_se_line_4c_net_earnings": f"{_P1}.f1_09[0]",
    },
)


class PdfSchSe(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule SE"

    _MAPPINGS: dict[int, dict] = {
        2022: _FIELDS_2022,
        2023: _FIELDS_2023_2025,
        2024: _FIELDS_2023_2025,
        2025: _FIELDS_2023_2025,
    }
