"""PDF field mapping for IRS Schedule E (Supplemental Income and Loss).

v1 scope: single rental property (slot A on Page 1). Property slots B
and C exist on the form but are not populated by v1 compute.

Part II (partnerships, S-corps via K-1) shares the Page 2 table frame.
The page-2 header fields (taxpayer_name_page2 / taxpayer_ssn_page2)
are mapping-layer concerns — the orchestrator derives them from the compute
outputs (taxpayer_name / taxpayer_ssn) when merging Part I + Part II values.
That way compute never leaks PDF-template structure.

Field names enumerated from ``pdfs/federal/2025/f1040se.pdf``.

Page 2 field discovery notes (2025 form):
  - Table_Line28a-f:  per-row name (f2_3/6/9/12), EIN (f2_4/7/10/13), and a
    third text field (f2_5/8/11/14) that appears to be col (f) passive income
    in the a-f sub-table.  The entity-type checkboxes sit alongside: P=c2_2,
    S=c2_3 for row A (and so on for B/C/D).
  - Table_Line28g-k:  five numeric columns per row at x≈65,187,288,389,490.
    Column order: (e) passive loss allowed, (f) passive income,
    (g) nonpassive loss, (h) §179 (skipped in v1), (i) nonpassive income.
  - Line 29a/b totals at y≈480/468 (f2_35–f2_44, five cols each).
  - Lines 30/31/32 single-column totals (f2_45/f2_46/f2_47).
  - Line 37 estate/trust total (f2_68) — always 0: estate_trust K-1s are rejected at load.
  - Line 41 total pass-through (f2_76).
"""

_P2 = "topmostSubform[0].Page2[0]"
_T28AF = f"{_P2}.Table_Line28a-f[0]"
_T28GK = f"{_P2}.Table_Line28g-k[0]"

_ROWS = ("A", "B", "C", "D")


def _row_mapping(row_letter: str) -> dict[str, str]:
    """Return the 8 PDF field entries for one Part II Line 28 row (A–D).

    Field-number strides within the form:
      AF sub-table (name, EIN, checkboxes) — +3 per row:
        name f2_(3,6,9,12), EIN f2_(4,7,10,13),
        partnership checkbox c2_(2,5,8,11), S-corp checkbox c2_(3,6,9,12)
      GK sub-table (income/loss columns) — +5 per row:
        passive_loss f2_(15,20,25,30), passive_income f2_(16,21,26,31),
        nonpassive_loss f2_(17,22,27,32),
        nonpassive_income f2_(19,24,29,34)  ← skips §179 at offset +2
    To add Row E: append "E" to _ROWS; strides extend automatically.
    """
    i = _ROWS.index(row_letter)
    row = row_letter.lower()
    af = f"{_T28AF}.Row{row_letter}[0]"
    gk = f"{_T28GK}.Row{row_letter}[0]"
    return {
        f"sch_e_part_ii_row_{row}_name":                     f"{af}.f2_{3 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_ein":                      f"{af}.f2_{4 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_entity_type_partnership":  f"{af}.c2_{2 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_entity_type_s_corp":       f"{af}.c2_{3 + 3 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_loss":             f"{gk}.f2_{15 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_passive_income":           f"{gk}.f2_{16 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_loss":          f"{gk}.f2_{17 + 5 * i}[0]",
        f"sch_e_part_ii_row_{row}_nonpassive_income":        f"{gk}.f2_{19 + 5 * i}[0]",
    }


class PdfSchE:
    _MAPPINGS: dict[int, dict] = {
        2025: {
            "scalars": {
                # ── Page 1 header ─────────────────────────────────────────────
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

                # ── Page 2 header ──────────────────────────────────────────────
                # These are derived by the orchestrator from taxpayer_name /
                # taxpayer_ssn — the compute does not produce _page2 variants.
                "taxpayer_name_page2": f"{_P2}.f2_1[0]",
                "taxpayer_ssn_page2":  f"{_P2}.f2_2[0]",

                # ── Part II — Line 28, Rows A–D (generated via _row_mapping) ──────
                **{
                    k: v
                    for letter in _ROWS
                    for k, v in _row_mapping(letter).items()
                },

                # ── Part II — Line 29 column totals ────────────────────────────
                # Line 29a row (y≈480): passive-loss(e), passive-income(f),
                #   nonpassive-loss(g), [§179(h) skip], nonpassive-income(i)
                "sch_e_line_29a_total_passive_loss":
                    f"{_P2}.f2_35[0]",
                "sch_e_line_29a_total_passive_income":
                    f"{_P2}.f2_36[0]",
                "sch_e_line_29a_total_nonpassive_loss":
                    f"{_P2}.f2_37[0]",
                "sch_e_line_29a_total_nonpassive_income":
                    f"{_P2}.f2_39[0]",
                # Line 29b row (y≈468): mirrors same columns
                "sch_e_line_29b_total_passive_loss":
                    f"{_P2}.f2_40[0]",
                "sch_e_line_29b_total_passive_income":
                    f"{_P2}.f2_41[0]",
                "sch_e_line_29b_total_nonpassive_loss":
                    f"{_P2}.f2_42[0]",
                "sch_e_line_29b_total_nonpassive_income":
                    f"{_P2}.f2_44[0]",

                # ── Part II — Lines 30 / 31 / 32 ───────────────────────────────
                # Line 30 total income, Line 31 total loss, Line 32 net
                "sch_e_line_30_total_income":    f"{_P2}.f2_45[0]",
                "sch_e_line_31_total_loss":      f"{_P2}.f2_46[0]",
                "sch_e_line_32_total_partnership_scorp": f"{_P2}.f2_47[0]",

                # ── Part III — Line 37 (estate/trust) — always 0 in v1 ────
                "sch_e_line_37_total_estate_trust": f"{_P2}.f2_68[0]",

                # ── Line 41 — total pass-through income / (loss) ───────────────
                "sch_e_line_41_total_pte": f"{_P2}.f2_76[0]",
            },
            "repeaters": {},
        },
    }

    @classmethod
    def get_mapping(cls, year: int) -> dict:
        if year not in cls._MAPPINGS:
            raise ValueError(f"No Schedule E PDF mapping for year {year}")
        return cls._MAPPINGS[year]
