"""PDF field mapping for IRS Schedule E (Supplemental Income and Loss).

v1 scope: single rental property (slot A on Page 1). Property slots B
and C exist on the form but are not populated by v1 compute. Page 2
(partnerships, S corps, estates, royalties via K-1) is out of scope.

Field names enumerated from ``pdfs/federal/2025/f1040se.pdf``. Each
expense Line5–Line22 exposes three per-property cells (A, B, C); we map
only the first (property A). Line 19 ("Other (list)") additionally
exposes a description field we skip in v1.
"""


class PdfSchE:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
                # Header
                "taxpayer_name": "topmostSubform[0].Page1[0].f1_1[0]",
                "taxpayer_ssn": "topmostSubform[0].Page1[0].f1_2[0]",

                # Line 1a — property A address
                "sch_e_property_a_address":
                    "topmostSubform[0].Page1[0].Table_Line1a[0].RowA[0].f1_3[0]",

                # Line 1b — property A type code (1-8)
                "sch_e_property_a_type_code":
                    "topmostSubform[0].Page1[0].Table_Line1b[0].RowA[0].f1_6[0]",

                # Line 2 — fair rental days / personal use days for A
                "sch_e_property_a_fair_rental_days":
                    "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_9[0]",
                "sch_e_property_a_personal_use_days":
                    "topmostSubform[0].Page1[0].Table_Line2[0].RowA[0].f1_10[0]",

                # Line 3 — rents received A
                "sch_e_property_a_rents":
                    "topmostSubform[0].Page1[0].Table_Income[0].Line3[0].f1_16[0]",

                # Lines 5–18: per-expense property-A amounts
                "sch_e_property_a_advertising":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line5[0].f1_22[0]",
                "sch_e_property_a_auto_and_travel":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line6[0].f1_25[0]",
                "sch_e_property_a_cleaning_and_maintenance":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line7[0].f1_28[0]",
                "sch_e_property_a_commissions":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line8[0].f1_31[0]",
                "sch_e_property_a_insurance":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line9[0].f1_34[0]",
                "sch_e_property_a_legal_and_professional_fees":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line10[0].f1_37[0]",
                "sch_e_property_a_management_fees":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line11[0].f1_40[0]",
                "sch_e_property_a_mortgage_interest":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line12[0].f1_43[0]",
                "sch_e_property_a_other_interest":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line13[0].f1_46[0]",
                "sch_e_property_a_repairs":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line14[0].f1_49[0]",
                "sch_e_property_a_supplies":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line15[0].f1_52[0]",
                "sch_e_property_a_taxes":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line16[0].f1_55[0]",
                "sch_e_property_a_utilities":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line17[0].f1_58[0]",
                "sch_e_property_a_depreciation":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line18[0].f1_61[0]",

                # Line 19 — "other" A amount (skipping the description cell f1_64)
                "sch_e_property_a_other_expenses":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line19[0].f1_65[0]",

                # Line 20 — total expenses A
                "sch_e_property_a_total_expenses":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line20[0].f1_68[0]",

                # Line 21 — income or (loss) A
                "sch_e_property_a_income_loss":
                    "topmostSubform[0].Page1[0].Table_Expenses[0].Line21[0].f1_71[0]",

                # Line 26 — total rental real estate / royalty income (page 1 summary)
                "sch_e_line_26_total":
                    "topmostSubform[0].Page1[0].f1_84[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule E PDF mapping for year {year}")
        return cls._MAPPINGS[year]
