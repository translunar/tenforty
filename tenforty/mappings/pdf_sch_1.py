"""PDF field mapping for IRS Schedule 1 (Additional Income & Adjustments).

V1 scope: Part I lines 1, 3, 4, 5, 6, 7, 10 (total additional income) and
Part II lines 11, 13, 15, 17, 20, 21, 26 (total adjustments). Other line
subparts (8a–8z "other income", 24a–24z "other adjustments", 19a alimony
paid, etc.) are in scope of the form but not populated by v1 compute —
they remain blank on the filled PDF.

Field names enumerated from ``pdfs/federal/2025/f1040s1.pdf``. Position
mapping (amount column x≈504, rows top-to-bottom) determined which
f1_NN/f2_NN field corresponds to which IRS line number.
"""

from tenforty.mappings.registry import PdfFormMapping, inherit_pdf_fields

_PAGE1 = "topmostSubform[0].Page1[0]"
_PAGE2 = "topmostSubform[0].Page2[0]"

_SCALARS_2025: dict[str, str] = {
    # Header
    "taxpayer_name": f"{_PAGE1}.f1_01[0]",
    "taxpayer_ssn": f"{_PAGE1}.f1_02[0]",
    # Part I — Additional Income
    "sch_1_line_1_taxable_refunds": f"{_PAGE1}.f1_03[0]",
    "sch_1_line_3_business_income": f"{_PAGE1}.f1_07[0]",
    "sch_1_line_4_other_gains": f"{_PAGE1}.f1_08[0]",
    "sch_1_line_5_rental_re_royalty": f"{_PAGE1}.f1_09[0]",
    "sch_1_line_6_farm_income": f"{_PAGE1}.f1_10[0]",
    "sch_1_line_7_unemployment": f"{_PAGE1}.f1_12[0]",
    "sch_1_line_10_total_additional_income": f"{_PAGE1}.f1_37[0]",
    # Part II — Adjustments
    "sch_1_line_11_educator": f"{_PAGE2}.f2_01[0]",
    "sch_1_line_13_hsa": f"{_PAGE2}.f2_03[0]",
    "sch_1_line_15_se_tax": f"{_PAGE2}.f2_05[0]",
    "sch_1_line_17_se_health": f"{_PAGE2}.f2_07[0]",
    "sch_1_line_20_ira": f"{_PAGE2}.f2_12[0]",
    "sch_1_line_21_student_loan_interest": f"{_PAGE2}.f2_13[0]",
    "sch_1_line_26_total_adjustments": f"{_PAGE2}.f2_29[0]",
}


class PdfSch1(PdfFormMapping[dict]):
    _FORM_NAME = "Schedule 1"

    _MAPPINGS: dict[int, dict] = {
        2025: {"scalars": _SCALARS_2025, "repeaters": {}},
        # 2024 re-issue renamed the root container (topmostSubform[0] ->
        # form1[0], the opposite direction from Schedule A) and moved two
        # fields: line 7 (unemployment) nests inside Line8a_ReadOrder, and
        # line 10's total shifted field number (f1_37 -> f1_33) because of
        # that nesting. Everything else is unchanged (pinned by
        # tests/test_mapping_year_identity.py).
        2024: {
            "scalars": inherit_pdf_fields(
                _SCALARS_2025,
                root_swap=("topmostSubform[0]", "form1[0]"),
                overrides={
                    "sch_1_line_7_unemployment":
                        "form1[0].Page1[0].Line8a_ReadOrder[0].f1_12[0]",
                    "sch_1_line_10_total_additional_income":
                        "form1[0].Page1[0].f1_33[0]",
                },
            ),
            "repeaters": {},
        },
        # 2023 keeps the form1[0] root but the IRS renumbered Part I: a
        # top-of-Schedule-1 1099-K entry field added in 2024 shifted lines
        # 3-7 down one field number, line 7 (unemployment) is flat (not
        # nested in Line8a_ReadOrder), line 10's total moved, and line 26
        # shifted because the line-24 "other adjustments" block differs in
        # field count. Every path rendered-position probed against
        # pdfs/federal/2023/f1040s1.probe.pdf (the differ reports CHANGED, and
        # several 2024 field numbers exist on the 2023 template at DIFFERENT
        # lines — inheritance would silently mis-map, so these are probed).
        2023: {
            "scalars": inherit_pdf_fields(
                _SCALARS_2025,
                root_swap=("topmostSubform[0]", "form1[0]"),
                overrides={
                    "sch_1_line_3_business_income":
                        "form1[0].Page1[0].f1_06[0]",
                    "sch_1_line_4_other_gains":
                        "form1[0].Page1[0].f1_07[0]",
                    "sch_1_line_5_rental_re_royalty":
                        "form1[0].Page1[0].f1_08[0]",
                    "sch_1_line_6_farm_income":
                        "form1[0].Page1[0].f1_09[0]",
                    "sch_1_line_7_unemployment":
                        "form1[0].Page1[0].f1_10[0]",
                    "sch_1_line_10_total_additional_income":
                        "form1[0].Page1[0].f1_36[0]",
                    "sch_1_line_26_total_adjustments":
                        "form1[0].Page2[0].f2_31[0]",
                },
            ),
            "repeaters": {},
        },
    }


# 2022's Schedule 1 keeps 2023's identical field-NAME inventory and the same
# mapped paths (form1[0] root). Widget geometry has two isolated sub-row nudges
# vs 2023 (header SSN -1pt; line-10 total f1_36 +12pt), neither changing a line:
# marker-probed on pdfs/federal/2022/f1040s1.probe.pdf, f1_36 renders on line 10
# and every mapped field on its 2023 line. So 2022 reuses the 2023 payload.
PdfSch1._MAPPINGS[2022] = PdfSch1._MAPPINGS[2023]
