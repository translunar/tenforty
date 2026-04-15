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

_PAGE1 = "topmostSubform[0].Page1[0]"
_PAGE2 = "topmostSubform[0].Page2[0]"


class PdfSch1:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
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
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule 1 PDF mapping for year {year}")
        return cls._MAPPINGS[year]
